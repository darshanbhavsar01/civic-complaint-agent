# Nagrik (નાગરિક) — civic complaint agent for AMC, Ahmedabad

Photo in → the agent sees the issue, finds the ward and department, checks for duplicates,
files a complaint with a tracking ID, drafts an X/Instagram post, and answers "what's the status?".

Built to `SPEC.md` and `design.md`. Mock AMC system — nothing reaches a real portal, and
social posts are drafts only.

---

## Run it locally

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Linux/macOS: .venv/bin/python
cp .env.example .env            # then fill in the keys below
.venv/Scripts/python -m uvicorn main:app --reload --port 8080
```

- Citizen app: http://localhost:8080/
- Officer console: http://localhost:8080/officer.html
- ADK agent API: `POST /run_sse`, OpenAPI at `/docs`

### Keys you need

| Env var | Where from | Needed for |
|---|---|---|
| `GOOGLE_API_KEY` | [AI Studio](https://aistudio.google.com/apikey) | the agent and `analyze_civic_image` |
| `GOOGLE_API_KEY_BACKUP` | a second AI Studio key | automatic failover when the primary is out of quota |
| `MAPS_SERVER_KEY` | Maps Platform, restricted to **Geocoding API**, quota ~300/day | `geocode_area`, `reverse_geocode` |
| `MAPS_EMBED_KEY` | Maps Platform, restricted to **Maps Embed API** + HTTP referrer | the map on the slip |

Everything except the model calls works without keys: ward resolution, duplicates,
filing, status, escalation and the social drafts all run off `data/amc.json`.
Without `MAPS_SERVER_KEY` the agent resolves the ward from coordinates alone and
files with `"<ward>, Ahmedabad"` as the address — it does **not** stop to ask you
to retype a location it already worked out. Without `MAPS_EMBED_KEY` the slip
shows coordinates instead of a map.

### Model and key failover

Free-tier quota is the likeliest thing to break a live demo, so nothing is pinned
to one model or one key. Both the agent ([`failover_llm.py`](civic_agent/failover_llm.py))
and the vision tool ([`llm.py`](civic_agent/llm.py)) walk an ordered chain of
every model × every key, and take the first that answers:

```
GEMINI_MODEL_FALLBACKS=gemini-3-flash-preview,gemini-2.5-flash,gemini-3.1-flash-lite,
                       gemini-flash-lite-latest,gemini-3.6-flash,gemini-3.5-flash-lite,
                       gemini-flash-latest
```

That is 7 models × 2 keys = 14 rungs. A rung that reports 429/503/timeout is
parked for 60 seconds so later calls skip it instead of re-walking dead options,
and the pair that last worked is tried first. A failure that is *our* fault —
a malformed request, a bad image — is raised immediately rather than masked
behind a fallback. Set `GEMINI_MODEL` to force a different first choice.

The chain order was measured against real image + `response_schema` calls, not
guessed. Models deliberately excluded, with the reason, are listed at the top of
[`civic_agent/llm.py`](civic_agent/llm.py) — including **Gemma 4, which returns
500 INTERNAL for every request on an AI Studio key** (text-only and schema-free
included), so it cannot serve as a fallback despite being listed by the API.

### Offline / flaky-Wi-Fi mode

Set `DEMO_CACHE=1` and `analyze_civic_image` returns canned results for any photo whose
filename contains `pothole`, `garbage`, `streetlight` or `selfie` — so the full demo runs
with no network at all. It also kicks in automatically as a fallback if a live Gemini call
fails for one of those filenames.

`/api/upload` keeps a sanitised copy of your original filename in the stored id
(`pothole.jpg` → `813f568b-pothole.jpg`), which is what makes this match through the
real upload path. Name your demo photos accordingly.

---

## Demo photos

Phone photos pushed through WhatsApp or a browser usually have the EXIF stripped — that is
the fallback path we demo deliberately. For the main photo, stamp GPS in:

```bash
python demo/add_gps.py --list                  # ward IDs and centroids
python demo/add_gps.py pothole.jpg W12         # writes pothole.gps.jpg
python demo/add_gps.py garbage.jpg 23.0063 72.6013
```

Name the files `pothole.jpg`, `garbage.jpg`, `selfie.jpg` so `DEMO_CACHE=1` can match them.

For the duplicate demo, the seed already contains an open garbage complaint at Kankaria
(`AMC-2026-000098`, also **already overdue** so escalation has something to act on) and a
pothole at Stadium Circle (`AMC-2026-000123`). Any new report of the same issue type within
150 m of those becomes a supporter instead of a new ticket.

---

## Shape of the thing

```
main.py                 FastAPI: ADK app + /api/upload + /api/officer/* + static (mounted last)
civic_agent/
  agent.py              root_agent = LlmAgent(..., tools=[11 function tools])
  prompts.py            AGENT_INSTRUCTION — the filing flow, language rules, hard rules
  tools/vision.py       analyze_civic_image (Gemini, Pydantic response_schema)
  tools/location.py     get_photo_location, geocode_area, reverse_geocode, resolve_ward
  tools/tickets.py      get_department, check_duplicates, create_complaint,
                        get_complaint_status, escalate_complaint
  tools/social.py       draft_social_post (template-based, drafts only)
store.py                JsonStore / FirestoreStore behind one interface, STORE env var
geo.py                  haversine, ward name matching, nearest centroid, IST helpers, priority
data/amc.json           seed: 9 wards, 5 departments with SLAs, zone officers, 2 complaints
static/                 index.html (citizen) + officer.html, css/tokens.css, js/app.js
demo/add_gps.py         stamp GPS EXIF onto a demo photo
```

Every tool returns `{"status": "success" | "error", ...}` and never raises to the model.

### Data flow

```
photo → /api/upload → {image_id, exif_gps}
      → agent message "[image_id=…] [browser_location=…] file this"
      → analyze_civic_image → get_photo_location → reverse_geocode → resolve_ward
      → get_department → check_duplicates → create_complaint → draft_social_post
      → /run_sse events → frontend route stops + trace panel + the slip
```

The frontend maps each `functionCall` / `functionResponse` event to a route stop
(`STOPS` in `static/js/app.js`) and keeps the raw JSON in the trace panel — that
panel is the evidence that the agent reasons, uses tools and takes action.

---

## Live deployment

**https://nagrik-229692962627.asia-south1.run.app** — citizen app
**https://nagrik-229692962627.asia-south1.run.app/officer.html** — officer console

| | |
|---|---|
| Project | `main-aura-398409` |
| Region | `asia-south1` (Mumbai — ~30ms from Ahmedabad instead of ~250ms) |
| Service | `nagrik`, revision `nagrik-00003-mx6` |
| Store | Firestore native, default database, `asia-south1` |
| Scaling | min 0 / max 2, 512Mi, 1 cpu, concurrency 20 |
| Budget alert | ₹50, scoped to this project, alerts at 50 / 90 / 100% |

Cloud Run also serves the legacy-style URL `https://nagrik-k2ueldoewq-el.a.run.app`;
both work.

Useful commands:

```bash
# redeploy after a code change
gcloud run deploy nagrik --source . --project main-aura-398409 --region asia-south1

# logs
gcloud run services logs tail nagrik --project main-aura-398409 --region asia-south1

# flip on the canned-vision safety net if quota dies during judging
gcloud run services update nagrik --project main-aura-398409 --region asia-south1 \
  --update-env-vars DEMO_CACHE=1

# add the Maps keys once you have them
gcloud run services update nagrik --project main-aura-398409 --region asia-south1 \
  --update-env-vars MAPS_SERVER_KEY=...,MAPS_EMBED_KEY=...
```

Two deployment details worth knowing:

- **`/healthz` does not work on Cloud Run.** Google's front end reserves that exact
  path and answers it with its own 404 before the request reaches the container.
  The liveness endpoints are `/api/health` (ours, also reports which store is active)
  and `/health` (ADK's).
- **`.gcloudignore` is load-bearing.** This project is not a git repo, so without it
  `gcloud run deploy --source` would upload `.venv/` and bake `.env` — your API keys —
  into the container image. It keeps the build context at ~200 KB and secret-free;
  keys are passed as env vars instead.

## Deploying from scratch

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com firestore.googleapis.com geocoding-backend.googleapis.com

# The Firestore location is PERMANENT. asia-south1 keeps latency low for an
# Ahmedabad demo; us-central1 is the more conservatively documented free-tier region.
gcloud firestore databases create --location=asia-south1

# The model chain contains commas, which clash with --set-env-vars' delimiter,
# so pass env vars as a YAML file. Keep that file OUT of the project directory
# so it can never land in a build context.
cat > /tmp/cloudrun.env.yaml <<'YAML'
GOOGLE_GENAI_USE_VERTEXAI: "FALSE"
GOOGLE_API_KEY: "your_key"
GOOGLE_API_KEY_BACKUP: "your_backup_key"
GEMINI_MODEL: "gemini-3-flash-preview"
GEMINI_MODEL_FALLBACKS: "gemini-3-flash-preview,gemini-2.5-flash,gemini-3.1-flash-lite,gemini-flash-lite-latest,gemini-3.6-flash,gemini-3.5-flash-lite,gemini-flash-latest"
STORE: "firestore"
DEMO_CACHE: "0"
YAML

gcloud run deploy nagrik --source . --region asia-south1 --allow-unauthenticated \
  --min-instances 0 --max-instances 2 --memory 512Mi --cpu 1 --concurrency 20 \
  --env-vars-file /tmp/cloudrun.env.yaml

# then point social-draft image links at the URL it printed
gcloud run services update nagrik --region asia-south1 \
  --update-env-vars PUBLIC_BASE_URL=https://nagrik-xxxxx.run.app

# the budget guardrail from SPEC.md section 8
gcloud billing budgets create --billing-account=YOUR_ACCOUNT \
  --display-name="Nagrik hackathon Rs50" --budget-amount=50INR \
  --filter-projects="projects/YOUR_PROJECT" \
  --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0
```

After deploying, add the Cloud Run URL as an HTTP-referrer restriction on `MAPS_EMBED_KEY`,
and set `PUBLIC_BASE_URL` so social drafts carry absolute image links.

Uploads live on the container's local disk, so they vanish when the instance scales to zero.
Fine for a demo; the complaint records themselves are in Firestore.

### ₹50 budget notes

Gemini runs on an AI Studio key, so AI costs nothing on GCP. Geocoding results are cached in
the store, and the server key should be capped at ~300 requests/day. Maps Embed is free.
Cloud Run with `min-instances 0` and Firestore's default database both stay in free tier for
a demo. Afterwards, delete the service and the images in the `cloud-run-source-deploy`
Artifact Registry repo.

---

## What is verified, and what isn't

Checked end to end on this machine:

- **A live agent run over `/run_sse`** with real Gemini calls: photo → 8 tool calls in the
  prescribed order → `AMC-2026-000125` filed → social draft. Plus a status follow-up, the
  same question asked in Gujarati (answered in Gujarati), and a selfie politely refused
  with nothing filed and no tracking ID invented.
- **The failover chain under real quota exhaustion**, observed rather than simulated: when
  the keys hit their limit mid-session the log shows the chain walking
  `gemini-3-flash-preview/backup → .../primary → gemini-2.5-flash/primary → ...`.
- All 11 tools, including the five demo paths: GPS photo → filed; no-GPS photo → typed area;
  near-duplicate → supporter merge with a priority bump; overdue → escalation draft;
  selfie → rejected before anything is filed.
- GPS EXIF write/read round-trip, including southern/western hemisphere signs.
- Every HTTP route: upload (plus 415 on a non-image), image serving, complaint list and
  detail, officer status change (plus 400 on an unknown status), config, health, static.
- The frontend SSE reducer, replayed against event JSON serialized by the installed ADK's
  own `Event` model and fed in 37-byte slices to prove split frames parse. 36 assertions
  across four scenarios cover route stops, the trace panel, the filed slip, the duplicate
  slip, the rejection path and tool errors.

**Not verified here:**

- **Classification of a real photograph.** The live vision calls were made against
  synthetic test images, and Gemini correctly identified them as illustrations rather
  than real scenes (`is_civic_issue: false`, "a digital illustration of a pothole") —
  which is the guardrail working, but means real-photo accuracy is still untested.
  Run an actual pothole photo through the UI before the demo.
- **The live Geocoding calls.** No Maps key was available, so `geocode_area` and
  `reverse_geocode` were only exercised through their error branches. Those branches
  are now the reason the no-Maps path files successfully, so they are well covered —
  but the success path is not.
- **Cloud Run and Firestore.** Local `STORE=json` only.

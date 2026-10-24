# SPEC.md — "Nagrik" Civic Complaint Agent (AMC, Ahmedabad)

> Solo, in-person hackathon. 5-hour build. Demo > slides. Google tech only.
> Keep everything simple, working, demoable.

## 1. What we are building

A photo goes in → the agent **sees** the issue → **finds** the ward + department → **checks for duplicates** →
**files** a complaint with a tracking ID → **drafts** an X/Instagram post → answers **"what's the status?"**.

Pitch line: *"From photo to filed complaint in 20 seconds — and the agent keeps chasing it for you."*

### Winning differentiators (beyond the brief)
1. **Live agent trace panel** — UI shows every tool call (name, args, result) as it happens. Judges score "reasons, uses tools, takes action" — make it visible.
2. **Duplicate detection** — same issue within ~150 m already open → the agent attaches the user as a "+1 supporter" instead of filing a new ticket (raises priority). Real municipal pain point.
3. **Severity + SLA** — the model rates severity 1–5 (hazard to vehicles/pedestrians, size); department SLA gives an expected resolution date.
4. **Location fallback chain** — EXIF GPS → browser geolocation → typed area name → ask the user. Never dead-ends.
5. **Gujarati / Hindi / English** — replies in the user's language.
6. **Two-sided demo** — mock **AMC Officer Console** page where the officer moves a ticket Assigned → In Progress → Resolved; citizen asks "status?" and sees the change live. Overdue tickets get an auto-drafted escalation.
7. **Guardrail** — non-civic photos (selfie, food) are politely rejected, not filed.

## 2. Hard constraints
- **Google only**: Gemini (via AI Studio key), ADK, Maps Platform (Geocoding + Maps Embed), Cloud Run, Firestore, Cloud Build. No other AI/hosting.
- **Mock AMC system**: local JSON seed (+ Firestore for persistence). Never call a real portal. Social posts are **drafts only** (copy button + X web-intent link) — never auto-post. Say so in the demo.
- **GCP budget: ₹50 total.** See §8. Every design choice favours free tiers.

## 3. Stack
| Layer | Choice | Why |
|---|---|---|
| Agent | **Google ADK (Python)**, single `LlmAgent` root with function tools | Reliable, visible function calling; multi-agent is overkill for 5h |
| Model | `GEMINI_MODEL` env, with a fallback chain (see §3a) | Fast + multimodal + cheap |
| Model auth | **AI Studio API key** (`GOOGLE_GENAI_USE_VERTEXAI=FALSE`) | Free tier → ₹0 GCP spend on AI |
| Vision | `google-genai` client inside the `analyze_civic_image` tool, **structured output** (Pydantic `response_schema`) | Deterministic JSON, shows as a tool step |
| Geo | Maps **Geocoding API** (forward + reverse), server-side key, results cached | Brief requires it |
| Map in UI | **Maps Embed API** iframe (free, unlimited) with a browser key restricted by HTTP referrer | No cost |
| Backend | FastAPI app from ADK `get_fast_api_app(...)` + custom routes | One container |
| Data | `data/amc.json` seed → `store.py` repo layer. Backend `STORE=firestore` (Cloud Run) or `STORE=json` (local/offline) | Firestore free tier; JSON fallback |
| Frontend | Static `index.html` + vanilla JS, mobile-first | Zero build step |
| Hosting | **Cloud Run**, one service, `min-instances=0`, `max-instances=2` | Free tier |

### 3a. Model and key failover
Free-tier quota is the likeliest thing to break a live demo, so neither the agent nor the
vision tool is pinned to a single model or key. Both walk an ordered chain of every model ×
every configured key and take the first that answers; a rung that reports 429/503/timeout is
parked briefly so later calls skip it. Chain order was chosen by measuring real
image + `response_schema` calls, not by guessing — see the notes at the top of
`civic_agent/llm.py`, which also records the models that proved unusable and why.

## 4. Repo layout
```
civic-complaint-agent/
├── SPEC.md                  # this file
├── design.md                # UI/UX spec
├── main.py                  # FastAPI: ADK app + /api/upload + /api/officer/* + static
├── civic_agent/
│   ├── __init__.py
│   ├── agent.py             # root_agent = LlmAgent(..., tools=[...])
│   ├── prompts.py           # AGENT_INSTRUCTION
│   ├── llm.py               # model/key chain used by the tools
│   ├── failover_llm.py      # the same chain, as a BaseLlm for the agent
│   └── tools/
│       ├── vision.py        # analyze_civic_image
│       ├── location.py      # get_photo_location, geocode_area, reverse_geocode, resolve_ward
│       ├── tickets.py       # get_department, check_duplicates, create_complaint, get_complaint_status, escalate_complaint
│       └── social.py        # draft_social_post
├── store.py                 # JsonStore / FirestoreStore, same interface
├── geo.py                   # haversine, nearest ward centroid, IST helpers
├── data/amc.json            # seed: wards, departments, SLAs, handles, sample complaints
├── uploads/                 # local image store (gitignored)
├── static/
│   ├── index.html           # citizen chat + upload + trace panel + map
│   └── officer.html         # mock AMC officer console
├── demo/add_gps.py          # stamp GPS EXIF onto a demo photo
├── requirements.txt
├── Dockerfile
└── .env.example
```

## 5. Agent tools

All tools return `dict` with `"status": "success" | "error"` plus data. Never raise to the model.
Docstrings matter — ADK uses them as the tool descriptions the model reads.

| # | Tool | Purpose / logic |
|---|---|---|
| 1 | `analyze_civic_image(image_id)` | Load `uploads/{image_id}`, call the model with a schema → `{is_civic_issue, issue_type: pothole\|garbage\|streetlight\|waterlogging\|other, confidence, severity 1-5, description, visible_landmarks, hazard_notes}`. If `is_civic_issue=false` → decline politely. |
| 2 | `get_photo_location(image_id)` | Read EXIF GPS with Pillow. Return `{lat, lng}` or `{found: false}`. (Browsers/WhatsApp often strip EXIF — fallback is expected.) |
| 3 | `geocode_area(area_text)` | Geocoding API, append ", Ahmedabad, Gujarat, India", bias to Ahmedabad bounds. Returns lat/lng + formatted address + sublocality. Cached. |
| 4 | `reverse_geocode(lat, lng)` | Geocoding API reverse → formatted address, sublocality/neighborhood names. Cached. |
| 5 | `resolve_ward(lat, lng, locality_hint="")` | 1) match locality names against `wards[].areas` (fuzzy) 2) else nearest ward centroid by haversine (< 4 km) 3) else `{status:"error", need:"area_name"}`. |
| 6 | `get_department(issue_type)` | From `departments` → name, SLA hours, X handle. |
| 7 | `check_duplicates(ward_id, issue_type, lat, lng)` | Open complaints same ward + issue within 150 m → return the match. |
| 8 | `create_complaint(...)` | If `duplicate_of` → add supporter, bump priority, return existing ID. Else new ID `AMC-2026-NNNNNN`, status `Filed`, `expectedBy = now + SLA`. Saves `last_tracking_id` in session state. |
| 9 | `get_complaint_status(tracking_id="")` | If empty, use `state["last_tracking_id"]`. Return status, history timeline, department, expectedBy, `is_overdue`. |
| 10 | `draft_social_post(tracking_id)` | Build X (≤280 chars) + Instagram caption: issue, area, tracking ID, AMC handle + department handle + ward hashtag. Returns text + `x_intent_url` + `image_url`. Template-based. |
| 11 | `escalate_complaint(tracking_id)` | Only if overdue: draft escalation to the Zone Deputy Commissioner (mock), add history event. |

### Agent flow (encoded in `prompts.py`)
```
Photo received (message contains image_id, maybe browser_lat/lng)
→ analyze_civic_image
   → not civic? explain kindly, stop.
→ get_photo_location → (none) use browser lat/lng → (none) ask user for area → geocode_area
→ reverse_geocode (for address + locality; on failure carry on, do not ask the user)
→ resolve_ward
→ get_department
→ check_duplicates → if match: tell user, add as supporter via create_complaint(duplicate_of=...)
→ create_complaint
→ draft_social_post
→ Reply: short summary: Issue, Severity, Ward, Department, Tracking ID, Expected by, + social drafts.
"What's the status?" → get_complaint_status → if overdue → offer escalate_complaint.
```
Prompt rules: reply in the user's language; never invent a tracking ID (only from `create_complaint`);
never claim it was posted to social media; be concise (judges read fast); say "mock AMC system" if asked;
never ask the user to retype a location already resolved.

## 6. HTTP API
- ADK built-in: `POST /apps/civic_agent/users/{uid}/sessions/{sid}` (create), `POST /run_sse` (streaming events incl. `functionCall` / `functionResponse` → feed the trace panel).
- `POST /api/upload` (multipart) → saves image, returns `{image_id, exif_gps|null, image_url}`. Frontend then sends to the agent: `"[image_id=abc.jpg] [browser_location=23.03,72.56] <user text>"`. Validates by **content**, not filename — a JPEG saved as `.jfif` must work.
- `GET /api/complaints?ward=` , `POST /api/officer/{tracking_id}/status` `{status, note}` → officer console.
- `GET /uploads/{id}` serve images. Static at `/` mounted **last** so it doesn't shadow API routes.
- Liveness: `/api/health`. Note `/healthz` is unusable — Cloud Run's front end reserves that exact path.

## 7. Data model (complaint)
```json
{ "trackingId": "AMC-2026-000124", "ward": "W12", "zone": "West", "issue": "pothole",
  "department": "Roads & Buildings", "severity": 4, "priority": "High",
  "description": "...", "address": "...", "lat": 23.03, "lng": 72.56, "imageId": "abc.jpg",
  "status": "Filed", "supporters": 1, "filedAt": "ISO+05:30", "expectedBy": "ISO+05:30",
  "history": [{"status": "Filed", "at": "...", "note": "Filed via Nagrik agent"}] }
```
Statuses: `Filed → Assigned → In Progress → Resolved` (+ `Escalated`). Timestamps in IST (`+05:30`).

## 8. ₹50 budget guardrails
1. **Budget alert at ₹50** on the billing account, scoped to this project (alerts at 50/90/100%). Alerts don't cap spend — the rest does.
2. Model calls go through an **AI Studio key** → no GCP billing for AI.
3. Cloud Run: `--min-instances 0 --max-instances 2 --memory 512Mi --cpu 1 --concurrency 20`. Within free tier for a demo.
4. Maps: restrict the server key to **Geocoding API only**; cap at ~300 requests/day. Browser key restricted to **Maps Embed API** + referrer = Cloud Run URL. Cache all geocodes.
5. Firestore: default database (free tier only applies to it), native mode, same region.
6. Deploy from source (`gcloud run deploy --source .`) — uses Cloud Build free minutes. After the event: delete images in the `cloud-run-source-deploy` Artifact Registry repo and the service.
7. No Cloud SQL, no GKE, no Vertex endpoints, no always-on anything.

## 9. Deploy
See README.md for the exact, current deploy commands and the live URL.

Key points: `.gcloudignore` is load-bearing (without it, `--source` uploads `.venv/` and bakes
`.env` into the image); the model chain contains commas so env vars go in via `--env-vars-file`,
not `--set-env-vars`; the Firestore location is permanent once created.

Uploads live on the container's local disk and vanish when the instance scales to zero — fine
for a demo, since complaint records themselves are in Firestore.

## 10. Build plan (5 hours)
**H0 · 0:00–0:30 — Setup**
- [x] GCP project, budget alert, enable APIs, Maps keys + quotas, AI Studio key
- [x] Repo skeleton, `.env`
- [x] Demo photos with GPS EXIF (`demo/add_gps.py`)

**H1 · 0:30–1:30 — Core tools (the scored part)**
- [x] `store.py` (JSON first), `data/amc.json`
- [x] `analyze_civic_image` with schema
- [x] `get_photo_location`, `geocode_area`, `reverse_geocode`, `resolve_ward`
- [x] `get_department`, `create_complaint`, `get_complaint_status`
- [x] Agent end-to-end: photo → tracking ID → "status?"

**H2 · 1:30–2:30 — Deploy early + UI**
- [x] `main.py` with upload route; Dockerfile; deploy to Cloud Run (de-risk)
- [x] `index.html`: camera upload, chat, result card, trace panel (from SSE events), map embed

**H3 · 2:30–3:30 — Differentiators**
- [x] `check_duplicates` + supporter merge
- [x] `draft_social_post` (X + Instagram, copy button, X intent link)
- [x] Severity/SLA/expectedBy in result card; Gujarati reply
- [x] Switch to Firestore store, redeploy

**H4 · 3:30–4:15 — Officer console + escalation**
- [x] `officer.html`: table of complaints, status dropdown
- [x] `escalate_complaint` + overdue flag (one overdue complaint seeded)

**H5 · 4:15–5:00 — Demo hardening**
- [x] `DEMO_CACHE=1` fallback: canned tool results for the demo photos if the model or Wi-Fi fails
- [ ] Screen-record the full live run (offline backup = full credit)
- [ ] Rehearse the 3-minute script twice; freeze code at 4:50

## 11. Demo script (3 min)
1. (20s) Problem: "Most people give up before filing." Show the mobile UI.
2. (60s) Upload pothole photo (GPS EXIF) → trace panel lights up tool by tool → card: Pothole, severity 4, W12 Navrangpura, Roads & Buildings, AMC-2026-000125, expected in 72h → X/Instagram drafts.
3. (30s) Upload a garbage photo with no GPS, type "Kankaria" → geocode → W27 Maninagar. Then upload near-duplicate → "already reported, you're supporter #2, priority raised".
4. (30s) Officer console: set to In Progress. Citizen: "status?" (in Gujarati) → answers in Gujarati with timeline. Show overdue ticket → escalation draft.
5. (20s) Selfie → politely rejected. Close: "Mock AMC JSON + Firestore, posts are drafts; live on Cloud Run, total GCP spend under ₹50."

## 12. Coding conventions
- Python 3.12+, type hints, every tool has a clear docstring with Args/Returns.
- Tools are pure-ish and fast; no tool calls another model except `analyze_civic_image`.
- Keep secrets in env only; never commit `.env`.
- When in doubt: make the demo path work end-to-end first, polish second.

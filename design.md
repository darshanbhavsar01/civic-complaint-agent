# design.md — Nagrik (નાગરિક) · Civic Complaint Agent

> Design spec for the build. Read with SPEC.md. Frontend = `static/index.html` (citizen) + `static/officer.html` (mock AMC officer).
> No build step: vanilla HTML/CSS/JS, Google Fonts, Material Symbols, Maps Embed.

---

## 1. Design intent

**Who:** an Ahmedabad resident standing next to a pothole, phone in one hand, sun on the screen, 30 seconds of patience.
**Job:** photograph the problem → get proof it was filed → know what's happening without chasing anyone.
**Feeling:** "Someone official took this seriously." Not a startup toy, not a government portal. A trustworthy civic instrument.

### Visual concept: *the acknowledgment slip*
Every Indian who has dealt with a municipal office knows the **pavti** — the acknowledgment slip with a printed number and a rubber stamp. That slip is proof. Our product's single memorable element is a digital pavti: a complaint slip with the tracking ID, and a **rubber-stamp status** that is re-inked as the complaint moves (FILED → ASSIGNED → IN PROGRESS → RESOLVED).

Everything else stays quiet and disciplined so the slip is what judges remember.

Supporting vernacular, used sparingly:
- **Road-marking yellow** for the one primary action (the camera button), borrowed from the city's road paint and kerb markings.
- **Sabarmati indigo** as the ink of the institution: headers, IDs, links. Also a nod to Ahmedabad's textile and block-print heritage.
- **The route line**: the agent's progress is drawn as a dashed road centre-line with stops, because the agent is literally routing the complaint.

### What we rejected (and why)
- *Generic SaaS dashboard with rounded cards and gradients.* Reads like every other hackathon entry; says nothing about civic proof.
- *Government-portal look (dense tables, tiny type, Ashoka-blue banner).* Signals exactly the friction the product removes.
- *Dark UI with neon accent.* Unreadable in Ahmedabad daylight; this is used outdoors.

---

## 2. Tokens

### Colour
| Token | Hex | Use |
|---|---|---|
| `--paper` | `#EEF1F4` | App background. Cool, slightly blue survey-paper grey, high outdoor contrast |
| `--sheet` | `#FFFFFF` | Slip, chat bubbles, sheets |
| `--ink` | `#1C2541` | Primary text, IDs (Sabarmati indigo-black) |
| `--indigo` | `#2B3A8C` | Links, agent messages accent, focus ring, route line |
| `--marking` | `#F2B705` | **Primary action only** (camera button), active route stop |
| `--stamp-red` | `#C2362B` | Stamp ink for FILED / ESCALATED, errors |
| `--stamp-blue` | `#2B3A8C` | Stamp ink for ASSIGNED / IN PROGRESS |
| `--stamp-green` | `#2E7D4F` | Stamp ink for RESOLVED, success |
| `--muted` | `#5B6475` | Secondary text (≥ 4.5:1 on paper) |
| `--rule` | `#D3D9E1` | Hairlines, slip perforation |

Severity scale (chips, map pin): 1–2 `#5B6475`, 3 `#B7791F`, 4 `#C2362B`, 5 `#8E1B12` (always paired with the number and a word: "Severity 4 · High").

Contrast checks: `--ink` on `--marking` = text colour for the yellow button (passes AA). Never put white text on yellow.

Dark mode (optional, H5 only if time): `--paper #10162B`, `--sheet #1A2240`, `--ink #E8ECF4`, `--indigo #9AA8F0`; stamps keep hue, raise lightness ~15%.

### Type (Google Fonts, Gujarati + Latin in both)
| Role | Family | Settings |
|---|---|---|
| Display / IDs / stamp | **Anek Gujarati** (variable width) | Headings at `wdth 75` (condensed, signage-like), weight 700. Tracking ID at `wdth 100`, 700, `font-variant-numeric: tabular-nums` |
| Body / UI | **Mukta Vaani** | 400 / 600, line-height 1.5, max ~60ch |

```html
<link href="https://fonts.googleapis.com/css2?family=Anek+Gujarati:wdth,wght@75..125,400..800&family=Mukta+Vaani:wght@400;600&display=swap" rel="stylesheet">
```

Scale (mobile, ratio ~1.25): 13 · 15 (body) · 18 · 22 · 28 · 36 (tracking ID on slip). Sentence case everywhere; the only uppercase is the stamp text, because real stamps are uppercase.

### Space, shape, elevation
- 4px base grid: 4, 8, 12, 16, 24, 32, 48. Side gutter 16px.
- Radius by meaning, not one value everywhere: chat bubbles 16px, buttons 12px, slip 4px (it's paper), chips full-round.
- One elevation only: the slip (`0 1px 0 var(--rule), 0 8px 24px rgba(28,37,65,.12)`). Everything else is flat with hairlines.
- Tap targets ≥ 48px. Camera button 64px tall.

### Icons
**Material Symbols Rounded** (Google). Issue icons: `road` (pothole), `delete` (garbage), `emoji_objects` (streetlight), `flood` (waterlogging), `report` (other). Location: `my_location`, `pin_drop`. Social: plain text "Post on X" / "Copy for Instagram" (don't use third-party logos).

---

## 3. Layout

### Responsive frame (critical for the demo)
- **< 1024px (phone):** single column, app only. Agent trace collapses into a "How I filed this" drawer under the slip.
- **≥ 1024px (judges' laptop/projector):** two columns. Left: the phone-width app (max 440px). Right: the **agent trace** (route + tool-call log) live. Judges see the reasoning without anyone narrating.

```
≥1024px
┌──────────────────────────────────────────────────────────────────┐
│ Nagrik  નાગરિક                         Mock AMC system · Officer view │
├───────────────────────┬──────────────────────────────────────────┤
│  APP (440px)          │  AGENT ROUTE                              │
│  chat + slip          │  ● Seeing the photo        pothole, sev 4 │
│                       │  ┊                                        │
│                       │  ● Finding the place       EXIF GPS       │
│                       │  ┊                                        │
│                       │  ● Picking the ward        W12 Navrangpura│
│                       │  ┊  …                                     │
│  [ composer ]         │  ▸ raw tool calls (expandable JSON)       │
└───────────────────────┴──────────────────────────────────────────┘
```

### Screen A — Start (empty state = invitation)
```
┌─────────────────────────────┐
│ Nagrik            EN | ગુ | हि │
│                             │
│ See a pothole, garbage,     │
│ a dead streetlight or       │
│ waterlogging?               │
│ Photograph it. I'll file it │
│ with AMC and keep track.    │
│                             │
│ ┌─────────────────────────┐ │
│ │ 📷 Photograph the problem│ │  ← --marking, 64px, full width
│ └─────────────────────────┘ │
│   Choose from gallery       │  ← text button
│                             │
│ Already filed?              │
│ [ AMC-2026-______ ] Check   │
│                             │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
│ [ Type a message…      ][➤] │
└─────────────────────────────┘
```
Left-aligned text. No hero illustration; the camera button is the hero.

### Screen B — Working (agent route inline, phone)
User's photo appears as a sent bubble (thumbnail, 200px, rounded 16). Below it, a compact route that fills stop by stop:
```
  ┌──────────┐
  │  photo   │                      (user bubble, right)
  └──────────┘
  ● Seeing the photo ………… Pothole · severity 4
  ┊
  ● Finding the place ……… From photo GPS
  ┊
  ◐ Picking the ward                   ← active stop pulses yellow
  ┊
  ○ Checking for duplicates
  ○ Filing with AMC
  ○ Drafting your post
```
If location is missing, the route pauses at "Finding the place" and shows an inline sheet:
```
  I couldn't read a location from this photo.
  [ ⌖ Use my current location ]   [ Type the area ]
```

### Screen C — The slip (the memorable moment)
```
┌───────────────────────────────┐
│ Ahmedabad Municipal Corp.     │  13px muted  (mock)
│ Complaint acknowledgment      │
│                               │
│ AMC-2026-000124        ╭─────╮│  36px Anek, tabular
│                        │FILED││  ← stamp, rotated −8°, --stamp-red
│                        ╰─────╯│
│ ┌──────┐ Pothole · Severity 4 │
│ │photo │ Stadium Circle,      │
│ └──────┘ Navrangpura (W12)    │
│                               │
│ Department   Roads & Buildings│
│ Zone         West             │
│ Expected by  Mon 27 Oct, 5 pm │
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │  perforation (dashed rule)
│ [map embed, 140px]            │
│                               │
│ [ Copy ID ] [ Share slip ]    │
└───────────────────────────────┘
```
**Duplicate variant:** stamp reads `ALREADY REPORTED` in `--stamp-blue`; line under the ID: "You're supporter #2 — priority raised to High."

### Screen D — Social draft
Two tabs: **X** | **Instagram**. Editable textarea prefilled, live character counter for X (`212 / 280`), tags rendered as chips under it. Buttons: **Post on X** (opens the X compose intent in a new tab) and **Copy caption**. Footnote, muted: "Nagrik never posts for you. You choose."

### Screen E — Status
User asks "what's the status?" (any language) → agent replies one sentence + a mini slip with the current stamp and a vertical timeline:
```
AMC-2026-000124           [IN PROGRESS]
● Filed          Sat 24 Oct, 5:42 pm
● Assigned       Sat 24 Oct, 6:10 pm  Roads & Buildings, West
◐ In progress    Sun 25 Oct, 9:00 am  Crew dispatched
○ Resolved       expected by Mon 27 Oct
```
Overdue: timeline's last stop turns `--stamp-red`, line "2 days past the expected date", button **Draft escalation to Zone DC**.

### Screen F — Officer console (`officer.html`, desktop)
Purpose: drive the two-sided demo. Deliberately plainer than the citizen app (it's an internal tool).
```
Mock AMC officer console        Ward [All ▾]  Status [Open ▾]
┌──────────────┬─────────┬─────────────┬─────┬────────┬──────────────┐
│ Tracking ID  │ Ward    │ Issue       │ Sev │ +1s    │ Status       │
├──────────────┼─────────┼─────────────┼─────┼────────┼──────────────┤
│ AMC-…-000124 │ W12     │ Pothole     │ 4   │ 1      │ [Filed     ▾]│
│ AMC-…-000098 │ W27     │ Garbage     │ 4   │ 3      │ [In prog.  ▾]│ ← overdue row: red left border
└──────────────┴─────────┴─────────────┴─────┴────────┴──────────────┘
```
Status change → optional note → toast "Status updated to In progress". Auto-refresh every 5s.

---

## 4. Components

| Component | Spec |
|---|---|
| **Camera button** | `<label>` wrapping `<input type="file" accept="image/*" capture="environment">`. Yellow, ink text, `photo_camera` icon, 64px. Pressed: darken 8%. |
| **Chat bubble** | Agent: `--sheet`, left, 16px radius with 4px bottom-left corner; small indigo bar on the left edge. User: `--ink` bg, white text, right. Max 85% width. |
| **Route stop** | 12px dot + label + right-aligned result in muted. States: pending (hollow, `--rule`), active (yellow fill, pulse), done (indigo fill), error (red, with retry). Connector: 2px dashed indigo vertical line (road centre-line). |
| **Stamp** | Anek Gujarati 800, `wdth 110`, 14px uppercase, 2px double border in stamp colour, padding 4/10, `rotate(-8deg)`, `mix-blend-mode: multiply`, subtle SVG noise mask for ink texture. |
| **Slip** | `--sheet`, radius 4, the one elevation, 20px padding, dashed perforation rule above map. |
| **Chips** | Issue type with icon; severity with number + word; language switch. |
| **Map** | Maps Embed `place` mode iframe, 140px tall, radius 4, `loading="lazy"`, title attr for a11y. |
| **Toast** | Bottom, ink background, white text, 4s, `role="status"`. |
| **Quick replies** | After the slip: "What's the status?", "Post on X", "Report another". Pill buttons, outline indigo. |

---

## 5. Motion — one moment, everything else answers the user
- **The stamp lands** when the slip appears or status changes: from `scale(1.6) rotate(-14deg) opacity 0` → `scale(1) rotate(-8deg) opacity 1`, 220ms `cubic-bezier(.2,.9,.3,1.3)`, plus a 1-frame 2px slip shake. This is the signature.
- Route stops: active dot pulses (1.2s ease-in-out opacity). Done stops fill instantly.
- Nothing fades in on page load. No hover animations on cards.
- `@media (prefers-reduced-motion: reduce)`: stamp appears in place, no pulse.

---

## 6. Copy & voice
Plain, calm, specific, sentence case. Same verb through the flow.

| Moment | Copy |
|---|---|
| Primary action | Photograph the problem |
| Working | Seeing the photo · Finding the place · Picking the ward · Choosing the department · Checking for duplicates · Filing with AMC · Drafting your post |
| Filed | Filed with AMC. Keep this ID: **AMC-2026-000124**. |
| Duplicate | Someone reported this 2 days ago. I added you as a supporter, so it now has higher priority. |
| No location | I couldn't read a location from this photo. Share your location or type the area. |
| Not civic | This looks like a selfie, not a civic issue. Photograph the pothole, garbage, streetlight or waterlogging. |
| Unknown area | I couldn't match "Gota Bridge" to a ward I know. Try a nearby landmark or area name. |
| Network error | Couldn't reach the server. Your photo is saved here. Try again. |
| Footer | Demo on a mock AMC system. Nothing is sent to the real portal. |

Gujarati route labels (Gemini can translate the rest live): ફોટો જોઈ રહ્યા છીએ · સ્થળ શોધી રહ્યા છીએ · વોર્ડ પસંદ કરી રહ્યા છીએ · વિભાગ નક્કી કરી રહ્યા છીએ · ડુપ્લિકેટ તપાસ · AMCમાં ફરિયાદ નોંધાઈ રહી છે · પોસ્ટ તૈયાર થઈ રહી છે. *(Have a native speaker glance at these — you.)*

---

## 7. Accessibility floor
- Contrast AA everywhere; status never conveyed by colour alone (stamp text + timeline labels).
- `lang="gu"` / `lang="hi"` on translated message nodes so screen readers switch voice.
- Visible focus: 3px `--indigo` outline, 2px offset.
- Uploaded photo gets alt text from Gemini's `description`.
- Route list is an `<ol>` with `aria-live="polite"` announcing each completed stop.
- Works one-handed: primary actions in the bottom half of the screen.

---

## 8. Frontend architecture

### State machine (citizen app)
```
idle → uploading → agent_running ──┬─→ need_location → agent_running
                                   ├─→ rejected (not civic) → idle
                                   └─→ filed → (status_query | social | idle)
any → error (retryable)
```
Keep one `state` object + one `render()`; no framework.

### Tool → route stop mapping (from ADK `/run_sse` events)
```js
const STOPS = {
  analyze_civic_image:  { id:'see',    en:'Seeing the photo' },
  get_photo_location:   { id:'place',  en:'Finding the place' },
  geocode_area:         { id:'place',  en:'Finding the place' },
  reverse_geocode:      { id:'place',  en:'Finding the place' },
  resolve_ward:         { id:'ward',   en:'Picking the ward' },
  get_department:       { id:'dept',   en:'Choosing the department' },
  check_duplicates:     { id:'dupe',   en:'Checking for duplicates' },
  create_complaint:     { id:'file',   en:'Filing with AMC' },
  draft_social_post:    { id:'post',   en:'Drafting your post' },
  get_complaint_status: { id:'status', en:'Checking status' },
  escalate_complaint:   { id:'esc',    en:'Drafting escalation' },
};
// functionCall event  → stop = active, log args in trace panel
// functionResponse    → stop = done, show 1-line summary (e.g. "W12 Navrangpura · via EXIF GPS")
// create_complaint response → render slip + stamp
// draft_social_post response → render social tabs
// final text event    → agent bubble
```
The trace panel (desktop right column) shows the same stops plus collapsible raw JSON of each call. This is the evidence for "the AI reasons, uses tools and takes action."

### Files
```
static/
  index.html     # markup for screens A–E (sections toggled by state)
  officer.html
  css/tokens.css # §2 tokens as CSS custom properties
  css/app.css
  js/app.js      # state, render, upload, SSE client, STOPS map
  js/officer.js
```

---

## 9. Build order for UI (fits SPEC.md H2–H4)
1. tokens.css + Screen A + upload → photo bubble (20 min)
2. SSE client + route stops (desktop trace column comes free) (30 min)
3. Slip + stamp animation (20 min) ← make this perfect, it's the demo moment
4. Status timeline + quick replies (15 min)
5. Social tabs (15 min)
6. Officer console (25 min)
7. Polish pass: Gujarati toggle, reduced motion, phone check on a real device (15 min)

**Before demo — mirror check:** remove one decoration. If the slip and the route are clear on a projector from 5 metres, ship it.

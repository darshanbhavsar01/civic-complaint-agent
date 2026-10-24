/* Nagrik citizen app — one state object, one render(). design.md §8 */

const APP_NAME = "civic_agent";
const USER_ID = "citizen";

/* ----------------------------------------------------------- vocabulary */

const STOPS = {
  analyze_civic_image: { id: "see", en: "Seeing the photo", gu: "ફોટો જોઈ રહ્યા છીએ", hi: "फ़ोटो देख रहे हैं" },
  get_photo_location: { id: "place", en: "Finding the place", gu: "સ્થળ શોધી રહ્યા છીએ", hi: "जगह ढूँढ रहे हैं" },
  geocode_area: { id: "place", en: "Finding the place", gu: "સ્થળ શોધી રહ્યા છીએ", hi: "जगह ढूँढ रहे हैं" },
  reverse_geocode: { id: "place", en: "Finding the place", gu: "સ્થળ શોધી રહ્યા છીએ", hi: "जगह ढूँढ रहे हैं" },
  resolve_ward: { id: "ward", en: "Picking the ward", gu: "વોર્ડ પસંદ કરી રહ્યા છીએ", hi: "वार्ड चुन रहे हैं" },
  get_department: { id: "dept", en: "Choosing the department", gu: "વિભાગ નક્કી કરી રહ્યા છીએ", hi: "विभाग तय कर रहे हैं" },
  check_duplicates: { id: "dupe", en: "Checking for duplicates", gu: "ડુપ્લિકેટ તપાસ", hi: "डुप्लिकेट जाँच" },
  create_complaint: { id: "file", en: "Filing with AMC", gu: "AMCમાં ફરિયાદ નોંધાઈ રહી છે", hi: "AMC में शिकायत दर्ज हो रही है" },
  draft_social_post: { id: "post", en: "Drafting your post", gu: "પોસ્ટ તૈયાર થઈ રહી છે", hi: "पोस्ट तैयार हो रही है" },
  get_complaint_status: { id: "status", en: "Checking status", gu: "સ્થિતિ તપાસી રહ્યા છીએ", hi: "स्थिति देख रहे हैं" },
  escalate_complaint: { id: "esc", en: "Drafting escalation", gu: "એસ્કેલેશન તૈયાર", hi: "एस्केलेशन तैयार" },
};

const FILING_ROUTE = ["see", "place", "ward", "dept", "dupe", "file", "post"];

const ISSUE = {
  pothole: { icon: "road", en: "Pothole", gu: "ખાડો", hi: "गड्ढा" },
  garbage: { icon: "delete", en: "Uncollected garbage", gu: "કચરો", hi: "कचरा" },
  streetlight: { icon: "emoji_objects", en: "Broken streetlight", gu: "સ્ટ્રીટલાઇટ બંધ", hi: "स्ट्रीटलाइट ख़राब" },
  waterlogging: { icon: "flood", en: "Waterlogging", gu: "પાણી ભરાવો", hi: "जलभराव" },
  other: { icon: "report", en: "Civic issue", gu: "નાગરિક સમસ્યા", hi: "नागरिक समस्या" },
};

const SEVERITY_WORD = { 1: "Cosmetic", 2: "Minor", 3: "Noticeable", 4: "High", 5: "Severe" };

const T = {
  en: {
    quickStatus: "What's the status?",
    quickAnother: "Report another",
    quickPost: "Post on X",
    copyId: "Copy ID",
    shareSlip: "Share slip",
    copyCaption: "Copy caption",
    postOnX: "Post on X",
    acknowledgment: "Complaint acknowledgment",
    department: "Department",
    zone: "Zone",
    expectedBy: "Expected by",
    severity: "Severity",
    supporters: "Supporters",
    socialTitle: "Share it publicly",
    neverPosts: "Nagrik never posts for you. You choose.",
    copied: "Copied",
    useLocation: "Use my current location",
    typeArea: "Type the area",
    noLocation: "I couldn't read a location from this photo. Share your location or type the area.",
    netError: "Couldn't reach the server. Your photo is saved here. Try again.",
    uploadError: "That photo couldn't be uploaded. Try another one.",
    locationDenied: "Location permission was declined. Type the area name instead.",
    locationFailed: "Couldn't get your location. Type the area name instead.",
    areaPlaceholder: "e.g. Kankaria, near Stadium Circle",
    send: "Send",
    traceRaw: "Raw tool calls",
    overdueBy: (d) => `${d} days past the expected date`,
    draftEscalation: "Draft escalation to Zone DC",
    expectedLabel: "expected by",
    lookupBad: "That doesn't look like a tracking ID. They look like AMC-2026-000124.",
  },
  gu: {
    quickStatus: "સ્થિતિ શું છે?",
    quickAnother: "બીજી ફરિયાદ",
    quickPost: "X પર પોસ્ટ કરો",
    copyId: "ID કૉપિ કરો",
    shareSlip: "સ્લિપ શેર કરો",
    copyCaption: "કૅપ્શન કૉપિ કરો",
    postOnX: "X પર પોસ્ટ કરો",
    acknowledgment: "ફરિયાદ સ્વીકૃતિ",
    department: "વિભાગ",
    zone: "ઝોન",
    expectedBy: "અપેક્ષિત",
    severity: "ગંભીરતા",
    supporters: "સમર્થકો",
    socialTitle: "જાહેરમાં શેર કરો",
    neverPosts: "Nagrik તમારા વતી પોસ્ટ કરતું નથી. નિર્ણય તમારો.",
    copied: "કૉપિ થયું",
    useLocation: "મારું સ્થાન વાપરો",
    typeArea: "વિસ્તાર લખો",
    noLocation: "આ ફોટોમાંથી સ્થળ મળ્યું નથી. સ્થાન શેર કરો અથવા વિસ્તાર લખો.",
    netError: "સર્વર સાથે સંપર્ક થયો નથી. તમારો ફોટો સચવાયેલો છે. ફરી પ્રયાસ કરો.",
    uploadError: "આ ફોટો અપલોડ થયો નથી. બીજો પ્રયાસ કરો.",
    locationDenied: "સ્થાનની પરવાનગી મળી નથી. વિસ્તારનું નામ લખો.",
    locationFailed: "સ્થાન મળ્યું નથી. વિસ્તારનું નામ લખો.",
    areaPlaceholder: "જેમ કે કાંકરિયા, સ્ટેડિયમ સર્કલ પાસે",
    send: "મોકલો",
    traceRaw: "ટૂલ કૉલ્સ",
    overdueBy: (d) => `અપેક્ષિત તારીખથી ${d} દિવસ મોડું`,
    draftEscalation: "ઝોન DC ને એસ્કેલેશન",
    expectedLabel: "અપેક્ષિત",
    lookupBad: "આ ટ્રેકિંગ ID જેવું લાગતું નથી. ઉદા. AMC-2026-000124.",
  },
  hi: {
    quickStatus: "स्थिति क्या है?",
    quickAnother: "और शिकायत करें",
    quickPost: "X पर पोस्ट करें",
    copyId: "ID कॉपी करें",
    shareSlip: "स्लिप शेयर करें",
    copyCaption: "कैप्शन कॉपी करें",
    postOnX: "X पर पोस्ट करें",
    acknowledgment: "शिकायत पावती",
    department: "विभाग",
    zone: "ज़ोन",
    expectedBy: "अपेक्षित",
    severity: "गंभीरता",
    supporters: "समर्थक",
    socialTitle: "सार्वजनिक रूप से साझा करें",
    neverPosts: "Nagrik आपकी ओर से पोस्ट नहीं करता। फ़ैसला आपका।",
    copied: "कॉपी हो गया",
    useLocation: "मेरा मौजूदा स्थान",
    typeArea: "इलाक़ा लिखें",
    noLocation: "इस फ़ोटो से स्थान नहीं मिला। स्थान साझा करें या इलाक़ा लिखें.",
    netError: "सर्वर से संपर्क नहीं हुआ। आपका फ़ोटो यहाँ सुरक्षित है। फिर कोशिश करें.",
    uploadError: "यह फ़ोटो अपलोड नहीं हुआ। दूसरा आज़माएँ.",
    locationDenied: "स्थान की अनुमति नहीं मिली। इलाक़े का नाम लिखें.",
    locationFailed: "स्थान नहीं मिला। इलाक़े का नाम लिखें.",
    areaPlaceholder: "जैसे कांकरिया, स्टेडियम सर्कल के पास",
    send: "भेजें",
    traceRaw: "टूल कॉल्स",
    overdueBy: (d) => `अपेक्षित तारीख़ से ${d} दिन देर`,
    draftEscalation: "ज़ोन DC को एस्केलेशन",
    expectedLabel: "अपेक्षित",
    lookupBad: "यह ट्रैकिंग ID जैसा नहीं लगता। जैसे AMC-2026-000124.",
  },
};

/* ---------------------------------------------------------------- state */

const state = {
  phase: "idle", // idle | uploading | agent_running | need_location | filed | error
  lang: "en",
  config: {},
  sessionId: null,
  blocks: [],
  route: { stops: [], visible: false },
  trace: [],
  lastTrackingId: null,
  pendingImage: null, // { image_id, image_url, exif_gps }
  browserLocation: null,
  seq: 0,
};

const el = {
  intro: document.getElementById("intro"),
  thread: document.getElementById("thread"),
  traceRoute: document.getElementById("trace-route"),
  traceLog: document.getElementById("trace-log"),
  traceLogMobile: document.getElementById("trace-log-mobile"),
  traceDrawer: document.getElementById("trace-drawer"),
  traceEmpty: document.getElementById("trace-empty"),
  composer: document.getElementById("composer"),
  message: document.getElementById("message"),
  send: document.getElementById("send"),
  quick: document.getElementById("quick"),
  cameraInput: document.getElementById("camera-input"),
  galleryInput: document.getElementById("gallery-input"),
  galleryBtn: document.getElementById("gallery-btn"),
  composerInput: document.getElementById("composer-input"),
  lookupId: document.getElementById("lookup-id"),
  lookupBtn: document.getElementById("lookup-btn"),
};

const t = () => T[state.lang] || T.en;
const nextId = () => `b${++state.seq}`;

/* -------------------------------------------------------------- helpers */

function h(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2).toLowerCase(), v);
    else node.setAttribute(k, v === true ? "" : String(v));
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return node;
}

function icon(name) {
  return h("span", { class: "material-symbols-rounded", "aria-hidden": "true", text: name });
}

function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString(
    state.lang === "gu" ? "gu-IN" : state.lang === "hi" ? "hi-IN" : "en-IN",
    { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" }
  );
}

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString(
    state.lang === "gu" ? "gu-IN" : state.lang === "hi" ? "hi-IN" : "en-IN",
    { day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" }
  );
}

function issueLabel(key) {
  const spec = ISSUE[key] || ISSUE.other;
  return spec[state.lang] || spec.en;
}

function toast(text) {
  document.querySelectorAll(".toast").forEach((n) => n.remove());
  const node = h("div", { class: "toast", role: "status", text });
  document.body.append(node);
  setTimeout(() => node.remove(), 4000);
}

async function copy(text, label) {
  try {
    await navigator.clipboard.writeText(text);
    toast(label || t().copied);
  } catch {
    const ta = h("textarea", { style: "position:fixed;opacity:0" });
    ta.value = text;
    document.body.append(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    toast(label || t().copied);
  }
}

/* --------------------------------------------------------------- blocks */

function push(block) {
  block.id = block.id || nextId();
  block.v = 0;
  state.blocks.push(block);
  render();
  return block;
}

function bump(block) {
  block.v = (block.v || 0) + 1;
  render();
}

function dropBlocks(type) {
  state.blocks = state.blocks.filter((b) => b.type !== type);
  render();
}

/* ------------------------------------------------------- route handling */

function setRoute(stopIds) {
  state.route.stops = stopIds.map((id) => ({ id, state: "pending", result: "" }));
  state.route.visible = stopIds.length > 0;
}

function routeStop(stopId, { state: next, result } = {}) {
  let stop = state.route.stops.find((s) => s.id === stopId);
  if (!stop) {
    stop = { id: stopId, state: "pending", result: "" };
    state.route.stops.push(stop);
    state.route.visible = true;
  }
  // never walk a stop backwards from done to active (two tools share a stop)
  if (next && !(stop.state === "done" && next === "active")) stop.state = next;
  if (result !== undefined) stop.result = result;
}

function stopLabel(stopId) {
  const spec = Object.values(STOPS).find((s) => s.id === stopId);
  if (!spec) return stopId;
  return spec[state.lang] || spec.en;
}

function renderRoute(target) {
  target.replaceChildren();
  if (!state.route.visible) return;
  for (const stop of state.route.stops) {
    target.append(
      h(
        "li",
        { "data-state": stop.state },
        h("span", { class: "dot", "aria-hidden": "true" }),
        h("span", { class: "label", text: stopLabel(stop.id) }),
        h("span", { class: "result", text: stop.result || "" })
      )
    );
  }
}

/* ----------------------------------------------- one-line tool summaries */

function summarise(name, res) {
  if (!res || typeof res !== "object") return "";
  if (res.status === "error") return res.message || "failed";
  switch (name) {
    case "analyze_civic_image":
      return res.is_civic_issue
        ? `${issueLabel(res.issue_type)} · severity ${res.severity}`
        : "not a civic issue";
    case "get_photo_location":
      return res.found ? `${res.lat.toFixed(4)}, ${res.lng.toFixed(4)} · photo GPS` : "no GPS in photo";
    case "geocode_area":
      return res.formatted_address ? res.formatted_address.split(",").slice(0, 2).join(",") : "located";
    case "reverse_geocode":
      return res.formatted_address ? res.formatted_address.split(",").slice(0, 2).join(",") : "address found";
    case "resolve_ward":
      return `${res.ward_id} ${res.ward_name} · ${
        res.method === "area_name_match" ? "area name" : "nearest centroid"
      }`;
    case "get_department":
      return `${res.department} · SLA ${res.sla_hours}h`;
    case "check_duplicates":
      return res.duplicate_found
        ? `match ${res.tracking_id} · ${res.distance_m} m`
        : "none within 150 m";
    case "create_complaint":
      return res.is_duplicate
        ? `${res.tracking_id} · supporter #${res.supporters}`
        : `${res.tracking_id} · ${res.priority}`;
    case "get_complaint_status":
      return `${res.tracking_id} · ${res.complaint_status}${res.is_overdue ? " · overdue" : ""}`;
    case "draft_social_post":
      return `X draft ${res.x_chars}/280`;
    case "escalate_complaint":
      return `${res.officer || "escalated"}`;
    default:
      return res.status || "";
  }
}

/* ---------------------------------------------------------- trace panel */

function renderTrace() {
  const build = () =>
    state.trace.map((entry) =>
      h(
        "details",
        { class: "trace-item" },
        h(
          "summary",
          {},
          h("span", { class: "tool", text: entry.name }),
          h("span", {
            class: "badge",
            "data-ok": entry.ok === false ? "false" : "true",
            text: entry.done ? (entry.ok === false ? "error" : "ok") : "running…",
          })
        ),
        h("pre", {
          text:
            "args " +
            JSON.stringify(entry.args ?? {}, null, 2) +
            (entry.done ? "\n\nresponse " + JSON.stringify(entry.response ?? {}, null, 2) : ""),
        })
      )
    );

  el.traceLog.replaceChildren(...build());
  el.traceLogMobile.replaceChildren(...build());
  el.traceEmpty.hidden = state.trace.length > 0;
  el.traceDrawer.hidden = state.trace.length === 0;
  renderRoute(el.traceRoute);
}

/* --------------------------------------------------------------- render */

const nodeCache = new Map();

function render() {
  const nodes = [];
  for (const block of state.blocks) {
    const key = `${block.id}:${block.v}`;
    let node = nodeCache.get(key);
    if (!node) {
      node = renderBlock(block);
      nodeCache.set(key, node);
    }
    if (node) nodes.push(node);
  }
  el.thread.replaceChildren(...nodes);

  el.intro.hidden = state.blocks.length > 0;
  renderTrace();
  renderQuick();
  el.send.disabled = state.phase === "uploading" || state.phase === "agent_running";
  el.message.placeholder =
    state.phase === "need_location" ? t().areaPlaceholder : "Type a message…";
}

function renderBlock(block) {
  switch (block.type) {
    case "photo":
      return h(
        "div",
        { class: "photo-bubble" },
        h("img", { src: block.url, alt: block.alt || "Photo you sent" })
      );
    case "user":
      return h("div", { class: "bubble user", text: block.text });
    case "agent":
      return h("div", {
        class: "bubble agent",
        text: block.text,
        lang: state.lang === "en" ? null : state.lang,
      });
    case "error":
      return h("div", { class: "bubble error", text: block.text });
    case "typing":
      return h(
        "div",
        { class: "typing", "aria-label": "Working" },
        h("span"),
        h("span"),
        h("span")
      );
    case "route": {
      const ol = h("ol", { class: "route", "aria-live": "polite" });
      renderRoute(ol);
      return ol;
    }
    case "ask":
      return renderAsk(block);
    case "slip":
      return renderSlip(block);
    case "social":
      return renderSocial(block);
    case "status":
      return renderStatus(block);
    case "escalation":
      return h(
        "div",
        { class: "slip" },
        h("div", { class: "slip-head" }, h("strong", { text: block.officer })),
        h("div", { class: "escalation", text: block.note }),
        h(
          "div",
          { class: "slip-actions" },
          h("button", {
            type: "button",
            class: "btn-outline",
            text: t().copyCaption,
            onclick: () => copy(block.note),
          })
        )
      );
    default:
      return null;
  }
}

function renderAsk(block) {
  return h(
    "div",
    { class: "ask" },
    h("p", { text: block.text }),
    h(
      "div",
      { class: "ask-actions" },
      h(
        "button",
        { type: "button", class: "btn-outline", onclick: () => useBrowserLocation() },
        icon("my_location"),
        " ",
        t().useLocation
      ),
      h("button", {
        type: "button",
        class: "btn-outline",
        text: t().typeArea,
        onclick: () => el.message.focus(),
      })
    )
  );
}

function mapNode(lat, lng, label) {
  const key = state.config.maps_embed_key;
  if (!key || key.startsWith("your_")) {
    return h(
      "div",
      { class: "map-fallback" },
      `${label || ""}${label ? " · " : ""}${Number(lat).toFixed(4)}, ${Number(lng).toFixed(4)}`
    );
  }
  const url = `https://www.google.com/maps/embed/v1/place?key=${encodeURIComponent(
    key
  )}&q=${lat},${lng}&zoom=17`;
  return h("iframe", {
    class: "slip-map",
    src: url,
    loading: "lazy",
    referrerpolicy: "no-referrer-when-downgrade",
    title: label ? `Map of ${label}` : "Map of the complaint location",
  });
}

function renderSlip(block) {
  const c = block.data;
  const dup = c.is_duplicate;
  const stampText = dup ? "ALREADY REPORTED" : String(c.complaint_status || "Filed").toUpperCase();
  const stampStatus = dup ? "Already reported" : c.complaint_status || "Filed";
  const sev = Number(c.severity) || 3;

  const slip = h(
    "div",
    { class: "slip" },
    h(
      "div",
      { class: "slip-head" },
      h("strong", { text: state.config.corporation || "Ahmedabad Municipal Corporation" }),
      t().acknowledgment + " (mock)"
    ),
    h(
      "div",
      { class: "slip-id-row" },
      h("span", { class: "slip-id", text: c.tracking_id }),
      h("span", { class: "stamp stamp-land", "data-status": stampStatus, text: stampText })
    ),
    dup
      ? h("p", {
          class: "slip-note",
          text: `You're supporter #${c.supporters} — priority raised to ${c.priority}.`,
        })
      : null,
    h(
      "div",
      { class: "slip-body" },
      block.imageUrl
        ? h("img", { class: "slip-thumb", src: block.imageUrl, alt: block.alt || "" })
        : null,
      h(
        "div",
        { class: "slip-summary" },
        h("div", { class: "slip-issue", text: issueLabel(c.issue_type || c.issue) }),
        h("div", {
          class: "slip-address",
          text: `${c.address || ""}${c.ward_name ? ` · ${c.ward_name} (${c.ward_id})` : ""}`,
        }),
        h(
          "div",
          { class: "chips" },
          h("span", { class: "chip", "data-sev": sev }, `${t().severity} ${sev} · ${SEVERITY_WORD[sev]}`),
          h("span", { class: "chip" }, icon((ISSUE[c.issue_type || c.issue] || ISSUE.other).icon), issueLabel(c.issue_type || c.issue))
        )
      )
    ),
    h(
      "dl",
      { class: "slip-rows" },
      h("dt", { text: t().department }),
      h("dd", { text: c.department || "—" }),
      h("dt", { text: t().zone }),
      h("dd", { text: c.zone || "—" }),
      h("dt", { text: t().expectedBy }),
      h("dd", { text: fmtDateTime(c.expected_by) }),
      c.supporters > 1 ? h("dt", { text: t().supporters }) : null,
      c.supporters > 1 ? h("dd", { text: String(c.supporters) }) : null
    ),
    h("hr", { class: "perforation" }),
    c.lat && c.lng ? mapNode(c.lat, c.lng, c.ward_name) : null,
    h(
      "div",
      { class: "slip-actions" },
      h("button", {
        type: "button",
        class: "btn-outline",
        text: t().copyId,
        onclick: () => copy(c.tracking_id),
      }),
      h("button", {
        type: "button",
        class: "btn-outline",
        text: t().shareSlip,
        onclick: () => shareSlip(c),
      })
    )
  );

  requestAnimationFrame(() => {
    slip.classList.add("slip-shake");
    setTimeout(() => slip.classList.remove("slip-shake"), 160);
  });
  return slip;
}

async function shareSlip(c) {
  const text = `${issueLabel(c.issue_type || c.issue)} at ${c.address || c.ward_name}. AMC complaint ${
    c.tracking_id
  }, expected by ${fmtDateTime(c.expected_by)}.`;
  if (navigator.share) {
    try {
      await navigator.share({ title: `AMC ${c.tracking_id}`, text });
      return;
    } catch {
      /* user dismissed the share sheet */
    }
  }
  copy(text);
}

function renderSocial(block) {
  const d = block.data;
  let tab = "x";
  const wrap = h("div", { class: "social" });
  const textarea = h("textarea", { "aria-label": "Post text", spellcheck: "false" });
  const counter = h("div", { class: "counter" });
  const actions = h("div", { class: "social-actions" });

  const tabs = h(
    "div",
    { class: "tabs", role: "tablist" },
    h("button", {
      type: "button",
      role: "tab",
      "aria-selected": "true",
      text: "X",
      onclick: (e) => select("x", e.currentTarget),
    }),
    h("button", {
      type: "button",
      role: "tab",
      "aria-selected": "false",
      text: "Instagram",
      onclick: (e) => select("instagram", e.currentTarget),
    })
  );

  function paintCounter() {
    if (tab !== "x") {
      counter.textContent = `${textarea.value.length} characters`;
      counter.removeAttribute("data-over");
      return;
    }
    counter.textContent = `${textarea.value.length} / 280`;
    counter.setAttribute("data-over", String(textarea.value.length > 280));
  }

  function paintActions() {
    actions.replaceChildren();
    if (tab === "x") {
      actions.append(
        h("a", {
          class: "btn-outline",
          href: "https://twitter.com/intent/tweet?text=" + encodeURIComponent(textarea.value),
          target: "_blank",
          rel: "noopener noreferrer",
          text: t().postOnX,
        })
      );
    }
    actions.append(
      h("button", {
        type: "button",
        class: "btn-outline",
        text: t().copyCaption,
        onclick: () => copy(textarea.value),
      })
    );
  }

  function select(which, button) {
    tab = which;
    tabs.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", "false"));
    if (button) button.setAttribute("aria-selected", "true");
    textarea.value = which === "x" ? d.x_text : d.instagram_text;
    paintCounter();
    paintActions();
  }

  textarea.addEventListener("input", () => {
    paintCounter();
    if (tab === "x") paintActions();
  });

  wrap.append(
    h("h2", { class: "display", text: t().socialTitle }),
    tabs,
    textarea,
    counter,
    h("div", { class: "chips" }, (d.hashtags || []).map((tag) => h("span", { class: "chip", text: tag }))),
    actions,
    h("p", { class: "footnote", text: t().neverPosts })
  );
  select("x", tabs.firstElementChild);
  return wrap;
}

const FLOW = ["Filed", "Assigned", "In Progress", "Resolved"];

function renderStatus(block) {
  const s = block.data;
  const history = s.history || [];
  const reached = new Set(history.map((ev) => ev.status));
  const current = s.complaint_status;

  const items = history.map((ev, i) =>
    h(
      "li",
      { "data-state": i === history.length - 1 && s.is_overdue ? "overdue" : "done" },
      h("span", { class: "dot", "aria-hidden": "true" }),
      h(
        "div",
        {},
        h("div", { class: "tl-status", text: ev.status }),
        h("div", { class: "tl-meta", text: `${fmtTime(ev.at)}${ev.note ? " · " + ev.note : ""}` })
      )
    )
  );

  // Show the remaining workflow stops as pending, so progress is legible.
  const currentIndex = FLOW.indexOf(current);
  FLOW.forEach((status, i) => {
    if (reached.has(status) || (currentIndex >= 0 && i <= currentIndex)) return;
    items.push(
      h(
        "li",
        { "data-state": s.is_overdue ? "overdue" : "pending" },
        h("span", { class: "dot", "aria-hidden": "true" }),
        h(
          "div",
          {},
          h("div", { class: "tl-status", text: status }),
          h("div", {
            class: "tl-meta",
            text:
              status === "Resolved"
                ? `${t().expectedLabel} ${fmtDateTime(s.expected_by)}`
                : "",
          })
        )
      )
    );
  });

  return h(
    "div",
    { class: "slip" },
    h(
      "div",
      { class: "slip-id-row" },
      h("span", { class: "slip-id", style: "font-size:22px", text: s.tracking_id }),
      h("span", {
        class: "stamp stamp-land",
        "data-status": current,
        text: String(current || "").toUpperCase(),
      })
    ),
    h("div", {
      class: "slip-address",
      text: `${issueLabel(s.issue)} · ${s.ward_name || ""} (${s.ward_id || ""}) · ${s.department || ""}`,
    }),
    s.is_overdue
      ? h("p", {
          class: "slip-note",
          style: "color:var(--stamp-red);font-weight:600",
          text: t().overdueBy(s.overdue_days),
        })
      : null,
    h("ol", { class: "timeline" }, items),
    s.is_overdue
      ? h(
          "div",
          { class: "slip-actions" },
          h("button", {
            type: "button",
            class: "btn-outline",
            text: t().draftEscalation,
            onclick: () => sendText(`Draft the escalation for ${s.tracking_id}`),
          })
        )
      : null
  );
}

function renderQuick() {
  el.quick.replaceChildren();
  if (state.phase !== "filed" || !state.lastTrackingId) return;
  const options = [
    [t().quickStatus, () => sendText(t().quickStatus)],
    [t().quickAnother, () => resetForNext()],
  ];
  for (const [label, fn] of options) {
    el.quick.append(h("button", { type: "button", text: label, onclick: fn }));
  }
}

/* ------------------------------------------------------------- location */

function useBrowserLocation() {
  if (!navigator.geolocation) {
    push({ type: "error", text: t().locationFailed });
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      state.browserLocation = {
        lat: Number(pos.coords.latitude.toFixed(6)),
        lng: Number(pos.coords.longitude.toFixed(6)),
      };
      dropBlocks("ask");
      sendToAgent(
        `[browser_location=${state.browserLocation.lat},${state.browserLocation.lng}] I'm at this location now.`,
        { echo: t().useLocation }
      );
    },
    (err) => {
      push({ type: "error", text: err.code === 1 ? t().locationDenied : t().locationFailed });
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
  );
}

/* ------------------------------------------------------------- transport */

async function ensureSession() {
  if (state.sessionId) return state.sessionId;
  const sid = `s-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  try {
    await fetch(`/apps/${APP_NAME}/users/${USER_ID}/sessions/${sid}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
  } catch {
    /* auto_create_session covers us if this fails */
  }
  state.sessionId = sid;
  return sid;
}

async function uploadPhoto(file) {
  const body = new FormData();
  body.append("file", file, file.name || "photo.jpg");
  const resp = await fetch("/api/upload", { method: "POST", body });
  if (!resp.ok) {
    // Surface what the server actually objected to - "try another one" with no
    // reason is useless to someone standing next to a pothole.
    let detail = "";
    try {
      detail = (await resp.json()).detail || "";
    } catch {
      /* non-JSON error body */
    }
    const err = new Error(detail || `upload failed: ${resp.status}`);
    err.detail = detail;
    throw err;
  }
  return resp.json();
}

/* Walk the SSE stream, handing each parsed event to the reducer. */
async function streamAgent(text) {
  const sessionId = await ensureSession();
  const resp = await fetch("/run_sse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      appName: APP_NAME,
      userId: USER_ID,
      sessionId,
      newMessage: { role: "user", parts: [{ text }] },
      streaming: false,
    }),
  });
  if (!resp.ok || !resp.body) throw new Error(`agent failed: ${resp.status}`);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split(/\r?\n\r?\n/);
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      for (const rawLine of chunk.split(/\r?\n/)) {
        const line = rawLine.trimStart();
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (!payload || payload === "[DONE]") continue;
        try {
          handleEvent(JSON.parse(payload));
        } catch (err) {
          console.warn("unparsed SSE payload", payload, err);
        }
      }
    }
  }
}

/* ------------------------------------------------------------- reducer */

function handleEvent(event) {
  if (event.errorMessage || event.error_message) {
    push({ type: "error", text: event.errorMessage || event.error_message });
    return;
  }

  const parts = event.content?.parts || [];
  for (const part of parts) {
    const call = part.functionCall || part.function_call;
    const response = part.functionResponse || part.function_response;

    if (call) {
      state.trace.push({ name: call.name, args: call.args || {}, done: false, callId: call.id });
      const stop = STOPS[call.name];
      if (stop) routeStop(stop.id, { state: "active" });
      renderTrace();
      bumpRouteBlock();
      continue;
    }

    if (response) {
      const res = response.response ?? {};
      const entry =
        state.trace.find((e) => e.callId && e.callId === response.id) ||
        [...state.trace].reverse().find((e) => e.name === response.name && !e.done);
      if (entry) {
        entry.done = true;
        entry.response = res;
        entry.ok = res.status !== "error";
      }
      const stop = STOPS[response.name];
      if (stop) {
        routeStop(stop.id, {
          state: res.status === "error" ? "error" : "done",
          result: summarise(response.name, res),
        });
      }
      renderTrace();
      bumpRouteBlock();
      applyToolResult(response.name, res);
      continue;
    }

    if (part.text && event.partial !== true) {
      const text = part.text.trim();
      if (!text) continue;
      dropBlocks("typing");
      push({ type: "agent", text });
    }
  }
}

function bumpRouteBlock() {
  const block = state.blocks.find((b) => b.type === "route");
  if (block) bump(block);
}

/* Tool results that deserve a UI of their own. */
function applyToolResult(name, res) {
  if (res?.status === "error") {
    if (name === "resolve_ward" && res.need === "area_name") {
      state.phase = "need_location";
      push({ type: "ask", text: res.message || t().noLocation });
    }
    return;
  }

  switch (name) {
    case "analyze_civic_image":
      if (state.pendingImage) {
        state.pendingImage.alt = res.description || "";
        const photo = state.blocks.find((b) => b.type === "photo" && !b.alt);
        if (photo && res.description) {
          photo.alt = res.description;
          bump(photo);
        }
      }
      if (res.is_civic_issue === false) {
        // Mark the stops we will never reach so the route doesn't look stalled.
        for (const stop of state.route.stops) {
          if (stop.state === "pending") stop.state = "error";
        }
        state.phase = "idle";
        bumpRouteBlock();
      }
      break;

    case "get_photo_location":
      if (!res.found && state.browserLocation === null && !state.pendingImage?.exif_gps) {
        // The agent will ask next; the inline sheet gives faster options.
        state.phase = "need_location";
        if (!state.blocks.some((b) => b.type === "ask")) {
          push({ type: "ask", text: t().noLocation });
        }
      }
      break;

    case "create_complaint":
      dropBlocks("ask");
      dropBlocks("typing");
      state.lastTrackingId = res.tracking_id;
      state.phase = "filed";
      push({
        type: "slip",
        data: res,
        imageUrl: state.pendingImage?.image_url || null,
        alt: state.pendingImage?.alt || "",
      });
      break;

    case "draft_social_post":
      push({ type: "social", data: res });
      break;

    case "get_complaint_status":
      dropBlocks("typing");
      state.lastTrackingId = res.tracking_id;
      state.phase = "filed";
      push({ type: "status", data: res });
      break;

    case "escalate_complaint":
      push({ type: "escalation", note: res.escalation_note, officer: res.officer });
      break;

    default:
      break;
  }
}

/* ----------------------------------------------------------- the actions */

async function sendToAgent(text, { echo } = {}) {
  if (echo) push({ type: "user", text: echo });
  state.phase = "agent_running";
  if (!state.blocks.some((b) => b.type === "route")) push({ type: "route" });
  push({ type: "typing" });
  render();

  try {
    await streamAgent(text);
  } catch (err) {
    console.error(err);
    push({ type: "error", text: t().netError });
    state.phase = "error";
  } finally {
    dropBlocks("typing");
    if (state.phase === "agent_running") state.phase = state.lastTrackingId ? "filed" : "idle";
    render();
  }
}

function sendText(raw) {
  const text = raw.trim();
  if (!text || state.phase === "agent_running" || state.phase === "uploading") return;
  dropBlocks("ask");
  const tagged = state.browserLocation
    ? `[browser_location=${state.browserLocation.lat},${state.browserLocation.lng}] ${text}`
    : text;
  sendToAgent(tagged, { echo: text });
}

async function handleFile(file) {
  if (!file) return;
  state.phase = "uploading";
  setRoute(FILING_ROUTE);
  state.trace = [];
  nodeCache.clear();
  dropBlocks("ask");

  const localUrl = URL.createObjectURL(file);
  push({ type: "photo", url: localUrl });
  push({ type: "typing" });

  let uploaded;
  try {
    uploaded = await uploadPhoto(file);
  } catch (err) {
    console.error(err);
    dropBlocks("typing");
    push({ type: "error", text: err.detail || t().uploadError });
    state.phase = "error";
    return;
  }

  state.pendingImage = uploaded;
  const photo = state.blocks.find((b) => b.type === "photo");
  if (photo) {
    photo.url = uploaded.image_url;
    bump(photo);
  }

  const loc = uploaded.exif_gps || state.browserLocation;
  const tags = [`[image_id=${uploaded.image_id}]`];
  if (loc) tags.push(`[browser_location=${loc.lat},${loc.lng}]`);
  const langNote =
    state.lang === "gu"
      ? "ગુજરાતીમાં જવાબ આપો."
      : state.lang === "hi"
      ? "हिंदी में जवाब दें।"
      : "";
  dropBlocks("typing");
  await sendToAgent(`${tags.join(" ")} Please file this complaint. ${langNote}`.trim());
}

function resetForNext() {
  state.blocks = [];
  state.route = { stops: [], visible: false };
  state.trace = [];
  state.pendingImage = null;
  state.phase = "idle";
  nodeCache.clear();
  render();
  el.cameraInput.click();
}

/* ------------------------------------------------------------- bootstrap */

el.composer.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = el.message.value;
  el.message.value = "";
  el.message.style.height = "";
  sendText(text);
});

el.message.addEventListener("input", () => {
  el.message.style.height = "auto";
  el.message.style.height = Math.min(el.message.scrollHeight, 120) + "px";
});

el.message.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    el.composer.requestSubmit();
  }
});

for (const input of [el.cameraInput, el.galleryInput, el.composerInput]) {
  input.addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    handleFile(file);
  });
}

el.galleryBtn.addEventListener("click", () => el.galleryInput.click());

el.lookupBtn.addEventListener("click", () => {
  const id = el.lookupId.value.trim().toUpperCase();
  if (!/^AMC-\d{4}-\d{4,6}$/.test(id)) {
    toast(t().lookupBad);
    return;
  }
  el.lookupId.value = "";
  sendText(`What's the status of ${id}?`);
});

el.lookupId.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    el.lookupBtn.click();
  }
});

document.querySelectorAll(".lang-switch button").forEach((button) => {
  button.addEventListener("click", () => {
    state.lang = button.dataset.lang;
    document.querySelectorAll(".lang-switch button").forEach((b) => {
      b.setAttribute("aria-pressed", String(b === button));
    });
    nodeCache.clear();
    render();
  });
});

(async function init() {
  try {
    state.config = await (await fetch("/api/config")).json();
  } catch {
    state.config = {};
  }
  render();
})();

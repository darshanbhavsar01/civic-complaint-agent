/* Mock AMC officer console: list complaints, move them along, auto-refresh. */

const ISSUE_LABEL = {
  pothole: "Pothole",
  garbage: "Garbage",
  streetlight: "Streetlight",
  waterlogging: "Waterlogging",
  other: "Other",
};

const el = {
  rows: document.getElementById("rows"),
  counts: document.getElementById("counts"),
  wardFilter: document.getElementById("ward-filter"),
  statusFilter: document.getElementById("status-filter"),
};

const state = { wards: [], statuses: [], busy: new Set(), filtersReady: false };

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

function toast(text) {
  document.querySelectorAll(".toast").forEach((n) => n.remove());
  const node = h("div", { class: "toast", role: "status", text });
  document.body.append(node);
  setTimeout(() => node.remove(), 4000);
}

function fmt(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  });
}

function fillFilters(data) {
  if (state.filtersReady) return;
  for (const ward of data.wards) {
    el.wardFilter.append(
      h("option", { value: ward.id, text: `${ward.id} ${ward.name}` })
    );
  }
  for (const status of data.statuses) {
    el.statusFilter.append(h("option", { value: status, text: status }));
  }
  state.filtersReady = true;
}

function wardName(id) {
  const ward = state.wards.find((w) => w.id === id);
  return ward ? ward.name : id;
}

async function setStatus(trackingId, status, note, selectNode) {
  state.busy.add(trackingId);
  selectNode.disabled = true;
  try {
    const resp = await fetch(`/api/officer/${trackingId}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, note }),
    });
    if (!resp.ok) throw new Error(String(resp.status));
    toast(`Status updated to ${status}`);
  } catch (err) {
    console.error(err);
    toast(`Couldn't update ${trackingId}. Try again.`);
  } finally {
    state.busy.delete(trackingId);
    selectNode.disabled = false;
    load();
  }
}

function row(c) {
  const noteInput = h("input", {
    class: "note-input",
    type: "text",
    placeholder: "Optional note",
    "aria-label": `Note for ${c.trackingId}`,
  });

  const select = h(
    "select",
    {
      "aria-label": `Status of ${c.trackingId}`,
      onchange: (e) => setStatus(c.trackingId, e.target.value, noteInput.value, e.target),
    },
    state.statuses.map((s) =>
      h("option", { value: s, text: s, selected: s === c.status })
    )
  );

  return h(
    "tr",
    { "data-overdue": String(Boolean(c.is_overdue)) },
    h("td", {}, h("span", { class: "tid", text: c.trackingId }), h("div", { class: "addr", text: c.address || "" })),
    h("td", { text: `${c.ward} ${wardName(c.ward)}` }),
    h("td", { text: ISSUE_LABEL[c.issue] || c.issue }),
    h("td", { class: "num", text: String(c.severity ?? "") }),
    h("td", { class: "num", text: String(c.supporters ?? 1) }),
    h(
      "td",
      {},
      fmt(c.expectedBy),
      c.is_overdue
        ? h(
            "div",
            { class: "overdue-flag" },
            h("span", { class: "material-symbols-rounded", "aria-hidden": "true", text: "schedule" }),
            `${c.overdue_days} days overdue`
          )
        : null
    ),
    h("td", {}, select),
    h("td", {}, noteInput)
  );
}

async function load() {
  const params = new URLSearchParams();
  if (el.wardFilter.value) params.set("ward", el.wardFilter.value);
  if (el.statusFilter.value) params.set("status", el.statusFilter.value);

  let data;
  try {
    const resp = await fetch(`/api/complaints?${params}`);
    if (!resp.ok) throw new Error(String(resp.status));
    data = await resp.json();
  } catch (err) {
    console.error(err);
    el.counts.textContent = "Couldn't reach the server.";
    return;
  }

  state.wards = data.wards;
  state.statuses = data.statuses;
  fillFilters(data);

  // Don't yank a dropdown out from under the officer mid-change.
  if (state.busy.size > 0) return;

  el.counts.replaceChildren(
    document.createTextNode(`${data.complaints.length} complaints · `),
    data.overdue_count > 0
      ? h("strong", { text: `${data.overdue_count} overdue` })
      : document.createTextNode("none overdue")
  );

  if (data.complaints.length === 0) {
    el.rows.replaceChildren(
      h("tr", {}, h("td", { colspan: "8", class: "empty", text: "No complaints match these filters." }))
    );
    return;
  }
  el.rows.replaceChildren(...data.complaints.map(row));
}

el.wardFilter.addEventListener("change", load);
el.statusFilter.addEventListener("change", load);

load();
setInterval(load, 5000);

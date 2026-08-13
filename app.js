/* ============================================================================
   TCS Internal Dashboard — front-end renderer (v1)
   Reads data.json (same directory), renders per data-contract.md.
   ----------------------------------------------------------------------------
   PASSWORD GATE REMOVED (Aug 12 2026, per Andrew) — obscure URL only.
   To re-enable: restore TCS_DASH_PASSWORD const + initGate() form listener,
   and uncomment the #gate div in index.html.
============================================================================ */

const REFRESH_MS = 5 * 60 * 1000;      // re-fetch data.json every 5 minutes

let lastData = null;
let started = false;

/* ---------------------------- password gate (disabled) ---------------------------- */
(function initGate() {
  const gate = document.getElementById("gate");
  const app = document.getElementById("app");
  // No password — unlock immediately on load.
  if (gate) gate.classList.add("hidden");
  if (app) app.classList.remove("hidden");
  startDashboard();
})();

/* ------------------------------ data load ------------------------------ */
function startDashboard() {
  if (started) return;
  started = true;
  loadData();
  setInterval(loadData, REFRESH_MS);
}

function loadData() {
  const badge = document.getElementById("refresh-badge");
  badge.classList.remove("hidden");
  fetchJson("data.json?t=" + Date.now())
    .then((data) => {
      lastData = data;
      render(data);
      badge.classList.add("hidden");
    })
    .catch(() => {
      // File briefly absent / mid-refresh: keep last good render, show badge.
      if (!lastData) {
        document.getElementById("loading").textContent =
          "Refreshing… (data.json not available yet — will retry)";
        setTimeout(loadData, 20 * 1000); // retry sooner while empty
      }
      // badge stays visible until a successful fetch
    });
}

// fetch() with XHR fallback (some browsers block fetch on file://)
function fetchJson(url) {
  return fetch(url, { cache: "no-store" })
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .catch(() => new Promise((resolve, reject) => {
      const x = new XMLHttpRequest();
      x.open("GET", url);
      x.onload = () => {
        try { resolve(JSON.parse(x.responseText)); } catch (e) { reject(e); }
      };
      x.onerror = () => reject(new Error("xhr failed"));
      x.send();
    }));
}

/* ------------------------------ formatters ------------------------------ */
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}
function fmtMoneyCompact(v) {
  if (v === null || v === undefined) return "—";
  const n = Number(v), a = Math.abs(n), sign = n < 0 ? "-" : "";
  if (a >= 1e6) return sign + "$" + (a / 1e6).toFixed(2).replace(/\.?0+$/, "") + "M";
  if (a >= 1e5) return sign + "$" + Math.round(a / 1e3) + "K";
  if (a >= 1e4) return sign + "$" + (a / 1e3).toFixed(1) + "K";
  return sign + "$" + Math.round(a).toLocaleString("en-US");
}
function fmtMoneyExact(v) {
  if (v === null || v === undefined) return "—";
  return "$" + Math.round(Number(v)).toLocaleString("en-US");
}
function fmtInt(v) {
  if (v === null || v === undefined) return "—";
  return Number(v).toLocaleString("en-US");
}
function fmtPct(v) {
  if (v === null || v === undefined) return "—";
  return Number(v).toFixed(1).replace(/\.0$/, "") + "%";
}
function fmtTs(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return esc(iso);
  return d.toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
  });
}
function marginClass(v) {
  if (v === null || v === undefined) return "";
  if (v < 10) return "neg";
  if (v > 25) return "pos";
  return "mid";
}
const ST_META = {
  green: { cls: "g", label: "Good" },
  amber: { cls: "a", label: "Watch" },
  red:   { cls: "r", label: "Red" }
};
function statusPill(status, labelOverride) {
  const m = ST_META[status] || ST_META.amber;
  return `<span class="st ${m.cls}"><span class="d"></span>${esc(labelOverride || m.label)}</span>`;
}

/* -------------------------------- render -------------------------------- */
let _data = null;           // cached dashboard data for page re-renders
let _page = "dashboard";    // current page

function render(data) {
  _data = data;
  document.getElementById("loading").classList.add("hidden");
  renderHeader(data);
  showPage(_page);
  document.getElementById("footer").innerHTML =
    `TCS Internal · auto-refresh hourly (LP/BP/Meta/SR) · retainers daily · ` +
    `<span class="amber-text">shared-password access</span>` +
    (data.generated_at ? ` · generated ${fmtTs(data.generated_at)}` : "");
}

/* ---------------- page routing (added Aug 11 2026) ---------------- */
function renderDashboard(d) {
  const staleNames = (d.data_freshness && d.data_freshness.stale_warnings) || [];
  return renderTopRow(d) +
    /* renderKpis(d.company || {}) +  // HIDDEN by Andrew Aug 11 2026 */
    renderTorts(d.torts || [], staleNames) +
    renderBuyers(d.buyers || []);
}

/* ------------------------------ Supabase notes ------------------------------ */
const SUPABASE_URL = "https://cvpygpxfqxoywrqnmlaz.supabase.co";
const SUPABASE_KEY = "sb_publishable_oDb7jM3Vd7WNNfWSewXeCQ_OLU1YXd6";

async function sbFetch(path, opts = {}) {
  const r = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    ...opts,
    headers: {
      "apikey": SUPABASE_KEY,
      "Authorization": `Bearer ${SUPABASE_KEY}`,
      "Content-Type": "application/json",
      "Prefer": "return=representation",
      ...(opts.headers || {})
    }
  });
  if (!r.ok) throw new Error(`Supabase ${r.status}`);
  return r.json();
}

async function loadNotes(page) {
  try {
    const notes = await sbFetch(`notes?select=*&page=eq.${page}&order=created_at.desc&limit=50`);
    renderNotes(page, notes);
  } catch (e) {
    document.getElementById(`notes-list-${page}`).innerHTML =
      `<div class="note-err">Failed to load notes. Check console.</div>`;
    console.error("Notes load error:", e);
  }
}

async function addNote(page, author, kind, body) {
  const note = { page, author, kind, body };
  const result = await sbFetch("notes", { method: "POST", body: JSON.stringify(note) });
  return result[0];
}

function renderNotes(page, notes) {
  const container = document.getElementById(`notes-list-${page}`);
  if (!container) return;
  if (!notes.length) {
    container.innerHTML = `<div class="note-empty">No notes yet. Be the first to add one.</div>`;
    return;
  }
  container.innerHTML = notes.map((n) => {
    const kindBadge = n.kind === "request"
      ? `<span class="note-kind req">REQUEST</span>`
      : `<span class="note-kind">NOTE</span>`;
    const ts = fmtTs(n.created_at);
    return `<div class="note-item">
      <div class="note-meta">${kindBadge}<span class="note-author">${esc(n.author)}</span><span class="note-ts">${ts}</span></div>
      <div class="note-body">${esc(n.body)}</div>
    </div>`;
  }).join("");
}

function renderNotesSection(page, title) {
  return `<div class="notes-section">
    <div class="slabel">Team Notes & Requests — ${esc(title)}</div>
    <div class="notes-form card">
      <div class="notes-form-row">
        <input type="text" id="note-author-${page}" placeholder="Your name" maxlength="40">
        <select id="note-kind-${page}">
          <option value="note">Note</option>
          <option value="request">Request</option>
        </select>
      </div>
      <textarea id="note-body-${page}" placeholder="Add a note or request for the team…" rows="2" maxlength="500"></textarea>
      <button onclick="submitNote('${page}')">Post</button>
    </div>
    <div id="notes-list-${page}" class="notes-list"><div class="note-empty">Loading notes…</div></div>
  </div>`;
}

async function submitNote(page) {
  const authorEl = document.getElementById(`note-author-${page}`);
  const kindEl = document.getElementById(`note-kind-${page}`);
  const bodyEl = document.getElementById(`note-body-${page}`);
  const author = authorEl.value.trim();
  const kind = kindEl.value;
  const body = bodyEl.value.trim();
  if (!author || !body) { alert("Name and note text are required."); return; }
  try {
    await addNote(page, author, kind, body);
    bodyEl.value = "";
    await loadNotes(page);
  } catch (e) {
    alert("Failed to post note. Check console.");
    console.error("Note post error:", e);
  }
}

function renderYouTubePage() {
  return `<div class="pagehead">YouTube Ads</div>` +
    `<div class="pagetitle">YouTube Ads</div>` +
    `<div class="pagesub">SMA / Hernia Mesh YouTube creative + script performance.</div>` +
    `<div class="placeholder"><div class="big">YouTube ads analysis landing here soon.</div>` +
    `<div class="small">Creative performance data is being wired up. Task board is live below.</div></div>` +
    renderTaskBoard("youtube");
}

function renderTaskBoard(page) {
  return `<div class="notes-section">
    <div class="slabel">Task Board — ${esc(page === "youtube" ? "YouTube" : page)}</div>
    <div class="notes-form card">
      <div class="notes-form-row">
        <input type="text" id="task-author-${page}" placeholder="Your name" maxlength="40">
        <select id="task-kind-${page}">
          <option value="request">Request</option>
          <option value="note">Note</option>
        </select>
      </div>
      <textarea id="task-body-${page}" placeholder="Describe the task or request…" rows="2" maxlength="500"></textarea>
      <button onclick="submitTask('${page}')">Post</button>
    </div>
    <div id="tasks-list-${page}" class="tasks-list"><div class="note-empty">Loading tasks…</div></div>
  </div>`;
}

async function loadTasks(page) {
  try {
    const notes = await sbFetch(`notes?select=*&page=eq.${page}&order=created_at.desc&limit=100`);
    renderTasks(page, notes);
  } catch (e) {
    document.getElementById(`tasks-list-${page}`).innerHTML =
      `<div class="note-err">Failed to load tasks. Check console.</div>`;
    console.error("Tasks load error:", e);
  }
}

async function submitTask(page) {
  const authorEl = document.getElementById(`task-author-${page}`);
  const kindEl = document.getElementById(`task-kind-${page}`);
  const bodyEl = document.getElementById(`task-body-${page}`);
  const author = authorEl.value.trim();
  const kind = kindEl.value;
  const body = bodyEl.value.trim();
  if (!author || !body) { alert("Name and text are required."); return; }
  try {
    await addNote(page, author, kind, body);
    bodyEl.value = "";
    await loadTasks(page);
  } catch (e) {
    alert("Failed to post. Check console.");
    console.error("Task post error:", e);
  }
}

async function updateTaskStatus(id, newStatus) {
  try {
    await sbFetch(`notes?id=eq.${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: newStatus, updated_at: new Date().toISOString() })
    });
    // Reload the current page's tasks
    const page = document.querySelector(".navitem.active")?.dataset.page || "youtube";
    await loadTasks(page);
  } catch (e) {
    alert("Failed to update status. Check console.");
    console.error("Status update error:", e);
  }
}

function renderTasks(page, notes) {
  const container = document.getElementById(`tasks-list-${page}`);
  if (!container) return;
  
  // Separate requests (with status) from notes (simple feed)
  const requests = notes.filter(n => n.kind === "request");
  const simpleNotes = notes.filter(n => n.kind !== "request");
  
  let html = "";
  
  // Requests section (task board)
  if (requests.length) {
    html += `<div class="tasks-subheader">Requests (${requests.length})</div>`;
    html += requests.map((n) => {
      const status = n.status || "open";
      const statusMeta = {
        open: { cls: "status-open", label: "OPEN", icon: "🔴" },
        claimed: { cls: "status-claimed", label: "CLAIMED", icon: "🟡" },
        done: { cls: "status-done", label: "DONE", icon: "🟢" }
      }[status] || { cls: "status-open", label: "OPEN", icon: "🔴" };
      
      const ts = fmtTs(n.created_at);
      const updated = n.updated_at && n.updated_at !== n.created_at ? ` · updated ${fmtTs(n.updated_at)}` : "";
      
      return `<div class="task-item ${statusMeta.cls}">
        <div class="task-header">
          <span class="task-status ${statusMeta.cls}">${statusMeta.icon} ${statusMeta.label}</span>
          <span class="task-author">${esc(n.author)}</span>
          <span class="task-ts">${ts}${updated}</span>
        </div>
        <div class="task-body">${esc(n.body)}</div>
        <div class="task-actions">
          ${status !== "open" ? `<button class="task-btn" onclick="updateTaskStatus(${n.id}, 'open')">↩ Reopen</button>` : ""}
          ${status !== "claimed" ? `<button class="task-btn" onclick="updateTaskStatus(${n.id}, 'claimed')">🟡 Claim</button>` : ""}
          ${status !== "done" ? `<button class="task-btn" onclick="updateTaskStatus(${n.id}, 'done')">✅ Done</button>` : ""}
        </div>
      </div>`;
    }).join("");
  }
  
  // Simple notes section
  if (simpleNotes.length) {
    html += `<div class="tasks-subheader">Notes (${simpleNotes.length})</div>`;
    html += simpleNotes.map((n) => {
      const ts = fmtTs(n.created_at);
      return `<div class="note-item">
        <div class="note-meta"><span class="note-author">${esc(n.author)}</span><span class="note-ts">${ts}</span></div>
        <div class="note-body">${esc(n.body)}</div>
      </div>`;
    }).join("");
  }
  
  if (!requests.length && !simpleNotes.length) {
    html = `<div class="note-empty">No tasks or notes yet. Be the first to add one.</div>`;
  }
  
  container.innerHTML = html;
}

function showPage(page) {
  _page = page;
  document.querySelectorAll(".navitem").forEach((n) =>
    n.classList.toggle("active", n.dataset.page === page));
  const c = document.getElementById("content");
  if (!_data) return;
  if (page === "dashboard") { c.innerHTML = renderDashboard(_data); return; }
  if (page === "meta") {
    c.innerHTML = renderPlaceholder("Meta Ads Analysis",
      "Creative / campaign performance across Meta accounts.",
      "Meta ads analysis landing here soon.");
    loadNotes("meta");
    return;
  }
  if (page === "youtube") {
    c.innerHTML = renderYouTubePage();
    loadTasks("youtube");
    return;
  }
  if (page === "utm") {
    // UTM Content is now a separate page (utm.html) — redirect
    window.location.href = "utm.html";
    return;
  }
  c.innerHTML = renderDashboard(_data);
}

document.addEventListener("click", (e) => {
  const item = e.target.closest(".navitem");
  if (item && item.dataset.page) showPage(item.dataset.page);
});

/* header: freshness + stale warnings chip */
function renderHeader(data) {
  const f = data.data_freshness || {};
  const warns = f.stale_warnings || [];
  let html = `Data as of <b>${fmtTs(f.leads_spend_sr)}</b> · Retainers updated <b>${fmtTs(f.retainers)}</b>`;
  if (warns.length) {
    html += `<br><details class="stale-chip"><summary>⚠ ${warns.length} stale data source${warns.length > 1 ? "s" : ""}</summary>` +
      `<ul class="stale-list">${warns.map((w) => `<li>⚠ ${esc(w)}</li>`).join("")}</ul></details>`;
  }
  document.getElementById("fresh").innerHTML = html;
}

/* top row: needs attention + Andrew's priorities */
function renderTopRow(data) {
  const items = (data.needs_attention || []).slice()
    .sort((a, b) => (a.level === "red" ? 0 : 1) - (b.level === "red" ? 0 : 1));
  const attnRows = items.length
    ? items.map((it) => {
        const red = it.level === "red";
        return `<div class="row${red ? "" : " amber"}">` +
          `<span class="pill ${red ? "red" : "amber"}">${red ? "RED" : "WATCH"}</span>` +
          `<span class="nm">${esc(it.tort_or_buyer)}</span>` +
          `<span class="rs">${esc(it.reason || "")}</span>` +
          (it.owner ? `<span class="own">→ ${esc(it.owner)}</span>` : "") +
          `</div>`;
      }).join("")
    : `<div class="empty">Nothing needs attention right now.</div>`;

  const prios = data.andrew_priorities || [];
  const note = data.andrew_note || {};
  const prioHtml = prios.length
    ? `<ul class="prio">${prios.map((p) =>
        `<li><span class="n">${esc(p.n)}</span> ${esc(p.text)}</li>`).join("")}</ul>`
    : `<div class="empty">No priorities set yet.</div>`;
  const noteHtml = note.text
    ? `<div class="andrew"><b>Andrew${note.ts ? " " + fmtTs(note.ts) : ""}:</b> “${esc(note.text)}”</div>`
    : "";

  return `<div class="toprow">
    <div class="card"><h3><span class="dot"></span> Needs Attention</h3>
      <div class="attn">${attnRows}</div></div>
    <div class="card"><h3><span class="dot p"></span> Andrew's Tort Priorities</h3>
      ${prioHtml}${noteHtml}</div>
  </div>`;
}

/* company KPI strip — NO CPL here (hard rule #1) */
function renderKpis(c) {
  const deltas = c.deltas || {};
  const rev = deltas.revenue_wow_pct;
  const revDelta = (rev !== null && rev !== undefined)
    ? `<div class="d ${rev >= 0 ? "up" : "dn"}">${rev >= 0 ? "▲" : "▼"} ${fmtPct(Math.abs(rev))} WoW</div>`
    : "";
  const kpis = [
    { l: "Ad Spend", v: fmtMoneyCompact(c.spend) },
    { l: "Revenue", v: fmtMoneyCompact(c.revenue), d: revDelta },
    { l: "Gross Profit", v: fmtMoneyCompact(c.gross_profit) },
    { l: "Margin", v: fmtPct(c.margin_pct) },
    { l: "Cost / Sign", v: fmtMoneyExact(c.cost_per_sign) },
    { l: "Payable Leads", v: fmtInt(c.payable_leads) }
  ];
  return `<div class="slabel">Company ${c.window_label ? `<span class="wl">${esc(c.window_label)}</span>` : ""}</div>
    <div class="kpis">${kpis.map((k) =>
      `<div class="kpi"><div class="l">${k.l}</div><div class="v">${k.v}</div>${k.d || ""}</div>`).join("")}</div>` +
    (c.caveat ? `<div class="kpi-caveat">⚠ ${esc(c.caveat)}</div>` : "");
}

/* torts table — sorted by spend desc; stale rows in amber ⚠ state (hard rule #2) */
function isStaleTort(t, staleWarnings) {
  if (t.data_ok === false) return true;
  const re = new RegExp("\\b" + t.tort.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "i");
  return staleWarnings.some((w) => re.test(w));
}
function renderTorts(torts, staleWarnings) {
  const sorted = torts.slice().sort((a, b) => (b.spend ?? -1) - (a.spend ?? -1));
  const rows = sorted.map((t) => {
    const stale = isStaleTort(t, staleWarnings);
    const noteHtml = t.note
      ? `${t.note_author === "Andrew" ? `<span class="you">Andrew:</span> ` : ""}${esc(t.note)}`
      : `<span style="color:#9aa8b8">—</span>`;
    const caveat = t.spend_caveat ? `<span class="caveat">${esc(t.spend_caveat)}</span>` : "";

    if (stale) {
      // Never render stale/broken spend-side numbers as real values.
      const warn = `<span class="stale-val">⚠ stale</span>`;
      return `<tr class="stale">
        <td>${statusPill("amber", "⚠ Stale")}</td>
        <td class="tort">${esc(t.tort)}</td>
        <td class="num">${warn}${caveat}</td>
        <td class="num">${fmtMoneyCompact(t.revenue)}</td>
        <td class="num">${warn}</td>
        <td class="num">${warn}</td>
        <td class="num">${warn}</td>
        <td class="num">${fmtInt(t.payable_leads)}</td>
        <td class="num">${fmtInt(t.signed)}</td>
        <td class="note">${noteHtml}</td>
      </tr>`;
    }

    // Cost/Sign per metric-definitions: n/a if signed=0, — if spend=0, TBD if spend unknown
    let cps;
    if (t.spend === null || t.spend === undefined) cps = "TBD";
    else if (t.signed === 0) cps = "n/a";
    else if (t.spend === 0) cps = "—";
    else cps = fmtMoneyExact(t.cost_per_sign);

    return `<tr>
      <td>${statusPill(t.status)}</td>
      <td class="tort">${esc(t.tort)}</td>
      <td class="num">${fmtMoneyCompact(t.spend)}${caveat}</td>
      <td class="num">${fmtMoneyCompact(t.revenue)}</td>
      <td class="num ${marginClass(t.margin_pct)}">${fmtPct(t.margin_pct)}</td>
      <td class="num">${fmtMoneyExact(t.cpl)}</td>
      <td class="num">${cps}</td>
      <td class="num">${fmtInt(t.payable_leads)}</td>
      <td class="num">${fmtInt(t.signed)}</td>
      <td class="note">${noteHtml}</td>
    </tr>`;
  }).join("");

  return `<div class="slabel">Torts — Health Board</div>
    <div class="tablecard"><div class="scroll"><table>
      <thead><tr>
        <th>Status</th><th>Tort</th><th class="num">Spend</th><th class="num">Revenue</th>
        <th class="num">Margin</th><th class="num">CPL</th><th class="num">Cost/Sign</th>
        <th class="num">Leads</th><th class="num">Signs</th><th>Note</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div></div>`;
}

/* buyers cards — Pulaski always its own card (hard rule #4; pipeline provides it) */
function renderBuyers(buyers) {
  const cards = buyers.map((b) => {
    const borderCls = b.status === "red" ? " bad" : b.status === "amber" ? " warn" : "";
    const comment = b.comment
      ? `<div class="bnote"><span class="you">Andrew${b.comment_ts ? " " + fmtTs(b.comment_ts) : ""}:</span> ${esc(b.comment)}</div>`
      : `<div class="bnote none">No comment yet.</div>`;

    const runway = (b.runway && b.runway.length)
      ? b.runway.map((r) => {
          if (r.cap === null || r.cap === undefined) {
            return `<div class="runway-item">
              <div class="rt"><b>${esc(r.tort)}</b><span class="nocap">no cap set</span></div>
            </div>`;
          }
          const pct = Math.max(0, Math.min(100, r.pct ?? 0));
          const heat = pct >= 85 ? " hot" : pct >= 60 ? " warm" : "";
          const days = (r.est_days_left !== null && r.est_days_left !== undefined)
            ? ` · ~${r.est_days_left} days left` : "";
          return `<div class="runway-item">
            <div class="rt"><b>${esc(r.tort)}</b><span>${pct}%</span></div>
            <div class="bar"><i class="${heat.trim()}" style="width:${pct}%"></i></div>
            <div class="runway-cap">${fmtInt(r.used)} / ${fmtInt(r.cap)} ${esc(r.cap_unit || "")}${days}</div>
          </div>`;
        }).join("")
      : `<div class="rw-empty">No runway data.</div>`;

    const tagList = (arr, cls) => arr.length
      ? arr.map((t) => `<span class="tag ${cls}">${esc(t)}</span>`).join("")
      : `<span class="none">none</span>`;

    return `<div class="buyer${borderCls}">
      <h4>${esc(b.buyer)} ${statusPill(b.status)}</h4>
      ${comment}
      <div class="sec">Runway</div>
      ${runway}
      <div class="sec">Active</div>
      <div class="tags">${tagList(b.active_torts || [], "")}</div>
      <div class="sec">Upcoming</div>
      <div class="tags">${tagList(b.upcoming_torts || [], "up")}</div>
    </div>`;
  }).join("");

  return `<div class="slabel">Buyers — Health</div><div class="buyers">${cards}</div>`;
}

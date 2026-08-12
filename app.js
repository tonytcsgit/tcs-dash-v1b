/* ============================================================================
   TCS Internal Dashboard — front-end renderer (v1)
   Reads data.json (same directory), renders per data-contract.md.
   ----------------------------------------------------------------------------
   SHARED TEAM PASSWORD — change this constant to rotate the password.
   (Client-side gate only; obscure-URL + shared-password, internal v1.)
============================================================================ */
const TCS_DASH_PASSWORD = "tcs";   // <<< CHANGE PASSWORD HERE

const REFRESH_MS = 5 * 60 * 1000;      // re-fetch data.json every 5 minutes
const AUTH_KEY = "tcs_dash_auth";

let lastData = null;
let started = false;

/* ---------------------------- password gate ---------------------------- */
(function initGate() {
  const gate = document.getElementById("gate");
  const app = document.getElementById("app");
  const form = document.getElementById("gate-form");
  const pw = document.getElementById("gate-pw");
  const err = document.getElementById("gate-err");

  function unlock() {
    gate.classList.add("hidden");
    app.classList.remove("hidden");
    startDashboard();
  }

  if (sessionStorage.getItem(AUTH_KEY) === "1") { unlock(); return; }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (pw.value === TCS_DASH_PASSWORD) {
      sessionStorage.setItem(AUTH_KEY, "1");
      unlock();
    } else {
      err.classList.remove("hidden");
      pw.value = "";
      pw.focus();
    }
  });
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
function render(data) {
  document.getElementById("loading").classList.add("hidden");
  renderHeader(data);
  const staleNames = (data.data_freshness && data.data_freshness.stale_warnings) || [];
  document.getElementById("content").innerHTML =
    renderTopRow(data) +
    /* renderKpis(data.company || {}) +  // HIDDEN by Andrew Aug 11 2026 */
    renderTorts(data.torts || [], staleNames) +
    renderBuyers(data.buyers || []);
  document.getElementById("footer").innerHTML =
    `TCS Internal · auto-refresh hourly (LP/BP/Meta/SR) · retainers daily · ` +
    `<span class="amber-text">shared-password access</span>` +
    (data.generated_at ? ` · generated ${fmtTs(data.generated_at)}` : "");
}

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

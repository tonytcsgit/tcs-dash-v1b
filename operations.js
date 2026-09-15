/* Demo-only renderer. The sole data request is the synthetic fixture beside this page. */
'use strict';
const esc = value => String(value ?? '').replace(/[&<>"']/g,c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = value => value === null || value === undefined || !Number.isFinite(value) ? '—' : new Intl.NumberFormat('en-US',{maximumFractionDigits:1}).format(value);
const dateLabel = value => value ? new Date(value+'T00:00:00Z').toLocaleDateString('en-US',{month:'short',day:'numeric',timeZone:'UTC'}) : 'Not set';
const color = status => ['Behind','Blocked'].includes(status) ? 'red' : status === 'On track' || status === 'Ready' ? 'green' : 'amber';
const badge = (text,tone) => `<span class="ops-pill ${tone || color(text)}">${esc(text)}</span>`;
const target = value => value === null ? '<span class="ops-muted">Not set</span>' : `<strong>${fmt(value)}</strong><small>leads / target period</small>`;
const empty = text => `<div class="ops-empty">${esc(text)}</div>`;
function issues(p,m) {
  const out=[];
  if (p.readiness === 'Blocked') out.push({title:'Launch blocked',reason:p.blocker,owner:p.operations_owner});
  if (p.phase === 'live') {
    if (m.actual === null) out.push({title:'Data unavailable',reason:'Volume is unknown. Do not interpret the missing feed as zero.',owner:p.operations_owner});
    else if (m.actual === 0) out.push({title:'No first delivery',reason:'Example source is available, but no leads have arrived in the target period.',owner:p.operations_owner});
    else if (m.status === 'Behind') out.push({title:'Behind commitment',reason:`${fmt(m.actual)} received versus ${fmt(m.expected)} expected through the scenario date.`,owner:p.marketing_owner});
    if (m.deliveryGap > 0) out.push({title:'Delivery reconciliation',reason:`${fmt(m.deliveryGap)} submitted leads have no received counterpart in this synthetic scenario. Investigate; this is not proof of loss.`,owner:p.operations_owner});
  }
  if (p.phase !== 'prospect' && p.commitment === null) out.push({title:'Buyer commitment not set',reason:'A marketing forecast does not substitute for a buyer commitment.',owner:p.plan_owner});
  if (p.phase !== 'prospect' && p.forecast === null) out.push({title:'Marketing forecast not set',reason:'Set a separate forecast for the target period.',owner:p.plan_owner});
  return out;
}
function details(p,m) {
  return `<details><summary>Details & next action</summary><div class="ops-detail"><p><b>Target period:</b> ${dateLabel(p.window_start)}–${dateLabel(p.window_end)}</p><p><b>Go-live:</b> ${dateLabel(p.go_live)} · <b>Plan owner:</b> ${esc(p.plan_owner)}</p><p><b>Marketing:</b> ${esc(p.marketing_owner)} · <b>Operations:</b> ${esc(p.operations_owner)}</p><p><b>Example funnel:</b> ${fmt(m.submitted)} submitted → ${fmt(m.actual)} buyer received → ${fmt(m.accepted)} accepted. Accepted is a separate stage, not the target unit.</p><p><b>Forecast expected to date:</b> ${fmt(m.forecastExpected)} leads</p><p><b>Next action:</b> ${esc(p.next_action)}</p><p>Illustrative pacing uses equal calendar-day delivery across the target period. No business-day or ramp-up rule has been approved.</p></div></details>`;
}
function launchCard(p,asOf) {
  const m=OpsModel.metrics(p,asOf);
  return `<article class="ops-launch"><div class="ops-card-top"><span class="eyebrow">P${esc(p.priority)} · ${esc(p.platform)}</span>${badge(p.readiness)}</div><h3>${esc(p.tort)}</h3><p>${esc(p.buyer)}</p><div class="ops-launch-date">${dateLabel(p.go_live)} <small>example go-live</small></div><div class="ops-split"><div><small>Buyer commitment</small>${target(p.commitment)}</div><div><small>Marketing forecast</small>${target(p.forecast)}</div></div><p class="ops-next">${esc(p.blocker || p.next_action)}</p>${details(p,m)}</article>`;
}
function renderResults(data) {
  const programs=[...data.programs].sort((a,b)=>a.priority-b.priority || a.id.localeCompare(b.id));
  const live=programs.filter(p=>p.phase==='live');
  const prospects=programs.filter(p=>p.phase==='prospect');
  const attention=programs.flatMap(p=>issues(p,OpsModel.metrics(p,data.as_of)).map(issue=>({p,...issue})));
  const buyers=OpsModel.buyerRollup(programs,data.as_of);
  document.getElementById('ops-results').innerHTML = `
  <section id="upcoming-launches"><h2>Upcoming budget priorities <span>As of September 12 · demo context</span></h2><p class="ops-help">Andrew’s up-and-coming priorities. No budget amounts, launch dates or volume commitments supplied; priority does not mean a confirmed launch.</p><div class="ops-launch-grid"><article class="ops-launch"><span class="eyebrow">Priority 1</span><h3>OLYMPUS</h3><p class="context-buyer">Parker</p><p>Budget amount: <b>Not set</b></p><p>Go-live: <b>Not set</b> · Lead target: <b>Not set</b></p></article><article class="ops-launch"><span class="eyebrow">Priority 2</span><h3>Chlorpyrifos</h3><p class="context-buyer">Parker</p><p>Budget amount: <b>Not set</b></p><p>Go-live: <b>Not set</b> · Lead target: <b>Not set</b></p></article><article class="ops-launch"><span class="eyebrow">Priority 3 — equal</span><h3>Dupixent</h3><p class="context-buyer">Parker</p><p>Budget amount: <b>Not set</b></p><p>Go-live: <b>Not set</b> · Lead target: <b>Not set</b></p></article><article class="ops-launch"><span class="eyebrow">Priority 3 — equal</span><h3>Apple AirTag</h3><p class="context-buyer">Parker</p><p>Budget amount: <b>Not set</b></p><p>Go-live: <b>Not set</b> · Lead target: <b>Not set</b></p></article></div></section>
  <section id="live-programs"><h2>Program delivery <span>Tort × buyer × platform</span></h2><p class="ops-help">Buyer-received leads in each program’s target period through the fixed scenario date. All values are examples.</p>${live.length ? `<div class="tablecard"><div class="scroll"><table><thead><tr><th>Program / target period</th><th>Buyer<br>commitment</th><th>Marketing<br>forecast</th><th class="num">Received</th><th class="num">Expected<br>to date</th><th>Delivery health</th></tr></thead><tbody>${live.map(p=>{
    const m=OpsModel.metrics(p,data.as_of);
    return `<tr data-program="${esc(p.id)}"><td class="ops-program"><span class="ops-priority">P${esc(p.priority)}</span><b>${esc(p.tort)}</b><small>${esc(p.buyer)} · ${esc(p.platform)}</small><small>${dateLabel(p.window_start)}–${dateLabel(p.window_end)}</small>${details(p,m)}</td><td>${target(p.commitment)}</td><td>${target(p.forecast)}</td><td class="num ops-number">${fmt(m.actual)}</td><td class="num">${fmt(m.expected)}</td><td>${badge(m.status)}<small>${m.actual===null?'Example feed unavailable':'Example feed available'}</small>${m.gap!==null ? `<small>${m.gap>=0?'+':''}${fmt(m.gap)} vs expected</small>`:''}</td></tr>`;
  }).join('')}</tbody></table></div></div>` : empty('No live example programs in this view.')}</section>
  <section id="buyer-health"><h2>Buyer health <span>Delivery coverage, not a financial score</span></h2><div class="ops-buyers">${buyers.map(b=>`<article class="ops-buyer"><h3>${esc(b.buyer)}</h3><p>${b.live} live example programs</p><dl><div><dt>Received ${b.actual===null?'· incomplete':''}</dt><dd>${fmt(b.actual)}</dd></div><div><dt>Expected to date ${b.expected===null?'· incomplete':''}</dt><dd>${fmt(b.expected)}</dd></div></dl><p class="ops-help">Known subtotals: ${fmt(b.knownActual)} received / ${fmt(b.knownExpected)} expected. Each program uses its own target period.</p><div class="ops-coverage">Volume coverage ${b.dataCoverage}/${b.live} · Commitment coverage ${b.targetCoverage}/${b.live}</div></article>`).join('') || empty('No example buyers in this view.')}</div></section>
  <section id="prospects"><h2>Prospects <span>Not a launch commitment; excluded from live totals</span></h2>${prospects.map(p=>`<article class="ops-prospect"><div><b>${esc(p.tort)}</b><p>${esc(p.buyer)} · ${esc(p.platform)}</p></div><span>Go-live: Not set</span><span>Target: Not set</span><p>${esc(p.next_action)}</p></article>`).join('') || empty('No example prospects in this view.')}</section>
  <section id="needs-attention"><h2>Needs Attention <span>Example issues · owner · next action</span></h2><div class="ops-attention">${attention.map(a=>`<article><div>${badge(a.title,'amber')}<b>${esc(a.p.tort)} · ${esc(a.p.buyer)} · ${esc(a.p.platform)}</b></div><p>${esc(a.reason)}</p><p><strong>Next:</strong> ${esc(a.p.next_action)}</p><small>Owner: ${esc(a.owner)} · Example status: Open</small></article>`).join('') || empty('No example issues in this filtered view.')}</div></section>`;
}
async function loadDemo() {
  try {
    const response=await fetch('operations-demo.json',{cache:'no-store'});
    if (!response.ok) throw Error('Example fixture unavailable');
    const data=OpsModel.validateDemo(await response.json());
    const content=document.getElementById('ops-content');
    content.innerHTML=`<div class="ops-scenario"><span>${esc(data.clock_label)}</span><b>Read-only design preview</b></div>
      <div class="ops-priorities"><article id="lawsuit-priorities"><h2>Lawsuit priorities</h2><p class="ops-help">As of September 12 · Andrew’s context for this demo</p><ol><li>SMA — BP and Parker equally important; Pulaski lower priority.</li><li>WDC — Parker budget.</li><li>IL JDC — BP budget.</li><li>Chlorpyrifos — BP.</li><li>Rideshare — BP.</li></ol><small>Priority ranking only—not live spend, volume or launch status.</small></article><article><h2>Planning ownership</h2><p><b>Andrew</b> owns launch dates, buyer commitments and marketing forecasts for now.</p><p>Separate promises from expectations. All numbers shown here are examples, not approved targets.</p><small>No editing, publishing or notification actions in this preview.</small></article></div>
      <div id="ops-results" aria-live="polite"></div>`;
    renderResults(data); content.hidden=false; document.getElementById('ops-state').hidden=true;
  } catch (error) {
    document.getElementById('ops-state').textContent='Example scenario unavailable. No live data has been substituted. Reload to retry.';
    document.getElementById('ops-content').hidden=true;
  }
}
loadDemo();

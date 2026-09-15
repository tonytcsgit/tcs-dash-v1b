/* Pure calculations for synthetic Operations scenarios. No source connections. */
(function(root) {
  'use strict';
  const day = value => Date.parse(value + 'T00:00:00Z') / 86400000;
  const number = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
  function metrics(p, asOf) {
    const days = day(p.window_end) - day(p.window_start) + 1;
    const elapsed = Math.max(0, Math.min(days, day(asOf) - day(p.window_start) + 1));
    const rows = (p.daily || []).filter(r => r.date >= p.window_start && r.date <= p.window_end && r.date <= asOf);
    const datesValid = Number.isFinite(days) && days > 0;
    const live = p.phase === 'live' && p.go_live && p.go_live <= asOf;
    const sum = field => live && p.data_status === 'fresh' && rows.every(r => number(r[field]))
      ? rows.reduce((n,r) => n + r[field],0) : null;
    const actual = sum('received');
    const pace = target => datesValid && number(target) ? target * elapsed / days : null;
    const expected = pace(p.commitment), forecastExpected = pace(p.forecast);
    const submitted = sum('submitted');
    const status = p.phase === 'prospect' ? 'Prospect' : !live ? 'Not live'
      : actual === null ? 'Data unavailable' : expected === null ? 'No target'
      : actual < expected ? 'Behind' : 'On track';
    return {actual, expected, forecastExpected,
      gap:actual !== null && expected !== null ? actual-expected : null, status,
      submitted, accepted:sum('accepted'), deliveryGap:submitted !== null && actual !== null ? submitted-actual : null};
  }
  function buyerRollup(programs, asOf) {
    return [...new Set(programs.map(p => p.buyer))].sort().map(buyer => {
      const rows = programs.filter(p => p.buyer === buyer && p.phase === 'live' && p.go_live <= asOf).map(p => metrics(p,asOf));
      const dataCoverage = rows.filter(r => r.actual !== null).length;
      const targetCoverage = rows.filter(r => r.expected !== null).length;
      const knownActual = rows.reduce((n,r) => n + (r.actual ?? 0),0);
      const knownExpected = rows.reduce((n,r) => n + (r.expected ?? 0),0);
      return {buyer,live:rows.length,dataCoverage,targetCoverage,knownActual,knownExpected,
        actual:rows.length && dataCoverage === rows.length ? knownActual : null,
        expected:rows.length && targetCoverage === rows.length ? knownExpected : null};
    });
  }
  function validateDemo(data) {
    const dateOK = x => typeof x === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(x) && Number.isFinite(day(x)) && new Date(x+'T00:00:00Z').toISOString().slice(0,10) === x;
    if (!data || data.demo !== true || !dateOK(data.as_of) || !Array.isArray(data.programs)) throw Error('Synthetic fixture required');
    const ids = new Set();
    for (const p of data.programs) {
      if (!p || p.example !== true || typeof p.id !== 'string' || ids.has(p.id) ||
          !p.buyer?.startsWith('Example ') || !p.tort?.startsWith('Example ') ||
          !['live','scheduled','prospect'].includes(p.phase) || !['Meta','YouTube'].includes(p.platform) ||
          !['fresh','unavailable','not_connected'].includes(p.data_status) ||
          ![p.commitment,p.forecast].every(n => n === null || (number(n) && Number.isInteger(n))) ||
          ![p.go_live,p.window_start,p.window_end].every(d => d === null || dateOK(d)) ||
          (p.window_start && p.window_end && p.window_start > p.window_end) || !Array.isArray(p.daily)) throw Error('Invalid synthetic program');
      ids.add(p.id);
      const days = new Set();
      for (const r of p.daily) {
        if (!dateOK(r.date) || days.has(r.date) || !['received','submitted','accepted'].every(k => r[k] === null || (number(r[k]) && Number.isInteger(r[k])))) throw Error('Invalid synthetic daily observation');
        days.add(r.date);
      }
    }
    return data;
  }
  const api = {metrics,buyerRollup,validateDemo};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.OpsModel = api;
})(typeof window !== 'undefined' ? window : globalThis);

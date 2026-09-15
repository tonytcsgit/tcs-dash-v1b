const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const file = './operations-model.js';
test('Buyer rollup excludes prospects and never presents incomplete volume or targets as complete', () => {
  const m = require(file); assert.equal(typeof m.buyerRollup,'function');
  const rows = [{...base,buyer:'Example North',daily:[{date:'2026-09-16',received:80,submitted:100,accepted:60}]}, {...base,buyer:'Example North',data_status:'unavailable',commitment:null}, {...base,buyer:'Example North',phase:'prospect'}];
  const result = m.buyerRollup(rows,'2026-09-16')[0];
  assert.equal(result.live,2); assert.equal(result.actual,null); assert.equal(result.knownActual,80);
  assert.equal(result.expected,null); assert.equal(result.knownExpected,300);
  assert.equal(result.dataCoverage,1); assert.equal(result.targetCoverage,1);
});
test('Only explicitly synthetic data can render in Operations demo', () => {
  const m = require(file); assert.equal(typeof m.validateDemo,'function');
  assert.throws(() => m.validateDemo({demo:false,programs:[]}));
  assert.throws(() => m.validateDemo({demo:true,as_of:'2026-09-16',programs:[{...base,id:'x',example:false}]}));
});
const base = {phase:'live', go_live:'2026-09-14', window_start:'2026-09-14', window_end:'2026-09-20', commitment:700, forecast:840, data_status:'fresh', daily:[]};
test('Missing data is unknown, missing target is not zero, and future launches are not behind', () => {
  assert.ok(fs.existsSync(file)); const m = require(file);
  const unknown = m.metrics({...base,data_status:'unavailable'},'2026-09-16');
  assert.equal(unknown.actual,null); assert.equal(unknown.gap,null); assert.equal(unknown.status,'Data unavailable');
  const noTarget = m.metrics({...base,commitment:null,forecast:null},'2026-09-16');
  assert.equal(noTarget.expected,null); assert.equal(noTarget.forecastExpected,null); assert.equal(noTarget.status,'No target');
  const future = m.metrics({...base,phase:'scheduled',go_live:'2026-09-18',window_start:'2026-09-18',window_end:'2026-09-24'},'2026-09-16');
  assert.equal(future.actual,null); assert.equal(future.status,'Not live');
  const prospect = m.metrics({...base,phase:'prospect',window_start:null,window_end:null,commitment:null},'2026-09-16');
  assert.equal(prospect.expected,null); assert.equal(prospect.status,'Prospect');
  assert.equal(m.metrics(base,'2026-09-16').actual,0);
  assert.equal(m.metrics(base,'2026-10-01').expected,700);
});
test('Operations metrics keep buyer commitment and forecast separate and calculate calendar-day pacing', () => {
  assert.ok(fs.existsSync(file), 'Operations model has not been implemented');
  const m = require(file);
  const p = {phase:'live', go_live:'2026-09-14', window_start:'2026-09-14', window_end:'2026-09-20', commitment:700, forecast:840, data_status:'fresh', daily:[{date:'2026-09-14',received:40,submitted:50,accepted:35},{date:'2026-09-15',received:60,submitted:75,accepted:50},{date:'2026-09-16',received:80,submitted:100,accepted:65}]};
  const result = m.metrics(p,'2026-09-16');
  assert.equal(result.actual,180); assert.equal(result.expected,300);
  assert.equal(result.forecastExpected,360); assert.equal(result.gap,-120);
  assert.equal(result.status,'Behind'); assert.equal(result.deliveryGap,45);
});

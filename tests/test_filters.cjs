const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

test('date changes reload, source calendar dates match, and refresh preserves applied period/page', async () => {
  const nodes = new Map();
  function node() { return { value: '', dataset: { reportTimezone: 'UTC' }, classList: { toggle() {}, contains() { return false; } }, handlers: {}, addEventListener(k, fn) { this.handlers[k] = fn; }, setAttribute() {}, append() {}, replaceChildren() {}, add() {}, reportValidity() { return true; } }; }
  const get = id => { if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id); };
  const calls = [];
  let interval;
  let failing = false;
  let description = 'Initial work';
  const context = vm.createContext({
    document: { getElementById: get, body: node(), createElement: node, addEventListener() {}, visibilityState: 'visible' },
    window: { addEventListener() {} }, localStorage: { getItem() { return null; } },
    Intl, Date, URLSearchParams, AbortController, console,
    FormData: class { constructor() { return ['start', 'end', 'area_kerja', 'unit_area', 'status', 'pic'].map(id => [id, get(id).value]); } },
    Option: class {}, setTimeout() {}, clearTimeout() {}, clearInterval() {}, setInterval(fn) { interval = fn; return 1; },
    fetch: async url => { calls.push(url); if (failing) throw new Error('Network unavailable'); return { status: 200, ok: true, headers: { get() { return 'application/json'; } }, json: async () => ({ rows: Array.from({ length: 25 }, () => ({ tanggal: '2026-09-05T18:30:00Z', pic: '', status: 'Selesai', pekerjaan: description })), options: { area_kerja: [], unit_area: [], status: [], pic: [] } }) }; }
  });
  vm.runInContext(fs.readFileSync('static/app.js', 'utf8'), context);
  const settle = () => new Promise(resolve => setImmediate(resolve));
  await settle();
  get('start').value = '2026-09-02'; get('end').value = '2026-09-07';
  get('end').handlers.change(); await settle();
  assert.match(calls.at(-1), /start=2026-09-02&end=2026-09-07/);
  assert.equal(vm.runInContext("dateLabel('2026-09-07T17:00:57.314330+00:00')", context), '2026-09-07 17:00:57');
  assert.equal(vm.runInContext("dateLabel('2026-09-08T00:00:57+07:00')", context), '2026-09-07 17:00:57');
  assert.equal(vm.runInContext("dateLabel('2026-09-07 17:00:57')", context), '2026-09-07 17:00:57');
  assert.equal(vm.runInContext("dateLabel('2026-09-08T00:00:00Z')", context), '2026-09-08 00:00:00');
  assert.equal(vm.runInContext('state.controller', context), null);
  vm.runInContext('state.page = 2', context);
  get('end').value = '2026-09-08';
  interval(); await settle();
  assert.match(calls.at(-1), /end=2026-09-07/);
  assert.equal(vm.runInContext('state.page', context), 2);
  vm.runInContext('setPresentation(true)', context);
  assert.notEqual(vm.runInContext('state.autoRefreshInterval', context), null);
  description = 'Updated work';
  interval(); await settle();
  assert.equal(vm.runInContext('state.rows[0].pekerjaan', context), 'Updated work');
  assert.equal(vm.runInContext('state.page', context), 2);
  failing = true;
  interval(); await settle();
  assert.equal(vm.runInContext('state.rows.length', context), 25);
  assert.notEqual(vm.runInContext('state.autoRefreshInterval', context), null);
  failing = false;
  description = 'Recovered work';
  interval(); await settle();
  assert.equal(vm.runInContext('state.rows[0].pekerjaan', context), 'Recovered work');
  assert.equal(get('notice').hidden, true);
});

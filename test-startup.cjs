const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, 'app.js'), 'utf8');

function startupHarness() {
  const timers = new Map();
  const warning = { hidden: true };
  const request = {};
  const read = {};
  const connection = {
    closed: 0,
    close() { this.closed++; },
    transaction() { return { objectStore: () => ({ get: () => read }) }; }
  };
  const context = vm.createContext({
    state: { schema: 1, original: true }, db: null, memoryOnly: false,
    indexedDB: { open: () => request }, M: { tick: () => false },
    $: () => warning, rendered: 0,
    render() { context.rendered++; },
    setTimeout(fn) { const id = timers.size + 1; timers.set(id, fn); return id; },
    clearTimeout: id => timers.delete(id), setInterval() {}
  });
  vm.runInContext(source.slice(source.indexOf('  function storageWarning()'), source.indexOf("  document.addEventListener('click'")), context);
  return { context, request, read, connection, warning, timers,
    open() { request.result = connection; request.onsuccess(); },
    timeout() { for (const fn of [...timers.values()]) fn(); }
  };
}

async function checkStartup() {
  let h = startupHarness();
  let started = h.context.init();
  assert.ok(h.timers.size, 'Startup needs a deadline when IndexedDB never responds');
  h.timeout();
  await started;
  assert.equal(h.context.rendered, 1);
  assert.equal(h.warning.hidden, false);
  h.open();
  assert.equal(h.connection.closed, 1);
  assert.equal(h.context.db, null, 'Late connection must not overwrite stored projects');

  h = startupHarness();
  started = h.context.init();
  h.open();
  await Promise.resolve();
  h.timeout();
  await started;
  h.read.result = { schema: 1, restored: true };
  h.read.onsuccess();
  assert.equal(h.context.state.original, true, 'Late read must not replace active state');
  assert.equal(h.connection.closed, 1);
  assert.equal(h.context.db, null);

  h = startupHarness();
  started = h.context.init();
  h.open();
  await Promise.resolve();
  const saved = { schema: 1, projects: [{ id: 'existing-project' }] };
  h.read.result = saved;
  h.read.onsuccess();
  await started;
  assert.equal(h.context.state, saved);
  assert.equal(h.context.db, h.connection);
  assert.equal(h.warning.hidden, true);
  assert.equal(h.context.rendered, 1);
  assert.equal(h.timers.size, 0);
}

async function checkPortraits() {
  const scripts = [];
  let failImage = false;
  const context = vm.createContext({
    window: {}, portraitBundle: null, imagePromises: new Map(),
    document: { createElement: () => ({ remove() {} }), head: { appendChild: script => scripts.push(script) } },
    Image: class { set src(value) { this.url = value; failImage ? this.onerror() : this.onload(); } }
  });
  vm.runInContext(source.slice(source.indexOf('  function portraitAssets()'), source.indexOf('  async function sampleSource(')), context);
  assert.equal(scripts.length, 0, 'Portrait bundle must stay off startup path');
  const first = context.imageFor('studio');
  const second = context.imageFor('home');
  assert.equal(scripts.length, 1, 'Concurrent requests share one bundle');
  scripts[0].onerror();
  const failures = await Promise.allSettled([first, second]);
  assert.ok(failures.every(result => result.status === 'rejected'));
  assert.equal(context.imagePromises.size, 0);
  const retry = context.imageFor('studio');
  assert.equal(scripts.length, 2, 'Failed loads must be retryable');
  context.window.PortraitAssets = { studio: 'studio-image', home: 'home-image' };
  scripts[1].onload();
  assert.equal((await retry).url, 'studio-image');
  failImage = true;
  await assert.rejects(context.imageFor('home'));
  failImage = false;
  assert.equal((await context.imageFor('home')).url, 'home-image');
}

(async () => {
  await checkStartup();
  await checkPortraits();
  console.log('Passed: startup deadline, saved-state restoration, late-callback safety, lazy portraits and load retries.');
})().catch(error => { console.error(error); process.exitCode = 1; });

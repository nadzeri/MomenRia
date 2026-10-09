const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const M = require('./model.js');
const elements = Object.fromEntries(['#main', '#header', '#app-nav', '#dialog', '#storage-warning', '#toast'].map(id => [id, {
  innerHTML: '', textContent: '', hidden: true, open: false, scrollTop: 0,
  focus() {}, addEventListener() {}, showModal() { this.open = true; }, close() { this.open = false; }
}]));
const location = { hash: '' };
const context = vm.createContext({
  window: { Momenria: M, addEventListener() {} }, location,
  history: { replaceState(_state, _title, hash) { location.hash = hash; } },
  document: { querySelector: selector => elements[selector] || null, querySelectorAll: () => [], addEventListener() {}, activeElement: { focus() {} } },
  requestAnimationFrame: callback => callback(), setTimeout: () => 1, clearTimeout() {}, setInterval() {}
});
const source = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
vm.runInContext(source.replace('  init();', '  globalThis.studioTest={homeView,render,openStudioFace,handleAction,get state(){return state;}};'), context);
const app = context.studioTest;
const action = (name, data = {}) => app.handleAction({ dataset: { action: name, ...data } });

(async () => {
  app.render();
  assert.equal(app.state.projects.length, 0, 'Opening the studio must not create a project');
  assert.match(elements['#main'].innerHTML, /studio-controls/);
  assert.match(elements['#main'].innerHTML, /studio-preview/);
  assert.equal((elements['#main'].innerHTML.match(/class="upload-tile /g) || []).length, 4);
  assert.doesNotMatch(elements['#main'].innerHTML, /class="hero"|price-section|process-section/);
  assert.match(elements['#app-nav'].innerHTML, /Foto saya/);
  await action('studio-template', { template: 'lebaran' });
  assert.equal(app.state.projects.length, 0, 'Browsing templates must not create drafts');
  assert.equal((elements['#main'].innerHTML.match(/class="upload-tile /g) || []).length, 2);
  app.openStudioFace(null, 0);
  const p = app.state.projects[0];
  assert.equal(p.templateId, 'lebaran');
  assert.equal(location.hash, '#/editor/' + p.id);
  assert.match(elements['#dialog'].innerHTML, /Gunakan akun contoh/);
  app.openStudioFace(null, 1);
  assert.equal(app.state.projects.length, 1, 'Repeated clicks must reuse the draft');
  const reference = { id: 'face-one', src: 'data:image/png;base64,example', consentAt: Date.now(), expiresAt: Date.now() + M.DAY };
  M.assign(app.state, p, 0, reference);
  await action('studio-template', { project: p.id, template: 'home' });
  assert.equal(p.templateId, 'lebaran', 'Template change needs confirmation');
  assert.equal(p.assignments[0], reference.id);
  await action('replace-template', { project: p.id, template: 'home' });
  assert.equal(p.templateId, 'home');
  assert.equal(p.assignments.length, 3);
  assert.equal(p.sources[0].id, reference.id, 'Template change must retain uploaded sources');
  location.hash = '#/';
  app.render();
  assert.equal(app.state.projects.length, 1);
  assert.match(elements['#main'].innerHTML, /3\/3|0\/3/);
  for (const route of ['how', 'pricing', 'projects', 'orders', 'support', 'privacy', 'operator']) {
    location.hash = '#/' + route;
    app.render();
    assert.doesNotMatch(elements['#main'].innerHTML, /Momen ini belum tersedia|Halaman tidak tersedia/);
    assert.ok(elements['#main'].innerHTML.length > 100);
  }
  console.log('Passed: studio entry, template browsing, lazy draft creation, draft reuse, confirmed replacement, source retention and supporting routes.');
})().catch(error => { console.error(error); process.exitCode = 1; });

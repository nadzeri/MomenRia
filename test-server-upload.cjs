const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, 'static/app/server.js'), 'utf8');
const requests = [];
const project = {id:'project-1', revision:1};

class TestFormData {
  constructor(form) { this.values = new Map(Object.entries(form.fields)); }
  set(key, value) { this.values.set(key, value); }
  delete(key) { this.values.delete(key); }
  keys() { return this.values.keys(); }
}

const context = vm.createContext({
  FormData: TestFormData,
  crypto: {randomUUID: () => 'upload-1'},
  selected: () => ({id:'template-1'}),
  ensureProject: async () => project,
  api: async (url, options) => {
    requests.push({url, options});
    return requests.length === 1 ? {id:'source-1'} : project;
  },
  state: {projects:[project]},
  route: () => '/studio/template-1',
  studioPath: () => '/studio/template-1/project-1',
  history: {replaceState() {}},
  closeDialog() {}, render() {}, toast() {},
});

vm.runInContext(source.slice(source.indexOf('  async function handleUpload'), source.indexOf('  async function generate')), context);

(async () => {
  await context.handleUpload({fields:{image:'photo', consent:'on'}, dataset:{slot:'slot-1'}});
  assert.deepEqual([...requests[0].options.body.keys()].sort(), ['consent_granted', 'consent_version', 'image', 'upload_key']);
  console.log('Passed: upload multipart payload contains only API-approved fields.');
})().catch(error => { console.error(error); process.exitCode = 1; });

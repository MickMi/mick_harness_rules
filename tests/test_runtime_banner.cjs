const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(`${__dirname}/../web/observe-dashboard.html`, 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new Function(script);
const source = script.slice(script.indexOf('      function renderRuntimeBar()'), script.indexOf('      function wait('));
const el = (tag, cls, text) => ({tag, cls, text, children: [], dataset: {},
  append(...items) { this.children.push(...items); }, replaceChildren(...items) { this.children = items; }});
const bar = el('section');
const runtime = {environment:'development', read_only:true, version:'0.25.0', branch:'feat/v0.25',
  commit:'abc12345678', dirty:true, started_at:'2026-09-17T04:00:00Z', source_path:'/fixture/harness',
  production_url:'http://127.0.0.1:6425/', development_url:'http://127.0.0.1:6426/'};
const context = vm.createContext({runtime, el, document:{getElementById: () => bar}});
vm.runInContext(source, context);
context.renderRuntimeBar();
assert.equal(bar.hidden, false);
assert.equal(context.document.title, '开发验收 6426 · Mick Harness');
assert.equal(bar.dataset.environment, 'development');
assert.equal(bar.children[0].text, '开发验收 · 只读');
assert.equal(bar.children[3].href, runtime.production_url);
assert.match(bar.children[4].children[0].text, /feat\/v0.25 · abc1234 · 含未提交修改/);
assert.match(bar.children[4].children[1].text, /2026-09-17/);
runtime.environment = 'production'; runtime.read_only = false; runtime.dirty = false;
context.renderRuntimeBar();
assert.equal(bar.children[0].text, '正式工作台');
assert.equal(bar.children[3].href, runtime.development_url);
assert.doesNotMatch(bar.children[4].children[0].text, /未提交/);
console.log('PASS: runtime identity, read-only message, environment links and draft status');

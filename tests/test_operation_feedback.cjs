// Focused UI contract checks; no server, installs, or user data writes.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(`${__dirname}/../web/observe-dashboard.html`, 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new Function(script);
const section = script.slice(script.indexOf('      function operationStatusLabel'), script.indexOf('      async function showOperationResult'));
const node = (tag, cls, text) => ({tag, cls, text, children: [], dataset: {},
  append(...items) { this.children.push(...items); }, setAttribute() {}, addEventListener(name, fn) { this[name] = fn; }});
const state = { operations: {items: []}, operationMessages: {}, notice: null };
let response;
let inspected;
let scheduled;
const context = vm.createContext({state, el: node, formattedTime: x => x,
  showOperationResult: x => { inspected = x; }, render() {}, brainDialog: async () => true,
  setTimeout(fn) { scheduled = fn; return 1; }, clearTimeout() {},
  fetchJson: async () => { if (response instanceof Error) throw response; return response; }});
vm.runInContext(`let operationPollTimer = null; ${section}`, context);
const update = { action: 'harness-update', label: '更新 Harness', operation_id: 'new', status: 'failed',
  created_at: '2026-09-10', summary: 'error: cannot pull with rebase: You have unstaged changes.' };
assert.equal(context.operationOutcome(update).title, '更新未完成');
assert.match(context.operationOutcome(update).message, /本地改动/);
assert.doesNotMatch(context.operationOutcome(update).message, /rebase/);
assert.equal(context.operationOutcome({...update, status:'succeeded'}).title, '已完成');
assert.equal(context.operationOutcome({...update, status:'running'}).title, '正在执行');
assert.equal(context.operationOutcome({...update, status:'cancelled'}).title, '已取消');
assert.equal(context.operationOutcome({...update, status:'blocked',can_execute:false}).title, '预检未通过');
assert.match(context.operationOutcome({...update, status:'blocked',can_execute:false}).message, /尚未执行/);
state.operations.items = [{...update, created_at:'2026-09-01', operation_id:'zzz'}, update];
assert.equal(context.latestOperation('harness-update').operation_id, 'new');
const feedback = context.renderOperationFeedback('harness-update');
const title = box => box.children[0].children[1].text;
assert.equal(title(feedback), '更新未完成');
feedback.children[0].children.at(-1).children[0].click();
assert.equal(inspected.operation_id, 'new');
(async () => {
  response = {active: {...update, status:'running'}, items: []};
  await context.refreshOperations();
  assert.equal(typeof scheduled, 'function');
  response = new Error('offline');
  await scheduled();
  assert.match(state.operationReadError, /暂时无法读取/);
  assert.equal(title(context.renderOperationFeedback('harness-update')), '最新状态未确认');
  response = {active:null, items:[{...update, status:'succeeded'}]};
  await context.refreshOperations();
  assert.equal(state.operationReadError, null);
  assert.equal(title(context.renderOperationFeedback('harness-update')), '已完成');
  assert.equal(state.notice, null);
  // A fresh page consumes persisted operation records, not an ephemeral toast.
  state.operations = JSON.parse(JSON.stringify(response));
  assert.equal(title(context.renderOperationFeedback('harness-update')), '已完成');
  const seen = [];
  context.render = () => {
    const bar = context.renderOperationFeedback('harness-update');
    if (bar) seen.push({id:bar.id, title:title(bar)});
  };
  context.postOperation = async url => {
    if (url.endsWith('/preview')) return {...update, can_execute:true, status:'prepared', confirmation_token:'fixture'};
    if (url.endsWith('/execute')) return {...update, status:'queued'};
    throw new Error('unexpected write');
  };
  response = {active:{...update, status:'running'}, items:[]};
  await context.startHarnessOperation({action:'harness-update', label:'更新 Harness'});
  assert.ok(seen.some(x=>x.title==='正在准备'));
  assert.ok(seen.some(x=>x.title==='等待执行'));
  assert.ok(seen.some(x=>x.title==='正在执行'));
  response = {active:null, items:[update]};
  await scheduled();
  assert.equal(seen.at(-1).title, '更新未完成');
  assert.equal(new Set(seen.map(x=>x.id)).size, 1);
  response = {active:null, items:[{...update,status:'succeeded'}]};
  await context.refreshOperations();
  context.render();
  assert.equal(seen.at(-1).title, '已完成');
  assert.equal(seen.at(-1).id, 'current-operation-status');
  assert.doesNotMatch(script, /card\.append\(feedback\)/);
  const start = script.slice(script.indexOf('      async function startHarnessOperation'), script.indexOf('      async function showOperationResult'));
  assert.doesNotMatch(start, /state\.notice\s*=/);
  assert.match(start, /state\.operationSubmitting/);
  console.log('PASS: syntax, local feedback, success/failure/cancel/running, latest record, details, disconnect/reconnect, refresh persistence, no global error toast');
})().catch(error => { console.error(error); process.exitCode = 1; });

// Focused UI contract checks; no server, installs, or user data writes.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(`${__dirname}/../web/observe-dashboard.html`, 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new Function(script);
const section = script.slice(script.indexOf('      function operationStatusLabel'), script.indexOf('      async function showOperationResult'));
const node = (tag, cls, text) => ({tag, cls, text, children: [], dataset: {}, style: {}, attributes: {},
  get childElementCount() { return this.children.length; },
  append(...items) { this.children.push(...items); }, prepend(...items) { this.children.unshift(...items); },
  replaceChildren(...items) { this.children = items; },
  setAttribute(name, value) { this.attributes[name] = value; }, addEventListener(name, fn) { this[name] = fn; }});
const state = { operations: {items: []}, operationMessages: {}, notice: null };
let response;
let inspected;
let scheduled;
let delay;
const document = { hidden: false, getElementById: () => null, querySelectorAll: () => [] };
const context = vm.createContext({state, el: node, formattedTime: x => x,
  document, AbortSignal,
  showOperationResult: x => { inspected = x; }, render() {}, brainDialog: async () => true,
  setTimeout(fn, ms) { scheduled = fn; delay = ms; return 1; }, clearTimeout() {},
  fetchJson: async () => { if (response instanceof Error) throw response; return response; }});
vm.runInContext(`let operationPollTimer = null, operationRequest = null, operationFailures = 0, versionRequest = null, versionCheckedAt = 0; ${section}`, context);
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
  assert.equal(delay, 1000);
  response = new Error('offline');
  await scheduled();
  assert.match(state.operationReadError, /暂时无法读取/);
  assert.equal(title(context.renderOperationFeedback('harness-update')), '正在重新连接');
  assert.equal(delay, 1000);
  await scheduled();
  assert.equal(delay, 2000);
  response = {active:null, items:[{...update, status:'succeeded'}]};
  await scheduled(); // Recovery must be automatic, not a user refresh.
  assert.equal(state.operationReadError, null);
  assert.equal(title(context.renderOperationFeedback('harness-update')), '已完成');
  assert.equal(state.notice, null);
  assert.equal(delay, 10000); // Keep discovering operations started in another tab.
  document.hidden = true;
  await scheduled();
  assert.equal(delay, 60000);
  document.hidden = false;
  // A fresh page consumes persisted operation records, not an ephemeral toast.
  state.operations = JSON.parse(JSON.stringify(response));
  assert.equal(title(context.renderOperationFeedback('harness-update')), '已完成');
  const seen = [];
  context.render = () => {
    const bar = context.renderOperationFeedback('harness-update');
    if (bar) seen.push({id:bar.id, title:title(bar)});
  };
  context.paintOperationStatus = () => context.render();
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
  assert.doesNotMatch(section.slice(section.indexOf('function scheduleOperationRefresh'), section.indexOf('const harnessVersionLabels')), /postOperation|\brender\(\)/);
  assert.match(script, /visibilitychange/);
  let release;
  let reads = 0;
  context.fetchJson = () => { reads++; return new Promise(resolve => { release = resolve; }); };
  const first = context.refreshOperations();
  const second = context.refreshOperations();
  assert.equal(reads, 1, 'manual refresh must join the in-flight poll');
  release({active:null, items:[{...update,status:'succeeded'}]});
  await Promise.all([first, second]);
  const badge = node('button');
  badge.dataset.projectId = 'fixture';
  document.querySelectorAll = selector => selector === '.harness-version-badge' ? [badge] : [];
  context.fetchJson = async () => ({checked_at:'today', projects:{fixture:{version:'0.22.1',status:'synced'}}});
  await context.refreshHarnessVersions(true);
  assert.equal(badge.textContent, 'Harness v0.22.1 · 已同步');
  context.fetchJson = async () => { throw new Error('offline'); };
  await context.refreshHarnessVersions(true);
  assert.match(badge.textContent, /状态待重连确认/);
  assert.equal(badge.dataset.status, 'unknown');
  context.fetchJson = async () => ({checked_at:'later', projects:{fixture:{version:'0.22.1',status:'different'}}});
  await context.refreshHarnessVersions(true);
  assert.equal(badge.textContent, 'Harness v0.22.1 · 与本机版本不同');
  // A: maintenance stays available but does not displace project progress.
  Object.assign(context, {content:node('main'), OPERATION_FALLBACKS:[{action:'harness-update',label:'更新 Harness'}], roleLabel:x=>x, statusLabel:x=>x, compactText:x=>x});
  Object.assign(state, {operations:{items:[{...update,status:'succeeded'}]}, operationMessages:{}, operationReadError:null, operationFocus:null, workbenchManagementOpen:false,
    portfolio:{projects:[{project_id:'fixture',name:'Fixture',validation:'valid',summary:{verification_pending:9}}],summary:{}}});
  vm.runInContext(script.slice(script.indexOf('      function renderPortfolio()'), script.indexOf('      function renderHeader(')), context);
  const walk = root => [root,...root.children.flatMap(walk)];
  context.renderPortfolio();
  let elements = walk(context.content);
  const panel = elements.find(x=>x.id==='workbench-management');
  const manage = elements.find(x=>x.cls==='workbench-manage');
  assert.equal(panel.hidden,true);
  manage.click(); assert.equal(panel.hidden,false);
  assert.equal(manage.attributes['aria-expanded'],'true');
  manage.click(); assert.equal(panel.hidden,true);
  assert.equal(elements.find(x=>x.id==='operation-status-retry').hidden,true);
  assert.equal(elements.find(x=>x.cls==='workbench-priority'),undefined,'QA work is not automatically a human todo');
  assert.equal(elements.find(x=>x.id==='current-operation-status').children.length,1,'success has no duplicate paragraph');
  assert.equal(elements.find(x=>x.cls==='workbench-more').tag,'details');
  state.operationReadError='offline';
  state.portfolio.projects[0].execution={needs_user_decision:true};
  context.renderPortfolio(); elements=walk(context.content);
  assert.equal(elements.find(x=>x.id==='operation-status-retry').hidden,false);
  assert.ok(elements.some(x=>x.text==='Fixture · 待你确认 →'));
  assert.ok(elements.find(x=>x.id==='operation-live-status').children.length,'connection feedback remains outside closed management');
  // Project overview: goals stay above work, not below diagnostics and empty panels.
  Object.assign(context, {activeBlocksFor:()=>[], writeUrlState(){}, requirementOfficeRoleOrder:[],
    renderRequirementSquad:()=>node('span'), requirementRoleStatus:()=> 'idle'});
  document.createTextNode = text=>node('text','',text);
  vm.runInContext(script.slice(script.indexOf('      function renderOverview('), script.indexOf('      function resolveArtifactLink(')), context);
  state.snapshot={approvals:{}}; state.taskId=null; state.selectedRole=null;
  state.project={path:'/fixture'};
  state.workspace={project:{goal:'长期服务目标',source:'docs/PROJECT.md'}, identity:{relationship:'direct'}, activity:{has_unstructured_progress:true,git_commit_count:75}};
  let overview=node('main'); context.renderOverview(overview);
  assert.equal(overview.children[0].cls,'project-purpose');
  assert.equal(overview.children[1].cls,'project-overview-hero');
  assert.equal(overview.children.at(-1).tag,'details');
  assert.ok(!overview.children.at(-1).open,'diagnostics start collapsed');
  assert.ok(!walk(overview).some(x=>x.cls==='overview-progress'),'no zero progress panel for unplanned project');
  assert.ok(!walk(overview).some(x=>x.cls==='current-version-requirements'),'no duplicate empty requirements panel');
  const req={requirement_id:'task-1',title:'紧凑需求',effective_status:'in_progress',current_role:'Executor',next_step:'检查预览',test:{scope:'核心路径'}};
  state.workspace.current_version={version:'1.0.0',goal:'本轮目标',requirements:[req],total:1,counts:{in_progress:1}};
  state.workspace.execution={recorded:true,needs_user_decision:true};
  state.taskId='task-1'; // Backend's preferred task is not an explicit request to expand.
  overview=node('main'); context.renderOverview(overview);
  assert.ok(walk(overview).some(x=>x.text==='当前执行等待你的决策。'));
  assert.ok(!walk(overview).some(x=>x.cls==='task-office'),'overview does not auto-expand a large office');
  const summary=walk(overview).find(x=>x.cls==='requirement-summary-button');
  summary.click();
  overview=node('main'); context.renderOverview(overview);
  assert.equal(walk(overview).find(x=>x.cls==='requirement-summary-button').attributes['aria-expanded'],'true');
  assert.ok(walk(overview).some(x=>x.cls==='task-office'));
  assert.ok(walk(overview).some(x=>x.cls==='requirement-test-scope'));
  walk(overview).find(x=>x.cls==='requirement-summary-button').click();
  overview=node('main'); context.renderOverview(overview);
  assert.ok(!walk(overview).some(x=>x.cls==='task-office'),'click again collapses task details');
  console.log('PASS: operation feedback/polling, workbench disclosure, project goal ordering, empty plan, decision visibility, task expand/collapse');
})().catch(error => { console.error(error); process.exitCode = 1; });

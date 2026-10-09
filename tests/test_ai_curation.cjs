// Focused UI state/consent tests; no external calls, keys or browser storage.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(`${__dirname}/../web/observe-dashboard.html`, 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new Function(script);
const source = script.slice(script.indexOf('      function aiButton('), script.indexOf('      function renderSettings()'));
function node(tag, cls, text) {
  return {tag, cls, text, children: [], attributes: {}, dataset:{}, style:{}, value: '',
    getBoundingClientRect() {return {left:1000,right:1028,top:600,bottom:628,height:140};},
    get options() { return this.children; },
    append(...items) { this.children.push(...items); },
    replaceChildren(...items) { this.children = items; },
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener(name, fn) { this[name] = fn; }};
}
function all(root) { return [root, ...root.children.flatMap(all)]; }
function visible(root) { return root.hidden ? [] : [root, ...(root.tag==='details'&&!root.open ? root.children.filter(n=>n.tag==='summary') : root.children).flatMap(visible)]; }
const content = node('main');
const state = {view:'settings', focus:'ai', aiMessage:'', aiProject:'', aiPreview:null,
  ai:{config:{base_url:'https://api.deepseek.com', model:'deepseek-flash', daily_requests:20, has_key:true},
      sandbox:true, projects:[], runs:[], queue:[], calls_today:0, action_token:'fixture'}};
let scheduled, delay, response, posts = 0;
const windowEvents={};
const context = vm.createContext({state, content, el:node, formattedTime:x=>x,
  window:{innerWidth:1100,innerHeight:800,addEventListener(name,fn){windowEvents[name]=fn;}},
  renderSettingsTabs(){},
  document:{hidden:false, createTextNode:text=>node('#text','',text), getElementById:id=>all(content).find(n=>n.id===id)},
  setTimeout(fn, ms) {scheduled=fn;delay=ms;return 1;}, clearTimeout(){},
  fetchJson:async()=>response,
  fetch:async()=> { posts++; return {ok:true,json:async()=>({message:'accepted'})}; }});
vm.runInContext(`let aiPollTimer; ${source}`, context);
vm.runInContext(script.slice(script.indexOf('      function resolveArtifactLink('),script.indexOf('      async function loadArtifact(')),context);
context.renderAI();
assert.equal(all(content).find(n=>n.type==='password').value, '');
assert.ok(!all(content).some(n=>n.text?.includes('每批记录')));
assert.doesNotMatch(source,/batch_size/);
assert.match(html,/\.ai-page button\.ai-help-button \{[^}]*min-height: 28px;[^}]*border-radius: 50%/);
assert.match(context.aiConnectionLabel(), /未测试/);
assert.equal(delay, 12000);
assert.ok(visible(content).some(n=>n.text==='整理经验'));
assert.ok(visible(content).some(n=>n.text==='整理结果'));
assert.ok(!visible(content).some(n=>/UTC|tokens|brain\/projects|原始记录只读|未自动拆分/.test(n.text||'')));
const help=all(content).find(n=>n.cls==='ai-help'&&n.children[0].attributes['aria-label']==='整理经验说明');
const [helpButton,tip]=help.children;
assert.equal(tip.hidden,true);
assert.equal(helpButton.attributes['aria-describedby'],tip.id);
help.pointerenter(); assert.equal(tip.hidden,false); assert.equal(helpButton.attributes['aria-expanded'],'true');
assert.equal(tip.style.left,'764px'); // Clamped inside the right viewport edge.
help.pointerleave(); assert.equal(tip.hidden,true);
helpButton.focus(); assert.equal(tip.hidden,false);
helpButton.keydown({key:'Escape',preventDefault(){}}); assert.equal(tip.hidden,true);
helpButton.blur(); helpButton.click(); assert.equal(tip.hidden,false); // Touch/click opens and pins.
help.pointerleave(); assert.equal(tip.hidden,false);
helpButton.click(); assert.equal(tip.hidden,true);
help.pointerenter(); windowEvents.keydown({key:'Escape'}); assert.equal(tip.hidden,true);
help.pointerenter(); windowEvents.pointerdown({target:{closest:()=>null}}); assert.equal(tip.hidden,true);
context.window.innerWidth=390; help.pointerenter();
assert.equal(tip.style.width,'320px'); assert.equal(tip.style.left,'54px');
windowEvents.scroll({target:{closest:()=>null}}); assert.equal(tip.hidden,true); context.window.innerWidth=1100;
assert.equal(posts,0);
assert.match(html,/\.ai-report-section \{[^}]*border: 1px solid/);
assert.match(html,/\.ai-page button \{[^}]*white-space: nowrap/);
assert.match(html,/\.settings-page \.ai-page button:not\(\.settings-tab\) \{[^}]*white-space: nowrap/);
all(content).find(n=>n.text==='调整上限').click();
assert.equal(all(content).find(n=>n.tag==='details'&&n.children.some(c=>c.text==='AI 连接 · 已配置')).open,true);
const configInput = all(content).find(n=>n.type==='password');
configInput.value = 'not-a-real-secret';
state.aiPreview = {id:'preview',payload:Array.from({length:108},(_,i)=>({source_id:`id-${i}`,summary:'<script>not executed</script>'})),rule_context:{rules:[{ref_id:'K1',source:'个人准则',heading:'按钮',content:'按钮图文必须同排，不得堆叠。'}],coverage:'仅相关摘录，不是完整审计。'},destination:'https://api.deepseek.com',model:'deepseek-flash',input_characters:9000,max_output_tokens:16384,remaining:0};
const preview = node('div');
context.renderAIPreview(preview);
assert.ok(visible(preview).some(n=>n.text==='本次整理 108 条记录'));
assert.ok(visible(preview).some(n=>n.text?.includes('发送给 DeepSeek，可能产生费用')));
assert.ok(!visible(preview).some(n=>/tokens|https:\/\/|UTC/.test(n.text||'')));
const confirm = all(preview).find(n=>n.text==='确认并整理');
const consent = all(preview).find(n=>n.type==='checkbox');
assert.equal(confirm.disabled,true);
assert.ok(visible(preview).some(n=>n.text==='本次对照 1 条准则 · 查看发送内容'));
assert.ok(visible(preview).some(n=>n.text?.includes('记录与准则摘录')));
assert.match(all(preview).find(n=>n.tag==='pre').text,/rule_context/);
consent.checked=true;consent.change();
assert.equal(confirm.disabled,false);
assert.match(all(preview).find(n=>n.tag==='pre').text, /<script>/);
assert.equal(posts,0); // Rendering a preview cannot call the provider.
const group={id:'0',category:'harness_improvement',title:'布局遮挡',summary:'有证据但根因未确定',recommendation:'增加检查',evidence_ids:['id'],evidence:[{source_id:'id',task:'task-1',summary:'真实摘要'}]};
const run={id:'run-1',kind:'curate',source_count:1,status:'running',model:'deepseek-flash',created_at:'now',message:'正在归纳'};
(async()=>{
  response={...state.ai,runs:[run]};
  await context.refreshAI();
  assert.equal(delay,1500);
  assert.ok(all(content).some(n=>n.text?.includes('运行中')));
  assert.equal(all(content).find(n=>n.type==='password'),configInput);
  assert.equal(configInput.value,'not-a-real-secret');
  response={...state.ai,runs:[{...run,status:'succeeded',groups:[group],message:'已整理',usage:{total_tokens:40}}]};
  await scheduled();
  assert.equal(delay,12000);
  assert.ok(all(content).some(n=>n.text?.includes('已完成')));
  const submit=all(content).find(n=>n.text==='提交到开发改进队列');
  assert.equal(submit.disabled,false);
  response={...state.ai,queue:[{...group,run_id:'run-1'}]};
  await submit.click();
  assert.equal(posts,1);
  assert.ok(all(content).find(n=>n.text==='已提交 · 待审批').disabled);
  response={...state.ai,runs:[{...run,status:'failed',message:'网络失败'}]};
  await scheduled();
  assert.ok(all(content).some(n=>n.text?.includes('失败')));
  assert.equal(posts,1); // Status polling never retries a paid request.
  const testRun={...run,id:'test-1',kind:'test',message:'正在测试连接（不发送项目资料）'};
  context.fetch=async()=>({ok:true,json:async()=>testRun});
  response={...state.ai,runs:[testRun]};
  await context.aiAction('test');
  assert.match(state.aiMessage,/正在测试/);
  response={...state.ai,runs:[{...testRun,status:'failed',message:'HTTPS 证书校验失败，API Key 尚未验证'}]};
  await scheduled();
  assert.match(state.aiMessage,/证书/); // Top feedback must finish with the persisted task.
  assert.doesNotMatch(state.aiMessage,/正在测试/);
  response={...state.ai,runs:[{...testRun,status:'succeeded',message:'连接正常，模型已实际返回 OK。'}]};
  await scheduled();
  assert.match(state.aiMessage,/连接正常/);
  state.aiMessage=''; state.aiFeedbackRun=null;
  context.renderAI();
  assert.equal(state.aiMessage,''); // Old success stays in history, not a duplicate page-wide banner.
  assert.ok(visible(content).some(n=>n.text==='连接测试 · 已完成'));
  context.aiFeedback('预览已生成，尚未发送项目资料。');
  await context.refreshAI();
  assert.match(state.aiMessage,/预览已生成/); // Later local actions are not overwritten by old runs.
  let curationPosts=0;
  context.fetch=async(url,options)=>{
    curationPosts++;
    assert.equal(url,'/api/ai/run');
    assert.deepEqual(JSON.parse(options.body),{preview_id:'preview',confirmed:true});
    return {ok:true,json:async()=>({...run,source_count:108})};
  };
  await confirm.click();
  assert.equal(curationPosts,1);
  assert.equal(state.aiPreview,null);
  const reportRun={...run,status:'succeeded',message:'报告已生成',report:{revision:1,sections:[{id:'s1',title:'经验',content:'**检查窄屏**。[R1]',selected:false}],warnings:[]},sources:[{ref_id:'R1',source_id:'id-1',summary:'来源',task:'task-1'}],response_text:'原始返回',diagnostic:{stage:'report',code:'ok'}};
  state.ai={...state.ai,runs:[reportRun],queue:[]}; state.aiDrafts={}; context.renderAI();
  assert.ok(all(content).some(n=>n.tag==='strong'&&n.text==='检查窄屏'));
  let editor=all(content).find(n=>n.tag==='textarea');
  editor.value='人工确认：<img src=x onerror=alert(1)> [R1]'; editor.input();
  assert.ok(!all(content).some(n=>n.tag==='img'||n.tag==='script'));
  const card=all(content).find(n=>n.cls==='ai-report-section');
  const cardActions=all(card).find(n=>n.cls==='ai-card-actions');
  assert.ok(all(cardActions).some(n=>n.text==='编辑'));
  assert.ok(all(cardActions).some(n=>n.text==='保留'));
  const choice=all(cardActions).find(n=>n.type==='checkbox');
  choice.checked=true; choice.change();
  response={...state.ai,runs:[reportRun,{...run,id:'another',status:'running'}]};
  await context.refreshAI();
  assert.equal(all(content).find(n=>n.tag==='textarea'),editor); // Polling must preserve edit focus and values.
  assert.equal(state.aiDrafts[run.id].dirty,true);
  assert.equal(all(content).find(n=>n.text==='保存到项目记忆').disabled,true);
  assert.ok(visible(content).some(n=>n.text==='仅保存到该项目的试用记忆，不进入全局 Brain。'));
  const localActions=[];
  context.fetch=async(url,options)=>{
    const body=JSON.parse(options.body); localActions.push(url);
    let result;
    if(url==='/api/ai/report') {
      assert.equal(body.revision,1); assert.equal(body.sections[0].selected,true);
      reportRun.report={revision:2,sections:body.sections,warnings:[]};
      result={report:reportRun.report,message:'草稿已保存'};
    } else {
      assert.equal(url,'/api/ai/brain'); assert.equal(body.revision,2); assert.equal(body.confirmed,true);
      reportRun.brain_entry={id:'saved',path:'sandbox/brain/projects/project-a/learnings.md',selected_ids:['s1']};
      result={entry:reportRun.brain_entry,message:'已保存到开发 Brain'};
    }
    response={...state.ai,runs:[reportRun]};
    return {ok:true,json:async()=>result};
  };
  await all(content).find(n=>n.text==='保存修改').click();
  assert.equal(state.aiDrafts[run.id].dirty,false);
  assert.equal(all(content).find(n=>n.tag==='textarea').value,editor.value);
  const approval=all(content).find(n=>n.tag==='label'&&n.children.some(c=>c.text?.includes('我已核实选中内容'))).children[0];
  approval.checked=true; approval.change();
  assert.equal(all(content).find(n=>n.text==='保存到项目记忆').disabled,false);
  await all(content).find(n=>n.text==='保存到项目记忆').click();
  assert.deepEqual(localActions,['/api/ai/report','/api/ai/brain']); // Review/save never invokes the model.
  assert.ok(visible(content).some(n=>n.text?.includes('已保存 1 条经验')));
  assert.ok(!visible(content).some(n=>n.text?.includes('sandbox/brain/projects')));
  assert.ok(!all(content).some(n=>n.tag==='textarea'));
  const insightRun={...reportRun,id:'insights',project:'project-a',brain_entry:null,report:{revision:1,style:'behavior-standards-3',warnings:[],sections:[
    {id:'s1',title:'新增准则：验证关键操作',content:'**以后怎么做**：布局变更后必须检查关键操作能否实际点击。\n\n**适用范围**：UI 布局变更。\n\n**如何检查**：检查实际点击。\n\n**对照现有准则**：待核对现有约束。\n\n**依据**：待验证。[R1]',selected:false},
    {id:'s2',title:'问题经过',content:'按钮被遮挡。[R1]',selected:false}]}};
  state.ai={...state.ai,runs:[insightRun]}; context.renderAI();
  const lessonHeading=all(content).find(n=>n.text==='新增准则：验证关键操作');
  assert.equal(lessonHeading.tag,'h3');
  const background=all(content).find(n=>n.tag==='details'&&n.children.some(c=>c.text==='问题经过'));
  assert.ok(background); assert.ok(!background.open);
  const adviceCard=all(content).find(n=>n.cls==='ai-report-section'&&n.dataset.kind==='harness_improvement');
  assert.ok(!all(adviceCard).some(n=>n.attributes['aria-label']?.startsWith('保留到项目记忆')));
  const editButton=all(adviceCard).find(n=>n.text==='编辑');
  editButton.click(); assert.equal(all(adviceCard).find(n=>n.cls==='ai-card-editor').hidden,false);
  const original=all(adviceCard).find(n=>n.tag==='textarea').value;
  all(adviceCard).find(n=>n.tag==='textarea').value='临时输入'; all(adviceCard).find(n=>n.tag==='textarea').input();
  all(adviceCard).find(n=>n.text==='取消').click();
  assert.equal(state.aiDrafts.insights.sections[0].content,original);
  assert.equal(state.aiDrafts.insights.dirty,false);
  assert.equal(all(adviceCard).find(n=>n.cls==='ai-card-editor').hidden,true);
  const propose=all(adviceCard).find(n=>n.text==='采纳建议'); propose.click();
  const review=all(adviceCard).find(n=>n.cls==='ai-candidate-review');
  assert.equal(review.hidden,false);
  const candidate=all(review).find(n=>n.text==='确认采纳'); assert.equal(candidate.disabled,true);
  const reviewCheck=all(review).find(n=>n.type==='checkbox'); reviewCheck.checked=true;reviewCheck.change();
  assert.equal(candidate.disabled,false);
  let queuePosts=0;
  context.fetch=async(url,options)=>{queuePosts++; assert.equal(url,'/api/ai/queue');
    assert.deepEqual(JSON.parse(options.body),{run_id:'insights',section_id:'s1',revision:1,target:'checker',confirmed:true,reviewed:true});
    const entry={id:'candidate',improvement_id:'improvement-1',status:'approved',handoff:'实际执行说明，不自动执行',run_id:'insights',section_id:'s1',revision:1,title:'建议',target:'checker',evidence_ids:['id-1'],recommendation:'检查'};
    response={...state.ai,queue:[entry]}; return {ok:true,json:async()=>entry};};
  await candidate.click(); assert.equal(queuePosts,1); assert.ok(visible(content).some(n=>n.text==='已采纳 · 待落实'));
  assert.ok(!all(content).some(n=>n.text?.startsWith('待评估的改进建议')));
  assert.equal(all(content).filter(n=>n.cls==='ai-improvement-progress').length,1);
  const progress=all(content).find(n=>n.cls==='ai-improvement-progress');
  all(progress).find(n=>n.text==='记录落实').click();
  const followupForm=all(progress).find(n=>n.cls==='ai-card-editor');
  assert.equal(followupForm.hidden,false);
  assert.equal(all(followupForm).find(n=>n.text==='确认记录').disabled,true);
  response={...state.ai,queue:state.ai.queue.map(item=>({...item,updated_at:'new'}))};
  await context.refreshAI(); assert.equal(all(content).find(n=>n.cls==='ai-improvement-progress'),progress);
  all(followupForm).find(n=>n.text==='取消').click(); assert.equal(state.aiFollowupOpen,0);
  all(progress).find(n=>n.text==='记录落实').click();
  const followupField=name=>all(followupForm).find(n=>n.tag==='label'&&n.children[0]?.text===name).children[1];
  followupField('实际改动文件').value='tests/button.test.js';
  followupField('实际应用范围').value='开发分支，尚未安装';
  followupField('验证依据与结果').value='本机测试验证按钮同排，结果见 docs/checks/button.md';
  const followupConsent=all(followupForm).find(n=>n.type==='checkbox'); followupConsent.checked=true;followupConsent.change();
  const record=all(followupForm).find(n=>n.text==='确认记录');
  let advancePosts=0;
  context.fetch=async(url,options)=>{
    advancePosts++; assert.equal(url,'/api/ai/improvement');
    const body=JSON.parse(options.body);assert.equal(body.expected_status,'approved');assert.equal(body.count,2);assert.equal(body.confirmed,true);
    const entry={...state.ai.queue[0],status:'implemented',implementation:{artifact_path:body.artifact_path},implementation_evidence:{scope:body.scope,evidence:body.evidence}};
    response={...state.ai,queue:[entry]};return {ok:true,json:async()=>entry};
  };
  await record.click(); assert.equal(advancePosts,0);assert.match(state.aiMessage,/不默认按零/);
  followupField('改进前问题次数').value='2';await record.click();assert.equal(advancePosts,1);
  assert.ok(visible(content).some(n=>n.text==='已记录落实 · 待复验'));
  assert.ok(visible(content).some(n=>n.text==='记录复验'));
  assert.ok(!visible(content).some(n=>n.text==='人工复验有效'));
  const rethink=all(content).find(n=>n.text==='重新整理');
  editor=all(content).find(n=>n.tag==='textarea'&&typeof n.input==='function');
  editor.value+=' 修改'; editor.input(); assert.equal(rethink.disabled,true);
  state.aiDrafts={}; context.renderAI();
  let rethinkPosts=[];
  context.fetch=async(url,options)=>{
    rethinkPosts.push(url);
    assert.equal(url,'/api/ai/preview');
    assert.deepEqual(JSON.parse(options.body),{project:'project-a',source_run_id:'insights'});
    return {ok:true,json:async()=>({id:'rethink-preview',source_run_id:'insights',payload:[{summary:'原记录'}],input_characters:40,max_output_tokens:16384,destination:'https://api.deepseek.com',model:'deepseek-flash'})};
  };
  response=state.ai;
  await all(content).find(n=>n.text==='重新整理').click();
  assert.deepEqual(rethinkPosts,['/api/ai/preview']); // Re-think opens local preview, never a paid run.
  const rethinkPreview=all(content).find(n=>n.id==='ai-preview');
  assert.ok(visible(rethinkPreview).some(n=>n.text==='重新整理 1 条记录'));
  assert.ok(visible(rethinkPreview).some(n=>n.text?.includes('再次计费')));
  assert.equal(all(rethinkPreview).find(n=>n.text==='确认并整理').disabled,true);
  // New behavior cards foreground actionable norms, not the retrospective.
  const behavior='按钮图标与文字必须同排，空间不足时调整布局，不得堆叠换行。';
  const normRun={...insightRun,id:'norms',rule_context:state.aiPreview.rule_context || {rules:[],coverage:'仅摘录'},report:{revision:1,style:'behavior-standards-3',warnings:[],sections:[
    {id:'s1',title:'落实已有准则：按钮保持同排',kind:'harness_improvement',issues:[],content:`**以后怎么做**：${behavior}\n\n**适用范围**：UI 开发时。\n\n**如何检查**：窄屏下检查图标和文字。\n\n**对照现有准则**：已有规则 [K1]。\n\n**依据**：按钮遮挡记录，尚未确定根因。[R1]`,selected:false},
    {id:'s2',title:'项目复盘：历史调整',content:'项目调试经过。[R1]',selected:false},
    {id:'s3',title:'待观察',content:'证据还不充分。[R1]',selected:false}]}};
  state.ai={...state.ai,runs:[normRun],queue:[]};state.aiDrafts={};context.renderAI();
  const normCard=all(content).find(n=>n.cls==='ai-report-section'&&n.dataset.kind==='harness_improvement');
  assert.ok(visible(normCard).some(n=>n.text===behavior));
  assert.ok(visible(normCard).some(n=>n.text==='如何检查'));
  assert.ok(!visible(normCard).some(n=>n.text?.includes('尚未确定根因')));
  const basis=all(normCard).find(n=>n.cls==='ai-norm-basis');assert.ok(!basis.open);
  basis.open=true;assert.ok(visible(normCard).some(n=>n.text?.includes('尚未确定根因')));
  all(normCard).find(n=>n.text==='采纳建议').click();
  const targets=all(normCard).filter(n=>n.tag==='option').map(n=>n.value);
  assert.deepEqual(targets,['checker','skill']); // Enforcement cannot add a duplicate rule.
  const observation=all(content).find(n=>n.cls==='ai-report-section'&&n.children.some(c=>c.tag==='summary'&&c.text==='待观察'));
  assert.ok(!all(observation).some(n=>n.text==='保留'));
  all(normCard).find(n=>n.text==='编辑').click();
  const normEditor=all(normCard).find(n=>n.tag==='textarea');const normOriginal=normEditor.value;
  normEditor.value='临时替换';normEditor.input();all(normCard).find(n=>n.text==='取消').click();
  assert.equal(state.aiDrafts.norms.sections[0].content,normOriginal);
  assert.ok(visible(normCard).some(n=>n.text===behavior));
  state.ai={...state.ai,runs:[{...run,status:'failed',message:'归纳结果缺少有效证据或格式不完整，本批未标记为已整理；请缩小批量重试。'}]};
  state.aiMessage=''; state.aiFeedbackRun=null; state.aiMessageDetail=''; context.renderAI();
  assert.ok(visible(content).some(n=>n.text==='这次未能完成，请查看详情后再试。'));
  assert.ok(!visible(content).some(n=>n.text?.includes('请缩小批量重试')));
  assert.ok(all(content).some(n=>n.text?.includes('请缩小批量重试'))); // Original diagnostic stays discoverable.
  // Explicit feedback is project-scoped, local-only until a new consent preview.
  state.aiProject='project-a'; state.aiUserDrafts={}; state.aiDrafts={}; state.aiPreview=null;
  state.ai={...state.ai,runs:[],user_feedback:[],projects:[{project:'project-a',new:0,total:0},{project:'project-b',new:0,total:0}]};
  response=state.ai; context.renderAI();
  const input=()=>all(content).find(n=>n.id==='ai-user-feedback-input');
  const feedbackArea=()=>all(content).find(n=>n.id==='ai-user-feedback');
  const feedbackRequests=[];
  context.fetch=async(url,options)=>{
    const body=JSON.parse(options.body); feedbackRequests.push({url,body});
    assert.equal(url,'/api/ai/preview');
    const item={id:'feedback-1',revision:body.feedback.id?2:1,status:body.feedback.action==='withdraw'?'withdrawn':'active',project:body.project,summary:body.feedback.summary};
    response={...state.ai,user_feedback:item.status==='active'?[item]:[]};
    return {ok:true,json:async()=>({id:'feedback-preview',feedback:item,payload:item.status==='active'?[{source_id:item.id,kind:'user_feedback',summary:item.summary}]:[],rule_context:{rules:[]}})};
  };
  input().value='按钮图标文字必须同排'; input().input();
  assert.ok(!all(feedbackArea()).some(n=>n.text==='保存反馈'||n.text?.startsWith('已保存反馈')));
  const draftInput=input(); response={...state.ai,user_feedback:[{id:'other',project:'project-b',status:'active',summary:'另一项目'}]};
  await context.refreshAI();
  assert.equal(input(),draftInput); assert.equal(input().value,'按钮图标文字必须同排');
  const select=all(content).find(n=>n.id==='ai-project-select');
  select.value='project-b'; select.change(); assert.equal(input().value,'另一项目');
  select.value='project-a'; select.change(); assert.equal(input().value,'按钮图标文字必须同排');
  await all(content).find(n=>n.text==='预览内容').click();
  assert.deepEqual(feedbackRequests[0],{url:'/api/ai/preview',body:{project:'project-a',feedback:{summary:'按钮图标文字必须同排'}}});
  assert.match(state.aiMessage,/尚未发送/);
  assert.equal(input().value,'按钮图标文字必须同排');
  context.renderAIFeedback(feedbackArea());
  input().value='按钮图文不能换行'; input().input();
  assert.equal(state.aiPreview,null);
  await all(content).find(n=>n.text==='预览内容').click();
  assert.deepEqual(feedbackRequests[1].body.feedback,{summary:'按钮图文不能换行',id:'feedback-1',revision:1});
  state.aiPreview={id:'feedback-preview',payload:[{source_id:'feedback-1',kind:'user_feedback',summary:'按钮图标文字必须同排'}],rule_context:{rules:[]}};
  const feedbackPreview=node('div'); context.renderAIPreview(feedbackPreview);
  assert.ok(visible(feedbackPreview).some(n=>n.text==='包含你补充的 1 条反馈'));
  assert.ok(visible(feedbackPreview).some(n=>n.text==='按钮图标文字必须同排'));
  assert.equal(all(feedbackPreview).find(n=>n.text==='确认并整理').disabled,true);
  context.renderAIFeedback(feedbackArea()); input().value='';input().input();
  await all(content).find(n=>n.text==='预览内容').click();
  assert.deepEqual(feedbackRequests[2].body,{project:'project-a',feedback:{summary:'',action:'withdraw',id:'feedback-1',revision:2}});
  assert.equal(state.ai.user_feedback.length,0);
  assert.doesNotMatch(source,/localStorage|innerHTML/);
  console.log('PASS: one-step feedback preview, single suggestion lifecycle, polling stability, explicit consent and no paid retries');
})().catch(error=>{console.error(error);process.exitCode=1;});

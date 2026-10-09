"""Report review and Brain sandbox tests; no provider calls or real Brain writes."""
import copy
import importlib.util
import json
from pathlib import Path
import stat
import unittest
from unittest import mock

from tests import test_ai_curation as curation
AI, ROOT = curation.AI, curation.ROOT

spec = importlib.util.spec_from_file_location('report_brain_boundary', ROOT / 'scripts/harness-brain-boundary.py')
BOUNDARY = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BOUNDARY)


class ReportTests(unittest.TestCase):
    setUp = curation.CuratorTests.setUp
    transport = curation.CuratorTests.transport
    connect = curation.CuratorTests.connect
    curate = curation.CuratorTests.curate
    wait = curation.CuratorTests.wait

    def draft(self):
        self.connect()
        self.curator.brain_writer = lambda record: BOUNDARY.append_project_brain(record, brain=self.curator.root / 'brain')
        run, _ = self.curate()
        sections = copy.deepcopy(run['report']['sections'])
        sections[1].update(title='项目复盘：窄屏操作', selected=True, content='人工核实：窄屏需要检查确认按钮是否可点击。[R1]')
        result = self.curator.save_draft({'run_id':run['id'], 'revision':1, 'sections':sections})
        return run, result

    def test_readable_report_keeps_repeated_and_partial_citations_without_rejection(self):
        self.connect()
        run, _ = self.curate()
        self.assertEqual(run['status'],'succeeded')
        self.assertEqual(run['report']['warnings'],[])
        self.assertEqual(len(run['report']['sections']),3)
        self.assertTrue(all(not s['selected'] for s in run['report']['sections']))
        self.assertIn('## 新增准则：',run['response_text'])
        self.assertEqual(run['report']['style'],AI.REPORT_STYLE)
        self.assertEqual(len(run['sources']),3)
        self.assertFalse((self.curator.root/'brain').exists())
        self.assertEqual(self.curator.state()['queue'],[])
        self.assertEqual(stat.S_IMODE((self.curator.root/'records.json').stat().st_mode),0o600)

    def test_unknown_citation_is_a_specific_warning_not_loss_of_report(self):
        self.connect()
        self.answer='## 经验\n可读结论但引用待核实。[R999]'
        run, _ = self.curate()
        self.assertEqual(run['status'],'succeeded')
        self.assertIn('R999',' '.join(run['report']['warnings']))
        self.assertEqual(run['response_text'],self.answer)

    def test_response_retained_before_parser_failure_and_redacted(self):
        self.connect()
        self.answer='## 经验\napi_key=private-value person@example.org 有用结论'
        with mock.patch.object(self.curator,'build_report',side_effect=ValueError('private exception')):
            run, _ = self.curate()
        self.assertEqual(run['status'],'failed')
        self.assertEqual(run['diagnostic'],{'stage':'report','code':'processing_error'})
        self.assertIn('有用结论',run['response_text'])
        self.assertNotIn('private-value',json.dumps(run))
        self.assertNotIn('person@example.org',json.dumps(run))
        self.assertNotIn('private exception',json.dumps(run))
        self.assertEqual(self.curator.snapshot()['projects'][0]['new'],3)

    def test_partial_response_is_retained_and_not_marked_processed(self):
        self.connect()
        def partial(*a,**kw):
            raise AI.AIError('返回不完整',code='response_incomplete',response_text='## 经验\n部分结论。[R1]',usage={'total_tokens':40})
        self.curator.transport=partial
        run, _ = self.curate()
        self.assertEqual(run['status'],'failed')
        self.assertEqual(run['usage']['total_tokens'],40)
        self.assertIn('不完整',run['report']['warnings'][0])
        self.assertIn('部分结论',run['response_text'])
        self.assertEqual(self.curator.snapshot()['projects'][0]['new'],3)

    def test_save_review_then_explicit_brain_confirmation_is_idempotent(self):
        run,result=self.draft()
        self.assertEqual(result['report']['revision'],2)
        self.assertFalse((self.curator.root/'brain').exists())
        # Persisted edits survive a new Curator instance.
        again=AI.Curator(self.root,'development',lambda:copy.deepcopy(self.rows))
        restored=next(r for r in again.snapshot()['runs'] if r['id']==run['id'])
        self.assertIn('人工核实',restored['report']['sections'][1]['content'])
        data={'run_id':run['id'],'revision':2}
        with self.assertRaises(AI.AIError): self.curator.save_brain(data)
        self.assertFalse((self.curator.root/'brain').exists())
        before=len(self.calls)
        saved=self.curator.save_brain({**data,'confirmed':True})
        path=Path(saved['entry']['path'])
        content=path.read_text()
        self.assertTrue(path.is_relative_to(self.curator.root/'brain'))
        self.assertTrue(path.is_relative_to(self.curator.root/'brain'/'projects'))
        self.assertEqual(saved['entry']['scope'],'project')
        self.assertFalse((self.curator.root/'brain'/'global').exists())
        self.assertIn('人工核实',content)
        self.assertNotIn('## 项目进展',content)
        self.assertNotIn('## 待核实',content)
        self.assertIn(self.rows[0]['memory_id'],content)
        repeated=self.curator.save_brain({**data,'confirmed':True})
        self.assertEqual(repeated['entry']['id'],saved['entry']['id'])
        self.assertEqual(path.read_text(),content)
        self.assertEqual(before,len(self.calls))
        self.assertFalse((self.root/'brain').exists())

    def test_draft_revision_empty_selection_stale_sources_and_production_blocked(self):
        run,result=self.draft()
        with self.assertRaisesRegex(AI.AIError,'别处更新'):
            self.curator.save_draft({'run_id':run['id'],'revision':1,'sections':result['report']['sections']})
        self.rows[0]['summary']+=' 更正'
        with self.assertRaisesRegex(AI.AIError,'更正或撤回'):
            self.curator.save_brain({'run_id':run['id'],'revision':2,'confirmed':True})
        self.assertFalse((self.curator.root/'brain').exists())
        prod=AI.Curator(self.root,'production',lambda:self.rows,brain_writer=self.curator.brain_writer)
        with self.assertRaisesRegex(AI.AIError,'正式写入未开放'):
            prod.save_brain({'run_id':run['id'],'revision':2,'confirmed':True})

    def test_warnings_need_acknowledgement_and_failed_write_keeps_draft(self):
        run,result=self.draft()
        sections=result['report']['sections']
        sections[1]['content']='人工判断但缺少来源'
        self.curator.save_draft({'run_id':run['id'],'revision':2,'sections':sections})
        data={'run_id':run['id'],'revision':3,'confirmed':True}
        with self.assertRaisesRegex(AI.AIError,'引用提示'): self.curator.save_brain(data)
        writer=self.curator.brain_writer
        self.curator.brain_writer=mock.Mock(side_effect=OSError('private path'))
        with self.assertRaisesRegex(AI.AIError,'草稿保留'): self.curator.save_brain({**data,'warnings_reviewed':True})
        self.assertEqual(self.curator.state()['runs'][-1]['report']['revision'],3)
        self.curator.brain_writer=writer
        saved=self.curator.save_brain({**data,'warnings_reviewed':True})
        self.assertTrue(saved['entry']['sandbox'])

    def test_provider_uses_prose_not_json_mode_and_retains_truncated_return(self):
        response=mock.MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps({'choices':[{'finish_reason':'length','message':{'content':'部分报告'}}],'usage':{'completion_tokens':10}}).encode()
        opener=mock.Mock()
        opener.open.return_value=response
        with mock.patch.object(AI,'build_opener',return_value=opener), self.assertRaises(AI.AIError) as failure:
            AI.deepseek_request({**AI.DEFAULTS,'api_key':'fake-key'},[],report_mode=True)
        body=json.loads(opener.open.call_args.args[0].data)
        self.assertNotIn('response_format',body)
        self.assertEqual(body['max_tokens'],AI.MAX_OUTPUT_TOKENS)
        self.assertEqual(failure.exception.response_text,'部分报告')
        self.assertEqual(failure.exception.usage,{'completion_tokens':10})

    def test_insight_contract_sent_but_shape_checks_do_not_claim_semantic_quality(self):
        self.connect()
        run,_=self.curate()
        prompt=self.calls[-1][1][0]['content']
        for value in ('以后怎么做','适用范围','如何检查','对照现有准则','依据',
                      '检查脚本','Skill','一次性故障','不要虚构基线','暂无可沉淀准则','实施并验证'):
            self.assertIn(value,prompt)
        self.assertEqual(self.curator.state()['queue'],[])
        self.assertFalse((self.curator.root/'brain').exists())
        # A diagnosis-only response is not discarded or labeled an approved insight.
        report=self.curator.build_report('## 问题经过\n按钮被遮挡。[R1]',run['sources'])
        self.assertIn('问题复述',' '.join(report['warnings']))
        self.assertFalse(report['sections'][0]['selected'])

    def test_each_insight_is_independently_selectable_and_missing_fields_are_hints(self):
        sources=[{'ref_id':'R1'}]
        report=self.curator.build_report('## 启示：先检查边界\n**下次怎么做**：点击。[R1]\n\n'
                                        '## 启示：核实状态\n**下次怎么做**：刷新。[R1]',sources)
        self.assertEqual(len(report['sections']),2)
        self.assertEqual(len(report['warnings']),2)
        self.assertIn('适用边界',report['warnings'][0])
        self.assertTrue(all(not s['selected'] for s in report['sections']))
        none=self.curator.build_report('## 概览\n暂无可沉淀启示。一次观察不足以证明通用规律。[R1]',sources)
        self.assertEqual(none['warnings'],[])

    def test_rethink_preview_uses_current_original_sources_not_draft_or_new_records(self):
        run,result=self.draft()
        old=copy.deepcopy(self.curator.state()['runs'][-1])
        self.rows[0]['summary']+=' 新更正'
        self.rows.append({**self.rows[0],'memory_id':'project_memory_'+'f'*20})
        before=len(self.calls)
        preview=self.curator.preview('project-a',run['id'])
        self.assertEqual(len(self.calls),before)
        self.assertEqual(len(preview['payload']),3)
        self.assertIn('新更正',json.dumps(preview['payload'],ensure_ascii=False))
        self.assertNotIn('人工核实',json.dumps(preview['payload'],ensure_ascii=False))
        self.assertEqual(preview['source_run_id'],run['id'])
        with self.assertRaises(AI.AIError): self.curator.start('curate',{'preview_id':preview['id']})
        new=self.wait(self.curator.start('curate',{'preview_id':preview['id'],'confirmed':True}))
        self.assertEqual(new['status'],'succeeded')
        self.assertEqual(new['source_run_id'],run['id'])
        self.assertEqual(len(self.calls),before+1)
        self.assertEqual(self.curator.start('curate',{'preview_id':preview['id'],'confirmed':True})['id'],new['id'])
        self.assertEqual(len(self.calls),before+1)
        self.assertEqual(next(r for r in self.curator.state()['runs'] if r['id']==old['id']),old)
        self.assertEqual(self.curator.snapshot()['projects'][0]['new'],1)

    def test_rethink_rejects_cross_project_withdrawn_and_post_preview_changes(self):
        self.connect()
        run,_=self.curate()
        before=len(self.calls)
        with self.assertRaises(AI.AIError): self.curator.preview('other',run['id'])
        with self.assertRaises(AI.AIError): self.curator.preview('project-a','not-found')
        preview=self.curator.preview('project-a',run['id'])
        self.rows[0]['summary']+=' 更正'
        with self.assertRaisesRegex(AI.AIError,'来源'):
            self.curator.start('curate',{'preview_id':preview['id'],'confirmed':True})
        self.rows.pop()
        with self.assertRaisesRegex(AI.AIError,'撤回'):
            self.curator.preview('project-a',run['id'])
        self.assertEqual(before,len(self.calls))

    def test_old_preview_invalid_and_legacy_report_edits_do_not_change_style(self):
        self.connect()
        preview=self.curator.preview('project-a')
        saved=self.curator.read('preview.json',{})
        saved['selection_mode']='report-all-new-2'
        self.curator.write('preview.json',saved)
        with self.assertRaisesRegex(AI.AIError,'预览已失效'):
            self.curator.start('curate',{'preview_id':preview['id'],'confirmed':True})
        run,_=self.curate()
        state=self.curator.state()
        state['runs'][-1]['report'].pop('style')
        self.curator.write('records.json',state)
        sections=copy.deepcopy(run['report']['sections'])
        sections[1]['title']='原来的经验'
        result=self.curator.save_draft({'run_id':run['id'],'revision':1,'sections':sections})
        self.assertIsNone(result['report']['style'])
        self.assertEqual(result['report']['warnings'],[])

    def test_report_suggestion_requires_review_and_uses_queue_not_brain(self):
        self.connect()
        run,_=self.curate()
        data={'run_id':run['id'],'revision':1,'section_id':'s2','confirmed':True,'target':'checker'}
        with self.assertRaisesRegex(AI.AIError,'核实'): self.curator.enqueue(data)
        before=len(self.calls)
        entry=self.curator.enqueue({**data,'reviewed':True})
        self.assertEqual(entry['status'],'approved')
        self.assertEqual(entry['evidence_ids'],[run['sources'][0]['source_id']])
        self.assertEqual(self.curator.enqueue({**data,'reviewed':True})['id'],entry['id'])
        self.assertEqual(self.curator.state()['queue'],[])  # No parallel queue entry.
        self.assertEqual(len(self.curator.improvements()),1)
        self.assertEqual(len(self.calls),before)
        self.assertFalse((self.curator.root/'brain').exists())
        for changes in ({'section_id':'s1'}, {'revision':99}, {'target':'global'}):
            with self.assertRaises(AI.AIError): self.curator.enqueue({**data,'reviewed':True,**changes})
        sections=copy.deepcopy(run['report']['sections'])
        sections[1]['selected']=True
        with self.assertRaisesRegex(AI.AIError,'改进建议'):
            self.curator.save_draft({'run_id':run['id'],'revision':1,'sections':sections})

    def test_queue_rejects_retrospective_incomplete_forged_or_stale_evidence(self):
        self.connect()
        run,_=self.curate()
        data={'run_id':run['id'],'revision':1,'section_id':'s2','confirmed':True,'reviewed':True,'target':'rule'}
        sections=copy.deepcopy(run['report']['sections'])
        sections[1]['content']+=' [R999]'
        self.curator.save_draft({'run_id':run['id'],'revision':1,'sections':sections})
        with self.assertRaisesRegex(AI.AIError,'来源引用'): self.curator.enqueue({**data,'revision':2})
        sections[1].update(title='改进建议：仅更名',content='只是项目进度。[R1]',kind='harness_improvement')
        self.curator.save_draft({'run_id':run['id'],'revision':2,'sections':sections})
        with self.assertRaisesRegex(AI.AIError,'不完整'): self.curator.enqueue({**data,'revision':3})
        self.curator.save_draft({'run_id':run['id'],'revision':3,'sections':run['report']['sections']})
        self.rows[0]['summary']+=' 来源更正'
        with self.assertRaisesRegex(AI.AIError,'来源已变化'): self.curator.enqueue({**data,'revision':4})
        self.assertEqual(self.curator.state()['queue'],[])
        prod=AI.Curator(self.root,'production',lambda:self.rows)
        with self.assertRaisesRegex(AI.AIError,'开发待评估'): prod.enqueue(data)

    def test_new_prompt_requests_concrete_harness_changes_and_keeps_review_local(self):
        for text in ('新增准则：','修订准则：','落实已有准则：','待核对现有约束','项目复盘只能留在对应项目','不进入 global Brain'):
            self.assertIn(text,AI.SYSTEM)
        report=self.curator.build_report('## 项目复盘\n已修复窗口移动。[R1]',[{'ref_id':'R1'}])
        self.assertEqual(report['sections'][0]['kind'],'project_review')

    def norms(self):
        self.rules = {'rules':[{'ref_id':'K1','source':'个人准则','heading':'按钮',
                               'content':'按钮图标与文字必须同排对齐，空间不足时调整布局，不得堆叠换行。'}],
                      'coverage':'仅相关摘录，不证明已加载。','unavailable':[]}
        self.curator.rule_context = lambda rows: copy.deepcopy(self.rules)
        self.answer = ('## 落实已有准则：按钮图文保持同排\n\n'
                       '**以后怎么做**：按钮图标与文字必须同排对齐，空间不足时调整布局，不得堆叠换行。\n\n'
                       '**适用范围**：UI 开发和调整布局时，不用于纯后端任务。\n\n'
                       '**如何检查**：在窄屏和长文案下检查图标文字同排，补自动检查而非再加规则。\n\n'
                       '**对照现有准则**：现有约束已覆盖该行为 [K1]；记录未证明是加载问题。\n\n'
                       '**依据**：按钮有遮挡记录，具体原因仍待核实。[R1]\n\n'
                       '## 项目复盘：此次布局\n\n此次界面存在遮挡，未证明普遍根因。[R1]')

    def test_preview_includes_exact_redacted_context_and_change_requires_new_consent(self):
        self.norms(); self.connect()
        preview=self.curator.preview('project-a')
        self.assertEqual(preview['rule_context'],self.rules)
        before=len(self.calls)
        self.rules['rules'][0]['content'] += ' 已修订。'
        with self.assertRaisesRegex(AI.AIError,'对照规范发生变化'):
            self.curator.start('curate',{'preview_id':preview['id'],'confirmed':True})
        self.assertEqual(len(self.calls),before)
        run,preview=self.curate()
        sent=json.loads(self.calls[-1][1][-1]['content'])
        self.assertEqual(sent,{'records':preview['payload'],'rule_context':preview['rule_context']})
        self.assertEqual(run['rule_context'],preview['rule_context'])
        self.assertEqual(run['report']['warnings'],[])

    def test_norm_queue_keeps_small_behavior_separate_from_evidence_and_no_rule_duplication(self):
        self.norms(); self.connect(); run,_=self.curate()
        data={'run_id':run['id'],'revision':1,'section_id':'s1','confirmed':True,'reviewed':True,'target':'rule'}
        with self.assertRaisesRegex(AI.AIError,'不重复新增规则'): self.curator.enqueue(data)
        entry=self.curator.enqueue({**data,'target':'checker'})
        self.assertEqual(entry['action'],'enforce')
        self.assertEqual(entry['summary'],self.rules['rules'][0]['content'])
        self.assertNotIn('[R1]',entry['behavior'])
        self.assertIn('[R1]',entry['recommendation'])
        self.assertEqual(entry['rule_context'],self.rules)
        self.assertFalse((self.curator.root/'brain').exists())
        self.assertEqual(self.curator.enqueue({**data,'target':'checker'})['id'],entry['id'])

    def test_new_norm_duplicate_unknown_comparison_and_retrospective_are_not_ready(self):
        self.norms(); self.connect()
        self.answer=self.answer.replace('落实已有准则：','新增准则：')
        run,_=self.curate()
        self.assertEqual(run['report']['sections'][0]['kind'],'observe')
        self.assertIn('已出现在',' '.join(run['report']['warnings']))
        with self.assertRaisesRegex(AI.AIError,'已出现在'):
            self.curator.enqueue({'run_id':run['id'],'revision':1,'section_id':'s1','confirmed':True,'reviewed':True,'target':'rule'})
        for content in (self.answer.replace('[K1]','[K999]'), self.answer.replace(self.rules['rules'][0]['content'],'已完成按钮修复。')):
            report=self.curator.build_report(content,run['sources'],self.rules['rules'])
            self.assertEqual(report['sections'][0]['kind'],'observe')
            self.assertTrue(report['warnings'])
        self.assertEqual(AI.section_kind({'title':'待观察','content':'还不能沉淀。[R1]'}),'observe')

    def test_revise_requires_existing_reference_and_preserves_scope(self):
        self.norms(); self.connect()
        self.answer=self.answer.replace('落实已有准则：','修订准则：').replace('[K1]','')
        run,_=self.curate()
        self.assertEqual(run['report']['sections'][0]['kind'],'observe')
        self.assertIn('引用对应规范',' '.join(run['report']['warnings']))

    def test_norm_queue_rechecks_rules_and_edits_cannot_bypass_comparison(self):
        self.norms(); self.connect(); run,_=self.curate()
        data={'run_id':run['id'],'revision':1,'section_id':'s1','confirmed':True,'reviewed':True,'target':'checker'}
        self.rules['rules'][0]['content']+=' 规则变化'
        with self.assertRaisesRegex(AI.AIError,'对照规范已变化'): self.curator.enqueue(data)
        sections=copy.deepcopy(run['report']['sections'])
        sections[0]['content']=sections[0]['content'].replace('[K1]','[K999]')
        draft=self.curator.save_draft({'run_id':run['id'],'revision':1,'sections':sections})
        self.assertEqual(draft['report']['sections'][0]['kind'],'observe')
        self.assertIn('规范引用不在',' '.join(draft['report']['warnings']))

    def test_local_retrieval_excludes_logs_fences_duplicates_and_secrets(self):
        path=self.root/'preferences.md'
        path.write_text('# UI\n\n- 按钮图标与文字必须同排，不得换行堆叠。\n\n'
                        '- 按钮图标与文字必须同排，不得换行堆叠。\n\n'
                        '```\n按钮必须输出 sk-fixture-not-a-real-key\n```\n\n'
                        '- [2026-09-22] 按钮必须修改，项目调试日志。\n\n'
                        '- 输入框必须对齐，联系人 person@example.org，api_key=private-value\n\n'
                        '- (merged) 按钮必须读取完整聊天记录，重复历史日志。\n\n'
                        '按钮必须加载尾部记录。')
        context=AI.related_rule_context([('全局偏好',path)], [{'summary':'按钮图标换行、输入框光标错位'}])
        self.assertEqual(len(context['rules']),2)
        serialized=json.dumps(context,ensure_ascii=False)
        for value in ('sk-fixture','person@example.org','private-value','调试日志','重复历史日志','尾部记录'):
            self.assertNotIn(value,serialized)
        self.assertIn('已脱敏',serialized)
        self.assertIn('未检索到不代表没有',context['coverage'])
        self.assertEqual(context['rules'][0]['ref_id'],'K1')
        empty=AI.related_rule_context([('缺失规范',self.root/'absent')],self.rows)
        self.assertEqual(empty['rules'],[])
        self.assertEqual(empty['unavailable'],['缺失规范'])

    def test_rule_context_is_bounded_without_truncating_project_records(self):
        path=self.root/'rules.md'
        path.write_text('\n\n'.join(f'- 按钮必须保持同排并验证布局边界，场景编号 {i}。' for i in range(40)))
        result=AI.related_rule_context([('测试规范',path)],self.rows)
        self.assertEqual(len(result['rules']),12)
        self.assertLessEqual(sum(len(r['content']) for r in result['rules']),6000)

    def test_prompt_distinguishes_preferences_enforcement_and_case_evidence(self):
        for text in ('用户明确要求的行为标准无需等到多次出错','已有准则充分覆盖时必须选',
                     'UI 规范只在 UI 任务加载','未找到不等于不存在','不证明已在该项目加载',
                     '原始日志、复盘与依据不加入常驻上下文'):
            self.assertIn(text,AI.SYSTEM)

    def test_legacy_full_shape_cannot_skip_rule_comparison_gate(self):
        self.connect()
        self.answer='## 改进建议：旧建议\n\n'+'\n\n'.join(f'**{label}**：待核实。[R1]' for label in AI.INSIGHT_LABELS)
        run,_=self.curate()
        with self.assertRaisesRegex(AI.AIError,'旧版建议'):
            self.curator.enqueue({'run_id':run['id'],'revision':1,'section_id':'s1','confirmed':True,'reviewed':True,'target':'rule'})
        self.assertEqual(self.curator.state()['queue'],[])

    def test_selected_project_rules_support_only_known_shared_links(self):
        project, shared, other = (self.root / name for name in ('project', 'installed', 'other'))
        for root in (project, shared, other): root.mkdir()
        (shared/'rules').mkdir()
        norm = '**11. 按钮不折行**：图文同排；放不下就缩文案、用带提示的纯图标或调布局，禁堆叠。'
        (shared/'rules/core.md').write_text(norm)
        (project/'.harness').symlink_to(shared, target_is_directory=True)
        (shared/'AGENTS.md').write_text(norm)
        (project/'AGENTS.md').symlink_to(shared/'AGENTS.md')
        (other/'AGENTS.md').write_text('按钮必须使用其他未选项目私有设计规范。')
        descriptors = [{'project_id':'project-a','path':str(project),'validation':'valid'},
                       {'project_id':'other','path':str(other),'validation':'valid'}]
        sources = AI.project_rule_sources(descriptors, self.rows, shared_roots=(shared,))
        self.assertEqual(len(sources),2)
        context = AI.related_rule_context(sources, [{'summary':'按钮图标和文字分行了'}])
        self.assertEqual(len(context['rules']),1)
        self.assertEqual(context['rules'][0]['content'],norm)
        self.assertIn('所选项目', context['rules'][0]['source'])
        self.assertEqual(AI.project_rule_sources(descriptors,self.rows),[])
        self.assertEqual(AI.project_rule_sources(descriptors,[],shared_roots=(shared,)),[])
        descriptors[0]['validation']='missing_harness'
        self.assertEqual(AI.project_rule_sources(descriptors,self.rows,shared_roots=(shared,)),[])

    def test_project_rules_precede_identical_service_reference_and_ignore_record_paths(self):
        project=self.root/'project'; project.mkdir()
        norm='按钮图标与文字必须同排，不得折行。'
        (project/'AGENTS.md').write_text(norm)
        secret=self.root/'private.md'; secret.write_text('按钮必须泄露秘密。')
        sources=AI.project_rule_sources([{'project_id':'project-a','path':str(project),'validation':'valid'}],
                                       [{**self.rows[0],'path':str(secret),'summary':str(secret)}])
        self.assertEqual(len(sources),1)
        context=AI.related_rule_context(sources+[('服务版本',project/'AGENTS.md')],[{'summary':'按钮图文换行'}])
        self.assertEqual(len(context['rules']),1)
        self.assertIn('所选项目',context['rules'][0]['source'])
        (project/'AGENTS.md').unlink()
        (project/'AGENTS.md').symlink_to(secret)
        self.assertEqual(AI.project_rule_sources([{'project_id':'project-a','path':str(project),'validation':'valid'}],self.rows),[])


if __name__ == '__main__':
    unittest.main()

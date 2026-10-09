"""A single improvement lifecycle, isolated from formal Brain and paid calls."""
import copy
import threading
import unittest
from pathlib import Path
from unittest import mock
from tests import test_ai_curation as curation

AI = curation.AI


class EvolutionTests(unittest.TestCase):
    setUp = curation.CuratorTests.setUp
    transport = curation.CuratorTests.transport
    connect = curation.CuratorTests.connect
    curate = curation.CuratorTests.curate
    wait = curation.CuratorTests.wait

    def adopt(self):
        self.connect()
        run, _ = self.curate()
        data = dict(run_id=run['id'], revision=1, section_id='s2', confirmed=True, reviewed=True, target='checker')
        return run, data, self.curator.enqueue(data)

    def advance(self, entry, **changes):
        data = dict(improvement_id=entry['improvement_id'], expected_status=entry['status'], confirmed=True,
                    action='implement', artifact_path='tests/button.test.js', scope='NARC 开发分支，尚未安装',
                    count=2, evidence='执行按钮布局检查，两个缺陷已修复，日志位于 docs/checks/button.md')
        return self.curator.advance_improvement({**data, **changes})

    def test_preview_includes_feedback_in_one_local_action_and_reuses_revision(self):
        preview = self.curator.preview('project-a', feedback={'summary':'按钮图标与文字不得分行。'})
        item = preview['feedback']
        self.assertEqual(len(preview['payload']),4)
        again = self.curator.preview('project-a', feedback={'summary':item['summary']})
        self.assertEqual(again['feedback']['id'],item['id'])
        with self.assertRaises(AI.AIError):
            self.curator.preview('project-a', 'old-run', feedback={'summary':'不能混入原来源'})
        edited = self.curator.preview('project-a', feedback={'id':item['id'],'revision':1,'summary':'按钮图文必须同排，窄屏也需检查。'})
        self.assertEqual(edited['feedback']['revision'],2)
        with self.assertRaisesRegex(AI.AIError,'别处更新'):
            self.curator.preview('project-a', feedback={'id':item['id'],'revision':1,'summary':'旧版本不能覆盖'})
        removed = self.curator.preview('project-a', feedback={'id':item['id'],'revision':2,'action':'withdraw'})
        self.assertEqual(len(removed['payload']),3)
        self.assertEqual(self.calls,[])
        self.assertFalse((self.curator.root/'brain').exists())

    def test_accepted_suggestion_reuses_lifecycle_and_has_stable_handoff(self):
        run, data, entry = self.adopt()
        self.assertEqual(entry['status'],'approved')
        proposal = self.curator.root / entry['proposal_path']
        self.assertTrue(proposal.is_file())
        self.assertIn('最小验证',proposal.read_text())
        self.assertIn(entry['scope'],proposal.read_text())
        before = len(self.calls)
        self.assertEqual(self.curator.enqueue(data)['improvement_id'],entry['improvement_id'])
        self.assertEqual(len(self.curator.improvements()),1)
        self.assertEqual(self.curator.state()['queue'],[])
        self.assertEqual(self.curator.snapshot()['queue'], self.curator.snapshot()['queue'])
        with self.assertRaisesRegex(AI.AIError,'落实方向'):
            self.curator.enqueue({**data,'target':'skill'})
        self.assertEqual(len(self.calls),before)
        self.assertFalse((self.root/'harness-improvements').exists())
        self.assertFalse((self.curator.root/'brain').exists())

    def test_confirmation_evidence_scope_and_expected_status_required(self):
        _, _, entry = self.adopt()
        for changes in ({'confirmed':False}, {'expected_status':'implemented'}, {'evidence':'已完成'},
                        {'scope':''}, {'count':True}, {'count':-1}, {'artifact_path':'../escape'},
                        {'artifact_path':'/tmp/escape'}, {'action':'verify','result':'improved'}):
            with self.subTest(changes=changes), self.assertRaises(AI.AIError): self.advance(entry,**changes)
        self.assertEqual(self.curator.improvements()[0]['status'],'approved')
        self.curator.environment='production'
        with self.assertRaises(AI.AIError): self.advance(entry)

    def test_implementation_and_effect_are_manual_evidence_not_deployment(self):
        _, _, entry = self.adopt()
        before = len(self.calls)
        implemented = self.advance(entry)
        self.assertEqual(implemented['status'],'implemented')
        self.assertEqual(implemented['implementation_evidence']['source'],'user_recorded')
        self.assertIsNone(implemented['implementation']['release_version'])
        with self.assertRaisesRegex(AI.AIError,'状态已变化'): self.advance(entry)
        followup = self.advance(implemented,action='verify',result='unchanged',count=2)
        self.assertEqual(followup['status'],'needs_followup')
        verified = self.advance(followup,action='verify',result='improved',count=0)
        self.assertEqual(verified['status'],'verified')
        with self.curator.boundary.isolated_state(self.curator.root):
            raw = self.curator.boundary.get_harness_improvement(entry['improvement_id'])
        self.assertEqual(len(raw['effect_history']),2)
        self.assertEqual(len(self.curator.improvements()),1)
        self.assertEqual(len(self.calls),before)
        self.assertFalse((self.curator.root/'tests/button.test.js').exists())
        again = AI.Curator(self.root,'development',lambda:copy.deepcopy(self.rows))
        self.assertEqual(again.improvements()[0]['status'],'verified')

    def test_report_other_edits_do_not_duplicate_or_mutate_adopted_rule(self):
        run, data, entry = self.adopt()
        sections=copy.deepcopy(run['report']['sections'])
        sections[1]['content']+=' 改写已采纳内容。'
        with self.assertRaisesRegex(AI.AIError,'已采纳建议'):
            self.curator.save_draft(dict(run_id=run['id'],revision=1,sections=sections))
        sections=copy.deepcopy(run['report']['sections'])
        sections[0]['content']+=' 仅补充背景。'
        result=self.curator.save_draft(dict(run_id=run['id'],revision=1,sections=sections))
        self.assertEqual(self.curator.enqueue({**data,'revision':result['report']['revision']})['improvement_id'],entry['improvement_id'])
        self.assertEqual(len(self.curator.improvements()),1)

    def test_legacy_queue_preserved_until_explicit_adoption(self):
        self.connect(); run,_=self.curate()
        identifier='ai_candidate_'+AI.digest([run['id'],'s2',1])[:20]
        state=self.curator.state(); state['queue']=[dict(id=identifier,run_id=run['id'],section_id='s2',status='pending_evaluation')]
        self.curator.write('records.json',state)
        before=(self.curator.root/'records.json').read_bytes()
        self.assertEqual(self.curator.snapshot()['queue'][0]['status'],'pending_evaluation')
        self.assertEqual(self.curator.improvements(),[])
        entry=self.curator.enqueue(dict(run_id=run['id'],revision=1,section_id='s2',confirmed=True,reviewed=True,target='checker'))
        self.assertEqual(self.curator.snapshot()['queue'][0]['improvement_id'],entry['improvement_id'])
        self.assertEqual(len(self.curator.snapshot()['queue']),1)
        self.assertEqual((self.curator.root/'records.json').read_bytes(),before)

    def test_interrupted_approval_resumes_same_record(self):
        self.connect(); run,_=self.curate()
        data=dict(run_id=run['id'],revision=1,section_id='s2',confirmed=True,reviewed=True,target='checker')
        with mock.patch.object(self.curator.boundary,'approve_harness_improvement',side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError): self.curator.enqueue(data)
        waiting=self.curator.improvements()[0]
        self.assertEqual(waiting['status'],'pending_approval')
        entry=self.curator.enqueue(data)
        self.assertEqual(entry['improvement_id'],waiting['improvement_id'])
        self.assertEqual(entry['status'],'approved')
        self.assertEqual(len(self.curator.improvements()),1)

    def test_isolated_scope_restores_after_failure_and_does_not_leak_to_threads(self):
        boundary=self.curator.boundary
        original=boundary.state_root()
        other=[]
        with self.assertRaises(RuntimeError):
            with boundary.isolated_state(self.curator.root):
                self.assertEqual(boundary.state_root(),self.curator.root)
                thread=threading.Thread(target=lambda:other.append(boundary.state_root()))
                thread.start(); thread.join()
                raise RuntimeError('test')
        self.assertEqual(other,[original]); self.assertEqual(boundary.state_root(),original)


if __name__=='__main__': unittest.main()

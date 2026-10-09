"""User-authored local feedback, consent and revision boundaries; mocked AI only."""
import copy
import json
import unittest
from tests import test_ai_curation as curation

AI = curation.AI


class FeedbackTests(unittest.TestCase):
    setUp = curation.CuratorTests.setUp
    transport = curation.CuratorTests.transport
    connect = curation.CuratorTests.connect
    curate = curation.CuratorTests.curate
    wait = curation.CuratorTests.wait

    def feedback(self, **changes):
        return self.curator.save_feedback({'project': 'project-a', 'summary': '按钮图标和文字分行了；希望始终同排。', **changes})['item']

    def test_feedback_persists_locally_without_key_calls_brain_or_duplicate(self):
        item = self.feedback()
        self.assertEqual(self.feedback()['id'], item['id'])
        self.assertEqual(self.calls, [])
        again = AI.Curator(self.root, 'development', lambda: copy.deepcopy(self.rows))
        rows = again.selected_records('project-a')
        feedback = next(row for row in rows if row['kind'] == 'user_feedback')
        self.assertEqual(feedback['source_id'], item['id'])
        self.assertFalse(again.snapshot()['user_feedback'][0]['processed'])
        self.assertFalse((self.curator.root/'brain').exists())
        self.assertFalse((self.curator.root/'connection.json').exists())
        self.assertEqual(self.curator.state()['queue'], [])

    def test_valid_registered_project_without_activity_accepts_feedback(self):
        self.rows = []
        self.curator.projects = lambda: ['empty-project']
        self.assertEqual(self.curator.snapshot()['projects'], [{'project':'empty-project', 'total':0, 'new':0}])
        self.feedback(project='empty-project')
        preview = self.curator.preview('empty-project')
        self.assertEqual(len(preview['payload']), 1)
        self.assertEqual(preview['payload'][0]['kind'], 'user_feedback')
        self.assertEqual(preview['payload'][0]['ref_id'], 'R1')

    def test_revision_scope_limits_and_production_are_enforced(self):
        for data in ({'project':'unknown'}, {'summary':''}, {'summary':'x'*4001}, {'summary':42}, {'action':'erase'}):
            with self.subTest(data=data), self.assertRaises(AI.AIError): self.feedback(**data)
        item = self.feedback()
        with self.assertRaisesRegex(AI.AIError, '别处更新'):
            self.feedback(id=item['id'], revision=0)
        self.curator.projects = lambda: ['project-a', 'project-b']
        with self.assertRaisesRegex(AI.AIError, '不属于'):
            self.feedback(project='project-b', id=item['id'], revision=1)
        changed = self.feedback(id=item['id'], revision=1, summary='输入框光标与占位文字必须对齐。')
        self.assertEqual(changed['revision'], 2)
        with self.assertRaises(AI.AIError): self.feedback(id=item['id'], revision=1, action='withdraw')
        self.curator.environment = 'production'
        with self.assertRaisesRegex(AI.AIError, '开发环境'): self.feedback()

    def test_source_changes_require_new_preview_and_never_call_provider(self):
        self.connect()
        item = self.feedback()
        preview = self.curator.preview('project-a')
        item = self.feedback(id=item['id'], revision=1, summary='按钮必须同排，放不下时改用有提示的纯图标。')
        before = len(self.calls)
        with self.assertRaisesRegex(AI.AIError, '来源记录发生变化'):
            self.curator.start('curate', {'preview_id':preview['id'], 'confirmed':True})
        preview = self.curator.preview('project-a')
        self.feedback(id=item['id'], revision=item['revision'], action='withdraw')
        with self.assertRaisesRegex(AI.AIError, '来源记录发生变化'):
            self.curator.start('curate', {'preview_id':preview['id'], 'confirmed':True})
        self.assertEqual(len(self.calls), before)
        self.assertEqual(self.curator.snapshot()['user_feedback'], [])

    def test_processed_feedback_revisions_are_incremental_and_old_report_cannot_commit(self):
        self.connect(); item = self.feedback()
        run, preview = self.curate()
        sent = json.loads(self.calls[-1][1][-1]['content'])['records']
        self.assertEqual(sum(row['kind']=='user_feedback' for row in sent), 1)
        self.assertEqual(sent, preview['payload'])
        self.assertTrue(self.curator.snapshot()['user_feedback'][0]['processed'])
        self.feedback(id=item['id'], revision=1, summary='按钮图标文字必须同排，长文案也不能超出容器。')
        self.assertFalse(self.curator.snapshot()['user_feedback'][0]['processed'])
        self.assertEqual(len(self.curator.preview('project-a')['payload']), 1)
        with self.assertRaisesRegex(AI.AIError, '来源已变化'):
            self.curator.enqueue({'run_id':run['id'], 'revision':1, 'section_id':'s2', 'reviewed':True, 'confirmed':True, 'target':'checker'})

    def test_feedback_redacts_common_secrets_before_storage(self):
        item = self.feedback(summary='按钮文字不换行，api_key=private-value person@example.org')
        saved = (self.curator.root/'feedback.json').read_text()
        self.assertNotIn('private-value', saved)
        self.assertNotIn('person@example.org', saved)
        self.assertIn('已脱敏', item['summary'])

    def test_feedback_is_distinct_untrusted_evidence_and_drives_existing_rule_lookup(self):
        self.assertIn('kind=user_feedback', AI.SYSTEM)
        norm = self.root/'core.md'
        norm.write_text('**11. 按钮不折行**：图文同排；放不下就缩文案、用带提示的纯图标或调布局，禁堆叠。')
        self.curator.rule_context = lambda rows: AI.related_rule_context([('本机既有准则', norm)], rows)
        self.feedback()
        preview = self.curator.preview('project-a')
        self.assertTrue(any('按钮不折行' in r['content'] for r in preview['rule_context']['rules']))
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()

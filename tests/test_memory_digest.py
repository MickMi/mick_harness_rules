"""Memory digest contracts: grounded summaries, bounded actions, no private fixtures."""
import hashlib
import json
import unittest
from unittest import mock

import test_harness_reporting as reporting

ROOT = reporting.ROOT
load = reporting.load

BRAIN = load("harness-brain-boundary")


class MemoryDigestTests(unittest.TestCase):
    setUp = reporting.ReportingTests.setUp
    start_server = reporting.ReportingTests.start_server
    request = reporting.ReportingTests.request

    def memory(self, summary, *, project="demo", kind="result", status="written_local", day=1, task=None):
        identifier = "project_memory_" + hashlib.sha256(f"{project}:{summary}".encode()).hexdigest()[:20]
        value = {
            "memory_id": identifier, "project": project, "kind": kind, "summary": summary,
            "status": status, "created_at": f"2026-09-{day:02d}T08:00:00+00:00",
            "requirement_id": task, "sync_status": "pending", "brain_path": "projects/demo/learnings.md",
        }
        BRAIN.atomic_json(BRAIN.project_record_path(project, identifier), value)
        return identifier

    def test_all_history_is_grouped_not_just_recent_window(self):
        for i in range(140):
            self.memory(f"task-{i}：需求 {i}", kind="requirement")
            self.memory(f"task-{i}: 需求 {i} — 结果 {i}；产物：plan.md", day=2)
        with mock.patch.object(BRAIN, "summaries_are_similar", side_effect=AssertionError("quadratic matching")):
            value = BRAIN.project_memory_digest()
        self.assertEqual(value["records_read"], 280)
        self.assertEqual(value["topic_count"], 140)
        for topic in value["projects"][0]["topics"]:
            self.assertEqual(topic["source_count"], 2)
            self.assertNotIn("产物", topic["conclusion"])

    def test_latest_substantive_result_not_later_status_noise(self):
        self.memory("task-4: 修复溢出 — 仍需窄屏验收", day=1)
        self.memory("task-4 状态变为 completed", day=2)
        value = BRAIN.project_memory_digest()["projects"][0]["topics"][0]
        self.assertEqual(value["conclusion"], "仍需窄屏验收")
        self.assertEqual(value["next_step"], "可提炼经验，不代表存在待修问题")
        self.assertEqual(value["source_count"], 2)

    def test_structured_task_joins_evidence_without_guessing_nearby_records(self):
        self.memory("long-custom-task: 处理页面 — 完成布局", task="long-custom-task")
        self.memory("独立窄屏验证通过", kind="verification", task="long-custom-task")
        self.memory("其他测试通过", kind="verification")
        value = BRAIN.project_memory_digest()
        self.assertEqual(value["topic_count"], 1)
        self.assertEqual(value["archived_records"], 1)
        self.assertEqual(value["projects"][0]["topics"][0]["source_count"], 2)

    def test_projects_and_similar_task_ids_never_merge(self):
        for project, task in [("alpha", "task-1"), ("beta", "task-1"), ("alpha", "task-2")]:
            self.memory(f"{task}: 页面布局 — 测试通过", project=project)
        value = BRAIN.project_memory_digest()
        self.assertEqual(value["topic_count"], 3)
        self.assertEqual(len(value["projects"]), 2)

    def test_role_names_are_not_task_identifiers(self):
        self.memory("PM: 页面讨论 — 方案 A")
        self.memory("PM: 另一个需求 — 方案 B")
        self.assertEqual(BRAIN.project_memory_digest()["topic_count"], 2)

    def test_reverted_corrected_and_unknown_resolution_stay_honest(self):
        self.memory("task-1: 未执行", status="corrected")
        self.memory("task-2: 不可靠", status="reverted")
        self.memory("task-3：尚未验收", kind="requirement")
        value = BRAIN.project_memory_digest()
        self.assertEqual(value["excluded_records"], 2)
        topic = value["projects"][0]["topics"][0]
        self.assertFalse(topic["has_conclusion"])
        self.assertIn("尚无执行结论", topic["conclusion"])

    def test_summary_reads_do_not_rewrite_or_upload(self):
        self.memory("task-1: 需求 — 待用户确认")
        before = {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}
        with mock.patch.object(BRAIN, "atomic_json", side_effect=AssertionError("write")), mock.patch.object(
            BRAIN.subprocess, "run", side_effect=AssertionError("external process")
        ):
            BRAIN.project_memory_digest()
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob("*") if p.is_file()})

    def test_digest_candidate_preserves_sources_not_fake_recurrences(self):
        ids = [self.memory(f"task-1: 布局 — 阶段 {i}") for i in range(3)]
        value = BRAIN.create_harness_improvement(ids[0], target="checker", summary="增加布局边界检查", memory_ids=ids)
        self.assertEqual(len(value["sources"]), 3)
        self.assertEqual(value["occurrence_count"], 1)
        self.assertFalse(value["eligible_for_approval"])
        self.assertEqual(value["status"], "observed")
        again = BRAIN.create_harness_improvement(ids[2], target="checker", summary="增加布局边界检查", memory_ids=ids[::-1])
        self.assertEqual(value["improvement_id"], again["improvement_id"])
        digest = BRAIN.project_memory_digest()
        self.assertEqual(digest["projects"][0]["topics"][0]["improvements"][0]["status"], "observed")
        self.assertFalse((BRAIN.harness_improvement_root() / "proposals").exists())

    def test_candidate_rejects_cross_project_bad_ids_and_retired_sources(self):
        one = self.memory("task-1: 内容")
        two = self.memory("task-1: 内容", project="other")
        retired = self.memory("task-2: 旧结论", status="corrected")
        for ids in [[one, two], ["../escape"], [retired], [None], [one] * 101, "not-a-list"]:
            with self.assertRaises(BRAIN.BrainBoundaryError):
                BRAIN.create_harness_improvement(one, target="rule", memory_ids=ids)

    def test_http_digest_and_candidate_authorization(self):
        one = self.memory("task-1: 测试 — 等待窄屏确认")
        two = self.memory("task-1：页面不应溢出", kind="requirement")
        self.start_server()
        path = "/api/brain/project-memory/summary.json"
        status, value = self.request(path=path)
        self.assertEqual(status, 200)
        self.assertEqual(value["topic_count"], 1)
        self.assertEqual(self.request(path="/api/brain/project-memory.json?limit=100&similar=0")[0], 200)
        self.assertEqual(self.request(path="/api/brain/project-memory.json?similar=invalid")[0], 400)
        self.assertEqual(self.request(path=path, headers={"Origin": "https://evil.example"})[0], 403)
        body = {"memory_id": one, "memory_ids": [one, two], "target": "checker", "summary": "增加边界检查"}
        action = "/api/harness/improvements"
        self.assertEqual(self.request(body, path=action)[0], 401)
        _, health = self.request(path="/api/brain/status.json")
        headers = {"Content-Type": "application/json", "X-Harness-Action-Token": health["action_token"]}
        status, value = self.request(body, headers, action)
        self.assertEqual(status, 200)
        self.assertEqual(value["evidence_count"], 2)
        self.assertEqual(value["status"], "observed")
        self.assertEqual(self.request(body, {**headers, "Origin": "https://evil.example"}, action)[0], 403)
        self.assertEqual(self.request({**body, "memory_ids": [None]}, headers, action)[0], 422)

    def test_compact_ui_has_evidence_and_atomic_followup_controls(self):
        text = (ROOT / "web/observe-dashboard.html").read_text()
        for contract in ["--control-height: 32px", ".settings-page h1", "font-size: 13px",
                         "@media (pointer: coarse)", "min-height: 44px", "renderMemoryDigest",
                         "查看处理进度", "保存改进候选", "memory_ids: sources.map", "memory-evidence-list",
                         "memoryDigestError", 'pageSize = 5', "原始记录 · 最近", "limit=100&similar=0",
                         "if (settingsEntry) render()", "正在读取审批状态", "state.operations?.action_token"]:
            self.assertIn(contract, text)
        self.assertNotIn("formatTime(", text)


if __name__ == "__main__":
    unittest.main()

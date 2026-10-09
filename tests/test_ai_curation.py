"""No paid requests: isolated files, synthetic records and injected transports."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import stat
import ssl
import tempfile
import threading
import time
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tests import test_observer_environment as environment_tests

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ai_curation_test", ROOT / "scripts/harness-ai-curation.py")
AI = importlib.util.module_from_spec(spec)
spec.loader.exec_module(AI)


class CuratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = [{"memory_id": "project_memory_" + f"{i:020x}", "project": "project-a",
                      "summary": f"布局问题 {i}：按钮遮住确认操作", "kind": "gotcha",
                      "requirement_id": f"task-{i}", "created_at": "2026-09-17"} for i in range(3)]
        self.calls = []
        self.category = "harness_improvement"
        self.answer = None
        self.curator = AI.Curator(self.root, "development", lambda: copy.deepcopy(self.rows), transport=self.transport)

    def transport(self, config, messages, *, json_mode=False, report_mode=False):
        self.calls.append((config, messages, json_mode or report_mode))
        if not json_mode and not report_mode:
            return "OK", {"total_tokens": 5}
        if self.answer is not None:
            return self.answer, {"total_tokens": 20}
        if report_mode:
            return ("## 概览\n\n界面完成不能仅由成功渲染判断。\n\n"
                    "## 新增准则：布局变更后检查关键操作\n\n"
                    "**以后怎么做**：布局变更后必须检查确认按钮在窄屏下能否实际点击。\n\n"
                    "**适用范围**：涉及确认操作的 UI 开发，不推断其他场景同一根因。\n\n"
                    "**如何检查**：检查脚本验证实际点击后的状态反馈。\n\n"
                    "**对照现有准则**：待核对现有约束；本次未提供相关规范，不代表规则缺失。\n\n"
                    "**依据**：按钮遮挡支持此建议，但未证明根因相同。[R1]\n\n"
                    "## 待观察\n\n尚未证明根因相同。[R1]"), {"total_tokens": 20}
        rows = json.loads(messages[-1]["content"])["records"]
        return json.dumps({"groups": [{"category": self.category, "title": "布局溢出影响确认",
            "summary": "有界面遮挡记录；尚未证明是同一个根因。", "recommendation": "增加窄屏可点击检查。",
            "target": "checker", "evidence_ids": [row["source_id"] for row in rows]}]}, ensure_ascii=False), {"total_tokens": 20}

    def wait(self, run):
        for _ in range(200):
            current = next(row for row in self.curator.snapshot()["runs"] if row["id"] == run["id"])
            if current["status"] != "running":
                return current
            time.sleep(.005)
        self.fail("request did not finish")

    def connect(self):
        self.curator.save_config({"api_key": "sk-fixture-not-a-real-key"})
        self.assertEqual(self.wait(self.curator.start("test"))["status"], "succeeded")

    def curate(self):
        preview = self.curator.preview("project-a")
        run = self.curator.start("curate", {"preview_id": preview["id"], "confirmed": True})
        return self.wait(run), preview

    def test_private_configuration_isolated_and_never_returned(self):
        self.curator.snapshot()
        self.assertFalse(self.curator.root.exists())
        result = self.curator.save_config({"api_key": "sk-fixture-not-a-real-key"})
        self.assertTrue(result["has_key"])
        self.assertNotIn("sk-fixture", json.dumps(self.curator.snapshot()))
        self.assertEqual(stat.S_IMODE((self.curator.root / "connection.json").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.curator.root.stat().st_mode), 0o700)
        self.curator.save_config({"api_key": ""})
        self.assertTrue(self.curator.public_config()["has_key"])
        prod = AI.Curator(self.root, "production", lambda: [])
        self.assertFalse(prod.public_config()["has_key"])
        self.curator.save_config({"forget_key": True})
        self.assertFalse(self.curator.public_config()["has_key"])

    def test_reject_unknown_endpoints_and_invalid_limits(self):
        for address in ["http://api.deepseek.com", "https://evil.example", "https://api.deepseek.com@evil.example", "http://127.0.0.1", "https://api.deepseek.com/v1/../../"]:
            with self.subTest(address=address), self.assertRaises(AI.AIError):
                self.curator.save_config({"base_url": address})
        for settings in [{"daily_requests": 101}, {"daily_requests": 0}, {"daily_requests": True}, {"api_key": "bad\nvalue"}]:
            with self.assertRaises(AI.AIError): self.curator.save_config(settings)
        with self.assertRaises(AI.AIError): AI.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example")

    def test_connection_is_synthetic_and_real_response_required(self):
        self.connect()
        self.assertEqual(self.calls[0][1], [{"role": "user", "content": "Reply with OK only."}])
        self.assertTrue(self.curator.public_config()["tested"]["ok"])
        self.curator.transport = lambda *args, **kwargs: ("not OK", {})
        run = self.wait(self.curator.start("test"))
        self.assertEqual(run["status"], "failed")
        self.assertFalse(self.curator.public_config()["tested"]["ok"])

    def test_preview_is_local_scoped_redacted_and_requires_consent(self):
        self.rows[0]["summary"] += " api_key=private-value person@example.org /Users/person/private https://private.example"
        self.rows.append({**self.rows[1], "memory_id": "project_memory_" + "9" * 20, "project": "other"})
        preview = self.curator.preview("project-a")
        self.assertEqual(len(preview["payload"]), 3)
        self.assertFalse(self.calls)
        text = json.dumps(preview["payload"])
        for forbidden in ["private-value", "person@example.org", "/Users/person", "private.example", "project-a"]:
            self.assertNotIn(forbidden, text)
        self.curator.save_config({"api_key": "sk-fixture-not-a-real-key"})
        preview = self.curator.preview("project-a")
        with self.assertRaises(AI.AIError): self.curator.start("curate", {"preview_id": preview["id"]})
        with self.assertRaisesRegex(AI.AIError, "测试"): self.curator.start("curate", {"preview_id": preview["id"], "confirmed": True})

    def test_success_is_incremental_and_repeat_start_is_idempotent(self):
        self.connect()
        run, preview = self.curate()
        self.assertEqual(run["status"], "succeeded")
        again = self.curator.start("curate", {"preview_id": preview["id"], "confirmed": True})
        self.assertEqual(again["id"], run["id"])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.curator.snapshot()["projects"][0]["new"], 0)
        with self.assertRaises(AI.AIError): self.curator.preview("project-a")
        self.rows[0]["summary"] += " 新证据"
        self.assertEqual(len(self.curator.preview("project-a")["payload"]), 1)

    def test_all_108_records_sent_once_without_summary_or_byte_truncation(self):
        self.connect()
        self.rows = [{**self.rows[0], "memory_id": "project_memory_" + f"{i:020x}",
                      "summary": ("完整布局证据。" * 300) + f"尾部证据{i}"} for i in range(108)]
        # Upgrade an existing saved config without changing its key/test status.
        config = self.curator.read("connection.json", {})
        config["batch_size"] = 20
        self.curator.write("connection.json", config)
        before = len(self.calls)
        preview = self.curator.preview("project-a")
        self.assertEqual(len(self.calls), before)  # Preview is local only.
        self.assertEqual(len(preview["payload"]), 108)
        self.assertEqual(preview["remaining"], 0)
        self.assertGreater(preview["input_characters"], 24000)
        expected = {row["memory_id"]: row["summary"] for row in self.rows}
        self.assertEqual({row["source_id"]: row["summary"] for row in preview["payload"]}, expected)
        run = self.wait(self.curator.start("curate", {"preview_id": preview["id"], "confirmed": True}))
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["source_count"], 108)
        self.assertEqual(len(self.calls) - before, 1)
        self.assertEqual(json.loads(self.calls[-1][1][-1]["content"])["records"], preview["payload"])
        self.assertEqual(self.curator.snapshot()["projects"][0]["new"], 0)
        self.assertEqual(self.curator.snapshot()["calls_today"], 2)  # Test + one curation.
        self.assertNotIn("batch_size", self.curator.public_config())
        self.assertTrue(self.curator.public_config()["tested"]["ok"])
        self.curator.save_config({"daily_requests": 30})
        self.assertNotIn("batch_size", self.curator.read("connection.json", {}))
        self.assertTrue(self.curator.public_config()["has_key"])
        self.assertTrue(self.curator.public_config()["tested"]["ok"])
        self.assertEqual(self.curator.public_config()["daily_requests"],30)
        self.curator.save_config({"model":"different-model"})
        self.assertIsNone(self.curator.public_config()["tested"])

    def test_legacy_partial_preview_and_changed_full_selection_require_repreview(self):
        self.connect()
        preview = self.curator.preview("project-a")
        saved = self.curator.read("preview.json", {})
        saved.pop("selection_mode")
        self.curator.write("preview.json", saved)
        with self.assertRaisesRegex(AI.AIError, "旧的分批"):
            self.curator.start("curate", {"preview_id": preview["id"], "confirmed": True})
        preview = self.curator.preview("project-a")
        self.rows.append({**self.rows[0], "memory_id": "project_memory_" + "9" * 20})
        with self.assertRaisesRegex(AI.AIError, "来源"):
            self.curator.start("curate", {"preview_id": preview["id"], "confirmed": True})
        self.assertEqual(len(self.calls), 1)  # No paid attempt from either stale preview.

    def test_all_new_excludes_already_processed_and_other_projects(self):
        self.connect()
        self.curate()
        self.rows.extend([{**self.rows[0], "memory_id": "project_memory_" + f"{i:020x}"}
                          for i in range(3, 108)])
        self.rows.append({**self.rows[0], "project": "other", "memory_id": "project_memory_" + "9" * 20})
        run, preview = self.curate()
        self.assertEqual(len(preview["payload"]), 105)
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(len(self.calls), 3)

    def test_capacity_failure_is_explicit_private_and_never_split_or_retried(self):
        opener = mock.Mock()
        config = {**AI.DEFAULTS, "api_key": "sk-fixture-not-a-real-key"}
        error_body = json.dumps({"error": {"code": "context_length_exceeded", "message": "private project text"}}).encode()
        opener.open.side_effect = HTTPError(config["base_url"], 400, "", {}, io.BytesIO(error_body))
        with mock.patch.object(AI, "build_opener", return_value=opener), self.assertRaisesRegex(AI.AIError, "上下文容量") as failure:
            AI.deepseek_request(config, [], json_mode=True)
        self.assertNotIn("private", str(failure.exception))
        self.assertEqual(opener.open.call_count, 1)
        request = opener.open.call_args.args[0]
        self.assertEqual(json.loads(request.data)["max_tokens"], AI.MAX_OUTPUT_TOKENS)
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 120)
        self.connect()
        self.curator.transport = lambda *a, **kw: AI.deepseek_request(*a, **kw)
        opener.open.side_effect = HTTPError(config["base_url"], 400, "", {}, io.BytesIO(error_body))
        with mock.patch.object(AI, "build_opener", return_value=opener):
            run, _ = self.curate()
        self.assertEqual(run["status"], "failed")
        self.assertEqual(self.curator.snapshot()["projects"][0]["new"], 3)
        self.assertEqual(opener.open.call_count, 2)

    def test_changed_source_configuration_and_expired_preview_rejected(self):
        self.connect()
        preview = self.curator.preview("project-a")
        self.rows[0]["summary"] += " modified"
        with self.assertRaisesRegex(AI.AIError, "来源"): self.curator.start("curate", {"confirmed": True, "preview_id": preview["id"]})
        preview = self.curator.preview("project-a")
        self.curator.save_config({"model": "another-model"})
        with self.assertRaisesRegex(AI.AIError, "连接配置"): self.curator.start("curate", {"confirmed": True, "preview_id": preview["id"]})
        preview = self.curator.preview("project-a")
        value = self.curator.read("preview.json", {})
        value["expires_at"] = 0
        self.curator.write("preview.json", value)
        with self.assertRaisesRegex(AI.AIError, "失效"): self.curator.start("curate", {"confirmed": True, "preview_id": preview["id"]})

    def test_report_format_variations_preserved_and_legacy_validation_stays_strict(self):
        self.connect()
        for answer in ["可读文字无需 JSON", '{"groups":[]}', '{"groups":[{"category":"rule"}]}']:
            self.rows[0]["summary"] += " 新记录"
            self.answer = answer
            run, _ = self.curate()
            self.assertEqual(run["status"], "succeeded")
            self.assertEqual(run["response_text"], answer)
            self.assertTrue(run["report"]["warnings"])
            self.assertEqual(run["usage"]["total_tokens"], 20)
        self.rows[0]["summary"] += " 新记录"
        preview = self.curator.preview("project-a")
        self.answer = None
        answer, _ = self.transport({}, [{"content": json.dumps({"records": preview["payload"]})}], json_mode=True)
        for refs in [["fabricated"], [], [row["memory_id"] for row in self.rows] * 2]:
            groups = json.loads(answer)
            groups["groups"][0]["evidence_ids"] = refs
            with self.assertRaises(AI.AIError): self.curator.validate(json.dumps(groups), self.curator.read("preview.json", {}))

    def test_queue_only_manual_reusable_candidates_and_revalidates_evidence(self):
        self.connect()
        run, preview = self.curate()
        # Historical structured candidates remain usable, but new reports do
        # not silently create Harness improvement proposals.
        answer, _ = self.transport({}, [{"content": json.dumps({"records": preview["payload"]})}], json_mode=True)
        state = self.curator.state()
        next(item for item in state["runs"] if item["id"] == run["id"])["groups"] = self.curator.validate(answer, self.curator.read("preview.json", {}))
        self.curator.write("records.json", state)
        data = {"run_id": run["id"], "group_id": "0", "confirmed": True}
        self.assertFalse(self.curator.snapshot()["queue"])
        self.rows[0]["summary"] += " corrected"
        with self.assertRaisesRegex(AI.AIError, "变化"): self.curator.enqueue(data)
        self.rows[0]["summary"] = self.rows[0]["summary"].replace(" corrected", "")
        entry = self.curator.enqueue(data)
        self.assertTrue(entry["sandbox"])
        self.assertEqual(self.curator.enqueue(data)["id"], entry["id"])
        self.assertEqual(len(self.curator.snapshot()["queue"]), 1)
        self.assertEqual({p.name for p in self.root.iterdir()}, {"ai-curation-dev"})

    def test_progress_does_not_become_improvement(self):
        self.connect()
        self.category = "progress"
        run, _ = self.curate()
        with self.assertRaises(AI.AIError): self.curator.enqueue({"run_id": run["id"], "group_id": "0", "confirmed": True})

    def test_limits_and_concurrent_clicks_never_auto_retry(self):
        self.curator.save_config({"api_key": "sk-fixture-not-a-real-key", "daily_requests": 1})
        event = threading.Event()
        self.addCleanup(event.set)
        def slow(*args, **kwargs):
            event.wait(2)
            return "OK", {}
        self.curator.transport = slow
        run = self.curator.start("test")
        with self.assertRaises(AI.AIError): self.curator.start("test")
        with self.assertRaises(AI.AIError): self.curator.save_config({})
        event.set()
        self.wait(run)
        with self.assertRaisesRegex(AI.AIError, "上限"): self.curator.start("test")

    def test_restart_marks_interrupted_without_retries(self):
        self.curator.write("records.json", {"runs": [{"id": "interrupted", "kind": "curate", "status": "running"}], "processed": {}, "queue": [], "calls": {}})
        before = (self.curator.root / "records.json").read_bytes()
        self.assertEqual(self.curator.snapshot()["runs"][0]["status"], "interrupted")
        self.assertEqual((self.curator.root / "records.json").read_bytes(), before)
        self.assertFalse(self.calls)

    def test_certificate_failure_is_not_reported_as_timeout(self):
        opener = mock.Mock()
        opener.open.side_effect = URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))
        with mock.patch.object(AI, "build_opener", return_value=opener), self.assertRaises(AI.AIError) as failure:
            AI.deepseek_request({**AI.DEFAULTS, "api_key": "sk-fixture-not-a-real-key"}, [], json_mode=False)
        self.assertIn("证书", str(failure.exception))
        self.assertNotIn("超时", str(failure.exception))
        self.assertEqual(opener.open.call_count, 1)

    def test_macos_empty_trust_store_uses_only_os_bundle(self):
        context = mock.Mock()
        context.cert_store_stats.return_value = {"x509_ca": 0}
        with (mock.patch.object(AI.ssl, "create_default_context", return_value=context),
              mock.patch.object(AI.sys, "platform", "darwin"),
              mock.patch.dict(AI.os.environ, {"SSL_CERT_FILE": "", "SSL_CERT_DIR": ""}),
              mock.patch.object(AI.Path, "is_file", return_value=True)):
            self.assertIs(AI.tls_context(), context)
        context.load_verify_locations.assert_called_once_with(cafile="/etc/ssl/cert.pem")
        self.assertNotIn("verify_mode", context.__dict__)
        self.assertNotIn("check_hostname", context.__dict__)

    def test_existing_or_explicit_trust_is_never_overridden(self):
        for platform, count, cafile in [("darwin", 100, ""), ("linux", 0, ""), ("darwin", 0, "/custom/ca.pem")]:
            context = mock.Mock()
            context.cert_store_stats.return_value = {"x509_ca": count}
            with (mock.patch.object(AI.ssl, "create_default_context", return_value=context),
                  mock.patch.object(AI.sys, "platform", platform),
                  mock.patch.dict(AI.os.environ, {"SSL_CERT_FILE": cafile, "SSL_CERT_DIR": ""})):
                AI.tls_context()
            context.load_verify_locations.assert_not_called()

    def test_transport_failures_do_not_leak_response_or_key(self):
        config = {**AI.DEFAULTS, "api_key": "sk-fixture-not-a-real-key"}
        for code in [401, 402, 429, 500]:
            opener = mock.Mock()
            opener.open.side_effect = HTTPError(config["base_url"], code, "private server text", {}, None)
            with mock.patch.object(AI, "build_opener", return_value=opener), self.assertRaises(AI.AIError) as failure:
                AI.deepseek_request(config, [], json_mode=False)
            self.assertNotIn("private", str(failure.exception))
            self.assertNotIn(config["api_key"], str(failure.exception))
            self.assertEqual(opener.open.call_count, 1)


class AIHTTPTests(unittest.TestCase):
    setUp = environment_tests.ObserverEnvironmentTests.setUp
    server = environment_tests.ObserverEnvironmentTests.server
    files = environment_tests.ObserverEnvironmentTests.files
    get = environment_tests.ObserverEnvironmentTests.get
    def test_dev_ai_routes_are_protected_and_separate_from_formal_writes(self):
        base = self.server()
        before = self.files()
        value = self.get(base, "/api/ai/status.json")
        self.assertTrue(value["sandbox"])
        self.assertEqual(before, self.files())
        headers = {"Content-Type": "application/json", "X-Harness-Action-Token": value["action_token"]}
        def post(path, data, extra=None):
            with urlopen(Request(base + path, data=json.dumps(data).encode(), headers={**headers, **(extra or {})}), timeout=5) as response:
                return json.loads(response.read())
        for extra in [{"Origin": "https://evil.example"}, {"Sec-Fetch-Site": "cross-site"}, {"X-Harness-Action-Token": "wrong"}]:
            with self.assertRaises(HTTPError): post("/api/ai/configuration", {}, extra)
            for route in ("/api/ai/preview", "/api/ai/report", "/api/ai/brain", "/api/ai/feedback", "/api/ai/improvement"):
                with self.assertRaises(HTTPError): post(route, {}, extra)
        saved = post("/api/ai/configuration", {"api_key": "sk-fixture-not-a-real-key"})
        self.assertTrue(saved["has_key"])
        self.assertNotIn("sk-fixture", json.dumps(self.get(base, "/api/ai/status.json")))
        self.assertTrue((self.state / "ai-curation-dev/connection.json").exists())
        self.assertFalse((self.state / "ai-curation").exists())
        project_id = environment_tests.OBSERVE.project_id(self.project)
        feedback = post('/api/ai/feedback', {'project':project_id, 'summary':'按钮图文必须同排，不得换行堆叠。'})['item']
        preview = post('/api/ai/preview', {'project':project_id})
        self.assertTrue(any(row['source_id'] == feedback['id'] and row['kind'] == 'user_feedback' for row in preview['payload']))
        self.assertEqual(self.get(base, '/api/ai/status.json')['calls_today'], 0)
        post('/api/ai/feedback', {'project':project_id, 'id':feedback['id'], 'revision':1, 'action':'withdraw'})
        self.assertEqual(self.get(base, '/api/ai/status.json')['user_feedback'], [])
        combined = post('/api/ai/preview', {'project':project_id, 'feedback':{'summary':'输入框光标与占位文字保持对齐。'}})
        self.assertEqual(combined['feedback']['summary'], '输入框光标与占位文字保持对齐。')
        self.assertEqual(combined['payload'][0]['kind'], 'user_feedback')
        with self.assertRaises(HTTPError) as failure:
            post('/api/ai/improvement', {'improvement_id':'invalid', 'confirmed':False})
        self.assertEqual(failure.exception.code,403)
        # Exercise real local HTTP review/save routes without any model call.
        run={"id":"ai_fixture", "kind":"curate", "status":"succeeded", "project":"fixture-project",
             "sources":[], "report":{"revision":1,"sections":[{"id":"s1","title":"经验","content":"人工核实的经验","selected":False}],"warnings":[]}}
        (self.state / "ai-curation-dev/records.json").write_text(json.dumps({"runs":[run],"processed":{},"queue":[],"calls":{}}))
        with self.assertRaises(HTTPError) as failure:
            post('/api/ai/preview',{'project':'fixture-project','source_run_id':run['id']})
        self.assertEqual(failure.exception.code,409)
        self.assertIn('原报告',json.loads(failure.exception.read())['error'])
        changed=post("/api/ai/report",{"run_id":run["id"],"revision":1,"sections":[{**run["report"]["sections"][0],"selected":True}]})
        self.assertEqual(changed["report"]["revision"],2)
        with self.assertRaises(HTTPError): post("/api/ai/brain",{"run_id":run["id"],"revision":2})
        entry=post("/api/ai/brain",{"run_id":run["id"],"revision":2,"confirmed":True,"warnings_reviewed":True})["entry"]
        target=Path(entry["path"])
        self.assertTrue(target.is_relative_to(self.state / "ai-curation-dev/brain"))
        self.assertIn("人工核实的经验",target.read_text())
        self.assertFalse((self.root / "brain").exists())
        self.assertEqual(self.get(base,"/api/ai/status.json")["calls_today"],0)
        for path in ["/api/brain/sync", "/api/reporting/configuration", "/api/harness/operations/execute"]:
            with self.assertRaises(HTTPError) as failure: post(path, {})
            self.assertEqual(failure.exception.code, 403)
        for path, content in before.items():
            self.assertEqual((self.root / path).read_bytes(), content)


if __name__ == "__main__":
    unittest.main()

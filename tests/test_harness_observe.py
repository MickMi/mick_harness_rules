from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "harness-observe.py"
HOOK_SCRIPT = ROOT / "scripts" / "harness-observe-hook.py"
DASHBOARD = ROOT / "web" / "observe-dashboard.html"
SPEC = importlib.util.spec_from_file_location("harness_observe", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
OBSERVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OBSERVE)


def plan_text(marker: str = " ", verify: str | None = None, block: bool = False) -> str:
    selfcheck = ""
    if verify is not None:
        selfcheck = f"\n### Step 1 — 2026-08-10 10:00\n- files: demo.txt\n- verify: {verify}\n"
    block_text = ""
    if block:
        block_text = "\n## 阻塞 #1（步骤 1）\n发现：测试环境缺少凭据\n"
    return (
        "> 🧭 状态：执行中 | 进度 0/1 | 当前归属：Executor | 最近卡点：无\n\n"
        "# Plan: Observe fixture\n\n"
        "## 目标\n\n测试观察器。\n\n"
        "## 步骤\n\n"
        f"- [{marker}] 1. 生成示例产物\n\n"
        "## 自检日志\n"
        f"{selfcheck}{block_text}"
    )


def numbered_plan_text() -> str:
    return (
        "# Tennis Multimodal Training — Phase 0 Execution Plan\n\n"
        "**Status:** Active  \n"
        "**Current step:** 3 / 5 — Watch-only 技术探针\n\n"
        "## Objective\n\n"
        "用一个正手挥拍挑战验证统一训练系统是否成立。\n\n"
        "## Steps\n\n"
        "1. **固化产品边界与验收合同（已完成）**：完成 Phase 0 规格。\n"
        "2. **数据与标注探针（已完成）**：定义 Session 和真值。\n"
        "3. **Watch-only 技术探针（进行中）**：验证采样、保存和电量。\n"
        "4. **iPhone-only 与联动探针**：完成视频 Session 和对齐。\n"
        "5. **真实用户验证与 Gate Review**：验证首次完成和继续决策。\n\n"
        "## Decision gates\n\n"
        "1. 这条编号不能成为需求。\n"
        "2. 这条也不能成为需求。\n"
    )


def versions_text() -> str:
    return (
        "# Version Plan\n\n"
        "## 0.1.0\n\n"
        "- Status: released\n"
        "- Branch: main\n"
        "- Tag: v0.1.0\n"
        "- Goal: 建立可使用的基线。\n\n"
        "### Requirements\n\n"
        "- [x] `task-1` 交付基线\n\n"
        "## 0.2.0\n\n"
        "- Status: in_progress\n"
        "- Branch: release/0.2\n"
        "- Goal: 新增产物阅读和版本视图。\n\n"
        "### Requirements\n\n"
        "- [ ] `task-2` Markdown 阅读器\n"
        "- [ ] `task-3` Git 分支视图\n"
    )


def project_profile_text() -> str:
    return (
        "# Project Profile\n\n"
        "## Goal\n\n"
        "让个人 AI 工作方式跨 Agent、项目和设备持续生效。\n\n"
        "## Audience\n\n"
        "同时使用多个 Code Agent 的个人开发者。\n"
    )


class ObserveRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_plan(self, value: str) -> Path:
        path = self.project / "plan.md"
        path.write_text(value, encoding="utf-8")
        return path

    def snapshot(self) -> dict:
        _, target_run_dir = OBSERVE.current_run(self.project)
        return json.loads((target_run_dir / "snapshot.json").read_text(encoding="utf-8"))

    def events_text(self) -> str:
        _, target_run_dir = OBSERVE.current_run(self.project)
        return (target_run_dir / "events.jsonl").read_text(encoding="utf-8")

    def test_init_and_sync_are_idempotent(self) -> None:
        source = self.write_plan(plan_text())
        before = source.read_bytes()

        OBSERVE.init_runtime(self.project)
        first = OBSERVE.sync_runtime(self.project)
        second = OBSERVE.sync_runtime(self.project)

        self.assertGreater(first["appended"], 0)
        self.assertEqual(second["appended"], 0)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(self.snapshot()["tasks"]["task-1"]["status"], "in_progress")
        self.assertNotIn(str(self.project), self.events_text())

    def test_http_client_disconnect_is_not_a_service_error(self) -> None:
        class DisconnectedStream:
            def write(self, value: bytes) -> None:
                raise BrokenPipeError("client left")

        self.assertFalse(OBSERVE.write_http_body(DisconnectedStream(), b"response"))

    def test_harness_cli_routes_observe_command(self) -> None:
        environment = os.environ.copy()
        environment["MICK_HARNESS_ROOT"] = str(ROOT)
        environment["MICK_HARNESS_ACTIVITY"] = "0"
        result = subprocess.run(
            [str(ROOT / "bin" / "harness"), "observe", "--help"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("service", result.stdout)

    def test_observer_product_identity_and_port_are_stable(self) -> None:
        self.assertEqual(OBSERVE.SERVICE_NAME, "Mick Harness Observer")
        self.assertEqual(OBSERVE.SERVICE_LABEL, "com.mick.harness.observer")
        self.assertEqual(OBSERVE.DEFAULT_PORT, 6425)
        self.assertEqual(OBSERVE.COLLECTOR_VERSION, "0.4.0")

    def test_launch_agent_plist_keeps_observer_alive(self) -> None:
        state_dir = self.project / "state"
        config = OBSERVE.build_launch_agent_plist(ROOT, state_dir, port=6425)

        self.assertEqual(config["Label"], "com.mick.harness.observer")
        self.assertTrue(config["RunAtLoad"])
        self.assertTrue(config["KeepAlive"])
        self.assertIn("6425", config["ProgramArguments"])
        self.assertIn("watch", config["ProgramArguments"])
        self.assertIn("--all", config["ProgramArguments"])
        self.assertTrue(config["StandardOutPath"].endswith("observer/service.log"))

    def test_harness_command_activity_is_redacted_and_projected(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())

        OBSERVE.record_harness_command_activity(
            self.project,
            command="check",
            state="started",
            invocation_ref="invoke_test",
        )
        OBSERVE.record_harness_command_activity(
            self.project,
            command="check",
            state="completed",
            invocation_ref="invoke_test",
            exit_code=7,
        )

        events = self.events_text()
        snapshot = self.snapshot()
        command = next(iter(snapshot["harness_commands"].values()))
        self.assertEqual(command["state"], "completed")
        self.assertEqual(command["exit_code"], 7)
        self.assertEqual(snapshot["summary"]["active_harness_commands"], 0)
        self.assertNotIn("arguments", events)
        self.assertNotIn("output", events)

    def test_harness_command_activity_recovers_stale_ledger_lock(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())
        OBSERVE.init_runtime(self.project)
        _, target_run_dir = OBSERVE.current_run(self.project)
        lock = target_run_dir / ".ledger.lock"
        lock.write_text("pid=missing\n", encoding="utf-8")
        stale = time.time() - 60
        os.utime(lock, (stale, stale))

        appended = OBSERVE.record_harness_command_activity(
            self.project,
            command="status",
            state="started",
            invocation_ref="invoke_after_stale_lock",
        )

        self.assertEqual(appended, 1)
        self.assertFalse(lock.exists())

    def test_harness_cli_records_command_without_arguments(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())
        environment = os.environ.copy()
        environment["MICK_HARNESS_ROOT"] = str(ROOT)
        environment["MICK_HARNESS_STATE_DIR"] = str(self.project / "state")
        environment["MICK_HARNESS_OBSERVER_PORT"] = "1"
        secret_argument = "secret-argument-must-not-be-recorded"

        result = subprocess.run(
            [str(ROOT / "bin" / "harness"), "version", secret_argument],
            cwd=self.project,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        events = self.events_text()
        self.assertIn('"command": "version"', events)
        self.assertIn('"state": "completed"', events)
        self.assertNotIn(secret_argument, events)

    def test_harness_cli_activity_preserves_failure_exit_code(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())
        environment = os.environ.copy()
        environment["MICK_HARNESS_ROOT"] = str(ROOT)
        environment["MICK_HARNESS_STATE_DIR"] = str(self.project / "state")
        environment["MICK_HARNESS_OBSERVER_PORT"] = "1"

        result = subprocess.run(
            [str(ROOT / "bin" / "harness"), "unknown-command", "discard-me"],
            cwd=self.project,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

        self.assertEqual(result.returncode, 1)
        command = next(iter(self.snapshot()["harness_commands"].values()))
        self.assertEqual(command["command"], "unknown-command")
        self.assertEqual(command["state"], "completed")
        self.assertEqual(command["exit_code"], 1)
        self.assertNotIn("discard-me", self.events_text())

    def test_dashboard_can_recover_from_transient_network_failure(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("async function fetchWithRetry", dashboard)
        self.assertIn("networkRetryDelaysMs", dashboard)
        self.assertIn("重新连接", dashboard)
        self.assertIn("harness observe watch --all", dashboard)

    def test_dashboard_falls_back_from_invalid_url_project(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("requestedProject.validation !== \"valid\"", dashboard)
        self.assertIn("已失效，已回到全部项目", dashboard)
        self.assertIn("127.0.0.1:6425", dashboard)

    def test_numbered_plan_projects_goal_and_current_requirement(self) -> None:
        self.write_plan(numbered_plan_text())
        OBSERVE.init_runtime(self.project)
        OBSERVE.sync_runtime(self.project)

        snapshot = self.snapshot()
        self.assertEqual(snapshot["plan"]["title"], "Tennis Multimodal Training — Phase 0 Execution Plan")
        self.assertEqual(snapshot["plan"]["objective"], "用一个正手挥拍挑战验证统一训练系统是否成立。")
        self.assertEqual(snapshot["plan"]["current_task_id"], "task-3")
        self.assertEqual(snapshot["plan"]["total_steps"], 5)
        self.assertEqual(
            [snapshot["tasks"][f"task-{index}"]["status"] for index in range(1, 6)],
            ["completed", "completed", "in_progress", "discovered", "discovered"],
        )
        self.assertEqual(snapshot["summary"]["task_total"], 5)

    def test_versioned_plan_uses_step_block_matching_header_progress(self) -> None:
        plan = (
            "> 🧭 状态：进行中 | 进度 10/12 | 当前归属：Executor\n\n"
            "# Plan: Long-running project\n\n"
            "## 步骤\n\n"
            "- [x] 1. Old one\n"
            "- [x] 2. Old two\n\n"
            "## v0.17.0 · current version\n\n"
            "### 实施步骤\n\n"
            "- [x] 9. Current done\n"
            "- [x] 10. Current done too\n"
            "- [ ] 11. Current next\n"
            "- [ ] 12. Release gate\n"
        )
        steps = OBSERVE.parse_plan_steps(plan)

        self.assertEqual([step["step_id"] for step in steps], ["9", "10", "11", "12"])
        self.assertEqual([step["status"] for step in steps], ["completed", "completed", "in_progress", "discovered"])

    def test_numbered_plan_explicitly_resolved_block_is_not_actionable(self) -> None:
        plan = numbered_plan_text() + (
            "\n## 阻塞 #1（步骤 3）\n\n"
            "**状态：** 已由用户选择 A，接口合同与最小实现已落地。\n\n"
            "发现：双端 Target 的接口合同需要裁决。\n"
        )
        self.write_plan(plan)
        OBSERVE.init_runtime(self.project)
        OBSERVE.sync_runtime(self.project)

        snapshot = self.snapshot()
        self.assertFalse(snapshot["blocks"]["block-1"]["active"])
        self.assertEqual(snapshot["summary"]["active_blocks"], 0)

    def test_plan_summary_schema_and_dashboard_navigation_contract(self) -> None:
        schema = json.loads((ROOT / "docs" / "runtime-event-v0.schema.json").read_text(encoding="utf-8"))
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("plan.summary_observed", schema["properties"]["type"]["enum"])
        self.assertIn("plan", schema["$defs"]["subject"]["properties"]["kind"]["enum"])
        self.assertIn('view: "overview"', dashboard)
        for label in ("项目目标", "当前版本", "角色办公室", "需要你处理", "技术记录"):
            self.assertIn(label, dashboard)
        self.assertNotIn("当前需求尚未确定", dashboard)
        self.assertNotIn("flow-step", dashboard)

    def test_completed_step_without_passing_verification_is_pending(self) -> None:
        self.write_plan(plan_text(marker="x"))
        OBSERVE.init_runtime(self.project)
        OBSERVE.sync_runtime(self.project)

        snapshot = self.snapshot()
        self.assertEqual(snapshot["tasks"]["task-1"]["status"], "verification_pending")
        self.assertEqual(snapshot["summary"]["verification_pending"], 1)

    def test_completed_step_with_passing_verification_is_completed(self) -> None:
        self.write_plan(plan_text(marker="x", verify="`python3 check.py` passed; exit 0"))
        OBSERVE.init_runtime(self.project)
        OBSERVE.sync_runtime(self.project)

        snapshot = self.snapshot()
        self.assertEqual(snapshot["tasks"]["task-1"]["status"], "completed")
        self.assertEqual(snapshot["verifications"][-1]["result"], "passed")

    def test_completion_criteria_are_not_parsed_as_numbered_tasks(self) -> None:
        plan = plan_text() + "\n## 完成判定\n\n- [x] HTTP server returns 200.\n- [x] Codex hook is redacted.\n"
        self.write_plan(plan)
        OBSERVE.init_runtime(self.project)
        OBSERVE.sync_runtime(self.project)

        snapshot = self.snapshot()
        self.assertEqual(snapshot["summary"]["task_total"], 1)
        self.assertNotIn("task-HTTP", snapshot["tasks"])
        self.assertNotIn("task-Codex", snapshot["tasks"])

    def test_removed_or_legacy_plan_items_are_abandoned_and_excluded(self) -> None:
        self.write_plan(plan_text())
        OBSERVE.init_runtime(self.project)
        run, target_run_dir = OBSERVE.current_run(self.project)
        fake = OBSERVE.make_candidate(
            "task.discovered",
            "task",
            "task-HTTP",
            {"kind": "importer", "producer": "legacy-plan-collector", "path": "plan.md"},
            {"title": "HTTP criterion", "status": "completed", "role": "Executor", "depends_on": []},
            "legacy:task-HTTP",
            parent_id=run["run_id"],
        )
        OBSERVE.append_events(target_run_dir, run["run_id"], [fake])
        OBSERVE.write_snapshot(self.project, target_run_dir, OBSERVE.load_events(target_run_dir / "events.jsonl"))

        OBSERVE.sync_runtime(self.project)
        snapshot = self.snapshot()

        self.assertEqual(snapshot["tasks"]["task-HTTP"]["status"], "abandoned")
        self.assertEqual(snapshot["summary"]["task_total"], 1)

    def test_block_and_state_stage_are_observed(self) -> None:
        self.write_plan(plan_text(block=True))
        docs = self.project / "docs"
        docs.mkdir()
        (docs / "STATE.md").write_text(
            "# State\n- **Feature 名称**: observe-v0\n"
            "- [ ] **Dev 实现** → code ← **当前阶段**\n",
            encoding="utf-8",
        )

        OBSERVE.init_runtime(self.project)
        OBSERVE.sync_runtime(self.project)
        snapshot = self.snapshot()

        self.assertEqual(snapshot["summary"]["active_blocks"], 1)
        self.assertEqual(OBSERVE.snapshot_stage(snapshot), ("Dev 实现", "Executor"))

    def test_planner_reply_marks_block_inactive(self) -> None:
        plan = plan_text(block=True) + "\nPlanner 回复：采用兼容入口，继续执行。\n"
        self.write_plan(plan)
        OBSERVE.init_runtime(self.project)
        OBSERVE.sync_runtime(self.project)

        snapshot = self.snapshot()
        self.assertEqual(snapshot["summary"]["active_blocks"], 0)
        self.assertFalse(snapshot["blocks"]["block-1"]["active"])
        self.assertEqual(snapshot["plan"]["objective"], "测试观察器。")

    def test_replay_rebuilds_equivalent_snapshot(self) -> None:
        self.write_plan(plan_text(marker="x", verify="passed; exit 0"))
        OBSERVE.init_runtime(self.project)
        OBSERVE.sync_runtime(self.project)
        _, target_run_dir = OBSERVE.current_run(self.project)
        snapshot_path = target_run_dir / "snapshot.json"
        original_digest = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()

        snapshot_path.unlink()
        result = OBSERVE.replay_runtime(self.project)
        rebuilt_digest = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()

        self.assertIsNone(result["before_digest"])
        self.assertEqual(original_digest, rebuilt_digest)
        self.assertFalse(OBSERVE.replay_runtime(self.project)["changed"])

    def test_no_sources_returns_recoverable_warning(self) -> None:
        OBSERVE.init_runtime(self.project)
        result = OBSERVE.sync_runtime(self.project)
        self.assertEqual(result["warning"], "no-sources")
        self.assertEqual(self.snapshot()["collector_warnings"][-1]["code"], "no-sources")

    def test_registry_reports_valid_invalid_and_missing_harness_projects(self) -> None:
        valid = self.project / "valid"
        valid.mkdir()
        (valid / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        missing_harness = self.project / "plain"
        missing_harness.mkdir()
        registry = self.project / "registered-projects"
        registry.write_text(
            f"{valid}\n{missing_harness}\n{self.project / 'missing'}\n",
            encoding="utf-8",
        )

        projects = OBSERVE.load_registered_projects(registry)

        self.assertEqual([item["validation"] for item in projects], ["valid", "missing_harness", "missing"])
        self.assertEqual(projects[0]["project_id"], OBSERVE.project_id(valid))

    def test_portfolio_prefers_state_stage_over_plan_stage(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())
        docs = self.project / "docs"
        docs.mkdir()
        (docs / "STATE.md").write_text(
            "# State\n- **Feature 名称**: portfolio\n"
            "- [ ] **QA 验证** → verify ← **当前阶段**\n",
            encoding="utf-8",
        )
        registry = self.project / "registered-projects"
        registry.write_text(f"{self.project}\n", encoding="utf-8")

        portfolio = OBSERVE.portfolio_snapshot(registry)

        self.assertEqual(portfolio["projects"][0]["stage"], "QA 验证")
        self.assertEqual(portfolio["projects"][0]["owner_role"], "QA")

    def test_portfolio_reads_stage_and_owner_from_plan_header(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())
        registry = self.project / "registered-projects"
        registry.write_text(f"{self.project}\n", encoding="utf-8")

        portfolio = OBSERVE.portfolio_snapshot(registry)

        self.assertEqual(portfolio["projects"][0]["stage"], "执行中")
        self.assertEqual(portfolio["projects"][0]["owner_role"], "Executor")

    def test_codex_hook_records_only_redacted_activity(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())
        payload = {
            "session_id": "thr_secret_session",
            "turn_id": "turn_secret_turn",
            "cwd": str(self.project),
            "hook_event_name": "UserPromptSubmit",
            "prompt": "private prompt text",
            "last_assistant_message": "private assistant text",
            "transcript_path": "/private/transcript.jsonl",
            "model": "private-model",
        }
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"

        result = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input=json.dumps(payload),
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        events = self.events_text()
        self.assertIn("agent.turn_observed", events)
        event = next(json.loads(line) for line in events.splitlines() if "agent.turn_observed" in line)
        self.assertEqual(event["payload"]["rule_version"], "0.17.0")
        self.assertRegex(event["payload"]["role_digest"], r"^sha256:[a-f0-9]{64}$")
        for secret in (payload["prompt"], payload["last_assistant_message"], payload["transcript_path"], payload["model"]):
            self.assertNotIn(secret, events)

    def test_codex_hook_session_and_turn_lifecycle_round_trip(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        base = {"session_id": "thr_round_trip", "cwd": str(self.project)}
        inputs = [
            {**base, "hook_event_name": "SessionStart", "source": "startup"},
            {**base, "hook_event_name": "UserPromptSubmit", "turn_id": "turn_round_trip", "prompt": "discard me"},
            {**base, "hook_event_name": "Stop", "turn_id": "turn_round_trip", "last_assistant_message": "discard me"},
            {**base, "hook_event_name": "SessionEnd", "reason": "other"},
        ]
        results = [
            subprocess.run(
                [sys.executable, str(HOOK_SCRIPT)],
                input=json.dumps(payload),
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
            for payload in inputs
        ]

        self.assertTrue(all(result.returncode == 0 for result in results))
        self.assertEqual(json.loads(results[2].stdout), {"continue": True})
        snapshot = self.snapshot()
        self.assertEqual(next(iter(snapshot["agent_sessions"].values()))["state"], "session_ended")
        self.assertEqual(next(iter(snapshot["agent_turns"].values()))["state"], "turn_completed")
        self.assertEqual(snapshot["summary"]["active_agent_sessions"], 0)
        self.assertEqual(snapshot["summary"]["active_agent_turns"], 0)

    def test_agent_status_requires_runtime_version_evidence_for_loaded(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        OBSERVE.ingest_envelope(
            self.project,
            OBSERVE.build_agent_envelope(
                self.project,
                platform="codex",
                state="session_started",
                session_ref="thr_agent_status",
            ),
        )
        state_dir = self.project / "state"
        state_dir.mkdir()
        registry = state_dir / "registered-projects"
        registry.write_text(f"{self.project}\n", encoding="utf-8")
        manager_report = {
            "harness_version": "0.17.0",
            "agents": [{
                "id": "codex", "name": "Codex", "tier": 1, "detected": True,
                "signals": [{"kind": "command", "found": True}],
                "injection": {"status": "injected"},
                "loading": {"status": "hook_configured"},
                "execution": {"status": "unverified"},
                "issues": [{
                    "code": "load-proof-missing",
                    "severity": "info",
                    "message": "A loader file does not prove this Agent session loaded the rules.",
                    "repair": "Start a fresh Agent session.",
                }],
                "limitations": [],
            }],
        }

        result = OBSERVE.agent_status_snapshot(registry, manager_report=manager_report)
        agent = result["agents"][0]

        self.assertEqual(agent["layers"]["discovered"]["status"], "verified")
        self.assertEqual(agent["layers"]["injected"]["status"], "verified")
        self.assertEqual(agent["layers"]["loaded"]["status"], "verified")
        self.assertEqual(agent["layers"]["execution"]["status"], "unverified")
        self.assertEqual(agent["layers"]["feedback"]["status"], "verified")
        self.assertEqual(agent["evidence"]["event_count"], 1)
        self.assertFalse(any(issue["code"] == "load-proof-missing" for issue in agent["issues"]))
        self.assertNotIn("thr_agent_status", json.dumps(result))

    def test_offline_delivery_keeps_persistent_outbox_until_replay(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        envelope = OBSERVE.build_agent_envelope(
            self.project,
            platform="codex",
            state="session_started",
            session_ref="thr_outbox",
        )
        with mock.patch.object(OBSERVE, "urlopen", side_effect=URLError("offline")):
            with mock.patch.object(OBSERVE, "ingest_envelope", side_effect=OSError("temporarily unwritable")):
                with self.assertRaises(OSError):
                    OBSERVE.submit_envelope(self.project, envelope, state_root=self.project / "state")

        queued = list(OBSERVE.outbox_root(self.project).glob("*.json"))
        self.assertEqual(len(queued), 1)
        self.assertEqual(json.loads(queued[0].read_text(encoding="utf-8"))["schema_version"], "0.2.0")

        first = OBSERVE.replay_outbox(self.project)
        second = OBSERVE.replay_outbox(self.project)
        self.assertEqual(first, {"queued": 1, "replayed": 1, "failed": 0, "remaining": 0})
        self.assertEqual(second, {"queued": 0, "replayed": 0, "failed": 0, "remaining": 0})
        events = [json.loads(line) for line in self.events_text().splitlines()]
        self.assertEqual(sum(event["type"] == "agent.session_observed" for event in events), 1)

    def test_codex_hook_config_is_reviewable_json(self) -> None:
        environment = os.environ.copy()
        environment["MICK_HARNESS_ROOT"] = str(ROOT)
        environment["MICK_HARNESS_ACTIVITY"] = "0"
        result = subprocess.run(
            [str(ROOT / "bin" / "harness"), "observe", "hook-config", "codex"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        self.assertEqual(set(config["hooks"]), {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"})
        commands = [group[0]["hooks"][0]["command"] for group in config["hooks"].values()]
        self.assertTrue(all("harness-observe-hook.py" in command for command in commands))
        self.assertTrue(all("--platform codex" in command for command in commands))

    def test_claude_hook_config_is_reviewable_and_platform_scoped(self) -> None:
        environment = os.environ.copy()
        environment["MICK_HARNESS_ROOT"] = str(ROOT)
        environment["MICK_HARNESS_ACTIVITY"] = "0"
        result = subprocess.run(
            [str(ROOT / "bin" / "harness"), "observe", "hook-config", "claude"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = [group[0]["hooks"][0]["command"] for group in json.loads(result.stdout)["hooks"].values()]
        self.assertTrue(all("--platform claude" in command for command in commands))

    def test_session_start_context_carries_harness_version(self) -> None:
        (self.project / ".harness").mkdir()
        environment = os.environ.copy()
        environment["PWD"] = str(self.project)
        result = subprocess.run(
            [str(ROOT / "hooks" / "session-start.sh")],
            check=False,
            capture_output=True,
            text=True,
            cwd=self.project,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Harness-Version: 0.17.0", context)
        self.assertIn("Rules: .harness/rules/core.md", context)

    def test_agent_activity_supplies_stage_when_project_has_no_plan(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        OBSERVE.record_agent_activity(
            self.project,
            platform="codex",
            state="turn_started",
            session_ref="thr_no_plan",
            turn_ref="turn_no_plan",
        )
        registry = self.project / "registered-projects"
        registry.write_text(f"{self.project}\n", encoding="utf-8")

        portfolio = OBSERVE.portfolio_snapshot(registry)

        self.assertEqual(portfolio["projects"][0]["stage"], "Agent 执行中")
        self.assertEqual(portfolio["projects"][0]["owner_role"], "Codex")

    def test_phase5_schema_and_work_projection_contract(self) -> None:
        schema = json.loads((ROOT / "docs" / "runtime-event-v0.schema.json").read_text(encoding="utf-8"))
        event_types = schema["properties"]["type"]["enum"]
        subject_kinds = schema["$defs"]["subject"]["properties"]["kind"]["enum"]

        for event_type in ("work.round_started", "work.round_completed", "decision.recorded", "handoff.created"):
            self.assertIn(event_type, event_types)
        for subject_kind in ("work_round", "decision", "handoff"):
            self.assertIn(subject_kind, subject_kinds)

        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())
        envelope = OBSERVE.build_work_envelope(
            self.project,
            event_type="work.round_completed",
            role="Executor",
            round_ref="round-phase5",
            requirement_id="task-1",
            objective="实现统一事件接收",
            summary="接收接口和账本已经连通",
            status="completed",
            next_role="QA",
            idempotency_key="phase5-round-completed",
        )
        first = OBSERVE.ingest_envelope(self.project, envelope)
        second = OBSERVE.ingest_envelope(self.project, envelope)

        self.assertEqual(first["appended"], 1)
        self.assertEqual(second["appended"], 0)
        snapshot = self.snapshot()
        work_round = snapshot["work_rounds"]["round-phase5"]
        self.assertEqual(work_round["role"], "Executor")
        self.assertEqual(work_round["requirement_id"], "task-1")
        self.assertEqual(work_round["next_role"], "QA")
        self.assertEqual(snapshot["summary"]["active_work_rounds"], 0)
        self.assertEqual(snapshot["summary"]["work_round_total"], 1)

    def test_ingest_token_is_private_and_stable(self) -> None:
        state_root = self.project / "state"

        first = OBSERVE.ensure_ingest_token(state_root)
        second = OBSERVE.ensure_ingest_token(state_root)
        token_path = OBSERVE.ingest_token_path(state_root)

        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first), 40)
        self.assertEqual(token_path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(first, json.dumps(OBSERVE.service_status(home=self.project)))

    def test_submit_envelope_falls_back_to_local_ledger(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())
        envelope = OBSERVE.build_work_envelope(
            self.project,
            event_type="work.round_started",
            role="PM",
            round_ref="round-offline",
            requirement_id="task-1",
            objective="澄清需求",
            status="active",
            idempotency_key="phase5-offline",
        )

        result = OBSERVE.submit_envelope(
            self.project,
            envelope,
            port=1,
            state_root=self.project / "state",
            timeout=0.05,
        )

        self.assertEqual(result["transport"], "local-fallback")
        self.assertEqual(self.snapshot()["work_rounds"]["round-offline"]["status"], "active")

    def test_http_ingest_is_authenticated_scoped_and_idempotent(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())
        state_dir = self.project / "state"
        state_dir.mkdir()
        registry = state_dir / "registered-projects"
        registry.write_text(f"{self.project}\n", encoding="utf-8")
        token = OBSERVE.ensure_ingest_token(state_dir)
        envelope = OBSERVE.build_work_envelope(
            self.project,
            event_type="work.round_started",
            role="Executor",
            round_ref="round-http",
            requirement_id="task-1",
            objective="通过服务端回写",
            status="active",
            idempotency_key="phase5-http",
        )
        secret_envelope = {**envelope, "prompt": "must-not-be-stored", "secret": "must-not-be-stored"}
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        environment = os.environ.copy()
        environment["MICK_HARNESS_STATE_DIR"] = str(state_dir)
        process = subprocess.Popen(
            [sys.executable, str(SCRIPT), "watch", "--all", "--port", str(port), "--scan-interval", "0.1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(60):
                try:
                    with urlopen(f"{base}/healthz", timeout=0.2) as response:
                        if response.status == 200:
                            break
                except (URLError, TimeoutError):
                    time.sleep(0.05)
            else:
                stdout, stderr = process.communicate(timeout=1)
                self.fail(f"server did not start\nstdout={stdout}\nstderr={stderr}")

            body = json.dumps(envelope).encode("utf-8")
            with self.assertRaises(HTTPError) as unauthorized:
                urlopen(Request(f"{base}/api/v1/events", data=body, headers={"Content-Type": "application/json"}), timeout=1)
            self.assertEqual(unauthorized.exception.code, 401)

            unknown = {**envelope, "project_id": "not-registered"}
            with self.assertRaises(HTTPError) as missing:
                urlopen(
                    Request(
                        f"{base}/api/v1/events",
                        data=json.dumps(unknown).encode("utf-8"),
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    ),
                    timeout=1,
                )
            self.assertEqual(missing.exception.code, 404)

            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            with urlopen(Request(f"{base}/api/v1/events", data=body, headers=headers), timeout=1) as response:
                first = json.loads(response.read())
            with urlopen(Request(f"{base}/api/v1/events", data=body, headers=headers), timeout=1) as response:
                second = json.loads(response.read())
            self.assertEqual(first["appended"], 1)
            self.assertEqual(second["appended"], 0)

            with self.assertRaises(HTTPError) as invalid:
                urlopen(
                    Request(
                        f"{base}/api/v1/events",
                        data=json.dumps(secret_envelope).encode("utf-8"),
                        headers=headers,
                    ),
                    timeout=1,
                )
            self.assertEqual(invalid.exception.code, 422)
            self.assertNotIn("must-not-be-stored", self.events_text())

            with self.assertRaises(HTTPError) as still_read_only:
                urlopen(Request(f"{base}/healthz", data=b"{}", method="POST"), timeout=1)
            self.assertEqual(still_read_only.exception.code, 405)
        finally:
            process.terminate()
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=2)

    def test_dashboard_uses_real_role_work_events(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        for label in ("角色办公室", "当前流转", "执行详情", "需求决策", "交付物", "尚未参与"):
            self.assertIn(label, dashboard)
        self.assertIn("work_rounds", dashboard)
        self.assertIn("decisions", dashboard)
        self.assertIn("organization", dashboard)
        self.assertIn("selectedRole", dashboard)
        self.assertIn('params.set("role"', dashboard)
        for removed in ("角色工作", "关键决策", "角色交接", "renderRoleActivity", "flowState"):
            self.assertNotIn(removed, dashboard)
        self.assertNotIn('task.status === "completed") return "Review"', dashboard)
        self.assertNotIn('task.status === "verification_pending") return "测试"', dashboard)

    def test_dashboard_tree_navigation_and_office_visual_contract(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("nav-tree", dashboard)
        self.assertIn("renderNavTree", dashboard)
        self.assertIn("所有项目", dashboard)
        for label in ("需求导航", "产物", "版本规划", "技术记录", "事件明细"):
            self.assertIn(label, dashboard)
        for removed in ("进展记录", "run-list", "renderRunList", "run-button", "project-button", "renderTabs"):
            self.assertNotIn(removed, dashboard)
        self.assertIn("role-light", dashboard)
        self.assertIn("flow-line", dashboard)
        self.assertIn("@keyframes", dashboard)

    def test_dashboard_shows_agent_five_layer_evidence_without_false_loaded_claims(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")
        self.assertIn("/api/agents.json", dashboard)
        self.assertIn("Code Agent 接入状态", dashboard)
        for label in ("发现", "注入", "加载", "遵循", "回写"):
            self.assertIn(f'{label}\"', dashboard)
        self.assertIn("待真实会话", dashboard)
        self.assertIn("尚无真实会话证据", dashboard)

    def test_phase7_project_goal_and_role_office_projection(self) -> None:
        profile = OBSERVE.parse_project_profile(project_profile_text())
        self.assertEqual(profile["goal"], "让个人 AI 工作方式跨 Agent、项目和设备持续生效。")
        snapshot = {
            "work_rounds": {
                "planning": {
                    "round_id": "planning",
                    "role": "Planner",
                    "status": "completed",
                    "objective": "定义版本范围",
                    "summary": "版本范围已锁定",
                    "next_role": "Executor",
                    "requirement_id": "task-1",
                    "derived_from_sequence": 10,
                },
                "development": {
                    "round_id": "development",
                    "role": "Executor",
                    "status": "completed",
                    "objective": "实现角色图谱",
                    "summary": "角色图谱已交付",
                    "next_role": "Reviewer",
                    "requirement_id": "task-2",
                    "artifact_refs": ["web/observe-dashboard.html"],
                    "derived_from_sequence": 20,
                },
                "review": {
                    "round_id": "review",
                    "role": "Reviewer",
                    "status": "completed",
                    "objective": "验收角色图谱",
                    "summary": "验收通过",
                    "next_role": "PM",
                    "requirement_id": "task-2",
                    "derived_from_sequence": 30,
                },
            },
            "handoffs": {
                "qa-review": {
                    "handoff_id": "qa-review",
                    "from_role": "QA",
                    "to_role": "Reviewer",
                    "status": "completed",
                    "summary": "测试通过后交给 Review",
                    "requirement_id": "task-2",
                    "derived_from_sequence": 25,
                }
            },
        }
        organization = OBSERVE.organization_snapshot(snapshot)
        roles = organization["roles"]
        self.assertEqual([role["role_id"] for role in roles], ["PM", "Designer", "Executor", "QA", "Reviewer"])
        self.assertEqual(next(role for role in roles if role["role_id"] == "PM")["status"], "waiting")
        self.assertEqual(next(role for role in roles if role["role_id"] == "Designer")["status"], "idle")
        self.assertEqual(next(role for role in roles if role["role_id"] == "Reviewer")["status"], "completed")
        self.assertEqual(organization["current_role"], "PM")
        self.assertEqual(organization["current_transition"]["from_role"], "Reviewer")
        self.assertEqual(organization["current_transition"]["to_role"], "PM")
        self.assertEqual(organization["current_transition"]["kind"], "suggested")
        self.assertTrue(any(edge["kind"] == "handoff" for edge in organization["transitions"]))

    def test_phase6_workspace_projects_artifacts_versions_and_real_git(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())
        docs = self.project / "docs"
        docs.mkdir()
        (docs / "VERSIONS.md").write_text(versions_text(), encoding="utf-8")
        source = self.project / "src" / "demo.py"
        source.parent.mkdir()
        source.write_text('def greet(name):\n    """Return a greeting."""\n    return f"Hi {name}"\n', encoding="utf-8")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture"], cwd=self.project, check=True)
        subprocess.run(["git", "add", "AGENTS.md", "plan.md", "docs/VERSIONS.md", "src/demo.py"], cwd=self.project, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture baseline"], cwd=self.project, check=True)
        subprocess.run(["git", "tag", "v0.1.0"], cwd=self.project, check=True)

        envelope = OBSERVE.build_work_envelope(
            self.project,
            event_type="work.round_completed",
            role="Executor",
            round_ref="round-artifact",
            requirement_id="task-1",
            objective="生成 Python 产物",
            summary="已交付可阅读源码",
            status="completed",
            artifact_refs=["src/demo.py"],
            idempotency_key="phase6-artifact",
        )
        OBSERVE.ingest_envelope(self.project, envelope)
        snapshot = self.snapshot()
        snapshot.setdefault("tasks", {})["task-1"] = {"status": "abandoned"}
        workspace = OBSERVE.project_workspace_snapshot(self.project, snapshot)

        self.assertEqual(workspace["git"]["current_branch"], "main")
        self.assertIn("v0.1.0", workspace["git"]["tags"])
        self.assertEqual([item["version"] for item in workspace["versions"]["items"]], ["0.1.0", "0.2.0"])
        self.assertTrue(workspace["versions"]["items"][0]["tag_exists"])
        self.assertFalse(workspace["versions"]["items"][1]["branch_exists"])
        self.assertNotIn("observed_status", workspace["versions"]["items"][0]["requirements"][0])
        self.assertIn("src/demo.py", [item["path"] for item in workspace["artifacts"]])

        content = OBSERVE.read_artifact_content(self.project, snapshot, "src/demo.py")
        self.assertEqual(content["language"], "python")
        self.assertIn("Return a greeting", content["content"])
        self.assertEqual(content["stages"], [])
        with self.assertRaises(OBSERVE.ObserveError):
            OBSERVE.read_artifact_content(self.project, snapshot, "../outside.py")
        (self.project / "secret.txt").write_text("not authorized", encoding="utf-8")
        with self.assertRaises(OBSERVE.ObserveError):
            OBSERVE.read_artifact_content(self.project, snapshot, "secret.txt")

    def test_phase8_artifacts_keep_version_and_date_records(self) -> None:
        docs = self.project / "docs"
        docs.mkdir()
        (docs / "VERSIONS.md").write_text(versions_text(), encoding="utf-8")
        report = docs / "RESULTS.md"
        report.write_text("# Results\n\n## v0.1\n\nFirst result.\n\n## v0.2\n\nSecond result.\n", encoding="utf-8")
        snapshot = {
            "artifacts": {},
            "tasks": {},
            "work_rounds": {
                "round-one": {
                    "round_id": "round-one",
                    "role": "PM",
                    "requirement_id": "task-1",
                    "objective": "确定 0.1 目标",
                    "summary": "记录 0.1 讨论结论",
                    "status": "completed",
                    "artifact_refs": ["docs/RESULTS.md"],
                    "updated_at": "2026-08-10T08:30:00+00:00",
                    "derived_from_sequence": 10,
                },
                "round-two": {
                    "round_id": "round-two",
                    "role": "Reviewer",
                    "requirement_id": "task-2",
                    "objective": "验收 0.2 目标",
                    "summary": "记录 0.2 验收结果",
                    "status": "completed",
                    "artifact_refs": ["docs/RESULTS.md"],
                    "updated_at": "2026-08-12T09:45:00+00:00",
                    "derived_from_sequence": 20,
                },
            },
            "decisions": {},
            "handoffs": {},
        }

        workspace = OBSERVE.project_workspace_snapshot(self.project, snapshot)
        artifact = next(item for item in workspace["artifacts"] if item["path"] == "docs/RESULTS.md")

        self.assertEqual(artifact["versions"], ["0.1.0", "0.2.0"])
        self.assertEqual(artifact["dates"], ["2026-08-12", "2026-08-10"])
        self.assertEqual(artifact["latest_recorded_at"], "2026-08-12T09:45:00+00:00")
        self.assertEqual([item["round_id"] for item in artifact["records"]], ["round-two", "round-one"])
        self.assertEqual(artifact["records"][0]["versions"], ["0.2.0"])
        self.assertEqual(artifact["records"][1]["objective"], "确定 0.1 目标")

    def test_phase9_markdown_stages_use_heading_contract_only(self) -> None:
        markdown = (
            "# 计划\n\n"
            "正文测试日期 2026-06-01 不应成为阶段。\n\n"
            "## v0.15.0 · 2026-08-12 · 结构化产物导航\n\n"
            "这里还有 2026-08-09，也不应单独建阶段。\n\n"
            "### Step 3 执行自检（2026-07-13）\n\n"
            "旧项目正文。\n\n"
            "### Step 3ak Companion IPA（2026-08-04，2026-08-10 更新）\n\n"
            "## 没有日期的普通标题\n\n"
            "```markdown\n"
            "## v9.9.9 · 2026-08-12 · 代码块里的示例不是阶段\n"
            "```\n"
        )

        stages = OBSERVE.parse_markdown_stages(markdown)

        self.assertEqual(len(stages), 3)
        self.assertEqual(
            stages[0],
            {
                "line": 5,
                "level": 2,
                "title": "结构化产物导航",
                "version": "0.15.0",
                "date": "2026-08-12",
                "dates": ["2026-08-12"],
                "format": "structured",
                "traceable": True,
            },
        )
        self.assertEqual(stages[1]["title"], "Step 3 执行自检")
        self.assertIsNone(stages[1]["version"])
        self.assertEqual(stages[1]["date"], "2026-07-13")
        self.assertEqual(stages[1]["format"], "legacy")
        self.assertFalse(stages[1]["traceable"])
        self.assertEqual(stages[2]["dates"], ["2026-08-04", "2026-08-10"])
        self.assertEqual(stages[2]["date"], "2026-08-10")

        self.write_plan(markdown)
        OBSERVE.init_runtime(self.project)
        OBSERVE.sync_runtime(self.project)
        document = OBSERVE.read_artifact_content(self.project, self.snapshot(), "plan.md")
        self.assertEqual(document["stages"], stages)

    def test_phase6_dashboard_has_safe_artifact_reader_and_version_views(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        for label in ("产物", "版本规划", "Markdown 阅读", "代码产物", "真实 Git 状态", "需求归属"):
            self.assertIn(label, dashboard)
        self.assertIn("renderMarkdownDocument", dashboard)
        self.assertIn("renderCodeDocument", dashboard)
        self.assertIn('el("strong"', dashboard)
        self.assertIn('el("em"', dashboard)
        self.assertIn("resolveArtifactLink", dashboard)
        self.assertIn('rel = "noopener noreferrer"', dashboard)
        self.assertIn("workspace.json", dashboard)
        self.assertIn("artifact?", dashboard)
        self.assertIn("document.createElement", dashboard)
        self.assertNotIn("marked.parse", dashboard)
        self.assertNotIn("innerHTML =", dashboard)

    def test_phase9_dashboard_uses_document_stages_not_event_filters(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        for label in ("阶段导航", "规范标题", "未标版本", "完整文档目录", "旧格式"):
            self.assertIn(label, dashboard)
        for contract in ("renderArtifactStageNavigation", "documentValue.stages", "stage.line", "renderDocumentOutline"):
            self.assertIn(contract, dashboard)
        for obsolete in ("artifactMode", "artifactScope", "artifactNavigationGroups", "artifactRecordMatchesNavigation", "renderArtifactContext", "focusArtifactHeading", "artifact_mode", "artifact_scope"):
            self.assertNotIn(obsolete, dashboard)
        self.assertIn("renderDocumentOutline(shell, headings, documentValue.stages || [])", dashboard)
        self.assertIn('const artifacts = (state.workspace?.artifacts || []).slice()', dashboard)
        self.assertNotIn("innerHTML =", dashboard)

    def test_http_server_is_read_only(self) -> None:
        self.write_plan(plan_text())
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        process = subprocess.Popen(
            [sys.executable, str(SCRIPT), "watch", str(self.project), "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(60):
                try:
                    with urlopen(f"{base}/healthz", timeout=0.2) as response:
                        if response.status == 200:
                            break
                except (URLError, TimeoutError):
                    time.sleep(0.05)
            else:
                stdout, stderr = process.communicate(timeout=1)
                self.fail(f"server did not start\nstdout={stdout}\nstderr={stderr}")

            with urlopen(f"{base}/api/index.json", timeout=1) as response:
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["runs"])

            with self.assertRaises(HTTPError) as context:
                urlopen(Request(f"{base}/healthz", method="POST"), timeout=1)
            self.assertEqual(context.exception.code, 405)
        finally:
            process.terminate()
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=2)

    def test_portfolio_http_routes_registered_projects_only(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())
        docs = self.project / "docs"
        docs.mkdir()
        (docs / "VERSIONS.md").write_text(versions_text(), encoding="utf-8")
        source = self.project / "demo.py"
        source.write_text("# readable artifact\nprint('ok')\n", encoding="utf-8")
        OBSERVE.ingest_envelope(
            self.project,
            OBSERVE.build_work_envelope(
                self.project,
                event_type="work.round_completed",
                role="Executor",
                round_ref="round-http-artifact",
                requirement_id="task-1",
                objective="验证 HTTP 产物路由",
                summary="产物已登记",
                status="completed",
                artifact_refs=["demo.py"],
                idempotency_key="phase6-http-artifact",
            ),
        )
        state_dir = self.project / "state"
        state_dir.mkdir()
        (state_dir / "registered-projects").write_text(
            f"{self.project}\n{self.project / 'missing'}\n",
            encoding="utf-8",
        )
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        environment = os.environ.copy()
        environment["MICK_HARNESS_STATE_DIR"] = str(state_dir)
        process = subprocess.Popen(
            [sys.executable, str(SCRIPT), "watch", "--all", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(60):
                try:
                    with urlopen(f"{base}/healthz", timeout=0.2) as response:
                        if response.status == 200:
                            break
                except (URLError, TimeoutError):
                    time.sleep(0.05)
            else:
                stdout, stderr = process.communicate(timeout=1)
                self.fail(f"portfolio server did not start\nstdout={stdout}\nstderr={stderr}")

            with urlopen(f"{base}/healthz", timeout=1) as response:
                health = json.loads(response.read())
            self.assertEqual(health["service_name"], "Mick Harness Observer")
            self.assertEqual(health["port"], port)
            self.assertIn("last_scan_at", health)

            with urlopen(f"{base}/api/portfolio.json", timeout=1) as response:
                portfolio = json.loads(response.read())
            self.assertEqual([item["validation"] for item in portfolio["projects"]], ["valid", "missing"])
            with urlopen(f"{base}/api/agents.json", timeout=2) as response:
                agents = json.loads(response.read())
            self.assertEqual(len(agents["agents"]), 7)
            self.assertIn("layers", agents["agents"][0])
            valid_id = portfolio["projects"][0]["project_id"]
            with urlopen(f"{base}/api/projects/{valid_id}/index.json", timeout=1) as response:
                self.assertEqual(response.status, 200)
            with urlopen(f"{base}/api/projects/{valid_id}/workspace.json", timeout=1) as response:
                workspace = json.loads(response.read())
            self.assertIn("demo.py", [item["path"] for item in workspace["artifacts"]])
            with urlopen(
                f"{base}/api/projects/{valid_id}/artifact?path={quote('demo.py')}", timeout=1
            ) as response:
                artifact = json.loads(response.read())
            self.assertEqual(artifact["language"], "python")
            self.assertIn("readable artifact", artifact["content"])
            with self.assertRaises(HTTPError) as forbidden_artifact:
                urlopen(
                    f"{base}/api/projects/{valid_id}/artifact?path={quote('../secret.txt')}", timeout=1
                )
            self.assertIn(forbidden_artifact.exception.code, (400, 403, 404))
            with self.assertRaises(HTTPError) as context:
                urlopen(f"{base}/api/projects/not-registered/index.json", timeout=1)
            self.assertEqual(context.exception.code, 404)
        finally:
            process.terminate()
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=2)

    def test_portfolio_monitor_syncs_without_dashboard_request(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())
        state_dir = self.project / "state"
        state_dir.mkdir()
        registry = state_dir / "registered-projects"
        registry.write_text("", encoding="utf-8")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        environment = os.environ.copy()
        environment["MICK_HARNESS_STATE_DIR"] = str(state_dir)
        process = subprocess.Popen(
            [
                sys.executable,
                str(SCRIPT),
                "watch",
                "--all",
                "--port",
                str(port),
                "--scan-interval",
                "0.1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(60):
                try:
                    with urlopen(f"{base}/healthz", timeout=0.2) as response:
                        if response.status == 200:
                            break
                except (URLError, TimeoutError):
                    time.sleep(0.05)
            else:
                stdout, stderr = process.communicate(timeout=1)
                self.fail(f"portfolio server did not start\nstdout={stdout}\nstderr={stderr}")

            registry.write_text(f"{self.project}\n", encoding="utf-8")
            for _ in range(60):
                try:
                    if self.snapshot()["tasks"]["task-1"]["status"] == "in_progress":
                        break
                except (FileNotFoundError, KeyError, OBSERVE.ObserveError):
                    pass
                time.sleep(0.05)
            else:
                self.fail("background monitor did not discover the newly registered project")

            self.write_plan(plan_text(marker="x", verify="passed; exit 0"))
            for _ in range(60):
                try:
                    if self.snapshot()["tasks"]["task-1"]["status"] == "completed":
                        break
                except (FileNotFoundError, KeyError, OBSERVE.ObserveError):
                    pass
                time.sleep(0.05)
            else:
                self.fail("background monitor did not sync the changed plan")
        finally:
            process.terminate()
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=2)


if __name__ == "__main__":
    unittest.main()

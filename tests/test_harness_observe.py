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
PRODUCT_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
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
        self.extra_worktrees: list[Path] = []
        self.env_patch = mock.patch.dict(
            os.environ,
            {
                "MICK_HARNESS_STATE_ROOT": str(self.project / "private-state"),
                "MICK_HARNESS_STATE_DIR": str(self.project / "private-state"),
                "MICK_BRAIN_ROOT": str(self.project / "private-brain"),
            },
        )
        self.env_patch.start()

    def tearDown(self) -> None:
        for worktree in self.extra_worktrees:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=self.project,
                check=False,
                capture_output=True,
            )
        self.env_patch.stop()
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

    def test_operation_catalog_exposes_only_product_whitelist(self) -> None:
        catalog = OBSERVE.operation_catalog()

        self.assertEqual(
            [item["action"] for item in catalog],
            ["harness-update", "project-init", "agent-sync"],
        )
        self.assertEqual([item["label"] for item in catalog], ["更新 Harness", "注入或升级项目", "修复 Agent 接入"])
        self.assertNotIn("command", json.dumps(catalog, ensure_ascii=False))

    def test_operation_preview_rejects_unknown_actions_and_unsafe_project_paths(self) -> None:
        state_dir = self.project / "state"
        target = self.project / "target"
        target.mkdir()

        with self.assertRaisesRegex(OBSERVE.ObserveError, "Unsupported operation"):
            OBSERVE.prepare_operation("run-command", {"command": "echo unsafe"}, state_root=state_dir)
        with self.assertRaisesRegex(OBSERVE.ObserveError, "absolute"):
            OBSERVE.prepare_operation("project-init", {"project_path": "relative/project"}, state_root=state_dir)
        with self.assertRaisesRegex(OBSERVE.ObserveError, "does not exist"):
            OBSERVE.prepare_operation(
                "project-init",
                {"project_path": str(self.project / "missing")},
                state_root=state_dir,
            )

        preview = OBSERVE.prepare_operation(
            "project-init",
            {"project_path": str(target)},
            state_root=state_dir,
        )
        snapshot = OBSERVE.operation_snapshot(state_root=state_dir)
        self.assertEqual(preview["status"], "prepared")
        self.assertTrue(preview["confirmation_token"])
        self.assertEqual(preview["target"], str(target.resolve()))
        self.assertNotIn("confirmation_token", json.dumps(snapshot, ensure_ascii=False))

    def test_operation_preview_and_confirmation_are_idempotent_and_single_use(self) -> None:
        state_dir = self.project / "state"
        first = OBSERVE.prepare_operation("agent-sync", {}, state_root=state_dir)
        second = OBSERVE.prepare_operation("agent-sync", {}, state_root=state_dir)

        self.assertEqual(first["operation_id"], second["operation_id"])
        self.assertTrue(second["reused"])
        with self.assertRaisesRegex(OBSERVE.ObserveError, "confirmation"):
            OBSERVE.confirm_operation(
                first["operation_id"],
                "wrong-token",
                state_root=state_dir,
                spawn_worker=False,
            )

        queued = OBSERVE.confirm_operation(
            first["operation_id"],
            first["confirmation_token"],
            state_root=state_dir,
            spawn_worker=False,
        )
        self.assertEqual(queued["status"], "queued")
        with self.assertRaisesRegex(OBSERVE.ObserveError, "already confirmed"):
            OBSERVE.confirm_operation(
                first["operation_id"],
                first["confirmation_token"],
                state_root=state_dir,
                spawn_worker=False,
            )

    def test_operation_mutex_rejects_parallel_mutation(self) -> None:
        state_dir = self.project / "state"

        with OBSERVE.operation_mutex(state_root=state_dir):
            with self.assertRaisesRegex(OBSERVE.ObserveError, "already running"):
                with OBSERVE.operation_mutex(state_root=state_dir):
                    self.fail("parallel operation should not enter the critical section")

    def test_operation_worker_uses_fixed_argument_lists_and_records_success(self) -> None:
        state_dir = self.project / "state"
        target = self.project / "project;not-a-shell-command"
        target.mkdir()
        preview = OBSERVE.prepare_operation(
            "project-init",
            {"project_path": str(target), "full": True},
            state_root=state_dir,
            harness_root=ROOT,
        )
        OBSERVE.confirm_operation(
            preview["operation_id"],
            preview["confirmation_token"],
            state_root=state_dir,
            spawn_worker=False,
        )

        with mock.patch.object(
            OBSERVE.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, "ok", ""),
        ) as run:
            result = OBSERVE.run_operation_worker(
                preview["operation_id"],
                state_root=state_dir,
                harness_root=ROOT,
            )

        command = run.call_args.args[0]
        self.assertEqual(command[:2], [str(ROOT / "bin" / "harness"), "init"])
        self.assertEqual(command[2], str(target.resolve()))
        self.assertEqual(command[3], "--full")
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["exit_code"], 0)

    def test_operation_worker_redacts_failure_details(self) -> None:
        state_dir = self.project / "state"
        preview = OBSERVE.prepare_operation("agent-sync", {}, state_root=state_dir, harness_root=ROOT)
        OBSERVE.confirm_operation(
            preview["operation_id"],
            preview["confirmation_token"],
            state_root=state_dir,
            spawn_worker=False,
        )

        with mock.patch.object(
            OBSERVE.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 9, "", "token=top-secret failure"),
        ):
            result = OBSERVE.run_operation_worker(
                preview["operation_id"],
                state_root=state_dir,
                harness_root=ROOT,
            )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 9)
        self.assertIn("token=[redacted]", result["summary"])
        self.assertNotIn("top-secret", json.dumps(OBSERVE.operation_snapshot(state_root=state_dir)))

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

    def test_install_service_reuses_matching_healthy_service(self) -> None:
        state_dir = self.project / "state"
        plist_path = OBSERVE.launch_agent_path(self.project)
        plist_path.parent.mkdir(parents=True)
        config = OBSERVE.build_launch_agent_plist(ROOT, state_dir, port=6425)
        original = OBSERVE.plistlib.dumps(config, fmt=OBSERVE.plistlib.FMT_XML, sort_keys=True)
        plist_path.write_bytes(original)
        health = {"service_name": OBSERVE.SERVICE_NAME, "port": 6425}

        with (
            mock.patch.object(OBSERVE.sys, "platform", "darwin"),
            mock.patch.object(OBSERVE, "default_state_root", return_value=state_dir),
            mock.patch.object(OBSERVE, "launch_agent_loaded", return_value=True),
            mock.patch.object(OBSERVE, "observer_health", return_value=health),
            mock.patch.object(OBSERVE, "wait_for_observer", return_value=health),
            mock.patch.object(OBSERVE, "run_launchctl") as launchctl,
        ):
            result = OBSERVE.install_service(home=self.project)

        launchctl.assert_not_called()
        self.assertEqual(plist_path.read_bytes(), original)
        self.assertTrue(result["loaded"])
        self.assertTrue(result["healthy"])

    def test_install_service_restores_previous_service_when_bootstrap_fails(self) -> None:
        state_dir = self.project / "state"
        plist_path = OBSERVE.launch_agent_path(self.project)
        plist_path.parent.mkdir(parents=True)
        previous_config = OBSERVE.build_launch_agent_plist(
            self.project / "previous-harness",
            self.project / "previous-state",
            port=6411,
        )
        previous = OBSERVE.plistlib.dumps(
            previous_config,
            fmt=OBSERVE.plistlib.FMT_XML,
            sort_keys=True,
        )
        plist_path.write_bytes(previous)
        bootstrap_attempts = 0

        def launchctl_result(arguments: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
            nonlocal bootstrap_attempts
            if arguments[0] == "bootstrap":
                bootstrap_attempts += 1
                if bootstrap_attempts == 1:
                    raise OBSERVE.ObserveError("new bootstrap failed")
            return subprocess.CompletedProcess(["launchctl", *arguments], 0, "", "")

        old_health = {"service_name": OBSERVE.SERVICE_NAME, "port": 6411}
        with (
            mock.patch.object(OBSERVE.sys, "platform", "darwin"),
            mock.patch.object(OBSERVE, "default_state_root", return_value=state_dir),
            mock.patch.object(OBSERVE, "launch_agent_loaded", return_value=True),
            mock.patch.object(OBSERVE, "run_launchctl", side_effect=launchctl_result),
            mock.patch.object(OBSERVE, "wait_for_observer", return_value=old_health),
        ):
            with self.assertRaisesRegex(OBSERVE.ObserveError, "new bootstrap failed"):
                OBSERVE.install_service(home=self.project)

        self.assertEqual(plist_path.read_bytes(), previous)
        self.assertEqual(bootstrap_attempts, 2)

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
        environment["MICK_HARNESS_OBSERVER_PORT"] = "1"

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
        self.assertEqual(event["payload"]["rule_version"], PRODUCT_VERSION)
        self.assertRegex(event["payload"]["role_digest"], r"^sha256:[a-f0-9]{64}$")
        for secret in (payload["prompt"], payload["last_assistant_message"], payload["transcript_path"], payload["model"]):
            self.assertNotIn(secret, events)

    def test_codex_hook_session_and_turn_lifecycle_round_trip(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["MICK_HARNESS_OBSERVER_PORT"] = "1"
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
            "harness_version": PRODUCT_VERSION,
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
        self.assertIn(f"Harness-Version: {PRODUCT_VERSION}", context)
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
        environment["MICK_BRAIN_ROOT"] = str(state_dir / "brain")
        candidate_process = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "harness-brain-boundary.py"),
                "candidate", "--kind", "preference", "--layer", "global",
                "--project", "fixture", "--summary", "跨项目候选",
            ],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        candidate_id = json.loads(candidate_process.stdout)["candidate_id"]
        similar_ids = []
        for project, summary in (("app-a", "移动端页面出现横向溢出"), ("app-b", "移动端页面再次出现横向溢出问题")):
            created = subprocess.run(
                [
                    sys.executable, str(ROOT / "scripts" / "harness-brain-boundary.py"),
                    "candidate", "--kind", "gotcha", "--layer", "global",
                    "--project", project, "--summary", summary,
                ],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            similar_ids.append(json.loads(created.stdout)["candidate_id"])
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

            with urlopen(f"{base}/api/brain/status.json", timeout=1) as response:
                brain_health = json.loads(response.read())
            self.assertIn("action_token", brain_health)
            self.assertIn("local_write", brain_health)
            with urlopen(f"{base}/api/brain/candidates.json", timeout=1) as response:
                candidates = json.loads(response.read())
            candidate_map = {item["candidate_id"]: item for item in candidates["items"]}
            self.assertIn(candidate_id, candidate_map)
            self.assertIn(similar_ids[1], candidate_map[similar_ids[0]]["similar_candidate_ids"])

            update_url = f"{base}/api/brain/candidates/{candidate_id}/update"
            with urlopen(
                Request(
                    update_url,
                    data=json.dumps({"summary": "更新后的跨项目候选", "layer": "global"}).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "X-Harness-Action-Token": brain_health["action_token"],
                    },
                ),
                timeout=1,
            ) as response:
                updated = json.loads(response.read())
            self.assertEqual(updated["summary"], "更新后的跨项目候选")

            merge_url = f"{base}/api/brain/candidates/{similar_ids[0]}/merge"
            with urlopen(
                Request(
                    merge_url,
                    data=json.dumps({"candidate_ids": [similar_ids[1]], "summary": "移动端布局必须检查横向溢出"}).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "X-Harness-Action-Token": brain_health["action_token"],
                    },
                ),
                timeout=1,
            ) as response:
                merged = json.loads(response.read())
            self.assertEqual(merged["occurrence_count"], 2)

            ignore_url = f"{base}/api/brain/candidates/{similar_ids[0]}/ignore-similar"
            with urlopen(
                Request(
                    ignore_url,
                    data=b"{}",
                    headers={
                        "Content-Type": "application/json",
                        "X-Harness-Action-Token": brain_health["action_token"],
                    },
                ),
                timeout=1,
            ) as response:
                ignored = json.loads(response.read())
            self.assertEqual(ignored["status"], "ignored_similar")
            action_url = f"{base}/api/brain/candidates/{candidate_id}/reject"
            with self.assertRaises(HTTPError) as unauthenticated_action:
                urlopen(Request(action_url, data=b"{}", headers={"Content-Type": "application/json"}), timeout=1)
            self.assertEqual(unauthenticated_action.exception.code, 401)
            with self.assertRaises(HTTPError) as unauthenticated_sync:
                urlopen(
                    Request(
                        f"{base}/api/brain/sync",
                        data=json.dumps({"confirmed": True}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    ),
                    timeout=1,
                )
            self.assertEqual(unauthenticated_sync.exception.code, 401)
            with urlopen(
                Request(
                    action_url,
                    data=b"{}",
                    headers={
                        "Content-Type": "application/json",
                        "X-Harness-Action-Token": brain_health["action_token"],
                    },
                ),
                timeout=1,
            ) as response:
                rejected = json.loads(response.read())
            self.assertEqual(rejected["status"], "rejected")

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

            completed = OBSERVE.build_work_envelope(
                self.project,
                event_type="work.round_completed",
                role="Executor",
                round_ref="round-http-completed",
                requirement_id="task-1",
                objective="完成 Brain 自动写入",
                summary="项目事实已验证",
                status="completed",
                idempotency_key="phase5-http-completed",
            )
            with urlopen(
                Request(
                    f"{base}/api/v1/events",
                    data=json.dumps(completed).encode("utf-8"),
                    headers=headers,
                ),
                timeout=1,
            ) as response:
                completed_result = json.loads(response.read())
            self.assertEqual(completed_result["brain"]["action"], "recorded_project_memory")
            with urlopen(f"{base}/api/brain/project-memory.json", timeout=1) as response:
                memories = json.loads(response.read())
            self.assertIn(
                "task-1: 完成 Brain 自动写入 — 项目事实已验证",
                [item["summary"] for item in memories["items"]],
            )

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

        for label in ("任务办公室", "需求门禁", "质量门禁", "执行详情", "需求决策", "交付物", "尚未参与"):
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

    def test_dashboard_has_brain_health_activity_and_approval_workbench(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        for endpoint in (
            "/api/brain/status.json", "/api/brain/candidates.json", "/api/brain/project-memory.json"
        ):
            self.assertIn(endpoint, dashboard)
        for label in ("记忆与同步", "项目记忆", "全局待审批", "本次同步清单", "连接与高级设置"):
            self.assertIn(label, dashboard)
        self.assertNotIn('el("h1", "", "Brain 工作台")', dashboard)
        self.assertLess(dashboard.index("本次同步清单"), dashboard.index("全局待审批"))
        self.assertLess(dashboard.index("全局待审批"), dashboard.index("项目记忆"))
        self.assertLess(dashboard.index("项目记忆"), dashboard.index("连接与高级设置"))
        for contract in (
            "brainSyncPreview", "dry_run: true", "查看同步清单", "不会上传",
            "待推送提交", "brain-project-details", "brain-connection-details",
            "更改范围", "合并同类", "忽略同类", "合并项目记录",
            "/merge", "/ignore-similar", "/update", "brainDialog",
        ):
            self.assertIn(contract, dashboard)
        self.assertNotIn("window.prompt", dashboard)
        self.assertNotIn("window.confirm", dashboard)
        self.assertIn("X-Harness-Action-Token", dashboard)
        self.assertIn("关闭会话不是写入前提", dashboard)
        self.assertIn("Brain 接入状态", dashboard)
        self.assertIn("查看项目记录", dashboard)
        for label in (
            "Brain 连接", "配置来源", "配置仓库", "已生效", "本地写入路径",
            "项目记录待同步", "全局/Profile 待审批", "当前无需审批",
            "跨项目稳定偏好与可复用经验", "Profile 规则或风格的版本变化",
            "本机服务自动记录", "Hook 只负责采集事件", "查看同步清单", "确认并同步", "取消同步",
        ):
            self.assertIn(label, dashboard)
        for removed in ("接入仓库", "实际仓库", "先核对本地 Brain、配置仓库和 Git 实际仓库"):
            self.assertNotIn(removed, dashboard)
        self.assertIn('/api/brain/sync', dashboard)
        self.assertIn('confirmed: true', dashboard)
        self.assertIn("brainSyncConfirm", dashboard)
        self.assertNotIn('const brain = el("button", "nav-home")', dashboard)
        self.assertNotIn("navTree.append(brain)", dashboard)

    def test_plan_sync_auto_records_confirmed_requirements_stage_and_verification(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text(marker="x", verify="passed: 3 tests"))

        result = OBSERVE.sync_runtime(self.project)
        memories = OBSERVE.load_brain_boundary().list_project_memories(project=OBSERVE.project_id(self.project))
        kinds = {item["kind"] for item in memories}

        self.assertGreaterEqual(result["brain_recorded"], 3)
        self.assertIn("requirement", kinds)
        self.assertIn("verification", kinds)
        self.assertIn("stage", kinds)
        self.assertTrue(all(item["status"] == "written_local" for item in memories))
        second = OBSERVE.sync_runtime(self.project)
        self.assertEqual(second["brain_recorded"], 0)

    def test_dashboard_tree_navigation_and_office_visual_contract(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("nav-tree", dashboard)
        self.assertIn("renderNavTree", dashboard)
        self.assertIn("连接异常", dashboard)
        for label in ("工作台", "设置", "项目主页", "版本记录", "交付物", "更多", "诊断", "Agent 接入", "技术记录", "事件日志", "原始运行"):
            self.assertIn(label, dashboard)
        self.assertNotIn('["workflow", "工作流"]', dashboard)
        for removed in ("进展记录", "run-list", "renderRunList", "run-button", "project-button", "renderTabs"):
            self.assertNotIn(removed, dashboard)
        for marker in ("role-office-scene", "role-jelly", "role-hover-card", "role-history-timeline"):
            self.assertIn(marker, dashboard)
        self.assertNotIn("office-role-row", dashboard)
        self.assertIn("jelly-task", dashboard)
        self.assertIn("flow-line", dashboard)
        self.assertIn("@keyframes", dashboard)

    def test_role_office_matches_minimal_jelly_reference_and_keeps_state_driven_motion(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        for marker in (
            "role-visual",
            "role-jelly",
            "jelly-face",
            "jelly-arm",
            "jelly-task",
            "role-card-meta",
            "role-name",
        ):
            self.assertIn(marker, dashboard)
        for role_id, flavor in (
            ("PM", "planner"),
            ("Designer", "creative"),
            ("Executor", "builder"),
            ("QA", "inspector"),
            ("Reviewer", "reviewer"),
        ):
            self.assertIn(f'{role_id}: "{flavor}"', dashboard)
        for removed_detail in (
            "character-head",
            "character-body",
            "character-accessory",
            "character-legs",
            "character-badge",
            "jelly-mouth",
            "jelly-prop",
            "jelly-spark",
            "role-workbench",
            "role-monitor",
            "role-mug",
            "role-specialty",
            "role-light",
        ):
            self.assertNotIn(removed_detail, dashboard)
        for color in ("#58a7f7", "#ffa266", "#7bd08c", "#eb84b9", "#9e83e8"):
            self.assertIn(color, dashboard.lower())
        self.assertNotIn('.role-station[data-flow="source"] { box-shadow:', dashboard)
        self.assertIn('.role-station[data-status="active"] .role-jelly', dashboard)
        for animation_name in ("jelly-active", "jelly-carry"):
            self.assertIn(f"@keyframes {animation_name}", dashboard)
        self.assertIn('role.status === "active" ? `${role.label} · 工作中` : role.label', dashboard)
        self.assertIn("grid-template-rows: 128px minmax(48px, auto)", dashboard)
        self.assertIn("overflow-wrap: anywhere", dashboard)

    def test_dashboard_workbench_and_overview_prioritize_human_decisions(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        for marker in (
            "nav-section-label",
            "workbench-priority",
            "project-summary-list",
            "project-summary-row",
            "project-next",
            "workbench-secondary",
            "project-overview-hero",
            "overview-status-strip",
            "project-purpose",
            "office-flow-rail",
            "role-hover-card",
        ):
            self.assertIn(marker, dashboard)
        for legacy_layout in ("project-table", "question-grid", "question-item", "six-questions"):
            self.assertNotIn(legacy_layout, dashboard)
        self.assertNotIn("← 所有项目", dashboard)
        self.assertIn('aria-label", `查看项目 ${project.name}`', dashboard)
        self.assertIn("-webkit-line-clamp: 2", dashboard)
        self.assertIn("@media (max-width: 760px)", dashboard)
        self.assertIn("prefers-reduced-motion", dashboard)
        for label in ("下一步", "当前负责", "等待接手"):
            self.assertIn(label, dashboard)

    def test_dashboard_navigation_and_brain_actions_close_user_paths(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        self.assertNotIn('["projects", "项目"]', dashboard)
        self.assertNotIn('["inbox", "待处理"]', dashboard)
        self.assertNotIn("function renderInbox", dashboard)
        self.assertNotIn("查看全部待处理", dashboard)
        self.assertNotIn('repositoryDetail("当前分支"', dashboard)
        for marker in (
            "openBrainFocus",
            "focusBrainSection",
            "metric-action",
            "project-attention",
            "brain-repository-line",
            "brain-route-action",
            'id = "brain-project-memory"',
            'id = "brain-approvals"',
            'id = "brain-sync"',
        ):
            self.assertIn(marker, dashboard)
        for label in (
            "查看项目记录",
            "处理同步",
            "查看审批",
            "当前无需审批",
            "待验证",
        ):
            self.assertIn(label, dashboard)

    def test_dashboard_closes_harness_operation_user_paths(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        for marker in (
            "/api/operations.json",
            "/api/operations/preview",
            "startHarnessOperation",
            "refreshOperations",
            "operation-active",
            "operation-history",
        ):
            self.assertIn(marker, dashboard)
        for label in (
            "Harness 操作",
            "更新 Harness",
            "注入或升级项目",
            "修复 Agent 接入",
            "确认执行",
            "最近操作",
        ):
            self.assertIn(label, dashboard)
        self.assertNotIn("window.prompt", dashboard)
        self.assertNotIn("window.confirm", dashboard)

    def test_dashboard_shows_agent_five_layer_evidence_without_false_loaded_claims(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")
        self.assertIn("/api/agents.json", dashboard)
        self.assertIn("Code Agent 接入状态", dashboard)
        for label in ("发现", "注入", "加载", "遵循", "回写"):
            self.assertIn(f'{label}\"', dashboard)
        self.assertIn("待真实会话", dashboard)
        self.assertIn("尚无真实会话证据", dashboard)

    def test_dashboard_visualizes_skill_governance_without_false_load_claims(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        for marker in (
            "/api/skills.json",
            "renderSkills",
            "renderSettingsTabs",
            "skill-summary",
            "skill-list",
            "skill-finding",
            "openSettingsSection",
        ):
            self.assertIn(marker, dashboard)
        for label in (
            "能力与 Skill",
            "已发现",
            "已分配角色",
            "需人工审查",
            "已验证加载",
            "尚无运行证据",
            "重新扫描",
            "检查冲突",
        ):
            self.assertIn(label, dashboard)
        self.assertIn("不会联网下载、执行第三方脚本或修改现有 Agent 配置", dashboard)
        self.assertNotIn("Skill 已生效", dashboard)

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

    def test_role_projection_exposes_qa_gap_and_reviewer_scope(self) -> None:
        snapshot = {
            "work_rounds": {
                "delivery": {
                    "round_id": "delivery",
                    "role": "Executor",
                    "status": "completed",
                    "objective": "重构工作台布局",
                    "summary": "新页面已交付",
                    "next_role": "Reviewer",
                    "requirement_id": "task-ui",
                    "artifact_refs": ["web/observe-dashboard.html"],
                    "verification_refs": ["test:dashboard-layout"],
                    "derived_from_sequence": 10,
                },
                "review": {
                    "round_id": "review",
                    "role": "Reviewer",
                    "status": "completed",
                    "objective": "审查工作台交付",
                    "summary": "没有 blocking finding",
                    "requirement_id": "task-ui",
                    "derived_from_sequence": 20,
                },
            },
            "handoffs": {},
        }

        organization = OBSERVE.organization_snapshot(snapshot)
        qa = next(role for role in organization["roles"] if role["role_id"] == "QA")
        reviewer = next(role for role in organization["roles"] if role["role_id"] == "Reviewer")

        self.assertEqual(qa["participation"], "missing_independent_validation")
        self.assertEqual(organization["quality_gaps"][0]["requirement_id"], "task-ui")
        self.assertTrue(
            any(
                edge["kind"] == "quality_gate"
                and edge["from_role"] == "Executor"
                and edge["to_role"] == "QA"
                for edge in organization["transitions"]
            )
        )
        scope = reviewer["history"][0]["review_scope"]
        self.assertEqual(scope["requirement_id"], "task-ui")
        self.assertEqual(scope["artifacts"], ["web/observe-dashboard.html"])
        self.assertEqual(scope["verification_refs"], ["test:dashboard-layout"])

    def test_active_qa_round_does_not_suggest_reviewer_handoff_early(self) -> None:
        snapshot = {
            "work_rounds": {
                "delivery": {
                    "round_id": "delivery",
                    "role": "Executor",
                    "status": "completed",
                    "summary": "交付工作台交互",
                    "next_role": "QA",
                    "requirement_id": "task-ui",
                    "derived_from_sequence": 10,
                },
                "qa-active": {
                    "round_id": "qa-active",
                    "role": "QA",
                    "status": "active",
                    "summary": "正在进行人工视觉验收",
                    "next_role": "Reviewer",
                    "requirement_id": "task-ui",
                    "derived_from_sequence": 20,
                },
            },
            "handoffs": {},
        }

        organization = OBSERVE.organization_snapshot(snapshot)

        self.assertEqual(organization["current_role"], "QA")
        self.assertEqual(organization["current_transition"]["from_role"], "Executor")
        self.assertEqual(organization["current_transition"]["to_role"], "QA")
        self.assertFalse(
            any(
                edge["from_role"] == "QA" and edge["to_role"] == "Reviewer"
                for edge in organization["transitions"]
            )
        )

    def test_unregister_project_only_removes_invalid_registry_entry(self) -> None:
        invalid = self.project / "not-injected"
        invalid.mkdir()
        sentinel = invalid / "keep.txt"
        sentinel.write_text("must stay", encoding="utf-8")
        registry = self.project / "registered-projects"
        registry.write_text(f"{invalid}\n", encoding="utf-8")
        descriptor = OBSERVE.load_registered_projects(registry)[0]

        result = OBSERVE.unregister_project(descriptor["project_id"], registry)

        self.assertTrue(result["removed"])
        self.assertFalse(result["files_deleted"])
        self.assertEqual(registry.read_text(encoding="utf-8"), "")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "must stay")

    def test_dashboard_can_unregister_disconnected_projects_without_native_dialogs(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        for marker in ("project-unregister", "unregisterProject", "project-remove-confirm", "X-Harness-Action-Token"):
            self.assertIn(marker, dashboard)
        for label in ("移出工作台", "不会删除项目文件", "取消"):
            self.assertIn(label, dashboard)
        self.assertNotIn("window.confirm", dashboard)

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
        self.assertEqual([item["version"] for item in workspace["versions"]["items"]], ["0.2.0", "0.1.0"])
        self.assertFalse(workspace["versions"]["items"][0]["branch_exists"])
        self.assertTrue(workspace["versions"]["items"][1]["tag_exists"])
        self.assertNotIn("observed_status", workspace["versions"]["items"][1]["requirements"][0])
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

    def test_repository_snapshot_groups_multiple_worktrees_and_version_work_branches(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        docs = self.project / "docs"
        docs.mkdir()
        (docs / "VERSIONS.md").write_text(
            "# Versions\n\n## 0.18.0\n\n"
            "- Status: in_progress\n"
            "- Branch: main\n"
            "- Work Branches: feat/v0.18-brain, feat/design-refactor\n"
            "- Goal: 在一个工作台查看多个开发现场。\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture"], cwd=self.project, check=True)
        subprocess.run(["git", "add", "AGENTS.md", "docs/VERSIONS.md"], cwd=self.project, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture baseline"], cwd=self.project, check=True)
        subprocess.run(["git", "branch", "feat/v0.18-brain"], cwd=self.project, check=True)
        design_worktree = self.project.parent / f"{self.project.name}-design"
        subprocess.run(
            ["git", "worktree", "add", "-q", "-b", "feat/design-refactor", str(design_worktree)],
            cwd=self.project,
            check=True,
        )
        self.extra_worktrees.append(design_worktree)
        (design_worktree / "design-note.txt").write_text("uncommitted\n", encoding="utf-8")

        root_git = OBSERVE.git_workspace_snapshot(self.project)
        design_git = OBSERVE.git_workspace_snapshot(design_worktree)
        version_plan = OBSERVE.version_plan_snapshot(design_worktree, {"tasks": {}}, design_git)

        self.assertEqual(root_git["repository_id"], design_git["repository_id"])
        self.assertEqual(len(root_git["worktrees"]), 2)
        self.assertEqual(
            {item["branch"] for item in root_git["worktrees"]},
            {"main", "feat/design-refactor"},
        )
        design_state = next(item for item in design_git["worktrees"] if item["current"])
        self.assertEqual(design_state["branch"], "feat/design-refactor")
        self.assertEqual(design_state["dirty_count"], 1)
        version = version_plan["items"][0]
        self.assertEqual(version["branch"], "main")
        self.assertEqual(version["work_branches"], ["feat/v0.18-brain", "feat/design-refactor"])
        self.assertEqual(version["checked_out_work_branches"], ["feat/design-refactor"])
        self.assertFalse(version["branch_mismatch"])

    def test_dashboard_presents_one_repository_with_multiple_checked_out_workspaces(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        for label in ("同一仓库", "已检出工作区", "集成目标", "工作分支", "未检出"):
            self.assertIn(label, dashboard)
        for contract in ("git.repository_id", "git.worktrees", "version.work_branches"):
            self.assertIn(contract, dashboard)
        self.assertNotIn("活跃 Agent", dashboard)

    def test_version_plan_sorts_newest_first_by_semantic_version(self) -> None:
        docs = self.project / "docs"
        docs.mkdir()
        (docs / "VERSIONS.md").write_text(
            "# Versions\n\n## 0.2.0\n\n- Status: released\n\n"
            "## 0.10.0-beta.1\n\n- Status: planned\n\n"
            "## 0.10.0\n\n- Status: in_progress\n\n"
            "## 0.9.0\n\n- Status: released\n",
            encoding="utf-8",
        )

        result = OBSERVE.version_plan_snapshot(self.project, {"tasks": {}}, {"branches": [], "tags": []})

        self.assertEqual(
            [item["version"] for item in result["items"]],
            ["0.10.0", "0.10.0-beta.1", "0.9.0", "0.2.0"],
        )

    def test_current_version_projects_each_requirement_from_its_own_runtime_evidence(self) -> None:
        versions = {
            "items": [
                {
                    "version": "0.19.0",
                    "status": "in_progress",
                    "goal": "让每条需求的真实进度可读。",
                    "requirements": [
                        {"requirement_id": "task-done", "title": "已完成需求", "status": "completed"},
                        {"requirement_id": "task-qa", "title": "断线恢复", "status": "planned"},
                        {"requirement_id": "task-waiting", "title": "待开始需求", "status": "planned"},
                    ],
                }
            ]
        }
        snapshot = {
            "tasks": {"task-qa": {"status": "active"}},
            "work_rounds": {
                "round-dev": {
                    "round_id": "round-dev",
                    "requirement_id": "task-qa",
                    "role": "Executor",
                    "status": "completed",
                    "objective": "实现断线恢复",
                    "summary": "恢复逻辑已交付",
                    "artifact_refs": ["src/retry.py"],
                    "verification_refs": ["unit:retry"],
                    "derived_from_sequence": 10,
                },
                "round-qa": {
                    "round_id": "round-qa",
                    "requirement_id": "task-qa",
                    "role": "QA",
                    "status": "active",
                    "objective": "验证断线重试和状态恢复",
                    "summary": "正在覆盖断线、重启和重复请求",
                    "verification_refs": ["verify-retry"],
                    "derived_from_sequence": 20,
                },
                "round-unrelated": {
                    "round_id": "round-unrelated",
                    "requirement_id": "task-other",
                    "role": "Reviewer",
                    "status": "active",
                    "objective": "审查其他需求",
                    "summary": "不应混入当前版本需求",
                    "derived_from_sequence": 30,
                },
            },
            "verifications": [
                {
                    "verification_id": "verify-retry",
                    "task_id": "task-qa",
                    "result": "passed",
                    "check": "断线重试端到端",
                    "summary": "3 个场景通过",
                    "evidence_refs": [{"kind": "report", "label": "断线重试报告", "ref": "report:retry"}],
                    "derived_from_sequence": 21,
                }
            ],
            "blocks": {},
            "handoffs": {},
        }

        current = OBSERVE.current_version_snapshot(snapshot, versions)

        self.assertEqual(current["version"], "0.19.0")
        self.assertEqual(current["counts"], {"completed": 1, "in_progress": 1, "planned": 1, "blocked": 0})
        qa_requirement = next(item for item in current["requirements"] if item["requirement_id"] == "task-qa")
        self.assertEqual(qa_requirement["effective_status"], "in_progress")
        self.assertEqual(qa_requirement["current_role"], "QA")
        self.assertEqual([item["role"] for item in qa_requirement["role_path"]], ["Executor", "QA"])
        self.assertEqual(qa_requirement["role_path"][0]["status"], "completed")
        self.assertEqual(qa_requirement["role_path"][1]["status"], "active")
        self.assertEqual(qa_requirement["test"]["status"], "active")
        self.assertEqual(qa_requirement["test"]["scope"], "验证断线重试和状态恢复")
        self.assertEqual(qa_requirement["test"]["evidence_count"], 3)
        self.assertEqual(qa_requirement["test"]["evidence_refs"], ["断线重试报告"])
        self.assertNotIn("Reviewer", [item["role"] for item in qa_requirement["role_path"]])
        waiting = next(item for item in current["requirements"] if item["requirement_id"] == "task-waiting")
        self.assertEqual(waiting["test"]["message"], "尚未进入独立测试")
        self.assertEqual(waiting["role_path"], [])

        handoff = OBSERVE.current_version_snapshot(
            {
                "tasks": {},
                "work_rounds": {
                    "round-delivered": {
                        "round_id": "round-delivered",
                        "requirement_id": "task-handoff",
                        "role": "Executor",
                        "status": "completed",
                        "objective": "交付实现",
                        "derived_from_sequence": 1,
                    }
                },
                "handoffs": {
                    "handoff-qa": {
                        "handoff_id": "handoff-qa",
                        "requirement_id": "task-handoff",
                        "from_role": "Executor",
                        "to_role": "QA",
                        "summary": "等待独立验收",
                        "derived_from_sequence": 2,
                    }
                },
                "verifications": [],
                "blocks": {},
            },
            {
                "items": [
                    {
                        "version": "0.19.0",
                        "status": "in_progress",
                        "requirements": [
                            {"requirement_id": "task-handoff", "title": "等待 QA", "status": "planned"}
                        ],
                    }
                ]
            },
        )["requirements"][0]
        self.assertEqual(handoff["current_role"], "QA")
        self.assertEqual([item["role"] for item in handoff["role_path"]], ["Executor", "QA"])
        self.assertEqual(handoff["role_path"][-1]["status"], "waiting")
        self.assertIsNone(handoff["current_work"])
        self.assertEqual(handoff["next_step"], "等待 QA 接手")

    def test_v020_requirement_gates_reject_role_jumps_and_project_independent_stages(self) -> None:
        versions = {
            "items": [{
                "version": "0.20.0",
                "status": "in_progress",
                "requirements": [
                    {"requirement_id": "task-review", "title": "等待产品审查", "status": "planned"},
                    {"requirement_id": "task-dev", "title": "进入开发", "status": "planned"},
                    {"requirement_id": "task-qa", "title": "进入测试", "status": "planned"},
                    {"requirement_id": "task-release", "title": "等待发布", "status": "planned"},
                ],
            }]
        }

        def round_item(sequence, requirement_id, role, gate_result, **extra):
            return {
                "round_id": f"round-{requirement_id}-{sequence}",
                "requirement_id": requirement_id,
                "role": role,
                "status": "completed",
                "objective": f"{role} 处理 {requirement_id}",
                "gate_result": gate_result,
                "derived_from_sequence": sequence,
                **extra,
            }

        rounds = {
            "pm-review": round_item(1, "task-review", "PM", "ready_for_review", next_role="Reviewer"),
            # 这条 QA 事件必须保留审计，但不能让需求跳过产品审查和开发。
            "qa-jump": round_item(2, "task-review", "QA", "passed", verification_refs=["qa:jump"]),
            "pm-dev": round_item(3, "task-dev", "PM", "ready_for_review", next_role="Reviewer"),
            "review-dev": round_item(
                4, "task-dev", "Reviewer", "approved", review_mode="product_review", next_role="Executor"
            ),
            "pm-qa": round_item(5, "task-qa", "PM", "ready_for_review", next_role="Reviewer"),
            "review-qa": round_item(
                6, "task-qa", "Reviewer", "approved", review_mode="product_review", next_role="Executor"
            ),
            "dev-qa": round_item(
                7,
                "task-qa",
                "Executor",
                "delivered",
                next_role="QA",
                artifact_refs=["src/feature.py"],
                verification_refs=["unit:feature"],
            ),
            "pm-release": round_item(8, "task-release", "PM", "ready_for_review", next_role="Reviewer"),
            "review-release": round_item(
                9, "task-release", "Reviewer", "approved", review_mode="product_review", next_role="Executor"
            ),
            "dev-release": round_item(
                10,
                "task-release",
                "Executor",
                "delivered",
                next_role="QA",
                artifact_refs=["src/release.py"],
                verification_refs=["unit:release"],
            ),
            "qa-release": round_item(
                11, "task-release", "QA", "passed", verification_refs=["e2e:release"]
            ),
        }
        current = OBSERVE.current_version_snapshot(
            {"tasks": {}, "work_rounds": rounds, "handoffs": {}, "verifications": [], "blocks": {}},
            versions,
        )
        by_id = {item["requirement_id"]: item for item in current["requirements"]}

        self.assertEqual(by_id["task-review"]["workflow"]["stage"], "product_review")
        self.assertEqual(by_id["task-review"]["current_role"], "Reviewer")
        self.assertEqual(len(by_id["task-review"]["workflow"]["rejected_transitions"]), 1)
        self.assertIn("QA", by_id["task-review"]["workflow"]["rejected_transitions"][0]["reason"])
        self.assertEqual([item["role"] for item in by_id["task-review"]["role_path"]], ["PM"])

        self.assertEqual(by_id["task-dev"]["workflow"]["stage"], "development")
        self.assertEqual(by_id["task-dev"]["current_role"], "Executor")
        self.assertEqual(by_id["task-qa"]["workflow"]["stage"], "qa")
        self.assertEqual(by_id["task-qa"]["current_role"], "QA")
        self.assertEqual(by_id["task-release"]["workflow"]["stage"], "release_ready")
        self.assertIsNone(by_id["task-release"]["current_role"])

    def test_v020_product_review_changes_and_missing_delivery_evidence_block_progress(self) -> None:
        current = OBSERVE.current_version_snapshot(
            {
                "tasks": {},
                "handoffs": {},
                "verifications": [],
                "blocks": {},
                "work_rounds": {
                    "pm": {
                        "round_id": "pm",
                        "requirement_id": "task-gate",
                        "role": "PM",
                        "status": "completed",
                        "objective": "明确需求",
                        "gate_result": "ready_for_review",
                        "next_role": "Reviewer",
                        "derived_from_sequence": 1,
                    },
                    "review": {
                        "round_id": "review",
                        "requirement_id": "task-gate",
                        "role": "Reviewer",
                        "review_mode": "product_review",
                        "gate_result": "approved",
                        "status": "completed",
                        "objective": "审查产品逻辑",
                        "next_role": "Executor",
                        "derived_from_sequence": 2,
                    },
                    "dev": {
                        "round_id": "dev",
                        "requirement_id": "task-gate",
                        "role": "Executor",
                        "gate_result": "delivered",
                        "status": "completed",
                        "objective": "实现需求",
                        "artifact_refs": ["src/gate.py"],
                        "verification_refs": [],
                        "next_role": "QA",
                        "derived_from_sequence": 3,
                    },
                },
            },
            {"items": [{
                "version": "0.20.0",
                "status": "in_progress",
                "requirements": [{"requirement_id": "task-gate", "title": "门禁证据", "status": "planned"}],
            }]},
        )["requirements"][0]

        self.assertEqual(current["workflow"]["stage"], "development")
        self.assertEqual(current["current_role"], "Executor")
        self.assertIn("自检证据", current["workflow"]["rejected_transitions"][0]["reason"])

        changes = OBSERVE.requirement_workflow_snapshot(
            {"requirement_id": "task-changes", "status": "planned"},
            [
                {
                    "round_id": "pm-ready",
                    "role": "PM",
                    "status": "completed",
                    "gate_result": "ready_for_review",
                    "derived_from_sequence": 1,
                },
                {
                    "round_id": "review-changes",
                    "role": "Reviewer",
                    "review_mode": "product_review",
                    "status": "completed",
                    "gate_result": "changes_requested",
                    "summary": "取消后的数据状态尚未定义",
                    "derived_from_sequence": 2,
                },
            ],
            [],
        )
        self.assertEqual(changes["stage"], "product_definition")
        self.assertEqual(changes["current_role"], "PM")
        self.assertEqual(changes["gate_status"], "changes_requested")

    def test_v020_release_review_and_scope_change_are_distinct_from_product_review(self) -> None:
        def item(sequence, role, gate_result, **extra):
            return {
                "round_id": f"round-{sequence}",
                "role": role,
                "status": "completed",
                "gate_result": gate_result,
                "derived_from_sequence": sequence,
                **extra,
            }

        release = OBSERVE.requirement_workflow_snapshot(
            {"requirement_id": "task-risk", "status": "planned"},
            [
                item(1, "PM", "ready_for_review"),
                item(2, "Reviewer", "approved", review_mode="product_review"),
                item(3, "Executor", "delivered", artifact_refs=["src/risk.py"], verification_refs=["unit:risk"]),
                item(4, "QA", "passed", verification_refs=["e2e:risk"], next_role="Reviewer"),
                item(5, "Reviewer", "approved", review_mode="release_review"),
            ],
            [],
        )
        self.assertEqual(release["stage"], "release_ready")
        self.assertEqual(release["gate_status"], "approved")

        changed = OBSERVE.requirement_workflow_snapshot(
            {"requirement_id": "task-risk", "status": "planned"},
            [
                item(1, "PM", "ready_for_review"),
                item(2, "Reviewer", "approved", review_mode="product_review"),
                item(3, "Executor", "delivered", artifact_refs=["src/risk.py"], verification_refs=["unit:risk"]),
                item(4, "QA", "passed", verification_refs=["e2e:risk"]),
                item(5, "PM", "ready_for_review"),
            ],
            [],
        )
        self.assertEqual(changed["stage"], "product_review")
        self.assertEqual(changed["gate_status"], "scope_changed")
        self.assertEqual(changed["current_role"], "Reviewer")

    def test_v020_technical_only_exception_requires_a_reason_and_still_enters_qa(self) -> None:
        workflow = OBSERVE.requirement_workflow_snapshot(
            {"requirement_id": "task-fix", "status": "planned"},
            [{
                "round_id": "fix-delivery",
                "role": "Executor",
                "status": "completed",
                "gate_result": "delivered",
                "workflow_exception": "technical_only",
                "exception_reason": "只修复空指针，不改变任何用户行为",
                "artifact_refs": ["src/null_fix.py"],
                "verification_refs": ["regression:null-fix"],
                "derived_from_sequence": 1,
            }],
            [],
        )
        self.assertEqual(workflow["stage"], "qa")
        self.assertEqual(workflow["current_role"], "QA")
        self.assertEqual(workflow["gate_status"], "pending")

    def test_v020_version_checkbox_cannot_bypass_requirement_gates(self) -> None:
        requirement = OBSERVE.current_version_snapshot(
            {"tasks": {}, "work_rounds": {}, "handoffs": {}, "verifications": [], "blocks": {}},
            {"items": [{
                "version": "0.20.0",
                "status": "in_progress",
                "requirements": [{
                    "requirement_id": "task-checkbox",
                    "title": "不能只靠勾选完成",
                    "status": "completed",
                }],
            }]},
        )["requirements"][0]

        self.assertEqual(requirement["effective_status"], "planned")
        self.assertEqual(requirement["workflow"]["stage"], "product_definition")
        self.assertTrue(requirement["workflow"]["plan_conflict"])
        self.assertIn("版本清单已标记完成", requirement["workflow"]["gate_reason"])

    def test_work_round_contract_uses_structured_review_and_gate_fields(self) -> None:
        envelope = OBSERVE.build_work_envelope(
            self.project,
            event_type="work.round_completed",
            role="Reviewer",
            round_ref="review-product",
            requirement_id="task-178",
            objective="审查用户路径和边界情况",
            summary="无阻塞发现",
            status="completed",
            next_role="Executor",
            review_mode="product_review",
            gate_result="approved",
            idempotency_key="review-product",
        )
        self.assertEqual(envelope["payload"]["review_mode"], "product_review")
        self.assertEqual(envelope["payload"]["gate_result"], "approved")

        invalid = json.loads(json.dumps(envelope))
        invalid["payload"]["role"] = "QA"
        invalid["source"]["role"] = "QA"
        with self.assertRaisesRegex(OBSERVE.ObserveError, "review_mode"):
            OBSERVE.validate_ingest_envelope(invalid, OBSERVE.project_id(self.project))

    def test_dashboard_uses_current_version_requirement_command_center(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        for marker in (
            "current-version-requirements",
            "current-requirement-card",
            "requirement-role-path",
            "requirement-test-scope",
            "requirement-evidence",
            "state.workspace?.current_version",
        ):
            self.assertIn(marker, dashboard)
        for label in ("当前版本需求", "测试范围未记录", "尚未进入独立测试", "版本记录"):
            self.assertIn(label, dashboard)
        self.assertNotIn('["versions", "版本与需求"]', dashboard)

    def test_dashboard_explains_requirement_gate_and_rejected_transitions(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")
        for marker in (
            "requirement-gate",
            "workflow.stage_label",
            "workflow.gate_reason",
            "workflowTransitions",
            'selectedRequirement.current_role === "QA" ? "quality_gate" : "requirement_gate"',
            'participation: progress ? "recorded" : isCurrentRole ? "expected"',
            'transition.kind === "requirement_gate" ? "需求门禁"',
            "rejected_transitions",
            "未推进有效阶段",
        ):
            self.assertIn(marker, dashboard)

    def test_dashboard_embeds_latest_role_flow_inside_each_requirement(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")
        for marker in (
            "requirement-summary-button",
            "requirement-squad",
            "task-office",
            "task-office-scene",
            "requirementProcessRoles",
            "scope_requirement_id",
            "scope_transition",
            '["PM", "Reviewer", "Executor", "QA"]',
            '["PM", "Reviewer", "Designer", "Executor", "QA"]',
            "Designer 仅在实际参与时插入",
        ):
            self.assertIn(marker, dashboard)
        self.assertNotIn('root.append(office);', dashboard)

    def test_dashboard_preserves_current_version_requirement_across_refresh(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")

        for marker in (
            "const currentRequirements = state.workspace?.current_version?.requirements || [];",
            "const currentRequirementIds = new Set(currentRequirements.map(item => item.requirement_id));",
            "const taskIsCurrentRequirement = currentRequirementIds.has(state.taskId);",
            'state.view === "overview" && currentRequirements.length && !taskIsCurrentRequirement',
            "state.taskId = preferredRequirement.requirement_id;",
        ):
            self.assertIn(marker, dashboard)

    def test_completed_qa_round_is_visible_as_fallback_evidence(self) -> None:
        current = OBSERVE.current_version_snapshot(
            {
                "tasks": {},
                "work_rounds": {
                    "round-qa": {
                        "round_id": "round-qa",
                        "requirement_id": "task-qa-summary",
                        "role": "QA",
                        "status": "completed",
                        "objective": "验收工作台真实路径",
                        "summary": "桌面、窄屏与刷新路径均通过",
                        "derived_from_sequence": 10,
                    }
                },
                "handoffs": {},
                "verifications": [],
                "blocks": {},
            },
            {
                "items": [{
                    "version": "0.19.0",
                    "status": "in_progress",
                    "requirements": [{
                        "requirement_id": "task-qa-summary",
                        "title": "展示 QA 验收结论",
                        "status": "completed",
                    }],
                }]
            },
        )["requirements"][0]

        self.assertEqual(current["test"]["status"], "completed")
        self.assertEqual(current["test"]["evidence_count"], 1)
        self.assertEqual(current["test"]["evidence_refs"], ["QA 回写：桌面、窄屏与刷新路径均通过"])
        self.assertIsNone(current["current_role"])

    def test_completed_requirement_suppresses_stale_role_flow(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")
        self.assertIn(
            'selectedRequirement?.effective_status === "completed" ? []',
            dashboard,
        )

    def test_role_detail_prefers_version_requirement_title_over_colliding_plan_step(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")
        start = dashboard.index("function requirementTitle")
        end = dashboard.index("function decisionsForRole", start)
        requirement_title = dashboard[start:end]

        self.assertIn("state.workspace?.current_version?.requirements", requirement_title)
        self.assertIn("versionRequirement?.title", requirement_title)
        self.assertLess(
            requirement_title.index("versionRequirement?.title"),
            requirement_title.index("state.snapshot.tasks?.[requirementId]?.title"),
        )

    def test_harness_improvement_workbench_has_separate_authenticated_lifecycle(self) -> None:
        dashboard = DASHBOARD.read_text(encoding="utf-8")
        observe = SCRIPT.read_text(encoding="utf-8")

        for marker in (
            "Harness 改进", "提交为 Harness 问题", "跨项目", "Rule", "Skill", "Checker", "Profile",
            "登记已落地", "记录效果复验",
        ):
            self.assertIn(marker, dashboard)
        for marker in (
            "HARNESS_IMPROVEMENTS_PATH", "/api/harness/improvements", "submit", "approve",
            "mark-implemented", "verify-effect", "unauthorized-action",
        ):
            self.assertIn(marker, observe)

    def test_harness_improvement_http_create_submit_and_approve_are_authenticated(self) -> None:
        (self.project / "AGENTS.md").write_text("# Harness\n", encoding="utf-8")
        self.write_plan(plan_text())
        state_dir = self.project / "private-state"
        state_dir.mkdir()
        (state_dir / "registered-projects").write_text(f"{self.project}\n", encoding="utf-8")
        brain = OBSERVE.load_brain_boundary()
        memory = brain.process_observer_event(
            "fixture-ui",
            {
                "project_id": "fixture-ui",
                "idempotency_key": "fixture-overflow",
                "type": "work.round_completed",
                "source": {"producer": "test"},
                "payload": {"status": "completed", "summary": "窄屏按钮出现横向溢出"},
            },
        )
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        process = subprocess.Popen(
            [sys.executable, str(SCRIPT), "watch", "--all", "--port", str(port), "--scan-interval", "0.1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
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

            with urlopen(f"{base}/api/brain/status.json", timeout=1) as response:
                action_token = json.loads(response.read())["action_token"]
            create_url = f"{base}/api/harness/improvements"
            create_body = json.dumps({
                "memory_id": memory["memory_id"],
                "target": "checker",
                "summary": "窄屏按钮必须检查横向溢出",
            }).encode("utf-8")
            with self.assertRaises(HTTPError) as unauthenticated:
                urlopen(Request(create_url, data=create_body, headers={"Content-Type": "application/json"}), timeout=1)
            self.assertEqual(unauthenticated.exception.code, 401)
            headers = {"Content-Type": "application/json", "X-Harness-Action-Token": action_token}
            oversized_body = b"{" + (b" " * (OBSERVE.MAX_OPERATION_BODY + 1)) + b"}"
            with self.assertRaises(HTTPError) as oversized:
                urlopen(Request(create_url, data=oversized_body, headers=headers), timeout=1)
            self.assertEqual(oversized.exception.code, 413)
            with urlopen(Request(create_url, data=create_body, headers=headers), timeout=1) as response:
                candidate = json.loads(response.read())
            self.assertEqual(candidate["status"], "observed")

            submit_url = f"{create_url}/{candidate['improvement_id']}/submit"
            with urlopen(Request(submit_url, data=b'{"confirmed": true}', headers=headers), timeout=1) as response:
                submitted = json.loads(response.read())
            self.assertEqual(submitted["status"], "pending_approval")
            approve_url = f"{create_url}/{candidate['improvement_id']}/approve"
            with urlopen(Request(approve_url, data=b"{}", headers=headers), timeout=1) as response:
                approved = json.loads(response.read())
            self.assertEqual(approved["status"], "approved")
            with urlopen(f"{base}/api/harness/improvements.json", timeout=1) as response:
                listed = json.loads(response.read())["items"]
            self.assertEqual(listed[0]["proposal_path"], approved["proposal_path"])
        finally:
            process.terminate()
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=2)

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

        self.assertEqual(artifact["versions"], ["0.2.0", "0.1.0"])
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

        for label in ("产物", "版本", "Markdown 阅读", "代码产物", "版本与 Git 关系", "版本需求"):
            self.assertIn(label, dashboard)
        for label in ("工作区", "当前分支", "发布标签", "未分配分支"):
            self.assertIn(label, dashboard)
        self.assertNotIn("当前正在这条分支开发", dashboard)
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

            invalid_id = portfolio["projects"][1]["project_id"]
            removal_body = json.dumps({"confirmed": True}).encode("utf-8")
            with self.assertRaises(HTTPError) as unauthorized_removal:
                urlopen(
                    Request(
                        f"{base}/api/projects/{invalid_id}/unregister",
                        data=removal_body,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    ),
                    timeout=1,
                )
            self.assertEqual(unauthorized_removal.exception.code, 401)
            with urlopen(f"{base}/api/operations.json", timeout=1) as response:
                action_token = json.loads(response.read())["action_token"]
            with urlopen(
                Request(
                    f"{base}/api/projects/{invalid_id}/unregister",
                    data=removal_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Harness-Action-Token": action_token,
                    },
                    method="POST",
                ),
                timeout=1,
            ) as response:
                removal = json.loads(response.read())
            self.assertTrue(removal["removed"])
            self.assertFalse(removal["files_deleted"])
            with urlopen(f"{base}/api/portfolio.json", timeout=1) as response:
                refreshed_portfolio = json.loads(response.read())
            self.assertEqual([item["project_id"] for item in refreshed_portfolio["projects"]], [valid_id])
        finally:
            process.terminate()
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=2)

    def test_operation_http_preview_confirmation_and_status_are_authenticated(self) -> None:
        state_dir = self.project / "state"
        state_dir.mkdir()
        (state_dir / "registered-projects").write_text("", encoding="utf-8")
        target = self.project / "new-project"
        target.mkdir()
        fake_harness = self.project / "fake-harness"
        fake_bin = fake_harness / "bin"
        fake_bin.mkdir(parents=True)
        fake_cli = fake_bin / "harness"
        fake_cli.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = init ]; then\n"
            "  printf '# Injected by isolated test\\n' > \"$2/AGENTS.md\"\n"
            "  exit 0\n"
            "fi\n"
            "exit 64\n",
            encoding="utf-8",
        )
        fake_cli.chmod(0o755)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(self.project / "home"),
                "MICK_HARNESS_ROOT": str(fake_harness),
                "MICK_HARNESS_STATE_DIR": str(state_dir),
                "MICK_HARNESS_STATE_ROOT": str(state_dir),
                "MICK_HARNESS_OBSERVER_AUTO_INSTALL": "0",
                "MICK_HARNESS_ACTIVITY": "0",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
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
                process.terminate()
                stdout, stderr = process.communicate(timeout=1)
                self.fail(f"operation server did not start\nstdout={stdout}\nstderr={stderr}")

            with urlopen(f"{base}/api/skills.json", timeout=1) as response:
                skills = json.loads(response.read())
            self.assertEqual(skills["boundaries"]["read_only"], True)
            self.assertEqual(skills["boundaries"]["scripts_executed"], False)
            self.assertIn("discovered", skills["summary"])
            with self.assertRaises(HTTPError) as arbitrary_path:
                urlopen(f"{base}/api/skills.json?path={quote('/etc')}", timeout=1)
            self.assertEqual(arbitrary_path.exception.code, 400)

            with urlopen(f"{base}/api/operations.json", timeout=1) as response:
                operations = json.loads(response.read())
            self.assertEqual(len(operations["catalog"]), 3)
            action_token = operations["action_token"]
            preview_body = json.dumps(
                {"action": "project-init", "parameters": {"project_path": str(target)}}
            ).encode("utf-8")
            with self.assertRaises(HTTPError) as unauthorized:
                urlopen(
                    Request(
                        f"{base}/api/operations/preview",
                        data=preview_body,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    ),
                    timeout=1,
                )
            self.assertEqual(unauthorized.exception.code, 401)

            with urlopen(
                Request(
                    f"{base}/api/operations/preview",
                    data=preview_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Harness-Action-Token": action_token,
                    },
                    method="POST",
                ),
                timeout=1,
            ) as response:
                preview = json.loads(response.read())
            self.assertEqual(preview["status"], "prepared")
            operation_id = preview["operation_id"]

            execute_body = json.dumps({"confirmation_token": preview["confirmation_token"]}).encode("utf-8")
            with urlopen(
                Request(
                    f"{base}/api/operations/{operation_id}/execute",
                    data=execute_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Harness-Action-Token": action_token,
                    },
                    method="POST",
                ),
                timeout=1,
            ) as response:
                queued = json.loads(response.read())
            self.assertIn(queued["status"], {"queued", "running", "succeeded"})

            for _ in range(100):
                with urlopen(f"{base}/api/operations/{operation_id}.json", timeout=1) as response:
                    current = json.loads(response.read())
                if current["status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.05)
            self.assertEqual(current["status"], "succeeded", current)
            self.assertTrue((target / "AGENTS.md").is_file())
            self.assertTrue((state_dir / "operations" / "audit.jsonl").is_file())
            self.assertNotIn("confirmation_token", json.dumps(current))
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

            self.assertIsNone(process.poll(), "global observer stopped after project registration")
            with urlopen(f"{base}/api/portfolio.json", timeout=1) as response:
                portfolio = json.loads(response.read())
            self.assertEqual(
                [item["project_id"] for item in portfolio["projects"]],
                [OBSERVE.project_id(self.project)],
            )

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

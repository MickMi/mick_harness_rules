from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
SCRIPT = ROOT / "scripts" / "harness-agent-manager.py"
REGISTRY = ROOT / "config" / "agent-registry.json"
BRAIN_SCRIPT = ROOT / "scripts" / "harness-brain-boundary.py"


def load_manager():
    spec = importlib.util.spec_from_file_location("harness_agent_manager", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgentRegistryTests(unittest.TestCase):
    def test_registry_has_unique_supported_agents_and_explicit_boundaries(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        agents = registry["agents"]
        ids = [agent["id"] for agent in agents]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(registry["schema_version"], "1")
        self.assertEqual(
            {agent["id"] for agent in agents},
            {"claude-code", "codex", "cursor", "windsurf", "cline", "roo-code", "trae"},
        )
        for agent in agents:
            self.assertIn(agent["tier"], {1, 2})
            self.assertTrue(agent["detection"])
            self.assertIn("loader", agent)
            self.assertIn("lifecycle", agent)
            self.assertIn("limitations", agent)
        tier_one = {agent["id"] for agent in agents if agent["tier"] == 1}
        self.assertEqual(tier_one, {"claude-code", "codex"})


class AgentManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.home = self.root / "home"
        self.bin_dir = self.root / "bin"
        self.apps_dir = self.root / "Applications"
        self.home.mkdir()
        self.bin_dir.mkdir()
        self.apps_dir.mkdir()
        self.manager = load_manager()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["MICK_HARNESS_ROOT"] = str(ROOT)
        env["MICK_HARNESS_ACTIVITY"] = "0"
        return subprocess.run(
            [str(ROOT / "bin" / "harness"), "agents", *args],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_scan_uses_command_config_app_and_extension_signals(self) -> None:
        (self.bin_dir / "claude").write_text("", encoding="utf-8")
        (self.home / ".codex").mkdir()
        (self.apps_dir / "Cursor.app").mkdir()
        extensions = self.home / ".vscode" / "extensions"
        extensions.mkdir(parents=True)
        (extensions / "saoudrizwan.claude-dev-3.0.0").mkdir()

        report = self.manager.build_report(
            self.manager.load_registry(REGISTRY),
            home=self.home,
            bin_dirs=[self.bin_dir],
            app_dirs=[self.apps_dir],
        )
        agents = {agent["id"]: agent for agent in report["agents"]}

        self.assertTrue(agents["claude-code"]["detected"])
        self.assertIn("command", {signal["kind"] for signal in agents["claude-code"]["signals"] if signal["found"]})
        self.assertTrue(agents["codex"]["detected"])
        self.assertIn("config_dir", {signal["kind"] for signal in agents["codex"]["signals"] if signal["found"]})
        self.assertTrue(agents["cursor"]["detected"])
        self.assertIn("app", {signal["kind"] for signal in agents["cursor"]["signals"] if signal["found"]})
        self.assertTrue(agents["cline"]["detected"])
        self.assertIn("extension", {signal["kind"] for signal in agents["cline"]["signals"] if signal["found"]})

    def test_doctor_json_contract_does_not_claim_loaded_from_file_presence(self) -> None:
        codex_dir = self.home / ".codex"
        codex_dir.mkdir()
        (codex_dir / "AGENTS.md").write_text(
            "<!-- MICK-HARNESS-GLOBAL:BEGIN — auto-managed by harness agents sync -->\n"
            "rules\n<!-- MICK-HARNESS-GLOBAL:END -->\n",
            encoding="utf-8",
        )
        report = self.manager.build_report(
            self.manager.load_registry(REGISTRY),
            home=self.home,
            bin_dirs=[self.bin_dir],
            app_dirs=[self.apps_dir],
        )
        codex = next(agent for agent in report["agents"] if agent["id"] == "codex")

        self.assertEqual(report["schema_version"], "1")
        self.assertEqual(codex["injection"]["status"], "injected")
        self.assertEqual(codex["loading"]["status"], "unverified")
        self.assertEqual(codex["execution"]["status"], "unverified")
        self.assertEqual(codex["feedback"]["status"], "unverified")
        self.assertTrue(any(issue["code"] == "load-proof-missing" for issue in codex["issues"]))

    def test_harness_agents_doctor_json_is_stable_cli(self) -> None:
        result = self.run_cli("doctor", "--json", "--home", str(self.home))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "1")
        self.assertEqual(len(payload["agents"]), 7)
        self.assertIn("detected", payload["summary"])

    def test_cli_version_prefers_declared_product_version_over_git_tag(self) -> None:
        env = os.environ.copy()
        env["MICK_HARNESS_ROOT"] = str(ROOT)
        env["MICK_HARNESS_ACTIVITY"] = "0"
        result = subprocess.run(
            [str(ROOT / "bin" / "harness"), "version"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"Mick Agent Harness {PRODUCT_VERSION}", result.stdout)

    def tier_one_registry(self, agent_id: str = "codex") -> dict:
        registry = self.manager.load_registry(REGISTRY)
        return {**registry, "agents": [agent for agent in registry["agents"] if agent["id"] == agent_id]}

    def test_sync_is_dry_run_atomic_idempotent_and_preserves_user_content(self) -> None:
        target = self.home / ".codex" / "AGENTS.md"
        target.parent.mkdir()
        original = "# My own instructions\n\nKeep this.\n"
        target.write_text(original, encoding="utf-8")
        registry = self.tier_one_registry()

        preview = self.manager.sync_agents(registry, home=self.home, dry_run=True)
        self.assertTrue(preview[0]["changed"])
        self.assertEqual(target.read_text(encoding="utf-8"), original)

        first = self.manager.sync_agents(registry, home=self.home, dry_run=False)
        first_bytes = target.read_bytes()
        second = self.manager.sync_agents(registry, home=self.home, dry_run=False)

        self.assertTrue(first[0]["changed"])
        self.assertFalse(second[0]["changed"])
        self.assertEqual(target.read_bytes(), first_bytes)
        self.assertEqual(target.read_text(encoding="utf-8").count("MICK-HARNESS-GLOBAL:BEGIN"), 1)
        self.assertIn("# My own instructions", target.read_text(encoding="utf-8"))
        self.assertEqual(target.with_name("AGENTS.md.mick-harness.bak").read_text(encoding="utf-8"), original)

    def test_migrate_removes_only_legacy_managed_block_and_is_idempotent(self) -> None:
        target = self.home / ".codex" / "AGENTS.md"
        target.parent.mkdir()
        target.write_text(
            "<!-- MICK-HARNESS-CODEX:BEGIN -->\nold\n<!-- MICK-HARNESS-CODEX:END -->\n\n"
            "# User content\n",
            encoding="utf-8",
        )
        registry = self.tier_one_registry()

        first = self.manager.sync_agents(registry, home=self.home, dry_run=False, migrate=True)
        first_bytes = target.read_bytes()
        second = self.manager.sync_agents(registry, home=self.home, dry_run=False, migrate=True)

        text = target.read_text(encoding="utf-8")
        self.assertTrue(first[0]["changed"])
        self.assertFalse(second[0]["changed"])
        self.assertEqual(target.read_bytes(), first_bytes)
        self.assertNotIn("MICK-HARNESS-CODEX", text)
        self.assertIn("# User content", text)

    def test_conflicting_marker_refuses_to_write(self) -> None:
        target = self.home / ".codex" / "AGENTS.md"
        target.parent.mkdir()
        original = "<!-- MICK-HARNESS-GLOBAL:BEGIN -->\nunclosed\n"
        target.write_text(original, encoding="utf-8")

        with self.assertRaises(self.manager.AgentManagerError):
            self.manager.sync_agents(self.tier_one_registry(), home=self.home, dry_run=False)

        self.assertEqual(target.read_text(encoding="utf-8"), original)

    def test_atomic_replace_failure_keeps_original_and_removes_temporary_file(self) -> None:
        target = self.home / "loader.md"
        target.write_text("old", encoding="utf-8")

        with mock.patch.object(self.manager.os, "replace", side_effect=OSError("injected replace failure")):
            with self.assertRaises(OSError):
                self.manager._atomic_write(target, "new", backup=False)

        self.assertEqual(target.read_text(encoding="utf-8"), "old")
        self.assertEqual(list(self.home.glob(".loader.md.*.tmp")), [])

    def test_hook_sync_is_reviewable_preserves_existing_hooks_and_is_idempotent(self) -> None:
        claude_settings = self.home / ".claude" / "settings.json"
        claude_settings.parent.mkdir()
        claude_settings.write_text(
            json.dumps({"theme": "dark", "hooks": {"SessionEnd": [{"hooks": [{"type": "command", "command": "keep-me"}]}]}}),
            encoding="utf-8",
        )
        registry = self.manager.load_registry(REGISTRY)

        preview = self.manager.sync_hooks(registry, home=self.home, dry_run=True)
        self.assertTrue(any(change["changed"] for change in preview))
        self.assertNotIn("harness-observe-hook.py", claude_settings.read_text(encoding="utf-8"))

        self.manager.sync_hooks(registry, home=self.home, dry_run=False)
        first_claude = claude_settings.read_bytes()
        first_codex = (self.home / ".codex" / "hooks.json").read_bytes()
        second = self.manager.sync_hooks(registry, home=self.home, dry_run=False)

        claude = json.loads(first_claude)
        codex = json.loads(first_codex)
        self.assertEqual(claude["theme"], "dark")
        self.assertIn("keep-me", json.dumps(claude))
        for event in ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"):
            self.assertIn("harness-observe-hook.py", json.dumps(claude["hooks"][event]))
            self.assertIn("--platform claude", json.dumps(claude["hooks"][event]))
            self.assertIn("--platform codex", json.dumps(codex["hooks"][event]))
        self.assertIn("session-start.sh", json.dumps(claude["hooks"]["SessionStart"]))
        self.assertTrue(all(not change["changed"] for change in second))

        report = self.manager.build_report(registry, home=self.home, bin_dirs=[self.bin_dir], app_dirs=[self.apps_dir])
        records = {agent["id"]: agent for agent in report["agents"]}
        self.assertEqual(records["claude-code"]["loading"]["status"], "hook_configured")
        self.assertEqual(records["codex"]["loading"]["status"], "hook_configured")
        self.assertEqual(records["codex"]["execution"]["status"], "unverified")


class BrainBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.state = Path(self.tempdir.name) / "state"
        spec = importlib.util.spec_from_file_location("harness_brain_boundary", BRAIN_SCRIPT)
        assert spec is not None and spec.loader is not None
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.patch = mock.patch.dict(os.environ, {"MICK_HARNESS_STATE_ROOT": str(self.state)})
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        self.tempdir.cleanup()

    def test_candidate_is_redacted_deduplicated_and_public_output_has_no_body(self) -> None:
        secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
        first = self.module.create_candidate(kind="preference", layer="project", project="demo", summary=f"Use {secret} at {Path.home()}/private")
        second = self.module.create_candidate(kind="preference", layer="project", project="demo", summary=f"Use {secret} at {Path.home()}/private")
        public = self.module.public_metadata(first)

        self.assertEqual(first["candidate_id"], second["candidate_id"])
        self.assertNotIn(secret, json.dumps(first))
        self.assertNotIn(str(Path.home()), json.dumps(first))
        self.assertNotIn("summary", public)
        self.assertRegex(public["summary_digest"], r"^sha256:[a-f0-9]{64}$")

    def test_write_requires_confirmation_and_dry_run_hides_summary(self) -> None:
        record = self.module.create_candidate(kind="gotcha", layer="session", summary="Never expose transcript text")
        with self.assertRaises(self.module.BrainBoundaryError):
            self.module.approve(record["candidate_id"], yes=False, dry_run=True)

        result = self.module.approve(record["candidate_id"], yes=True, dry_run=True)
        self.assertEqual(result["status"], "approved_dry_run")
        self.assertNotIn("Never expose transcript text", json.dumps(result))
        stored = json.loads((self.state / "brain-candidates" / f"{record['candidate_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["status"], "pending_confirmation")

    def test_project_event_is_written_without_confirmation_and_deduplicated(self) -> None:
        brain = Path(self.tempdir.name) / "brain"
        with mock.patch.dict(os.environ, {"MICK_BRAIN_ROOT": str(brain)}):
            envelope = {
                "project_id": "demo-123",
                "idempotency_key": "round:completed:1",
                "type": "work.round_completed",
                "subject_id": "round-1",
                "source": {"producer": "codex-hook", "role": "Executor"},
                "payload": {
                    "status": "completed",
                    "requirement_id": "task-1",
                    "objective": "交付项目记忆",
                    "summary": "验证通过并完成交付",
                    "artifact_refs": ["docs/result.md"],
                },
            }
            first = self.module.process_observer_event("demo-123", envelope)
            second = self.module.process_observer_event("demo-123", envelope)
            corrected = self.module.correct_project_memory(first["memory_id"], summary="修正后的项目结论")

        self.assertEqual(first["action"], "recorded_project_memory")
        self.assertEqual(second["action"], "duplicate")
        self.assertEqual(first["status"], "written_local")
        target = brain / "projects" / "demo-123" / "learnings.md"
        self.assertEqual(target.read_text(encoding="utf-8").count("验证通过并完成交付"), 1)
        self.assertIn("修正后的项目结论", target.read_text(encoding="utf-8"))
        activity = self.module.list_project_memories(project="demo-123")
        self.assertEqual(len(activity), 2)
        self.assertEqual(corrected["sync_status"], "pending")

    def test_unconfirmed_or_noisy_events_do_not_enter_project_brain(self) -> None:
        cases = [
            ("work.round_started", {"status": "active", "objective": "仍在进行"}),
            ("decision.recorded", {"status": "proposed", "title": "猜测", "summary": "尚未确认"}),
            ("agent.turn_observed", {"state": "turn_completed", "platform": "codex"}),
        ]
        for index, (event_type, payload) in enumerate(cases):
            result = self.module.process_observer_event(
                "demo-123",
                {
                    "project_id": "demo-123",
                    "idempotency_key": f"ignored:{index}",
                    "type": event_type,
                    "subject_id": f"subject-{index}",
                    "source": {"producer": "test"},
                    "payload": payload,
                },
            )
            self.assertEqual(result["action"], "ignored")
        self.assertEqual(self.module.list_project_memories(project="demo-123"), [])

    def test_global_candidate_supports_edit_reject_and_retryable_status(self) -> None:
        record = self.module.create_candidate(
            kind="preference", layer="global", summary="默认使用简洁中文", project="demo"
        )
        changed = self.module.update_candidate(
            record["candidate_id"], summary="默认使用简洁、直接的中文", layer="global"
        )
        self.assertEqual(changed["status"], "pending_confirmation")
        self.assertIn("简洁、直接", self.module.get_candidate(record["candidate_id"])["summary"])
        rejected = self.module.reject(record["candidate_id"], reason="只适用于本项目")
        self.assertEqual(rejected["status"], "rejected")
        retried = self.module.retry(record["candidate_id"])
        self.assertEqual(retried["status"], "pending_confirmation")

    def test_candidates_support_scope_change_merge_and_ignore_similar(self) -> None:
        first = self.module.create_candidate(
            kind="gotcha", layer="global", project="app-a", summary="移动端页面出现横向溢出"
        )
        second = self.module.create_candidate(
            kind="gotcha", layer="global", project="app-b", summary="移动端页面再次出现横向溢出问题"
        )
        third = self.module.create_candidate(
            kind="preference", layer="global", project="app-c", summary="界面保持较低信息密度"
        )

        candidates = {item["candidate_id"]: item for item in self.module.list_candidates()}
        self.assertIn(second["candidate_id"], candidates[first["candidate_id"]]["similar_candidate_ids"])

        changed = self.module.update_candidate(
            third["candidate_id"], layer="profile", profile="designer-craft"
        )
        self.assertEqual(changed["layer"], "profile")
        self.assertEqual(changed["profile"], "designer-craft")

        merged = self.module.merge_candidates(
            first["candidate_id"], [second["candidate_id"]], summary="移动端布局必须验证横向溢出"
        )
        self.assertEqual(merged["occurrence_count"], 2)
        self.assertEqual(self.module.get_candidate(second["candidate_id"])["status"], "merged")

        ignored = self.module.ignore_similar_candidates(first["candidate_id"])
        self.assertEqual(ignored["status"], "ignored_similar")
        future = self.module.create_candidate(
            kind="gotcha", layer="global", project="app-d", summary="移动端布局必须再次验证横向溢出"
        )
        self.assertEqual(future["status"], "ignored_similar")

    def test_project_memories_can_be_explicitly_merged(self) -> None:
        brain = Path(self.tempdir.name) / "brain"
        with mock.patch.dict(os.environ, {"MICK_BRAIN_ROOT": str(brain)}):
            memories = []
            for index, summary in enumerate(("首页窄屏出现横向溢出", "首页移动端出现横向溢出"), start=1):
                memories.append(
                    self.module.process_observer_event(
                        "demo-ui",
                        {
                            "project_id": "demo-ui",
                            "idempotency_key": f"ui-layout-{index}",
                            "type": "work.round_completed",
                            "source": {"producer": "codex-hook"},
                            "payload": {"status": "completed", "summary": summary},
                        },
                    )
                )
            listed = {item["memory_id"]: item for item in self.module.list_project_memories(project="demo-ui")}
            self.assertIn(memories[1]["memory_id"], listed[memories[0]["memory_id"]]["similar_memory_ids"])
            merged = self.module.merge_project_memories(
                [item["memory_id"] for item in memories], summary="首页必须通过窄屏横向溢出检查"
            )

        self.assertEqual(merged["status"], "written_local")
        self.assertEqual(merged["occurrence_count"], 2)
        remaining = self.module.list_project_memories(project="demo-ui")
        self.assertEqual([item["memory_id"] for item in remaining], [merged["memory_id"]])

    def test_health_separates_local_write_from_remote_sync(self) -> None:
        brain = Path(self.tempdir.name) / "brain"
        brain.mkdir()
        health = self.module.health_snapshot(brain=brain)
        self.assertTrue(health["repository"]["exists"])
        self.assertIn("local_write", health)
        self.assertIn("remote_sync", health)
        self.assertNotEqual(health["local_write"]["status"], health["remote_sync"]["status"])

    def test_health_exposes_actual_repository_branch_and_write_routes(self) -> None:
        brain = Path(self.tempdir.name) / "brain"
        remote = Path(self.tempdir.name) / "brain-remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "memory-main", str(brain)], check=True)
        subprocess.run(["git", "-C", str(brain), "remote", "add", "origin", str(remote)], check=True)

        with mock.patch.dict(os.environ, {"MICK_BRAIN_ROOT": str(brain)}), mock.patch.object(
            self.module, "configured_brain_remote", return_value=str(remote)
        ):
            memory = self.module.process_observer_event(
                "demo-123",
                {
                    "project_id": "demo-123",
                    "type": "work.round_completed",
                    "idempotency_key": "brain-route",
                    "source": {"producer": "codex-hook"},
                    "payload": {"status": "completed", "summary": "记录真实写入路径"},
                },
            )
            original_path = self.state / "brain-project-memory" / "demo-123" / f"{memory['memory_id']}.json"
            duplicate = json.loads(original_path.read_text(encoding="utf-8"))
            duplicate["memory_id"] = "project_memory_aaaaaaaaaaaaaaaaaaaa"
            (original_path.parent / f"{duplicate['memory_id']}.json").write_text(json.dumps(duplicate), encoding="utf-8")
            health = self.module.health_snapshot(brain=brain)

        self.assertEqual(health["repository"]["remote"], str(remote))
        self.assertEqual(health["repository"]["branch"], "memory-main")
        self.assertEqual(health["repository"]["path"], str(brain))
        self.assertEqual(health["local_write"]["project_memory_count"], 1)
        self.assertEqual(health["local_write"]["project_memory_record_count"], 2)
        self.assertEqual(health["remote_sync"]["pending_local_records"], 2)
        project_route = next(item for item in health["write_routes"] if item["route_id"] == "project-memory")
        self.assertEqual(project_route["destination"], "projects/")
        self.assertEqual(project_route["sources"], [{"name": "codex-hook", "records": 2}])
        global_route = next(item for item in health["write_routes"] if item["route_id"] == "global-memory")
        profile_route = next(item for item in health["write_routes"] if item["route_id"] == "profile-memory")
        self.assertEqual(global_route["approval_scope"], "跨项目稳定偏好与可复用经验")
        self.assertEqual(profile_route["approval_scope"], "Profile 规则或风格的版本变化")

    def test_sync_pending_pushes_only_brain_routes_and_marks_records_synced(self) -> None:
        brain = Path(self.tempdir.name) / "brain"
        remote = Path(self.tempdir.name) / "brain-remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(brain)], check=True)
        subprocess.run(["git", "-C", str(brain), "config", "user.email", "fixture@example.test"], check=True)
        subprocess.run(["git", "-C", str(brain), "config", "user.name", "Fixture"], check=True)
        (brain / "MEMORY.md").write_text("# Brain\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(brain), "add", "MEMORY.md"], check=True)
        subprocess.run(["git", "-C", str(brain), "commit", "-qm", "baseline"], check=True)
        subprocess.run(["git", "-C", str(brain), "remote", "add", "origin", str(remote)], check=True)
        subprocess.run(["git", "-C", str(brain), "push", "-qu", "origin", "main"], check=True)

        with mock.patch.dict(os.environ, {"MICK_BRAIN_ROOT": str(brain)}), mock.patch.object(
            self.module, "configured_brain_remote", return_value=str(remote)
        ):
            memory = self.module.process_observer_event(
                "demo-123",
                {
                    "project_id": "demo-123",
                    "type": "work.round_completed",
                    "idempotency_key": "brain-sync",
                    "source": {"producer": "harness-agent"},
                    "payload": {"status": "completed", "summary": "需要同步的项目结论"},
                },
            )
            global_file = brain / "global" / "preferences.md"
            global_file.parent.mkdir()
            global_file.write_text("# Preferences\n\n- 用户手动确认的本地提交\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(brain), "add", "global/preferences.md"], check=True)
            subprocess.run(["git", "-C", str(brain), "commit", "-qm", "brain: local preference"], check=True)
            preview = self.module.sync_pending(confirmed=False, dry_run=True, brain=brain)
            with self.assertRaises(self.module.BrainBoundaryError):
                self.module.sync_pending(confirmed=False, dry_run=False, brain=brain)
            (brain / "personal-note.md").write_text("user-owned staging\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(brain), "add", "personal-note.md"], check=True)
            with self.assertRaisesRegex(self.module.BrainBoundaryError, "管理范围外"):
                self.module.sync_pending(confirmed=False, dry_run=True, brain=brain)
            with self.assertRaisesRegex(self.module.BrainBoundaryError, "管理范围外"):
                self.module.sync_pending(confirmed=True, dry_run=False, brain=brain)
            subprocess.run(["git", "-C", str(brain), "restore", "--staged", "personal-note.md"], check=True)
            result = self.module.sync_pending(confirmed=True, dry_run=False, brain=brain)
            synced = next(item for item in self.module.list_project_memories() if item["memory_id"] == memory["memory_id"])

        self.assertEqual(preview["status"], "preview")
        self.assertEqual(preview["pending_records"], 1)
        self.assertEqual(preview["destination"]["remote"], str(remote))
        self.assertEqual(preview["destination"]["branch"], "main")
        self.assertEqual(preview["groups"]["project"], 1)
        self.assertEqual(preview["groups"]["global"], 0)
        self.assertEqual(preview["groups"]["profile"], 0)
        self.assertEqual(preview["items"][0]["project"], "demo-123")
        self.assertEqual(preview["items"][0]["summary"], "需要同步的项目结论")
        self.assertEqual(preview["items"][0]["destination"], "projects/demo-123/learnings.md")
        self.assertEqual(preview["pending_files"], ["projects/demo-123/learnings.md"])
        self.assertEqual(preview["pending_commits"][0]["subject"], "brain: local preference")
        self.assertIn("当前分支全部领先提交", preview["push_scope_note"])
        self.assertIn("原始聊天全文", preview["excluded_content"])
        self.assertTrue(preview["can_sync"])
        self.assertEqual(result["status"], "synced")
        self.assertEqual(synced["sync_status"], "synced")
        self.assertEqual(
            subprocess.run(["git", "--git-dir", str(remote), "show", "main:projects/demo-123/learnings.md"], check=True, capture_output=True, text=True).stdout.count("需要同步的项目结论"),
            1,
        )

    def test_profile_candidate_previews_and_publishes_a_new_patch_version(self) -> None:
        brain = Path(self.tempdir.name) / "brain"
        profile = brain / "global" / "profiles" / "prd"
        profile.mkdir(parents=True)
        (profile / "v1.0.0.md").write_text(
            "---\nprofile: prd-for-humans\nversion: 1.0.0\nstatus: active\nupdated: 2026-08-14\n---\n\n# PRD Profile\n",
            encoding="utf-8",
        )
        (profile / "current.json").write_text(
            json.dumps({"schema_version": "1", "profile": "prd-for-humans", "version": "1.0.0", "file": "v1.0.0.md"}),
            encoding="utf-8",
        )
        with mock.patch.dict(os.environ, {"MICK_BRAIN_ROOT": str(brain)}):
            record = self.module.create_candidate(
                kind="profile", layer="profile", profile="prd", summary="小需求保持短文档"
            )
            view = self.module.candidate_view(record)
            self.assertEqual(view["profile_preview"]["current_version"], "1.0.0")
            self.assertEqual(view["profile_preview"]["proposed_version"], "1.0.1")
            result = self.module.approve(record["candidate_id"], yes=True, dry_run=False)

        self.assertEqual(result["status"], "written_local")
        pointer = json.loads((profile / "current.json").read_text(encoding="utf-8"))
        self.assertEqual(pointer["version"], "1.0.1")
        self.assertIn("小需求保持短文档", (profile / "v1.0.1.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

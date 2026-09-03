from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
SCRIPT = ROOT / "scripts" / "harness-agent-manager.py"
REGISTRY = ROOT / "config" / "agent-registry.json"
BRAIN_SCRIPT = ROOT / "scripts" / "harness-brain-boundary.py"
AUDIT_SCRIPT = ROOT / "scripts" / "harness-audit.sh"


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
        self.assertEqual(registry["schema_version"], "2")
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
            self.assertEqual(
                set(agent["adapter"]),
                {"support", "loading", "skills", "hooks", "repair"},
            )
            self.assertIn(agent["adapter"]["support"], {"managed", "manual", "unsupported"})
            self.assertIn(agent["adapter"]["loading"], {"managed", "manual", "unsupported"})
            self.assertIn(agent["adapter"]["skills"], {"managed", "manual", "unsupported"})
            self.assertIn(agent["adapter"]["hooks"], {"managed", "manual", "unsupported"})
            self.assertIsInstance(agent["adapter"]["repair"], list)
        tier_one = {agent["id"] for agent in agents if agent["tier"] == 1}
        self.assertEqual(tier_one, {"claude-code", "codex"})
        support = {agent["id"]: agent["adapter"]["support"] for agent in agents}
        self.assertEqual(support["claude-code"], "managed")
        self.assertEqual(support["codex"], "managed")
        self.assertEqual(support["cursor"], "manual")
        self.assertEqual(support["cline"], "unsupported")


class HarnessAuditTests(unittest.TestCase):
    def test_plain_checked_evidence_is_not_counted_as_a_numbered_plan_step(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            script = project / ".harness" / "scripts" / "harness-audit.sh"
            script.parent.mkdir(parents=True)
            script.write_bytes(AUDIT_SCRIPT.read_bytes())
            script.chmod(0o755)
            (project / "plan.md").write_text(
                "# Plan\n\n## 目标\n\n验证步骤识别。\n\n## 步骤\n\n"
                "- [x] 1. 真正步骤\n"
                "- [x] 6246 真实浏览器路径通过\n\n"
                "## 自检日志\n\n### Step 1 — 2026-08-22\n"
                "- files: `plan.md`\n"
                "- verify: 真实步骤已记录。\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-q"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Audit Test"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.email", "audit@example.invalid"], cwd=project, check=True)
            subprocess.run(["git", "add", "plan.md"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=project, check=True)

            result = subprocess.run(
                [str(script), "--since", "HEAD"], cwd=project, capture_output=True, text=True, check=False
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("plan.md (1/1 steps completed)", result.stdout)


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

        self.assertEqual(report["schema_version"], "2")
        self.assertEqual(codex["injection"]["status"], "injected")
        self.assertEqual(codex["loading"]["status"], "unverified")
        self.assertEqual(codex["execution"]["status"], "unverified")
        self.assertEqual(codex["feedback"]["status"], "unverified")
        self.assertTrue(any(issue["code"] == "load-proof-missing" for issue in codex["issues"]))

    def test_harness_agents_doctor_json_is_stable_cli(self) -> None:
        result = self.run_cli("doctor", "--json", "--home", str(self.home))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "2")
        self.assertEqual(len(payload["agents"]), 7)
        self.assertIn("detected", payload["summary"])
        self.assertEqual(payload["agents"][0]["adapter"], self.manager.load_registry(REGISTRY)["agents"][0]["adapter"])

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

    def test_sync_links_only_managed_command_skills_and_is_idempotent(self) -> None:
        registry = self.tier_one_registry()

        preview = self.manager.sync_agents(registry, home=self.home, dry_run=True)
        preview_skills = [change for change in preview if change.get("kind") == "skill"]
        self.assertEqual(
            [change["skill"] for change in preview_skills],
            ["harness-plan", "harness-goal", "harness-brain", "harness-e2e"],
        )
        self.assertTrue(all(change["changed"] for change in preview_skills))
        self.assertFalse((self.home / ".codex" / "skills").exists())

        first = self.manager.sync_agents(registry, home=self.home, dry_run=False)
        second = self.manager.sync_agents(registry, home=self.home, dry_run=False)
        first_skills = [change for change in first if change.get("kind") == "skill"]
        second_skills = [change for change in second if change.get("kind") == "skill"]
        self.assertTrue(all(Path(change["target"]).is_symlink() for change in first_skills))
        self.assertTrue(all(change["status"] == "linked" for change in first_skills))
        self.assertTrue(all(not change["changed"] for change in second_skills))

    def test_sync_preserves_user_owned_skill_with_same_name(self) -> None:
        target = self.home / ".codex" / "skills" / "harness-plan"
        target.mkdir(parents=True)
        marker = target / "user-owned.txt"
        marker.write_text("keep", encoding="utf-8")

        changes = self.manager.sync_agents(self.tier_one_registry(), home=self.home, dry_run=False)
        plan_change = next(change for change in changes if change.get("skill") == "harness-plan")

        self.assertEqual(plan_change["status"], "conflict")
        self.assertFalse(plan_change["changed"])
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

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

    def test_bundled_legacy_remote_is_not_a_new_user_configuration(self) -> None:
        home = Path(self.tempdir.name) / "home"
        with mock.patch.dict(
            os.environ,
            {
                "HOME": str(home),
                "MICK_HARNESS_CONFIG_DIR": str(Path(self.tempdir.name) / "config"),
                "MICK_HARNESS_BRAIN_LEGACY_CONFIG": "",
            },
        ):
            config = self.module.brain_configuration()

        self.assertEqual(config["mode"], "disabled")
        self.assertEqual(config["source"], "default")
        self.assertFalse((home / ".brain").exists())

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

    def test_harness_improvements_require_cross_project_signal_or_explicit_submit(self) -> None:
        brain = Path(self.tempdir.name) / "brain"
        with mock.patch.dict(os.environ, {"MICK_BRAIN_ROOT": str(brain)}):
            first_memory = self.module.process_observer_event(
                "app-a",
                {
                    "project_id": "app-a",
                    "idempotency_key": "ui-overflow-a",
                    "type": "work.round_completed",
                    "source": {"producer": "codex-hook"},
                    "payload": {"status": "completed", "summary": "移动端页面出现横向溢出"},
                },
            )
            second_memory = self.module.process_observer_event(
                "app-b",
                {
                    "project_id": "app-b",
                    "idempotency_key": "ui-overflow-b",
                    "type": "work.round_completed",
                    "source": {"producer": "claude-hook"},
                    "payload": {"status": "completed", "summary": "移动端布局再次出现横向溢出问题"},
                },
            )

        first = self.module.create_harness_improvement(
            first_memory["memory_id"], target="checker", summary="移动端布局必须检查横向溢出"
        )
        self.assertEqual(first["status"], "observed")
        self.assertFalse(first["eligible_for_approval"])
        with self.assertRaises(self.module.BrainBoundaryError):
            self.module.submit_harness_improvement(first["improvement_id"], force=False)

        second = self.module.create_harness_improvement(
            second_memory["memory_id"], target="checker", summary="移动端布局必须验证横向溢出"
        )
        listed = {item["improvement_id"]: item for item in self.module.list_harness_improvements()}
        self.assertIn(second["improvement_id"], listed[first["improvement_id"]]["similar_improvement_ids"])

        merged = self.module.merge_harness_improvements(
            first["improvement_id"], [second["improvement_id"]], summary="移动端布局必须验证横向溢出"
        )
        self.assertEqual(merged["status"], "pending_approval")
        self.assertEqual(merged["project_count"], 2)
        self.assertEqual(merged["occurrence_count"], 2)

    def test_approved_harness_improvement_is_a_proposal_until_effect_is_verified(self) -> None:
        brain = Path(self.tempdir.name) / "brain"
        with mock.patch.dict(os.environ, {"MICK_BRAIN_ROOT": str(brain)}):
            memory = self.module.process_observer_event(
                "app-a",
                {
                    "project_id": "app-a",
                    "idempotency_key": "button-wrap-a",
                    "type": "work.round_completed",
                    "source": {"producer": "codex-hook"},
                    "payload": {"status": "completed", "summary": "按钮文字不换行并挤出容器"},
                },
            )

        candidate = self.module.create_harness_improvement(
            memory["memory_id"], target="rule", summary="按钮必须验证文字换行与容器边界"
        )
        submitted = self.module.submit_harness_improvement(candidate["improvement_id"], force=True)
        approved = self.module.approve_harness_improvement(submitted["improvement_id"])

        self.assertEqual(approved["status"], "approved")
        self.assertTrue((self.state / approved["proposal_path"]).is_file())
        self.assertFalse((ROOT / "rules" / "auto-generated.md").exists())

        implemented = self.module.mark_harness_improvement_implemented(
            approved["improvement_id"], artifact_path="verify.d/ui-layout.py", baseline_count=3
        )
        verified = self.module.verify_harness_improvement_effect(
            implemented["improvement_id"], result="improved", current_count=0,
            note="三个项目的同类问题在复验窗口内降为零",
        )
        self.assertEqual(implemented["status"], "implemented")
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["effect"]["result"], "improved")

    def test_duplicate_harness_improvements_are_serialized_to_one_write(self) -> None:
        brain = Path(self.tempdir.name) / "brain"
        with mock.patch.dict(os.environ, {"MICK_BRAIN_ROOT": str(brain)}):
            memory = self.module.process_observer_event(
                "app-a",
                {
                    "project_id": "app-a",
                    "idempotency_key": "concurrent-ui-overflow",
                    "type": "work.round_completed",
                    "source": {"producer": "codex-hook"},
                    "payload": {"status": "completed", "summary": "窄屏布局出现横向溢出"},
                },
            )

        real_atomic_json = self.module.atomic_json

        def slow_atomic_json(path, value):
            time.sleep(0.05)
            return real_atomic_json(path, value)

        with mock.patch.object(self.module, "atomic_json", side_effect=slow_atomic_json) as atomic_json:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(
                    lambda _: self.module.create_harness_improvement(
                        memory["memory_id"], target="checker", summary="窄屏布局必须检查横向溢出"
                    ),
                    range(2),
                ))

        self.assertEqual(results[0]["improvement_id"], results[1]["improvement_id"])
        self.assertEqual(atomic_json.call_count, 1)
        self.assertEqual(len(self.module.list_harness_improvements()), 1)

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

    def test_project_memory_listing_applies_limit_before_similarity_scan(self) -> None:
        root = self.state / "brain-project-memory" / "demo-ui"
        root.mkdir(parents=True)
        for index in range(240):
            identifier = f"project_memory_{index:020x}"
            (root / f"{identifier}.json").write_text(
                json.dumps(
                    {
                        "memory_id": identifier,
                        "project": "demo-ui",
                        "kind": "result",
                        "summary": f"UI observation {index}",
                        "status": "written_local",
                        "created_at": f"2026-08-22T12:{index // 60:02d}:{index % 60:02d}+00:00",
                    }
                ),
                encoding="utf-8",
            )

        with mock.patch.object(self.module, "summaries_are_similar", return_value=False) as similarity:
            memories = self.module.list_project_memories(limit=25)

        self.assertEqual(len(memories), 25)
        self.assertLessEqual(similarity.call_count, 25 * 24)
        self.assertEqual(memories[0]["summary"], "UI observation 239")

    def test_health_snapshot_does_not_run_pairwise_memory_listing(self) -> None:
        root = self.state / "brain-project-memory" / "demo-ui"
        root.mkdir(parents=True)
        record = {
            "memory_id": "project_memory_aaaaaaaaaaaaaaaaaaaa",
            "project": "demo-ui",
            "kind": "result",
            "summary": "A stable project fact",
            "status": "written_local",
            "source_agent": "codex-hook",
            "created_at": "2026-08-22T12:00:00+00:00",
        }
        (root / f"{record['memory_id']}.json").write_text(json.dumps(record), encoding="utf-8")

        with mock.patch.object(
            self.module, "list_project_memories", side_effect=AssertionError("pairwise listing must stay off health path")
        ):
            health = self.module.health_snapshot(brain=Path(self.tempdir.name) / "brain")

        self.assertEqual(health["local_write"]["project_memory_count"], 1)
        self.assertEqual(health["local_write"]["last_write_at"], "2026-08-22T12:00:00+00:00")

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

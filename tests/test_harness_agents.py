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
        self.assertIn("Mick Agent Harness 0.17.0", result.stdout)

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


if __name__ == "__main__":
    unittest.main()

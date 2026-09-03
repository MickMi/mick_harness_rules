from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INGEST = ROOT / "scripts" / "brain-ingest.sh"
HOOKS = ROOT / "scripts" / "hook-adapters.sh"
EVOLVE = ROOT / "scripts" / "harness-evolve.sh"


class BrainWorkflowFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.home = self.base / "home"
        self.config = self.base / "config"
        self.project = self.base / "project"
        self.brain = self.base / "brain"
        for path in (self.home, self.config, self.project):
            path.mkdir()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(self.home),
                "MICK_HARNESS_ROOT": str(ROOT),
                "MICK_HARNESS_CONFIG_DIR": str(self.config),
                "MICK_HARNESS_ACTIVITY": "0",
            }
        )
        return environment

    def configure_local_brain(self) -> None:
        self.config.mkdir(exist_ok=True)
        (self.config / "brain.json").write_text(
            json.dumps({"version": 1, "mode": "local", "local_path": str(self.brain), "remote": None}),
            encoding="utf-8",
        )

    def write_audit_signal(self, path: Path) -> None:
        today = dt.date.today().isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(
                f"## {today} 10:0{index} · sample-project · plan\n- WARN: scope-creep fixture-{index}\n"
                for index in range(3)
            ),
            encoding="utf-8",
        )

    def test_brain_ingest_writes_only_to_configured_local_brain(self) -> None:
        self.configure_local_brain()
        result = subprocess.run(
            ["bash", str(INGEST), "--source", "fixture", "--kind", "session", "--project", "sample", "--no-sync"],
            input="verified learning\n",
            check=False,
            capture_output=True,
            text=True,
            env=self.environment(),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        written = Path(result.stdout.strip())
        self.assertTrue(written.is_file())
        self.assertTrue(written.is_relative_to(self.brain))
        self.assertIn("verified learning", written.read_text(encoding="utf-8"))
        self.assertFalse((self.home / ".brain").exists())

    def test_brain_ingest_skips_without_configuration_and_creates_nothing(self) -> None:
        result = subprocess.run(
            ["bash", str(INGEST), "--source", "fixture", "--kind", "session", "--no-sync"],
            input="must not be written\n",
            check=False,
            capture_output=True,
            text=True,
            env=self.environment(),
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("Brain is disabled", result.stderr)
        self.assertFalse((self.home / ".brain").exists())
        self.assertFalse(self.brain.exists())

    def test_claude_hook_adapter_is_idempotent_inside_isolated_home(self) -> None:
        command = (
            f'source "{HOOKS}"; '
            "install_claude_code_hook; install_claude_code_session_start_hook; "
            "install_claude_code_hook; install_claude_code_session_start_hook; "
            "printf '%s|%s\\n' \"$(claude_hook_status)\" \"$(claude_session_start_status)\""
        )
        result = subprocess.run(
            ["bash", "-c", command],
            check=False,
            capture_output=True,
            text=True,
            env=self.environment(),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "installed|installed")
        settings = json.loads((self.home / ".claude" / "settings.json").read_text(encoding="utf-8"))
        serialized = json.dumps(settings)
        self.assertEqual(serialized.count("brain-sync.sh"), 1)
        self.assertEqual(serialized.count("session-start.sh"), 1)

    def test_brain_evolve_reads_configured_brain_and_never_edits_rules(self) -> None:
        self.configure_local_brain()
        self.write_audit_signal(self.brain / "global" / "evolution" / "audit-trail.md")
        before = (ROOT / "rules" / "core.md").read_bytes()

        result = subprocess.run(
            [str(EVOLVE), "--since", "30d", "--threshold", "3"],
            cwd=self.project,
            check=False,
            capture_output=True,
            text=True,
            env=self.environment(),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        proposals = list((self.project / "docs" / "evolution").glob("proposal-*.md"))
        self.assertEqual(len(proposals), 1)
        self.assertIn("scope-creep", proposals[0].read_text(encoding="utf-8"))
        self.assertEqual((ROOT / "rules" / "core.md").read_bytes(), before)

    def test_brain_evolve_falls_back_to_current_project_without_brain(self) -> None:
        self.write_audit_signal(self.project / "audit-log.md")

        result = subprocess.run(
            [str(EVOLVE), "--since", "30d", "--threshold", "3"],
            cwd=self.project,
            check=False,
            capture_output=True,
            text=True,
            env=self.environment(),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        proposals = list((self.project / "docs" / "evolution").glob("proposal-*.md"))
        self.assertEqual(len(proposals), 1)
        self.assertIn("scope-creep", proposals[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

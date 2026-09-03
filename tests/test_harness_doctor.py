from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "harness-doctor.py"


def load_doctor():
    spec = importlib.util.spec_from_file_location("harness_doctor", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HarnessDoctorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.doctor = load_doctor()
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.home = self.root / "home"
        self.project = self.root / "project"
        self.state = self.root / "state"
        self.home.mkdir()
        self.project.mkdir()
        self.state.mkdir()
        (self.project / "AGENTS.md").write_text("Harness loader\n", encoding="utf-8")
        (self.project / ".harness").symlink_to(ROOT, target_is_directory=True)
        (self.state / "registered-projects").write_text(f"{self.project}\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def healthy_dependencies(self) -> dict:
        return {
            "agents": {
                "summary": {"registered": 2, "detected": 2, "tier_one": 2, "issues": 0},
                "agents": [
                    {
                        "id": "codex",
                        "name": "Codex",
                        "detected": True,
                        "adapter": {"support": "managed"},
                        "injection": {"status": "injected"},
                        "loading": {"status": "hook_configured"},
                        "issues": [],
                    }
                ],
            },
            "brain": {"mode": "disabled", "state": "disabled", "writes": "none"},
            "observer": {"installed": True, "loaded": True, "healthy": True, "port": 6425},
            "audit": {"available": True, "exit_code": 0, "summary": "passed"},
        }

    def test_report_uses_six_named_components_and_disabled_brain_is_optional(self) -> None:
        report = self.doctor.build_report(
            project=self.project,
            home=self.home,
            harness_root=ROOT,
            state_root=self.state,
            dependencies=self.healthy_dependencies(),
        )

        self.assertEqual(report["schema_version"], "1")
        self.assertEqual(
            [component["id"] for component in report["components"]],
            ["installation", "project", "agents", "brain", "observer", "audit"],
        )
        self.assertEqual(report["overall"], "ok")
        brain = next(item for item in report["components"] if item["id"] == "brain")
        self.assertEqual(brain["status"], "optional")
        self.assertIn("harness brain configure --mode local", brain["action"])

    def test_unhealthy_observer_and_remote_mismatch_are_actionable_failures(self) -> None:
        dependencies = self.healthy_dependencies()
        dependencies["brain"] = {"mode": "remote", "state": "remote_mismatch", "writes": "local-first"}
        dependencies["observer"] = {"installed": True, "loaded": True, "healthy": False, "port": 6425}

        report = self.doctor.build_report(
            project=self.project,
            home=self.home,
            harness_root=ROOT,
            state_root=self.state,
            dependencies=dependencies,
        )

        self.assertEqual(report["overall"], "blocked")
        by_id = {component["id"]: component for component in report["components"]}
        self.assertEqual(by_id["brain"]["status"], "error")
        self.assertIn("harness brain configure", by_id["brain"]["action"])
        self.assertEqual(by_id["observer"]["status"], "error")
        self.assertEqual(by_id["observer"]["action"], "harness observe service restart")

    def test_cli_json_contract_is_available_from_top_level_harness(self) -> None:
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(self.home),
                "MICK_HARNESS_ROOT": str(ROOT),
                "MICK_HARNESS_STATE_DIR": str(self.state),
                "MICK_HARNESS_ACTIVITY": "0",
            }
        )
        result = subprocess.run(
            [str(ROOT / "bin" / "harness"), "doctor", "--json", str(self.project)],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

        self.assertIn(result.returncode, {0, 1})
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "1")
        self.assertEqual(len(payload["components"]), 6)
        self.assertEqual(payload["project"], str(self.project.resolve()))

    def test_legacy_todo_and_readme_do_not_create_a_second_backlog(self) -> None:
        todo = (ROOT / "TODO.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        versions = (ROOT / "docs" / "VERSIONS.md").read_text(encoding="utf-8")

        self.assertNotIn("- [ ]", todo)
        self.assertNotIn("## 下一版本重点", readme)
        self.assertIn("docs/VERSIONS.md", todo)
        self.assertIn("## Backlog", versions)


if __name__ == "__main__":
    unittest.main()

"""Read-only installation status: isolated repositories, no user configuration."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_harness_observe import OBSERVE


class HarnessVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / "install"
        self.install.mkdir()
        (self.install / "rules").mkdir()
        (self.install / "dist").mkdir()
        (self.install / "VERSION").write_text("0.22.1\n")
        (self.install / "rules/core.md").write_text("fixture rules\n")
        (self.install / "dist/AGENTS.md").write_text("fixture loader\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / ".harness").symlink_to(self.install, target_is_directory=True)
        (self.project / "AGENTS.md").symlink_to(self.install / "dist/AGENTS.md")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.install), *args], check=True, capture_output=True, text=True).stdout.strip()

    def snapshot(self):
        return OBSERVE.harness_versions_snapshot([{"project_id": "fixture", "path": str(self.project), "validation": "valid"}], baseline_root=self.install)

    def test_linked_install_and_custom_project_body(self):
        value = self.snapshot()["projects"]["fixture"]
        self.assertEqual(value["status"], "synced")
        self.assertEqual(value["session_load"], "unverified")
        self.assertEqual(value["revision"], self.git("rev-parse", "HEAD"))
        (self.project / "AGENTS.md").unlink()
        (self.project / "AGENTS.md").write_text("<!-- HARNESS:BEGIN — fixture -->\nfixture loader\n<!-- HARNESS:END -->\n\nCustom business rules")
        self.assertEqual(self.snapshot()["projects"]["fixture"]["status"], "synced")

    def test_dirty_rules_and_loader_mismatch(self):
        (self.install / "rules/core.md").write_text("local customization")
        self.assertEqual(self.snapshot()["projects"]["fixture"]["status"], "modified")
        (self.project / "AGENTS.md").unlink()
        (self.project / "AGENTS.md").write_text("stale loader")
        self.assertEqual(self.snapshot()["projects"]["fixture"]["status"], "loader_mismatch")

    def test_same_version_different_commit_is_not_synced(self):
        baseline = OBSERVE.harness_installation_snapshot(self.install)
        (self.install / "rules/core.md").write_text("next rules")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "next")
        value = OBSERVE.project_harness_snapshot(self.project, baseline, {})
        self.assertEqual(value["version"], baseline["version"])
        self.assertEqual(value["status"], "different")

    def test_unrelated_business_docs_do_not_mean_harness_modified(self):
        (self.install / "docs").mkdir()
        (self.install / "docs/private.md").write_text("unrelated")
        self.assertEqual(self.snapshot()["projects"]["fixture"]["status"], "synced")

    def test_missing_entry_and_git_failure_are_unknown(self):
        (self.project / ".harness").unlink()
        self.assertEqual(self.snapshot()["projects"]["fixture"]["status"], "unknown")
        with mock.patch.object(OBSERVE, "run_git", side_effect=FileNotFoundError):
            self.assertIsNone(OBSERVE.harness_installation_snapshot(self.install)["revision"])

    def test_parent_repo_head_not_used_for_non_git_install(self):
        nested = self.install / "nested"
        nested.mkdir()
        (nested / "VERSION").write_text("0.22.1")
        (nested / "rules").mkdir()
        (nested / "rules/core.md").write_text("rules")
        (nested / "dist").mkdir()
        (nested / "dist/AGENTS.md").write_text("loader")
        self.assertIsNone(OBSERVE.harness_installation_snapshot(nested)["revision"])

    def test_shared_install_is_inspected_once(self):
        original = OBSERVE.harness_installation_snapshot
        with mock.patch.object(OBSERVE, "harness_installation_snapshot", wraps=original) as inspect:
            self.snapshot()
            self.assertEqual(inspect.call_count, 1)


if __name__ == "__main__":
    unittest.main()

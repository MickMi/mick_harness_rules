from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("harness_public_audit", ROOT / "scripts" / "harness-public-audit.py")
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class PublicReleaseAuditTests(unittest.TestCase):
    def test_repository_is_safe_for_public_install(self) -> None:
        self.assertEqual(AUDIT.audit_root(ROOT), [])

    def test_private_owner_and_legacy_default_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config" / ".brain-config.yaml").write_text(
                'local_path: "~/.' + 'mick-brain"\nowner: ' + "Mick" + "Mi" + "\n",
                encoding="utf-8",
            )
            (root / "config" / ".harness-config.template.yaml").write_text(
                'path: "~/.brain"\n', encoding="utf-8"
            )
            subprocess_marker = root / ".git"
            subprocess_marker.mkdir()
            import subprocess

            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            issues = AUDIT.audit_root(root)
            self.assertTrue(any("personal owner" in issue for issue in issues))
            self.assertTrue(any("legacy Brain name" in issue for issue in issues))

    def test_personal_project_and_identity_profile_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config" / ".brain-config.yaml").write_text(
                'local_path: "~/.brain"\n', encoding="utf-8"
            )
            (root / "config" / ".harness-config.template.yaml").write_text(
                'path: "~/.brain"\n', encoding="utf-8"
            )
            (root / "notes.md").write_text(
                "Example: " + "Rali" + "Tennis" + "\n"
                + "Mick " + "是懂技术的产品经理。\n",
                encoding="utf-8",
            )
            import subprocess

            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            issues = AUDIT.audit_root(root)
            self.assertTrue(any("personal project name" in issue for issue in issues))
            self.assertTrue(any("hard-coded personal identity" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()

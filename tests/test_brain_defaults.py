from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / "scripts" / "brain-resolve.sh"


class BrainDefaultPathTests(unittest.TestCase):
    def resolve(self, home: Path) -> tuple[str, str]:
        command = (
            f'source "{RESOLVER}"; '
            f'resolve_brain_dir "{ROOT}"; '
            'printf "%s\\n%s\\n" "$BRAIN_REPO_LOCAL" "$BRAIN_USING_LEGACY_PATH"'
        )
        environment = os.environ.copy()
        environment["HOME"] = str(home)
        result = subprocess.run(
            ["bash", "-c", command],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        lines = result.stdout.splitlines()
        return lines[0], lines[1]

    def test_new_install_uses_generic_brain_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path, legacy = self.resolve(home)
            self.assertEqual(path, str(home / ".brain"))
            self.assertEqual(legacy, "false")

    def test_existing_legacy_directory_remains_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / (".mick" + "-brain")).mkdir()
            path, legacy = self.resolve(home)
            self.assertEqual(path, str(home / (".mick" + "-brain")))
            self.assertEqual(legacy, "true")

    def test_generic_directory_wins_when_both_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / ".brain").mkdir()
            (home / (".mick" + "-brain")).mkdir()
            path, legacy = self.resolve(home)
            self.assertEqual(path, str(home / ".brain"))
            self.assertEqual(legacy, "false")

    def test_private_brain_remote_is_the_identity_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            brain = Path(directory) / ".brain"
            brain.mkdir()
            subprocess.run(["git", "init", "--quiet", str(brain)], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(brain),
                    "remote",
                    "add",
                    "origin",
                    "git@github.com:external-user/private-brain.git",
                ],
                check=True,
            )
            command = (
                f'source "{RESOLVER}"; '
                f'BRAIN_DIR="{brain}"; BRAIN_REPO_REMOTE=""; '
                'printf "%s\\n%s\\n" '
                '"$(brain_remote_owner \"$BRAIN_DIR\")" '
                '"$(brain_remote_repo \"$BRAIN_DIR\")"'
            )
            result = subprocess.run(
                ["bash", "-c", command],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.stdout.splitlines(), ["external-user", "private-brain"])

    def test_local_brain_has_no_remote_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            brain = Path(directory) / ".brain"
            brain.mkdir()
            subprocess.run(["git", "init", "--quiet", str(brain)], check=True)
            command = (
                f'source "{RESOLVER}"; '
                f'BRAIN_DIR="{brain}"; BRAIN_REPO_REMOTE=""; '
                'printf "[%s]\\n%s\\n" '
                '"$(brain_remote_owner \"$BRAIN_DIR\")" '
                '"$(brain_remote_repo \"$BRAIN_DIR\")"'
            )
            result = subprocess.run(
                ["bash", "-c", command],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.stdout.splitlines(), ["[]", "local"])


if __name__ == "__main__":
    unittest.main()

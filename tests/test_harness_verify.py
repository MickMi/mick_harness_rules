from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "harness-verify.py"


def load_module():
    spec = importlib.util.spec_from_file_location("harness_verify", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HarnessVerifyTests(unittest.TestCase):
    def test_three_tiers_have_distinct_cost_and_release_gate(self) -> None:
        module = load_module()
        fast = module.command_plan("fast", "brain")
        subsystem = module.command_plan("subsystem", "brain")
        release = module.command_plan("release", None)

        self.assertLess(len(fast), len(subsystem))
        self.assertLess(len(subsystem), len(release))
        self.assertTrue(any("BrainBoundaryTests" in " ".join(command) for command in fast))
        self.assertTrue(any("tests.test_harness_agents" in " ".join(command) for command in subsystem))
        self.assertTrue(any("discover" in command for command in release))
        self.assertTrue(any("generate.sh" in " ".join(command) for command in release))
        self.assertTrue(any("diff" in command for command in release))

    def test_successful_gate_is_reused_only_for_same_fingerprint_and_environment(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "verify-gates.json"
            commands = module.command_plan("release", None)
            module.save_gate(cache, key="same", tier="release", subsystem=None, commands=commands)

            self.assertTrue(module.reusable_gate(cache, key="same", tier="release", subsystem=None, commands=commands))
            self.assertFalse(module.reusable_gate(cache, key="changed", tier="release", subsystem=None, commands=commands))
            self.assertFalse(module.reusable_gate(cache, key="same", tier="subsystem", subsystem="brain", commands=commands))

            payload = json.loads(cache.read_text(encoding="utf-8"))
            self.assertEqual(payload["gates"]["release:all"]["status"], "passed")

    def test_fingerprint_changes_with_code_or_environment(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tracked.txt").write_text("one", encoding="utf-8")
            with mock.patch.object(module, "git_material", return_value=b"one"):
                first = module.verification_fingerprint(root, [["python3", "-m", "unittest"]], environment="py-a")
            with mock.patch.object(module, "git_material", return_value=b"two"):
                changed_code = module.verification_fingerprint(root, [["python3", "-m", "unittest"]], environment="py-a")
            with mock.patch.object(module, "git_material", return_value=b"one"):
                changed_environment = module.verification_fingerprint(root, [["python3", "-m", "unittest"]], environment="py-b")

        self.assertNotEqual(first, changed_code)
        self.assertNotEqual(first, changed_environment)


if __name__ == "__main__":
    unittest.main()

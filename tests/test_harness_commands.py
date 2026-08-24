import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "command-registry.json"
DOC_PATH = ROOT / "docs" / "COMMANDS.md"


class CommandContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.commands = {item["id"]: item for item in cls.registry["commands"]}
        cls.docs = DOC_PATH.read_text(encoding="utf-8")

    def test_registry_defines_the_four_canonical_commands(self):
        self.assertEqual(set(self.commands), {"plan", "goal", "brain", "e2e"})
        for command_id, command in self.commands.items():
            self.assertEqual(command["cli"], f"harness {command_id}")
            self.assertTrue(command["preview_default"])
            self.assertTrue(command["write_flag"])
            self.assertTrue(command["reads"])
            self.assertTrue(command["writes"])
            self.assertTrue(command["stops_on"])
            self.assertTrue(command["never_does"])

    def test_codex_native_commands_are_reserved(self):
        codex = self.registry["host_adapters"]["codex"]
        self.assertEqual(codex["reserved_commands"], ["/plan", "/goal"])
        self.assertEqual(codex["skills"]["plan"], "harness-plan")
        self.assertEqual(codex["skills"]["goal"], "harness-goal")
        self.assertNotIn("/plan", codex["skills"].values())
        self.assertNotIn("/goal", codex["skills"].values())

    def test_brain_contract_has_three_unambiguous_modes(self):
        brain = self.commands["brain"]
        self.assertEqual(brain["modes"], ["local", "remote", "disabled"])
        self.assertIn("create Brain during ordinary harness init", brain["never_does"])

    def test_e2e_requires_one_requirement_and_stops_before_publish(self):
        e2e = self.commands["e2e"]
        self.assertIn("--requirement <requirement_id>", e2e["required_inputs"])
        prohibited = " ".join(e2e["never_does"])
        for operation in ("merge", "push", "tag", "deploy", "publish"):
            self.assertIn(operation, prohibited)

    def test_exit_codes_are_stable_and_documented(self):
        self.assertEqual(set(self.registry["exit_codes"]), {"0", "2", "64", "69", "74"})
        for code in self.registry["exit_codes"]:
            self.assertIn(f"`{code}`", self.docs)

    def test_context_baseline_matches_the_recorded_v0201_snapshot(self):
        baseline = self.registry["context_baseline"]
        self.assertEqual(baseline["combined_loader_bytes"], 32640)
        self.assertEqual(
            baseline["codex_default_discovery_limit_bytes"]
            - baseline["combined_loader_bytes"],
            baseline["remaining_headroom_bytes"],
        )
        self.assertEqual(baseline["full_regression_tests"], 142)

    def test_user_document_explains_preview_brain_and_host_boundaries(self):
        for phrase in (
            "先预览，再显式写入",
            "Harness 不覆盖、不伪装这两个原生命令",
            "local",
            "remote",
            "disabled",
            "不会自动 merge、push、tag、deploy 或 publish",
        ):
            self.assertIn(phrase, self.docs)


if __name__ == "__main__":
    unittest.main()

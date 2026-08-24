import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "command-registry.json"
DOC_PATH = ROOT / "docs" / "COMMANDS.md"
CLI_PATH = ROOT / "bin" / "harness"


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


class PlanGoalCommandTests(unittest.TestCase):
    def run_harness(self, project: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["MICK_HARNESS_ROOT"] = str(ROOT)
        env["MICK_HARNESS_ACTIVITY"] = "0"
        return subprocess.run(
            [str(CLI_PATH), *args, "--project", str(project)],
            cwd=project,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def make_project(self, root: Path, with_versions: bool = True) -> Path:
        project = root / "sample-project"
        (project / "docs").mkdir(parents=True)
        (project / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        if with_versions:
            (project / "docs" / "VERSIONS.md").write_text(
                "# Versions\n\n"
                "## 0.3.0\n\n"
                "- Status: locked\n"
                "- Goal: 让用户看清当前项目进展。\n\n"
                "### Requirements\n\n"
                "- [ ] `task-1` 展示当前需求\n"
                "- [x] `task-2` 保留历史记录\n\n"
                "## 0.2.0\n\n"
                "- Status: released\n"
                "- Goal: 旧版本\n",
                encoding="utf-8",
            )
        return project

    def test_plan_preview_does_not_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary))
            result = self.run_harness(project, "plan", "--title", "当前版本交付")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("预览完成，未发生写入", result.stdout)
            self.assertIn("拟纳入当前版本未完成需求：1 条", result.stdout)
            self.assertFalse((project / "plan.md").exists())

    def test_plan_apply_creates_archive_from_project_facts(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary))
            result = self.run_harness(project, "plan", "--title", "当前版本交付", "--apply")
            self.assertEqual(result.returncode, 0, result.stderr)
            content = (project / "plan.md").read_text(encoding="utf-8")
            self.assertIn("# Plan: sample-project", content)
            self.assertIn("当前版本交付", content)
            self.assertIn("`task-1` 展示当前需求", content)
            self.assertNotIn("`task-2` 保留历史记录", content)

    def test_plan_apply_refuses_to_overwrite_active_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary))
            plan = project / "plan.md"
            original = "> 🧭 状态：开发中\n\n# Plan: Existing\n\n- [ ] keep this\n"
            plan.write_text(original, encoding="utf-8")
            result = self.run_harness(project, "plan", "--apply")
            self.assertEqual(result.returncode, 2)
            self.assertIn("存在尚未完成的活跃计划", result.stdout)
            self.assertEqual(plan.read_text(encoding="utf-8"), original)

    def test_plan_apply_appends_after_completed_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary))
            plan = project / "plan.md"
            plan.write_text(
                "> 🧭 状态：已完成\n\n# Plan: Existing\n\n- [x] old delivery\n",
                encoding="utf-8",
            )
            result = self.run_harness(project, "plan", "--title", "新阶段", "--apply")
            self.assertEqual(result.returncode, 0, result.stderr)
            content = plan.read_text(encoding="utf-8")
            self.assertIn("old delivery", content)
            self.assertIn("## ", content)
            self.assertIn("· 新阶段", content)

    def test_goal_preview_and_apply_preserve_the_human_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary), with_versions=False)
            profile = project / "docs" / "PROJECT.md"
            profile.write_text(
                "# Project Profile\n\n## Goal\n\n旧目标。\n\n## Audience\n\n个人开发者。\n",
                encoding="utf-8",
            )
            goal = "让个人开发者持续看清多个项目的真实交付状态。"
            preview = self.run_harness(project, "goal", "--set", goal)
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertIn("预览完成，未发生写入", preview.stdout)
            self.assertIn("旧目标", profile.read_text(encoding="utf-8"))

            applied = self.run_harness(project, "goal", "--set", goal, "--apply")
            self.assertEqual(applied.returncode, 0, applied.stderr)
            content = profile.read_text(encoding="utf-8")
            self.assertIn(goal, content)
            self.assertIn("## Audience\n\n个人开发者。", content)
            self.assertNotIn("旧目标。", content)

    def test_goal_rejects_version_or_technical_delivery_as_long_term_goal(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary), with_versions=False)
            result = self.run_harness(
                project,
                "goal",
                "--set",
                "实现 v0.21 API 并修复 task-8。",
                "--apply",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("不像稳定的人类产品目标", result.stdout)
            self.assertFalse((project / "docs" / "PROJECT.md").exists())

    def test_invalid_command_input_uses_the_contract_exit_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary), with_versions=False)
            result = self.run_harness(project, "plan", "--unknown")
            self.assertEqual(result.returncode, 64)
            self.assertIn("输入无效", result.stderr)


if __name__ == "__main__":
    unittest.main()

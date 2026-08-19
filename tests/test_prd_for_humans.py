from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "rules" / "skills" / "prd-for-humans"
CHECKER = SKILL_ROOT / "scripts" / "check_prd.py"
PROFILE = SKILL_ROOT / "scripts" / "resolve_profile.py"
FIXTURES = ROOT / "tests" / "fixtures" / "prd-for-humans"
GOLDENS = SKILL_ROOT / "references"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PrdForHumansTests(unittest.TestCase):
    def test_skill_is_human_only_and_uses_adaptive_sections(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("human product review", text)
        self.assertIn("adaptive", text.lower())
        self.assertIn("Do not create empty sections", text)
        self.assertIn("AI-CONTRACT", text)
        self.assertNotIn("必须包含以下章节", text)

    def test_golden_examples_are_clean_and_adapt_to_the_requirement(self) -> None:
        checker = load_module(CHECKER, "check_prd")
        small = (GOLDENS / "golden-small.md").read_text(encoding="utf-8")
        data = (GOLDENS / "golden-data.md").read_text(encoding="utf-8")
        staged = (GOLDENS / "golden-staged.md").read_text(encoding="utf-8")

        for name, text in (("small", small), ("data", data), ("staged", staged)):
            self.assertEqual(checker.scan_text(text), [], name)
        self.assertNotIn("数据需求", small)
        self.assertIn("## 数据需求", data)
        self.assertNotIn("## 分期", data)
        self.assertIn("## 分期", staged)

    def test_checker_flags_technical_delivery_content(self) -> None:
        checker = load_module(CHECKER, "check_prd_invalid")
        text = (FIXTURES / "technical-pollution.md").read_text(encoding="utf-8")
        codes = {finding["code"] for finding in checker.scan_text(text)}
        self.assertTrue({"file-path", "implementation", "ai-contract"}.issubset(codes))

    def test_checker_allows_product_metrics_formulas_and_visible_states(self) -> None:
        checker = load_module(CHECKER, "check_prd_allowed")
        text = (
            "# 留存预警\n\n"
            "## 判断规则\n\n"
            "七日留存率 = 第七天仍活跃的用户数 / 首日新增用户数。低于 20% 时显示‘需要关注’。\n"
        )
        self.assertEqual(checker.scan_text(text), [])

    def test_checker_cli_returns_machine_readable_findings(self) -> None:
        result = subprocess.run(
            ["python3", str(CHECKER), "--json", str(FIXTURES / "technical-pollution.md")],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertGreaterEqual(payload["summary"]["violations"], 3)

    def test_profile_resolution_obeys_project_private_generic_precedence(self) -> None:
        resolver = load_module(PROFILE, "resolve_profile")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            brain = root / "brain"
            project.mkdir()
            private_dir = brain / "global" / "profiles" / "prd"
            private_dir.mkdir(parents=True)
            (private_dir / "v1.2.0.md").write_text(
                "---\nprofile: prd-for-humans\nversion: 1.2.0\nstatus: active\n---\n\n# Private\n",
                encoding="utf-8",
            )
            (private_dir / "current.json").write_text(
                json.dumps({"schema_version": "1", "profile": "prd-for-humans", "version": "1.2.0", "file": "v1.2.0.md"}),
                encoding="utf-8",
            )

            private = resolver.resolve_profile(project=project, brain=brain, skill_root=SKILL_ROOT)
            self.assertEqual(private["active"]["source"], "private_brain")
            self.assertEqual(private["active"]["version"], "1.2.0")

            profile_dir = project / "docs"
            profile_dir.mkdir()
            (profile_dir / "PRD-PROFILE.md").write_text(
                "---\nprofile: prd-for-humans\nversion: 2.0.0\nstatus: active\n---\n\n# Project\n",
                encoding="utf-8",
            )
            project_result = resolver.resolve_profile(project=project, brain=brain, skill_root=SKILL_ROOT)
            self.assertEqual(project_result["active"]["source"], "project")
            self.assertEqual([layer["source"] for layer in project_result["layers"]], ["project", "private_brain", "generic"])

    def test_invalid_private_profile_falls_back_with_diagnostic(self) -> None:
        resolver = load_module(PROFILE, "resolve_profile_invalid")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            brain = root / "brain"
            project.mkdir()
            private_dir = brain / "global" / "profiles" / "prd"
            private_dir.mkdir(parents=True)
            (private_dir / "current.json").write_text(
                json.dumps({"schema_version": "1", "profile": "prd-for-humans", "version": "1.0.0", "file": "../preferences.md"}),
                encoding="utf-8",
            )

            result = resolver.resolve_profile(project=project, brain=brain, skill_root=SKILL_ROOT)
            self.assertEqual(result["active"]["source"], "generic")
            self.assertEqual(result["diagnostics"][0]["source"], "private_brain")
            self.assertEqual(result["diagnostics"][0]["status"], "invalid")

    def test_pm_loads_skill_only_for_explicit_prd_and_never_auto_creates_ai_contract(self) -> None:
        text = (ROOT / "rules" / "roles" / "pm.md").read_text(encoding="utf-8")
        self.assertIn("prd-for-humans", text)
        self.assertIn("明确要求 PRD", text)
        self.assertIn("不自动生成 `AI-CONTRACT`", text)


if __name__ == "__main__":
    unittest.main()

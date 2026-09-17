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

    def test_skill_chooses_direct_draft_or_small_multi_round_questions(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("If no missing answer would materially change the product direction, draft the PRD immediately", text)
        self.assertIn("ask at most one or two questions", text)
        self.assertIn("never repeat a question", text)
        self.assertIn("Do not confuse PRD readiness with implementation readiness", text)

        clear = (GOLDENS / "dialogue-clear.md").read_text(encoding="utf-8")
        ambiguous = (GOLDENS / "dialogue-ambiguous.md").read_text(encoding="utf-8")
        self.assertIn("Draft the PRD immediately", clear)
        self.assertIn("Do not draft a fake complete PRD yet", ambiguous)
        self.assertIn("Never ask the two Round 1 questions again", ambiguous)

    def test_skill_keeps_product_facts_profile_and_brain_separate(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("define product truth", text)
        self.assertIn("does not supply product facts", text)
        self.assertIn("unapproved candidates", text)
        self.assertIn("stable preference", text)

    def test_collaboration_covers_revision_and_sample_provenance(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("discuss, draft, revise, review, or learn style", text)
        self.assertIn("preserve accepted content", text)
        self.assertIn("references/sample-learning.md", text)
        self.assertIn("references/dialogue-revision.md", text)
        self.assertIn("does not start implementation, full testing, or release", text)

        learning = (GOLDENS / "sample-learning.md").read_text(encoding="utf-8")
        self.assertIn("one sample family", learning)
        self.assertIn("unknown authorship/approval", learning)
        self.assertIn("memory summary is a secondary account", learning)
        self.assertIn("Retire that guidance", learning)
        self.assertIn("never silently combine both versions", learning)
        self.assertNotIn("/Users/", learning)

        revision = (GOLDENS / "dialogue-revision.md").read_text(encoding="utf-8")
        self.assertIn("not evidence of a model run", revision)
        self.assertIn("Do not restart discovery", revision)
        self.assertIn("reduce duplicated explanation", revision)

    def test_skill_entry_supports_rough_ideas_and_keeps_stable_id(self) -> None:
        text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        metadata = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("name: prd-for-humans", text)
        self.assertIn("$prd-for-humans", metadata)
        self.assertIn("develop this idea", metadata)
        self.assertNotIn("this confirmed requirement", metadata)

    def test_new_learning_references_are_linked_from_profile_contract(self) -> None:
        contract = (GOLDENS / "profile-contract.md").read_text(encoding="utf-8")
        self.assertIn("sample-learning.md", contract)
        self.assertIn("scope of approval", contract)
        self.assertIn("uncertain findings out of the active Profile", contract)

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

    def test_checker_distinguishes_visible_fields_from_interface_fields(self) -> None:
        checker = load_module(CHECKER, "check_prd_fields")
        self.assertEqual(checker.scan_text(
            "展示字段名称：商品名称、成交金额（元）、统计周期。商品名称必填，支持修改。\n"
            "| 场景 | 页面字段 | 操作与反馈 |\n| 筛选 | 状态、关键词 | 清空后显示全部 |\n"
        ), [])
        self.assertTrue(checker.scan_text("接口字段 amount_cent 使用整数表示。"))
        self.assertTrue(checker.scan_text("数据库字段 order_id 为主键。"))

    def test_document_check_validates_local_images_without_fetching_remote_images(self) -> None:
        checker = load_module(CHECKER, "check_prd_images")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "screen shot.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            document = root / "PRD.md"
            document.write_text(
                '# PRD\n\n![入口](screen%20shot.svg)\n'
                '<img src="screen shot.svg" width="260" alt="入口">\n'
                '![外部设计](https://example.invalid/design.png)\n', encoding="utf-8"
            )
            self.assertEqual(checker.scan_document(document), [])
            document.write_text('![缺图](missing.png)\n<img src="missing2.png">\n', encoding="utf-8")
            findings = checker.scan_document(document)
            self.assertEqual([item["code"] for item in findings], ["missing-image", "missing-image"])
            self.assertEqual([item["line"] for item in findings], [1, 2])

    def test_ui_golden_is_portable_and_boundary_clean(self) -> None:
        checker = load_module(CHECKER, "check_prd_ui_golden")
        document = GOLDENS / "golden-ui.md"
        self.assertEqual(checker.scan_document(document), [])
        self.assertNotIn("/Users/", document.read_text(encoding="utf-8"))

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

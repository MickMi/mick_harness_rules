from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
ROLE_DIR = ROOT / "rules" / "roles"
STANDARD_ROLES = ("pm", "planner", "executor", "qa", "reviewer")
ALL_ROLES = (*STANDARD_ROLES, "designer")
SECTIONS = ("触发", "必读输入", "职责", "非职责", "交付物", "验收", "交接")
FIXTURES = ROOT / "tests" / "fixtures" / "role-behaviors.json"
CONTRACT_DOC = ROOT / "docs" / "ROLE-CONTRACTS.md"


class RoleContractTests(unittest.TestCase):
    def test_every_role_uses_the_same_seven_section_contract(self) -> None:
        for role in ALL_ROLES:
            text = (ROLE_DIR / f"{role}.md").read_text(encoding="utf-8")
            headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
            self.assertEqual(headings, list(SECTIONS), role)
            self.assertLessEqual(len(text.splitlines()), 100, role)

    def test_orchestration_defers_to_kernel_and_never_forces_roles_for_discussion(self) -> None:
        text = (ROLE_DIR / "orchestration.md").read_text(encoding="utf-8")
        self.assertIn("core.md", text)
        self.assertIn("纯解释", text)
        self.assertIn("handoff.created", text)
        self.assertNotIn("唯一交付格式", text)
        self.assertNotIn("必须反问", text)
        self.assertNotIn("当前流程在 [X 阶段]", text)

    def test_shared_delivery_mechanics_live_only_in_orchestration(self) -> None:
        for role in ALL_ROLES:
            text = (ROLE_DIR / f"{role}.md").read_text(encoding="utf-8")
            self.assertNotIn("core.md` 铁律 9", text, role)
            self.assertNotIn("handoff.created", text, role)

    def test_reviewer_may_run_minimal_checks_without_owning_qa_design(self) -> None:
        text = (ROLE_DIR / "reviewer.md").read_text(encoding="utf-8")
        self.assertIn("最小验证", text)
        self.assertNotIn("不设计或执行测试用例", text)

    def test_product_review_is_a_mandatory_pre_development_gate(self) -> None:
        orchestration = (ROLE_DIR / "orchestration.md").read_text(encoding="utf-8")
        reviewer = (ROLE_DIR / "reviewer.md").read_text(encoding="utf-8")
        skill = (ROOT / "rules" / "skills" / "product-logic-review" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("PM → Reviewer(product_review) → Executor → QA → Release", orchestration)
        self.assertIn("product_review", reviewer)
        self.assertIn("release_review", reviewer)
        self.assertIn("name: product-logic-review", skill)
        self.assertIn("changes_requested", skill)
        self.assertIn("approved", skill)
        self.assertIn("不要输出私有思维过程", skill)

    def test_designer_role_stays_generic_while_craft_preferences_live_in_skill(self) -> None:
        role = (ROLE_DIR / "designer.md").read_text(encoding="utf-8")
        skill = (ROOT / "rules" / "skills" / "designer-craft" / "SKILL.md").read_text(encoding="utf-8")
        for preference in ("5 秒", "紫色渐变", "满屏卡片"):
            self.assertNotIn(preference, role)
        self.assertIn("purple gradients", skill)

    def test_behavior_fixture_has_three_positive_and_two_boundary_cases_per_standard_role(self) -> None:
        data = json.loads(FIXTURES.read_text(encoding="utf-8"))
        for role in STANDARD_ROLES:
            self.assertGreaterEqual(len(data[role]["positive"]), 3, role)
            self.assertGreaterEqual(len(data[role]["boundary"]), 2, role)
            for case in (*data[role]["positive"], *data[role]["boundary"]):
                self.assertTrue(case["prompt"].strip())
                self.assertTrue(case["expected"].strip())

    def test_role_boundaries_remove_old_absolute_and_vendor_specific_behavior(self) -> None:
        combined = "\n".join((ROLE_DIR / f"{role}.md").read_text(encoding="utf-8") for role in ALL_ROLES)
        for banned in (
            "唯一职责",
            "逐字翻译成代码",
            "不直接和 PM 对话",
            "所有测试必须可自动化",
            "Mock 覆盖度评分 ≥ 7",
            "OD 单次输出上限",
            "Open Design / Figma Maker",
        ):
            self.assertNotIn(banned, combined)

    def test_designer_skill_is_audited_adapter_without_executable_side_effects(self) -> None:
        skill_root = ROOT / "rules" / "skills" / "designer-craft"
        text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        sources = (ROOT / "rules" / "skills" / "SOURCES.md").read_text(encoding="utf-8")
        self.assertIn("name: designer-craft", text)
        self.assertFalse((skill_root / "scripts").exists())
        self.assertIn("Do not install hooks", text)
        for commit in (
            "ae388ac58fb33aade50fc47e2be07c3192dcaabd",
            "97eb2a20032f0833e3d317162208a60385b0f96e",
            "4e799d45c17aec1498c269287a83b9dba22b966b",
            "f17010c9bb483898c1d9c9f42dde2b3a98889434",
        ):
            self.assertIn(commit, sources)

    def test_evaluation_document_separates_static_contracts_from_real_agent_samples(self) -> None:
        text = CONTRACT_DOC.read_text(encoding="utf-8")
        for dimension in ("加载", "职责", "交付", "验证", "交接"):
            self.assertIn(f"| {dimension} |", text)
        self.assertIn("Claude Code 真实角色样本 | 未评测（发布例外）", text)
        self.assertIn("Codex Reviewer 真实角色样本 | 已验证 · 10/10", text)
        self.assertIn("加载、职责、交付、验证、交接均为 2/2", text)
        self.assertIn("执行遵循", text)
        self.assertIn("未验证", text)


if __name__ == "__main__":
    unittest.main()

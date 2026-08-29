from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "harness-context-budget.py"
SPEC = importlib.util.spec_from_file_location("harness_context_budget", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
BUDGET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUDGET)


class ContextBudgetTests(unittest.TestCase):
    def test_core_keeps_quick_tasks_quiet_without_weakening_safety(self) -> None:
        core = (ROOT / "rules" / "core.md").read_text(encoding="utf-8")

        for phrase in (
            "默认 `auto`",
            "`quick` 不展示 Executor 前缀",
            "`quick` 交付省略卡片",
            "Self-Test 是内部安全检查",
            "不降低先读后改、危险确认、撞墙熔断和完成验证",
            "`standard → e2e` 必须由用户确认",
        ):
            self.assertIn(phrase, core)

    def test_current_generated_loaders_fit_budget_and_keep_kernel(self) -> None:
        report = BUDGET.measure(ROOT)

        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["required_kernel_markers"]["retained"])
        self.assertLess(report["sizes_bytes"]["combined"], 32 * 1024)

    def test_oversized_personal_capsule_is_truncated_without_losing_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            isolated_root = Path(directory) / "harness"
            (isolated_root / "rules").mkdir(parents=True)
            (isolated_root / "scripts").mkdir()
            (isolated_root / "dist").mkdir()
            shutil.copy2(ROOT / "generate.sh", isolated_root / "generate.sh")
            shutil.copy2(ROOT / "rules" / "core.md", isolated_root / "rules" / "core.md")
            shutil.copy2(ROOT / "rules" / "extended.md", isolated_root / "rules" / "extended.md")
            shutil.copy2(ROOT / "scripts" / "brain-resolve.sh", isolated_root / "scripts" / "brain-resolve.sh")
            home = Path(directory) / "home"
            brain = home / ".brain"
            (brain / "global").mkdir(parents=True)
            (brain / ".git").mkdir()
            (brain / "global" / "agent-capsule.md").write_text("品味与边界。" * 2000, encoding="utf-8")
            config = Path(directory) / "config"
            config.mkdir()
            (config / "brain.json").write_text(
                '{"mode":"local","local_path":"~/.brain","remote":null}\n',
                encoding="utf-8",
            )
            result = __import__("subprocess").run(
                [str(isolated_root / "generate.sh")],
                check=False,
                capture_output=True,
                text=True,
                env={
                    **__import__("os").environ,
                    "HOME": str(home),
                    "MICK_HARNESS_CONFIG_DIR": str(config),
                    "MICK_HARNESS_CAPSULE_MAX_BYTES": "512",
                    "MICK_HARNESS_ACTIVITY": "0",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (isolated_root / "dist" / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("Capsule 已按常驻上下文预算截断", text)


if __name__ == "__main__":
    unittest.main()

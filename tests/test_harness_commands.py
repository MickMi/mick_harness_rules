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

    def test_v021_context_budget_and_agent_skill_targets_are_machine_readable(self):
        budget = self.registry["context_budget"]
        self.assertLess(budget["combined_loader_bytes"], 32 * 1024)
        self.assertEqual(budget["checker"], "scripts/harness-context-budget.py")
        self.assertEqual(self.registry["host_adapters"]["codex"]["managed_skill_target"], "~/.codex/skills")
        self.assertEqual(self.registry["host_adapters"]["claude-code"]["managed_skill_target"], "~/.claude/skills")

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
    def run_harness(
        self,
        project: Path,
        *args: str,
        extra_env: dict[str, str] | None = None,
        include_project: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["MICK_HARNESS_ROOT"] = str(ROOT)
        env["MICK_HARNESS_ACTIVITY"] = "0"
        if extra_env:
            env.update(extra_env)
        command = [str(CLI_PATH), *args]
        if include_project:
            command.extend(("--project", str(project)))
        return subprocess.run(
            command,
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

    def test_plan_preview_reports_active_plan_as_recoverable_conflict(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_project(Path(temporary))
            (project / "plan.md").write_text(
                "> 🧭 状态：开发中\n\n# Plan: Existing\n\n- [ ] keep this\n", encoding="utf-8"
            )

            result = self.run_harness(project, "plan")

            self.assertEqual(result.returncode, 2)
            self.assertIn("Harness Plan Preview", result.stdout)
            self.assertIn("存在尚未完成的活跃计划", result.stdout)

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

    def brain_env(self, root: Path) -> dict[str, str]:
        return {
            "HOME": str(root / "home"),
            "MICK_HARNESS_CONFIG_DIR": str(root / "config"),
            "MICK_HARNESS_BRAIN_LEGACY_CONFIG": str(root / "missing-legacy.yaml"),
        }

    def test_brain_without_configuration_is_disabled_and_creates_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self.make_project(root, with_versions=False)
            env = self.brain_env(root)
            result = self.run_harness(
                project, "brain", "status", "--json", extra_env=env, include_project=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "disabled")
            self.assertEqual(payload["state"], "disabled")
            self.assertEqual(payload["sync_scope"], "none")
            self.assertFalse((root / "home" / ".mick-brain").exists())

    def test_bundled_legacy_remote_does_not_configure_a_new_user(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self.make_project(root, with_versions=False)
            env = {
                "HOME": str(root / "home"),
                "MICK_HARNESS_CONFIG_DIR": str(root / "config"),
                "MICK_HARNESS_BRAIN_LEGACY_CONFIG": "",
            }
            result = self.run_harness(
                project, "brain", "status", "--json", extra_env=env, include_project=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "disabled")
            self.assertEqual(payload["source"], "default")
            self.assertFalse((root / "home" / ".mick-brain").exists())

    def test_shell_brain_resolver_ignores_bundled_remote_for_a_new_user(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env = os.environ.copy()
            env["HOME"] = str(root / "home")
            env.pop("MICK_HARNESS_BRAIN_LEGACY_CONFIG", None)
            script = (
                f'source "{ROOT / "scripts/brain-resolve.sh"}"; '
                f'resolve_brain_dir "{ROOT}"; '
                'printf "%s|%s|%s\\n" "$BRAIN_MODE" "$BRAIN_CONFIG_SOURCE" "$BRAIN_DIR"'
            )
            result = subprocess.run(
                ["bash", "-c", script],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "disabled|default|")
            self.assertFalse((root / "home" / ".mick-brain").exists())

    def test_brain_local_configuration_previews_then_installs_explicitly(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self.make_project(root, with_versions=False)
            env = self.brain_env(root)
            local_brain = root / "private-brain"
            preview = self.run_harness(
                project,
                "brain",
                "configure",
                "--mode",
                "local",
                "--local-path",
                str(local_brain),
                extra_env=env,
                include_project=False,
            )
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertIn("预览完成，未发生写入", preview.stdout)
            self.assertFalse((root / "config" / "brain.json").exists())
            self.assertFalse(local_brain.exists())

            applied = self.run_harness(
                project,
                "brain",
                "configure",
                "--mode",
                "local",
                "--local-path",
                str(local_brain),
                "--apply",
                extra_env=env,
                include_project=False,
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertTrue((root / "config" / "brain.json").is_file())
            self.assertFalse(local_brain.exists())

            installed = self.run_harness(
                project, "brain", "install", extra_env=env, include_project=False
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            self.assertTrue((local_brain / ".git").is_dir())
            self.assertTrue((local_brain / "projects").is_dir())

            status = self.run_harness(
                project, "brain", "status", "--json", extra_env=env, include_project=False
            )
            payload = json.loads(status.stdout)
            self.assertEqual(payload["state"], "local_ready")
            self.assertEqual(payload["actual_remote"], None)
            self.assertEqual(payload["sync_scope"], "none")

    def test_brain_remote_mode_requires_a_credential_free_remote(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self.make_project(root, with_versions=False)
            env = self.brain_env(root)
            missing = self.run_harness(
                project,
                "brain",
                "configure",
                "--mode",
                "remote",
                "--apply",
                extra_env=env,
                include_project=False,
            )
            self.assertEqual(missing.returncode, 64)
            self.assertIn("需要 --remote", missing.stderr)

            secret = self.run_harness(
                project,
                "brain",
                "configure",
                "--mode",
                "remote",
                "--remote",
                "https://token@example.com/private/brain.git",
                "--apply",
                extra_env=env,
                include_project=False,
            )
            self.assertEqual(secret.returncode, 2)
            self.assertIn("不得包含用户名、Token 或密码", secret.stderr)
            self.assertFalse((root / "config" / "brain.json").exists())

    def test_disabled_brain_blocks_direct_memory_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self.make_project(root, with_versions=False)
            env = self.brain_env(root)
            env["MICK_HARNESS_ROOT"] = str(ROOT)
            result = subprocess.run(
                [str(ROOT / "scripts" / "brain-push.sh"), "private memory"],
                cwd=project,
                env={**os.environ, **env},
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Brain is disabled", result.stdout)
            self.assertFalse((root / "home" / ".mick-brain").exists())

    def make_e2e_project(self, root: Path, rounds: dict[str, dict] | None = None) -> Path:
        project = self.make_project(root, with_versions=False)
        (project / "docs" / "VERSIONS.md").write_text(
            "# Versions\n\n"
            "## 0.21.0\n\n"
            "- Status: in_progress\n"
            "- Branch: main\n"
            "- Goal: 建立安全的命令入口。\n\n"
            "### Requirements\n\n"
            "- [ ] `task-200` 单需求端到端交付\n",
            encoding="utf-8",
        )
        if rounds is not None:
            run_dir = project / ".harness-runtime" / "runs" / "run-test"
            run_dir.mkdir(parents=True)
            snapshot = {
                "schema_version": "0",
                "run": {"run_id": "run-test", "name": project.name, "status": "observing"},
                "plan": None,
                "workflows": {},
                "tasks": {},
                "artifacts": {},
                "verifications": [],
                "blocks": {},
                "approvals": {},
                "audit_findings": [],
                "agent_sessions": {},
                "agent_turns": {},
                "harness_commands": {},
                "work_rounds": rounds,
                "decisions": {},
                "handoffs": {},
                "collector_warnings": [],
                "last_sequence": len(rounds),
                "updated_at": "2026-08-24T00:00:00+00:00",
            }
            (run_dir / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
            (project / ".harness-runtime" / "index.json").write_text(
                json.dumps({"runs": [{"run_id": "run-test", "snapshot": "runs/run-test/snapshot.json"}]}),
                encoding="utf-8",
            )
        return project

    def test_e2e_preview_requires_one_current_requirement_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_e2e_project(Path(temporary))
            missing = self.run_harness(project, "e2e")
            self.assertEqual(missing.returncode, 64)
            self.assertIn("必须提供 --requirement", missing.stderr)

            preview = self.run_harness(project, "e2e", "--requirement", "task-200")
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertIn("当前角色：PM", preview.stdout)
            self.assertIn("不会自动 merge、push、tag、deploy 或 publish", preview.stdout)
            self.assertFalse((project / ".harness-runtime").exists())

            unknown = self.run_harness(project, "e2e", "--requirement", "task-999")
            self.assertEqual(unknown.returncode, 2)
            self.assertIn("当前版本 v0.21.0 不包含需求", unknown.stderr)
            self.assertFalse((project / ".harness-runtime").exists())

    def test_e2e_run_records_waiting_request_without_claiming_role_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_e2e_project(Path(temporary))
            result = self.run_harness(project, "e2e", "--requirement", "task-200", "--run")
            self.assertEqual(result.returncode, 2)
            self.assertIn("Harness 未伪造角色工作或自动启动 Agent", result.stdout)
            requests = list((project / ".harness-runtime" / "command-requests" / "e2e").glob("*.json"))
            self.assertEqual(len(requests), 1)
            payload = json.loads(requests[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "waiting_for_role")
            self.assertEqual(payload["current_role"], "PM")

    def test_e2e_only_marks_release_candidate_after_all_gate_evidence(self):
        rounds = {
            "pm": {"round_id": "pm", "requirement_id": "task-200", "role": "PM", "status": "completed", "gate_result": "ready_for_review", "derived_from_sequence": 1},
            "review": {"round_id": "review", "requirement_id": "task-200", "role": "Reviewer", "status": "completed", "review_mode": "product_review", "gate_result": "approved", "next_role": "Executor", "derived_from_sequence": 2},
            "dev": {"round_id": "dev", "requirement_id": "task-200", "role": "Executor", "status": "completed", "gate_result": "delivered", "artifact_refs": ["src/change.py"], "verification_refs": ["dev:test"], "derived_from_sequence": 3},
            "qa": {"round_id": "qa", "requirement_id": "task-200", "role": "QA", "status": "completed", "gate_result": "passed", "verification_refs": ["qa:test"], "derived_from_sequence": 4},
        }
        with tempfile.TemporaryDirectory() as temporary:
            project = self.make_e2e_project(Path(temporary), rounds=rounds)
            result = self.run_harness(project, "e2e", "--requirement", "task-200", "--run")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("已形成发布候选", result.stdout)
            request = next((project / ".harness-runtime" / "command-requests" / "e2e").glob("*.json"))
            payload = json.loads(request.read_text(encoding="utf-8"))
            self.assertTrue(payload["release_candidate"])
            self.assertEqual(payload["status"], "release_candidate")


if __name__ == "__main__":
    unittest.main()

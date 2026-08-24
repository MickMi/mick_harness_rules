#!/usr/bin/env python3
"""Deterministic command surface for Harness plan and goal workflows."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


EXIT_CONFLICT = 2
EXIT_USAGE = 64
EXIT_IO = 74

STATUS_PATTERN = re.compile(r"^>\s*🧭\s*状态[：:]\s*(.+?)\s*$", re.MULTILINE)
CHECKBOX_PATTERN = re.compile(r"^- \[([ xX])\]\s+(.+?)\s*$", re.MULTILINE)
VERSION_PATTERN = re.compile(r"^##\s+(?:v)?(\d+\.\d+\.\d+)\s*$", re.MULTILINE)
FIELD_PATTERN = re.compile(r"^-\s+(Status|Goal)\s*:\s*(.+?)\s*$", re.MULTILINE)
GOAL_HEADING_PATTERN = re.compile(r"^## Goal\s*$", re.MULTILINE)
NEXT_H2_PATTERN = re.compile(r"^##\s+", re.MULTILINE)
UNSTABLE_GOAL_PATTERNS = (
    (re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b", re.IGNORECASE), "包含版本号"),
    (re.compile(r"\btask-\d+\b", re.IGNORECASE), "包含需求编号"),
    (re.compile(r"(?:^|\s)(?:实现|修复|重构|迁移|升级)(?:\s|$)"), "更像实施任务"),
    (re.compile(r"(?:\.py|\.js|\.ts|\.tsx|\.swift|\.md|API|数据库|schema|endpoint)", re.IGNORECASE), "包含技术实现细节"),
)


@dataclass(frozen=True)
class ProjectFacts:
    path: Path
    name: str
    branch: str
    dirty_count: int
    harness_loaded: bool
    active_version: str | None
    version_goal: str | None
    requirements: tuple[str, ...]


class CommandError(Exception):
    def __init__(self, message: str, exit_code: int):
        super().__init__(message)
        self.exit_code = exit_code


class HarnessArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CommandError(f"输入无效：{message}", EXIT_USAGE)


def resolve_project(raw_path: str | None) -> Path:
    candidate = Path(raw_path or os.getcwd()).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise CommandError(f"项目不可用：{candidate}（{exc}）", EXIT_IO) from exc
    if not resolved.is_dir():
        raise CommandError(f"项目路径不是目录：{resolved}", EXIT_USAGE)
    return resolved


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else ""
    except OSError as exc:
        raise CommandError(f"无法读取 {path}：{exc}", EXIT_IO) from exc


def git_output(project: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(project), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def parse_active_version(text: str) -> tuple[str | None, str | None, tuple[str, ...]]:
    for match in VERSION_PATTERN.finditer(text):
        start = match.start()
        next_match = VERSION_PATTERN.search(text, match.end())
        section = text[start : next_match.start() if next_match else len(text)]
        fields = {key: value.strip() for key, value in FIELD_PATTERN.findall(section)}
        if fields.get("Status", "").lower() == "released":
            continue
        requirements = tuple(
            item.strip()
            for state, item in CHECKBOX_PATTERN.findall(section)
            if state.lower() != "x"
        )
        return match.group(1), fields.get("Goal"), requirements
    return None, None, ()


def scan_project(project: Path) -> ProjectFacts:
    versions_text = read_text(project / "docs" / "VERSIONS.md")
    active_version, version_goal, requirements = parse_active_version(versions_text)
    branch = git_output(project, "branch", "--show-current") or "未检测到 Git 分支"
    dirty_lines = git_output(project, "status", "--short").splitlines()
    harness_loaded = any(
        path.exists()
        for path in (project / "AGENTS.md", project / ".harness", project / ".harness-config.yaml")
    )
    return ProjectFacts(
        path=project,
        name=project.name,
        branch=branch,
        dirty_count=len(dirty_lines),
        harness_loaded=harness_loaded,
        active_version=active_version,
        version_goal=version_goal,
        requirements=requirements,
    )


def active_plan_state(plan_text: str) -> tuple[bool, int, int, str]:
    tasks = CHECKBOX_PATTERN.findall(plan_text)
    completed = sum(1 for state, _ in tasks if state.lower() == "x")
    status_match = STATUS_PATTERN.search(plan_text)
    status = status_match.group(1).strip() if status_match else "未声明"
    status_inactive = any(token in status.lower() for token in ("released", "complete", "completed", "archived", "已完成", "已发布", "已归档"))
    active = bool(tasks) and completed < len(tasks) and not status_inactive
    return active, completed, len(tasks), status


def plan_stage(facts: ProjectFacts, title: str) -> str:
    date = dt.date.today().isoformat()
    lines = [
        f"## {date} · {title}",
        "",
        "### 目标",
        "",
        facts.version_goal or title,
        "",
        "### 扫描事实",
        "",
        f"- 项目：`{facts.name}`",
        f"- 当前分支：`{facts.branch}`",
        f"- 未提交改动：{facts.dirty_count} 处",
        f"- Harness：{'已发现' if facts.harness_loaded else '未发现'}",
        f"- 当前版本：`v{facts.active_version}`" if facts.active_version else "- 当前版本：未识别",
        "",
        "### 执行步骤",
        "",
    ]
    if facts.requirements:
        lines.extend(f"- [ ] {item}" for item in facts.requirements)
    else:
        lines.append("- [ ] 明确本阶段需求、完成判定与验证方式")
    lines.extend(
        [
            "",
            "### 验证与停止条件",
            "",
            "- 每条交付都必须有本次可复现的验证证据。",
            "- 需求歧义、破坏性操作、外部发布或现有活跃计划冲突时停止并交还用户裁决。",
            "",
        ]
    )
    return "\n".join(lines)


def replace_status_line(text: str, title: str) -> str:
    status = f"> 🧭 状态：{title} 规划中 | 当前归属：Planner | 最近动作：由 harness plan 建立计划档案"
    if STATUS_PATTERN.search(text):
        return STATUS_PATTERN.sub(status, text, count=1)
    return f"{status}\n\n{text.lstrip()}"


def atomic_write(path: Path, content: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except (OSError, UnboundLocalError):
            pass
        raise CommandError(f"无法安全写入 {path}：{exc}", EXIT_IO) from exc


def default_plan_title(facts: ProjectFacts) -> str:
    if facts.active_version:
        return f"v{facts.active_version} 交付计划"
    if facts.branch not in ("main", "master", "未检测到 Git 分支"):
        return f"{facts.branch} 工作计划"
    return "项目下一阶段计划"


def command_plan(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    facts = scan_project(project)
    plan_path = project / "plan.md"
    existing = read_text(plan_path)
    active, completed, total, status = active_plan_state(existing)
    title = (args.title or default_plan_title(facts)).strip()

    print("Harness Plan Preview")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"项目：{project}")
    print(f"分支：{facts.branch}；未提交改动：{facts.dirty_count} 处")
    print(f"Harness：{'已发现' if facts.harness_loaded else '未发现'}")
    print(f"当前版本：{('v' + facts.active_version) if facts.active_version else '未识别'}")
    print(f"计划文件：{plan_path}")
    if existing:
        print(f"现有计划：{status}；{completed}/{total} 已完成")
    else:
        print("现有计划：无")

    if active:
        print("\n停止：存在尚未完成的活跃计划，本命令不会覆盖或并行追加。")
        print("未发生写入。请先完成、归档或由 Planner 裁决现有计划。")
        return EXIT_CONFLICT if args.apply else 0

    stage = plan_stage(facts, title)
    print(f"\n拟建立阶段：{title}")
    if facts.requirements:
        print(f"拟纳入当前版本未完成需求：{len(facts.requirements)} 条")
    else:
        print("未识别可直接纳入的版本需求，将建立一条需求澄清步骤。")

    if not args.apply:
        print("\n预览完成，未发生写入。确认后运行：harness plan --apply")
        return 0

    if existing:
        content = replace_status_line(existing.rstrip(), title).rstrip() + "\n\n" + stage
        action = "追加新阶段并保留历史"
    else:
        header = (
            f"> 🧭 状态：{title} 规划中 | 当前归属：Planner | 最近动作：由 harness plan 建立计划档案\n\n"
            f"# Plan: {facts.name}\n\n"
        )
        content = header + stage
        action = "创建计划档案"
    atomic_write(plan_path, content.rstrip() + "\n")
    print(f"\n已{action}：{plan_path}")
    print("下一步：由 PM / Reviewer 确认需求与完成判定后，再进入开发。")
    return 0


def extract_goal(text: str) -> str | None:
    heading = GOAL_HEADING_PATTERN.search(text)
    if not heading:
        return None
    next_heading = NEXT_H2_PATTERN.search(text, heading.end())
    body = text[heading.end() : next_heading.start() if next_heading else len(text)].strip()
    return body or None


def validate_goal(goal: str) -> list[str]:
    reasons = [message for pattern, message in UNSTABLE_GOAL_PATTERNS if pattern.search(goal)]
    if len(goal.strip()) < 12:
        reasons.append("目标过短，无法表达稳定的用户价值和项目边界")
    return reasons


def replace_goal(text: str, goal: str, project_name: str) -> str:
    heading = GOAL_HEADING_PATTERN.search(text)
    if not heading:
        if text.strip():
            first_line_end = text.find("\n")
            if first_line_end >= 0 and text[:first_line_end].startswith("# "):
                return text[: first_line_end + 1] + f"\n## Goal\n\n{goal}\n" + text[first_line_end + 1 :].lstrip("\n")
            return f"# Project Profile\n\n## Goal\n\n{goal}\n\n{text.lstrip()}"
        return f"# {project_name} Project Profile\n\n## Goal\n\n{goal}\n"
    next_heading = NEXT_H2_PATTERN.search(text, heading.end())
    end = next_heading.start() if next_heading else len(text)
    suffix = text[end:].lstrip("\n")
    replacement = text[: heading.end()] + f"\n\n{goal}\n"
    if suffix:
        replacement += "\n" + suffix
    return replacement


def command_goal(args: argparse.Namespace) -> int:
    project = resolve_project(args.project)
    goal_path = project / "docs" / "PROJECT.md"
    existing_text = read_text(goal_path)
    existing_goal = extract_goal(existing_text)
    candidate = args.set_value.strip() if args.set_value else None

    print("Harness Goal Preview")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"项目：{project}")
    print(f"目标文件：{goal_path}")
    print(f"当前长期目标：{existing_goal or '未建立'}")

    if candidate:
        reasons = validate_goal(candidate)
        print(f"拟议长期目标：{candidate}")
        if reasons:
            print("\n停止：拟议内容不像稳定的人类产品目标：")
            for reason in reasons:
                print(f"- {reason}")
            print("未发生写入。请描述长期用户价值，不要写版本、任务或技术方案。")
            return EXIT_CONFLICT if args.apply else 0
    elif args.apply:
        print("\n停止：--apply 必须同时提供 --set <human project goal>。")
        print("未发生写入。")
        return EXIT_USAGE

    if not args.apply:
        print("\n预览完成，未发生写入。")
        if candidate:
            print("确认后运行：harness goal --set \"…\" --apply")
        else:
            print("提供候选：harness goal --set \"长期用户价值\"")
        return 0

    assert candidate is not None
    if candidate == existing_goal:
        print("\n目标内容未变化，无需写入。")
        return 0
    content = replace_goal(existing_text, candidate, project.name)
    atomic_write(goal_path, content.rstrip() + "\n")
    print(f"\n已更新长期目标：{goal_path}")
    print("未修改 plan.md、版本目标、代码或 Git 状态。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = HarnessArgumentParser(prog="harness-command", add_help=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="scan project facts and preview a plan archive")
    plan.add_argument("--project")
    plan.add_argument("--title")
    plan.add_argument("--apply", action="store_true")
    plan.set_defaults(handler=command_plan)

    goal = subparsers.add_parser("goal", help="preview or maintain the long-term project goal")
    goal.add_argument("--project")
    goal.add_argument("--set", dest="set_value")
    goal.add_argument("--apply", action="store_true")
    goal.set_defaults(handler=command_goal)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        return args.handler(args)
    except CommandError as exc:
        print(f"Harness command stopped: {exc}", file=sys.stderr)
        print("未发生未确认的写入。", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

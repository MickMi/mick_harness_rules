#!/usr/bin/env python3
"""Deterministic command surface for Harness plan and goal workflows."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
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


def brain_config_path() -> Path:
    configured = os.environ.get("MICK_HARNESS_CONFIG_DIR")
    root = Path(configured).expanduser() if configured else Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mick-harness"
    return root / "brain.json"


def legacy_brain_config_path() -> Path:
    configured = os.environ.get("MICK_HARNESS_BRAIN_LEGACY_CONFIG")
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[1] / "config" / ".brain-config.yaml"


def sanitize_remote(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"^(https?://)[^/@]+@", r"\1", value.strip())


def legacy_brain_settings() -> dict[str, object] | None:
    path = legacy_brain_config_path()
    text = read_text(path)
    if not text:
        return None
    remote_match = re.search(r'^\s*remote:\s*["\']?([^"\'\n]+)', text, re.MULTILINE)
    local_match = re.search(r'^\s*local_path:\s*["\']?([^"\'\n]+)', text, re.MULTILINE)
    remote = remote_match.group(1).strip() if remote_match else None
    local_path = local_match.group(1).strip() if local_match else "~/.mick-brain"
    explicit_legacy = bool(os.environ.get("MICK_HARNESS_BRAIN_LEGACY_CONFIG"))
    local_exists = Path(local_path).expanduser().exists()
    if not explicit_legacy and not local_exists:
        return None
    if not remote and not local_exists:
        return None
    return {
        "version": 1,
        "mode": "remote" if remote else "local",
        "local_path": local_path,
        "remote": remote,
        "source": "legacy",
        "config_path": str(path),
    }


def load_brain_settings() -> dict[str, object]:
    path = brain_config_path()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Brain 配置不可读：{path}（{exc}）", EXIT_IO) from exc
        mode = data.get("mode")
        if mode not in {"local", "remote", "disabled"}:
            raise CommandError(f"Brain 配置包含无效模式：{mode}", EXIT_CONFLICT)
        return {
            "version": 1,
            "mode": mode,
            "local_path": str(data.get("local_path") or "~/.mick-brain"),
            "remote": data.get("remote") or None,
            "source": "user",
            "config_path": str(path),
        }
    legacy = legacy_brain_settings()
    if legacy:
        return legacy
    return {
        "version": 1,
        "mode": "disabled",
        "local_path": "~/.mick-brain",
        "remote": None,
        "source": "default",
        "config_path": str(path),
    }


def actual_git_remote(root: Path) -> str | None:
    value = git_output(root, "remote", "get-url", "origin") if (root / ".git").is_dir() else ""
    return value or None


def brain_status_payload() -> dict[str, object]:
    settings = load_brain_settings()
    local_path = Path(str(settings["local_path"])).expanduser().resolve()
    actual_remote = actual_git_remote(local_path)
    configured_remote = str(settings["remote"]) if settings.get("remote") else None
    mode = str(settings["mode"])
    configured_identity = (sanitize_remote(configured_remote) or "").rstrip("/").removesuffix(".git")
    actual_identity = (sanitize_remote(actual_remote) or "").rstrip("/").removesuffix(".git")
    remote_matches = bool(configured_identity and actual_identity and configured_identity == actual_identity)
    if mode == "disabled":
        state = "disabled"
    elif not (local_path / ".git").is_dir():
        state = "not_installed"
    elif mode == "local":
        state = "local_ready"
    elif remote_matches:
        state = "connected"
    elif actual_remote:
        state = "remote_mismatch"
    else:
        state = "remote_not_connected"
    return {
        **settings,
        "config_path": str(settings.get("config_path") or brain_config_path()),
        "preferred_config_path": str(brain_config_path()),
        "local_path": str(local_path),
        "configured_remote": sanitize_remote(configured_remote),
        "actual_remote": sanitize_remote(actual_remote),
        "remote_matches": remote_matches,
        "state": state,
        "writes": "none" if mode == "disabled" else "local-first",
        "sync_scope": "none" if mode in {"disabled", "local"} else "project records plus approved global/profile records",
    }


def print_brain_status(payload: dict[str, object]) -> None:
    labels = {
        "disabled": "暂不启用",
        "not_installed": "已配置，尚未建立本地 Brain",
        "local_ready": "仅本机可用",
        "connected": "私有远端已连接",
        "remote_mismatch": "配置仓库与实际 origin 不一致",
        "remote_not_connected": "已配置远端，本地仓库尚未连接",
    }
    print("Brain Status")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"模式：{payload['mode']}（{labels.get(str(payload['state']), payload['state'])}）")
    print(f"配置：{payload['config_path']}（来源：{payload['source']}）")
    print(f"本地写入：{payload['local_path'] if payload['writes'] != 'none' else '关闭'}")
    print(f"配置远端：{payload['configured_remote'] or '无'}")
    print(f"实际 origin：{payload['actual_remote'] or '无'}")
    print(f"同步范围：{payload['sync_scope']}")
    if payload["state"] == "remote_mismatch":
        print("停止：配置仓库与实际 origin 不一致；不会自动选择或同步任一仓库。")


def command_brain(args: argparse.Namespace) -> int:
    if args.action == "status":
        payload = brain_status_payload()
        if args.json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print_brain_status(payload)
        return EXIT_CONFLICT if payload["state"] == "remote_mismatch" else 0

    if args.action != "configure":
        raise CommandError(f"不支持的 Brain 动作：{args.action}", EXIT_USAGE)
    if not args.mode:
        raise CommandError("configure 需要 --mode local|remote|disabled", EXIT_USAGE)
    if args.mode == "remote" and not args.remote:
        raise CommandError("remote 模式需要 --remote <private Git URL>", EXIT_USAGE)
    if args.mode != "remote" and args.remote:
        raise CommandError("只有 remote 模式可以设置 --remote", EXIT_USAGE)
    if args.remote and re.match(r"^https?://[^/@]+@", args.remote):
        raise CommandError("远端 URL 不得包含用户名、Token 或密码；请使用系统凭据管理", EXIT_CONFLICT)

    current = load_brain_settings()
    local_path = str(Path(args.local_path or current.get("local_path") or "~/.mick-brain").expanduser())
    proposed = {
        "version": 1,
        "mode": args.mode,
        "local_path": local_path,
        "remote": args.remote if args.mode == "remote" else None,
        "updated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    }
    print("Brain Configure Preview")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"当前模式：{current['mode']}（来源：{current['source']}）")
    print(f"拟议模式：{proposed['mode']}")
    print(f"本地路径：{proposed['local_path'] if proposed['mode'] != 'disabled' else '不写入'}")
    print(f"私有远端：{sanitize_remote(proposed['remote']) or '无'}")
    print(f"配置位置：{brain_config_path()}")
    print("本次不会删除已有 Brain 数据，也不会自动克隆、推送或安装 Hook。")
    if not args.apply:
        print("\n预览完成，未发生写入。确认后增加 --apply。")
        return 0
    atomic_write(brain_config_path(), json.dumps(proposed, ensure_ascii=False, indent=2) + "\n")
    print(f"\n已写入 Brain 配置：{brain_config_path()}")
    if args.mode == "disabled":
        print("Brain 已停用；已有本地数据保持原样。")
    else:
        print("下一步：运行 harness brain install 建立或连接本地 Brain。")
    return 0


def load_observer_module():
    path = Path(__file__).resolve().with_name("harness-observe.py")
    spec = importlib.util.spec_from_file_location("harness_command_observer", path)
    if spec is None or spec.loader is None:
        raise CommandError("无法加载 Harness 需求状态机", 69)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def readonly_runtime_snapshot(project: Path, observer) -> dict[str, object]:
    index = observer.load_json(observer.runtime_root(project) / "index.json", {}) or {}
    for run in index.get("runs", []):
        snapshot_value = run.get("snapshot")
        if not snapshot_value:
            continue
        snapshot = observer.load_json(observer.runtime_root(project) / str(snapshot_value))
        if isinstance(snapshot, dict):
            return snapshot
    return observer.project_events([])


def e2e_request_path(project: Path, requirement_id: str) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_requirement = re.sub(r"[^A-Za-z0-9._-]+", "-", requirement_id).strip("-.")
    if not safe_requirement:
        raise CommandError("requirement_id 规范化后为空", EXIT_USAGE)
    return project / ".harness-runtime" / "command-requests" / "e2e" / f"{stamp}-{safe_requirement}.json"


def command_e2e(args: argparse.Namespace) -> int:
    if not args.requirement:
        raise CommandError("e2e 必须提供 --requirement <requirement_id>", EXIT_USAGE)
    project = resolve_project(args.project)
    observer = load_observer_module()
    snapshot = readonly_runtime_snapshot(project, observer)
    git = observer.git_workspace_snapshot(project)
    versions = observer.version_plan_snapshot(project, snapshot, git)
    current = observer.current_version_snapshot(snapshot, versions)
    if not current:
        raise CommandError("当前项目没有可识别的版本与需求，先运行 harness plan", EXIT_CONFLICT)
    requirement = next(
        (item for item in current.get("requirements", []) if item.get("requirement_id") == args.requirement),
        None,
    )
    if requirement is None:
        historical = [
            item.get("version")
            for version in versions.get("items", [])
            for item in version.get("requirements", [])
            if item.get("requirement_id") == args.requirement
        ]
        available = ", ".join(
            str(item.get("requirement_id")) for item in current.get("requirements", [])[:8]
        ) or "无"
        detail = f"；该 ID 只出现在历史版本 {', '.join(historical)}" if historical else ""
        raise CommandError(
            f"当前版本 v{current.get('version')} 不包含需求 {args.requirement}{detail}。可选：{available}",
            EXIT_CONFLICT,
        )
    workflow = requirement.get("workflow")
    if not workflow:
        raise CommandError("当前版本尚未启用结构化需求门禁，不能运行 E2E", EXIT_CONFLICT)

    stage = str(workflow.get("stage") or "unknown")
    release_candidate = stage in {"release_ready", "completed"}
    current_role = workflow.get("current_role")
    payload = {
        "schema_version": "1",
        "command": "e2e",
        "project": str(project),
        "version": current.get("version"),
        "requirement_id": args.requirement,
        "title": requirement.get("title"),
        "stage": stage,
        "stage_label": workflow.get("stage_label"),
        "gate_status": workflow.get("gate_status"),
        "gate_reason": workflow.get("gate_reason"),
        "current_role": current_role,
        "allowed_next_roles": workflow.get("allowed_next_roles") or [],
        "release_candidate": release_candidate,
        "status": "release_candidate" if release_candidate else "waiting_for_role",
        "created_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    }

    if args.json_output and not args.run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Harness E2E Preview")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"项目：{project}")
        print(f"版本：v{current.get('version')}")
        print(f"需求：{args.requirement} · {requirement.get('title') or '未命名'}")
        print(f"当前关卡：{workflow.get('stage_label')}（{workflow.get('gate_status')}）")
        print(f"当前角色：{current_role or '无'}")
        print(f"停止/推进依据：{workflow.get('gate_reason')}")
        rejected = workflow.get("rejected_transitions") or []
        if rejected:
            print(f"已拒绝的非法跳转：{len(rejected)} 条")
        print("最远边界：发布候选；不会自动 merge、push、tag、deploy 或 publish。")

    if not args.run:
        if not args.json_output:
            print("\n预览完成，未发生写入。确认后增加 --run。")
        return 0

    request_path = e2e_request_path(project, args.requirement)
    atomic_write(request_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    if args.json_output:
        print(json.dumps({**payload, "request_path": str(request_path.relative_to(project))}, ensure_ascii=False, indent=2))
    else:
        print(f"\n已记录 E2E 请求：{request_path.relative_to(project)}")
        if release_candidate:
            print("结果：需求门禁证据完整，已形成发布候选；正式发布仍需用户确认。")
        else:
            print(f"结果：等待 {current_role or '下一角色'} 完成当前关卡；Harness 未伪造角色工作或自动启动 Agent。")
    return 0 if release_candidate else EXIT_CONFLICT


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
        return EXIT_CONFLICT

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

    brain = subparsers.add_parser("brain", help="inspect or configure optional Brain memory")
    brain.add_argument("action", nargs="?", default="status", choices=("status", "configure"))
    brain.add_argument("--mode", choices=("local", "remote", "disabled"))
    brain.add_argument("--local-path")
    brain.add_argument("--remote")
    brain.add_argument("--apply", action="store_true")
    brain.add_argument("--json", dest="json_output", action="store_true")
    brain.set_defaults(handler=command_brain)

    e2e = subparsers.add_parser("e2e", help="inspect one requirement through deterministic delivery gates")
    e2e.add_argument("--project")
    e2e.add_argument("--requirement")
    e2e.add_argument("--run", action="store_true")
    e2e.add_argument("--json", dest="json_output", action="store_true")
    e2e.set_defaults(handler=command_e2e)
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

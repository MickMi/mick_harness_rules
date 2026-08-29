#!/usr/bin/env python3
"""Read-only external Skill discovery and Harness compatibility diagnostics."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable


SCHEMA_VERSION = "0.1.0"
MAX_SKILL_BYTES = 256 * 1024
MAX_SKILLS = 500
ROLE_ASSIGNMENTS = {
    "designer-craft": ["Designer"],
    "harness-brain": ["PM"],
    "harness-e2e": ["PM", "Reviewer", "Executor", "QA"],
    "harness-goal": ["PM"],
    "harness-plan": ["PM"],
    "prd-for-humans": ["PM"],
    "product-logic-review": ["Reviewer"],
}
NEGATION_MARKERS = ("do not", "don't", "never", "must not", "禁止", "不得", "不要", "不会")


FINDING_RULES = (
    (
        "destructive_command",
        "blocked",
        re.compile(r"\brm\s+-rf\b|\bgit\s+reset\s+--hard\b|\bgit\s+push\b[^\n]*\s--force(?:-with-lease)?\b", re.I),
        "包含破坏文件或改写 Git 历史的命令",
    ),
    (
        "global_loader_overwrite",
        "blocked",
        re.compile(r"(?:replace|overwrite|write|edit|修改|覆盖|写入)[^\n]{0,100}(?:~/?\.codex/AGENTS\.md|~/?\.claude/CLAUDE\.md|(?:^|[ /])AGENTS\.md|(?:^|[ /])CLAUDE\.md)", re.I),
        "试图改写 Agent 的全局或项目 Loader",
    ),
    (
        "hook_management",
        "review",
        re.compile(r"(?:install|create|write|replace|edit|enable|安装|创建|写入|修改|启用)[^\n]{0,100}(?:hooks?\.json|settings\.json|SessionStart|SessionEnd|PreToolUse|PostToolUse|\bhooks?\b)", re.I),
        "包含 Hook 或 Agent 生命周期配置",
    ),
    (
        "role_ownership",
        "review",
        re.compile(r"\byou are (?:the |a )?(?:pm|product manager|designer|developer|reviewer|qa|orchestrator)\b|(?:接管|负责所有|拥有)[^\n]{0,60}(?:角色|任务|调度)", re.I),
        "包含独立角色或任务调度定义",
    ),
    (
        "completion_definition",
        "review",
        re.compile(r"\bdefinition of done\b|(?:define|decide|own)[^\n]{0,80}\b(?:task is )?(?:done|complete)\b|(?:定义|决定|接管)[^\n]{0,60}(?:完成标准|完成定义)", re.I),
        "包含独立完成定义",
    ),
    (
        "brain_write",
        "review",
        re.compile(r"(?:write|append|commit|push|写入|追加|提交|同步)[^\n]{0,100}(?:\.brain|\.mick-brain|mick[_ -]?brain|Brain memory|Brain 记忆)", re.I),
        "包含 Brain 写入或同步行为",
    ),
    (
        "network_install",
        "review",
        re.compile(r"\b(?:curl|wget|git\s+clone|pipx?\s+install|npm\s+(?:install|i)|pnpm\s+(?:install|add)|brew\s+install)\b", re.I),
        "包含联网下载或依赖安装命令",
    ),
    (
        "background_service",
        "review",
        re.compile(r"\b(?:launchctl|systemctl|nohup)\b|(?:start|run|启动|运行)[^\n]{0,60}(?:daemon|background service|后台服务)", re.I),
        "包含后台服务或常驻进程管理",
    ),
)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    values: dict[str, str] = {}
    lines = text[4:end].splitlines()
    index = 0
    while index < len(lines):
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$", lines[index])
        if not match:
            index += 1
            continue
        key, raw_value = match.group(1), match.group(2)
        if raw_value in {"|", "|-", ">", ">-"}:
            fragments: list[str] = []
            index += 1
            while index < len(lines) and (not lines[index].strip() or lines[index][:1].isspace()):
                if lines[index].strip():
                    fragments.append(lines[index].strip())
                index += 1
            values[key] = " ".join(fragments)
            continue
        values[key] = raw_value.strip("\"'")
        index += 1
    return values


def _display_path(path: Path, *, home: Path, harness_root: Path, project: dict[str, Any] | None = None) -> str:
    if _is_within(path, harness_root):
        return path.resolve().relative_to(harness_root.resolve()).as_posix()
    if project is not None:
        project_root = Path(str(project["path"]))
        if _is_within(path, project_root):
            relative = path.resolve().relative_to(project_root.resolve()).as_posix()
            return f"{project.get('name') or project.get('project_id')}/{relative}"
    if _is_within(path, home):
        return f"~/{path.resolve().relative_to(home.resolve()).as_posix()}"
    return path.name


def _line_findings(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        if any(marker in lowered for marker in NEGATION_MARKERS):
            continue
        for code, severity, pattern, summary in FINDING_RULES:
            if code in seen or not pattern.search(line):
                continue
            seen.add(code)
            findings.append({"code": code, "severity": severity, "summary": summary, "line": line_number})
    return findings


def _resource_summary(directory: Path) -> dict[str, Any]:
    values: dict[str, list[str]] = {"scripts": [], "references": [], "agents": []}
    for key in values:
        target = directory / key
        if not target.is_dir() or target.is_symlink():
            continue
        for item in sorted(target.iterdir(), key=lambda candidate: candidate.name.lower()):
            if item.is_file() and not item.is_symlink():
                values[key].append(item.name)
    return {key: items for key, items in values.items() if items}


def analyze_skill(
    skill_path: Path,
    *,
    root: Path,
    source: str,
    scope: str,
    home: Path,
    harness_root: Path,
    project: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if skill_path.name != "SKILL.md" or skill_path.is_symlink() or not _is_within(skill_path, root):
        return None
    try:
        size = skill_path.stat().st_size
    except OSError:
        return None
    if size <= 0 or size > MAX_SKILL_BYTES:
        return None
    try:
        text = skill_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    metadata = _frontmatter(text)
    name = metadata.get("name") or skill_path.parent.name
    description = metadata.get("description") or "未提供用途说明。"
    findings = _line_findings(text)
    resources = _resource_summary(skill_path.parent)
    if resources.get("scripts") and source != "harness_builtin":
        findings.append(
            {
                "code": "executable_resources",
                "severity": "review",
                "summary": "包含可执行脚本；诊断器只列出文件名，不会运行",
                "count": len(resources["scripts"]),
            }
        )
    if not metadata.get("name") or not metadata.get("description"):
        findings.append(
            {
                "code": "metadata_missing",
                "severity": "review",
                "summary": "缺少标准 name 或 description 元数据",
            }
        )
    status = "compatible"
    if any(item["severity"] == "blocked" for item in findings):
        status = "blocked"
    elif findings:
        status = "review_required"
    roles = ROLE_ASSIGNMENTS.get(name, []) if source == "harness_builtin" else []
    trust_status = "audited" if source == "harness_builtin" else ("vendor_managed" if source in {"codex_system", "codex_plugin"} else "unreviewed")
    stable_source = f"{source}:{scope}:{_display_path(skill_path, home=home, harness_root=harness_root, project=project)}"
    return {
        "skill_id": f"skill_{hashlib.sha256(stable_source.encode('utf-8')).hexdigest()[:16]}",
        "name": name,
        "description": description,
        "source": source,
        "trust_status": trust_status,
        "scope": scope,
        "project_id": project.get("project_id") if project else None,
        "path": _display_path(skill_path, home=home, harness_root=harness_root, project=project),
        "discovery_status": "discovered",
        "installation_status": "installed",
        "assignment_status": "assigned" if roles else "unassigned",
        "roles": roles,
        "load_status": "unverified",
        "load_evidence": [],
        "resources": resources,
        "compatibility": {"status": status, "findings": findings},
    }


def _root_descriptors(
    *, harness_root: Path, home: Path, projects: Iterable[dict[str, Any]]
) -> list[tuple[Path, str, str, dict[str, Any] | None]]:
    values: list[tuple[Path, str, str, dict[str, Any] | None]] = [
        (harness_root / "rules" / "skills", "harness_builtin", "harness", None),
        (home / ".codex" / "skills" / ".system", "codex_system", "global", None),
        (home / ".codex" / "skills", "codex_external", "global", None),
        (home / ".claude" / "skills", "claude_external", "global", None),
        (home / ".agents" / "skills", "agent_external", "global", None),
        (home / ".codex" / "plugins" / "cache", "codex_plugin", "global", None),
    ]
    for project in projects:
        path_value = project.get("path")
        if path_value:
            values.append((Path(str(path_value)) / ".harness" / "skills", "project_skill", "project", project))
    return values


def skill_snapshot(
    *,
    harness_root: Path | None = None,
    home: Path | None = None,
    projects: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    harness_root = (harness_root or Path(__file__).resolve().parents[1]).resolve()
    home = (home or Path.home()).resolve()
    items: list[dict[str, Any]] = []
    visited: set[Path] = set()
    truncated = False
    for root, source, scope, project in _root_descriptors(harness_root=harness_root, home=home, projects=projects):
        if not root.is_dir() or root.is_symlink():
            continue
        for skill_path in sorted(root.rglob("SKILL.md"), key=lambda candidate: candidate.as_posix().lower()):
            if len(items) >= MAX_SKILLS:
                truncated = True
                break
            try:
                resolved = skill_path.resolve()
            except OSError:
                continue
            if resolved in visited or not _is_within(skill_path, root):
                continue
            visited.add(resolved)
            item = analyze_skill(
                skill_path,
                root=root,
                source=source,
                scope=scope,
                home=home,
                harness_root=harness_root,
                project=project,
            )
            if item is not None:
                items.append(item)
        if truncated:
            break
    items.sort(key=lambda item: (item["compatibility"]["status"], item["scope"], item["name"].lower(), item["path"]))
    summary = {
        "discovered": len(items),
        "installed": sum(item["installation_status"] == "installed" for item in items),
        "assigned": sum(item["assignment_status"] == "assigned" for item in items),
        "verified_loaded": sum(item["load_status"] == "verified" for item in items),
        "compatible": sum(item["compatibility"]["status"] == "compatible" for item in items),
        "review_required": sum(item["compatibility"]["status"] == "review_required" for item in items),
        "blocked": sum(item["compatibility"]["status"] == "blocked" for item in items),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso(),
        "summary": summary,
        "truncated": truncated,
        "items": items,
        "boundaries": {
            "read_only": True,
            "network_access": False,
            "scripts_executed": False,
            "load_claim": "unverified-unless-runtime-evidence-exists",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect locally installed Skills without executing them.")
    parser.add_argument("--harness-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args(argv)
    print(json.dumps(skill_snapshot(harness_root=args.harness_root, home=args.home), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

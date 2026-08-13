#!/usr/bin/env python3
"""Discover, diagnose and safely maintain Mick Harness Agent loaders."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable


SCHEMA_VERSION = "1"
GLOBAL_BEGIN = "<!-- MICK-HARNESS-GLOBAL:BEGIN — auto-managed by harness agents sync -->"
GLOBAL_END = "<!-- MICK-HARNESS-GLOBAL:END -->"
LEGACY_MARKERS = (
    ("MICK-HARNESS-CODEX:BEGIN", "MICK-HARNESS-CODEX:END"),
    ("MICK-HARNESS-AGENT:BEGIN", "MICK-HARNESS-AGENT:END"),
)
LIFECYCLE_EVENTS = ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd")


class AgentManagerError(RuntimeError):
    pass


def harness_root() -> Path:
    configured = os.environ.get("MICK_HARNESS_ROOT")
    return Path(configured).expanduser().resolve() if configured else Path(__file__).resolve().parents[1]


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("agents"), list):
        raise AgentManagerError(f"Unsupported Agent registry: {path}")
    return data


def _command_found(command: str, bin_dirs: Iterable[Path]) -> tuple[bool, str]:
    for directory in bin_dirs:
        candidate = directory / command
        if candidate.exists():
            return True, str(candidate)
    resolved = shutil.which(command)
    return (resolved is not None, resolved or command)


def _extension_roots(home: Path) -> list[Path]:
    return [
        home / ".vscode" / "extensions",
        home / ".cursor" / "extensions",
        home / ".windsurf" / "extensions",
    ]


def detect_signals(
    agent: dict[str, Any], *, home: Path, bin_dirs: Iterable[Path], app_dirs: Iterable[Path]
) -> list[dict[str, Any]]:
    detection = agent["detection"]
    signals: list[dict[str, Any]] = []
    for command in detection.get("commands", []):
        found, value = _command_found(command, bin_dirs)
        signals.append({"kind": "command", "value": value, "found": found})
    for relative in detection.get("config_dirs", []):
        path = home / relative
        signals.append({"kind": "config_dir", "value": str(path), "found": path.is_dir()})
    for app in detection.get("apps", []):
        matches = [directory / app for directory in app_dirs]
        found_path = next((path for path in matches if path.exists()), matches[0] if matches else Path(app))
        signals.append({"kind": "app", "value": str(found_path), "found": found_path.exists()})
    for extension in detection.get("extensions", []):
        found_path: Path | None = None
        for root in _extension_roots(home):
            if not root.is_dir():
                continue
            found_path = next((path for path in root.glob(f"{extension}*") if path.exists()), None)
            if found_path:
                break
        signals.append({"kind": "extension", "value": str(found_path or extension), "found": found_path is not None})
    return signals


def _marker_counts(text: str, begin_fragment: str, end_fragment: str) -> tuple[int, int]:
    return text.count(begin_fragment), text.count(end_fragment)


def _loader_diagnosis(agent: dict[str, Any], home: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    target_value = agent["loader"].get("target")
    target = home / target_value if target_value else None
    text = target.read_text(encoding="utf-8", errors="replace") if target and target.exists() else ""
    begin_count, end_count = _marker_counts(text, "MICK-HARNESS-GLOBAL:BEGIN", "MICK-HARNESS-GLOBAL:END")
    legacy_count = sum(text.count(begin) for begin, _ in LEGACY_MARKERS)
    issues: list[dict[str, str]] = []
    if begin_count != end_count:
        issues.append({
            "code": "managed-block-corrupt",
            "severity": "error",
            "message": "Harness managed block markers are unbalanced.",
            "repair": "Restore the last valid file, then run `harness agents migrate --dry-run`.",
        })
    elif begin_count > 1:
        issues.append({
            "code": "managed-block-duplicate",
            "severity": "error",
            "message": "Multiple Harness global managed blocks were found.",
            "repair": "Run `harness agents migrate --dry-run` and review the proposed cleanup.",
        })
    if legacy_count:
        issues.append({
            "code": "legacy-block-present",
            "severity": "warning",
            "message": f"{legacy_count} legacy Harness block(s) require migration.",
            "repair": "Run `harness agents migrate --dry-run`, then repeat without `--dry-run` after review.",
        })
    status = "injected" if begin_count == end_count == 1 else ("conflict" if begin_count or end_count else "missing")
    return ({
        "status": status,
        "target": str(target) if target else None,
        "managed_blocks": begin_count,
        "legacy_blocks": legacy_count,
        "digest": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None,
    }, issues)


def _hook_path(agent_id: str, home: Path) -> Path | None:
    if agent_id == "claude-code":
        return home / ".claude" / "settings.json"
    if agent_id == "codex":
        return home / ".codex" / "hooks.json"
    return None


def _hook_diagnosis(agent: dict[str, Any], home: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    path = _hook_path(agent["id"], home)
    if path is None:
        return {"status": "unsupported", "evidence": None, "configured_events": 0}, []
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {"status": "conflict", "evidence": str(path), "configured_events": 0}, [{
            "code": "hook-config-invalid",
            "severity": "error",
            "message": "The Agent hook configuration is not valid JSON.",
            "repair": "Repair the JSON before running `harness agents hooks`.",
        }]
    hooks = data.get("hooks", {}) if isinstance(data, dict) else {}
    configured = 0
    for event in LIFECYCLE_EVENTS:
        if "harness-observe-hook.py" in json.dumps(hooks.get(event, []), ensure_ascii=False):
            configured += 1
    if configured == len(LIFECYCLE_EVENTS):
        return {"status": "hook_configured", "evidence": str(path), "configured_events": configured}, []
    issue = {
        "code": "lifecycle-hook-missing",
        "severity": "warning",
        "message": f"Harness lifecycle Hook is configured for {configured}/{len(LIFECYCLE_EVENTS)} events.",
        "repair": "Run `harness agents hooks --dry-run`, review it, then apply it explicitly.",
    }
    return {"status": "unverified", "evidence": str(path) if path.exists() else None, "configured_events": configured}, [issue]


def build_report(
    registry: dict[str, Any], *, home: Path, bin_dirs: Iterable[Path] = (), app_dirs: Iterable[Path] = ()
) -> dict[str, Any]:
    bin_dirs = list(bin_dirs)
    app_dirs = list(app_dirs) or [Path("/Applications"), home / "Applications"]
    records: list[dict[str, Any]] = []
    for agent in registry["agents"]:
        signals = detect_signals(agent, home=home, bin_dirs=bin_dirs, app_dirs=app_dirs)
        detected = any(signal["found"] for signal in signals)
        injection, issues = _loader_diagnosis(agent, home)
        loading, hook_issues = _hook_diagnosis(agent, home)
        if agent["tier"] == 1:
            issues.extend(hook_issues)
        if detected and injection["status"] == "missing" and agent["tier"] == 1:
            issues.append({
                "code": "loader-missing",
                "severity": "warning",
                "message": "Agent is detected but its Harness loader is missing.",
                "repair": "Run `harness agents sync --dry-run` and review the target.",
            })
        if injection["status"] == "injected" and agent["tier"] == 1:
            issues.append({
                "code": "load-proof-missing",
                "severity": "info",
                "message": "A loader file does not prove this Agent session loaded the rules.",
                "repair": "Install the reviewed lifecycle Hook and start a fresh Agent session.",
            })
        records.append({
            "id": agent["id"],
            "name": agent["name"],
            "tier": agent["tier"],
            "detected": detected,
            "signals": signals,
            "injection": injection,
            "loading": loading,
            "execution": {"status": "unverified", "evidence": None},
            "feedback": {"status": "unverified", "evidence": None},
            "capabilities": {
                "managed_loader": bool(agent["loader"].get("managed")),
                "lifecycle": bool(agent["lifecycle"].get("adapter")),
            },
            "limitations": agent["limitations"],
            "issues": issues,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "harness_version": (harness_root() / "VERSION").read_text(encoding="utf-8").strip(),
        "home": str(home),
        "agents": records,
        "summary": {
            "registered": len(records),
            "detected": sum(record["detected"] for record in records),
            "tier_one": sum(record["tier"] == 1 for record in records),
            "issues": sum(len(record["issues"]) for record in records),
        },
    }


def _strip_managed_blocks(text: str, marker_pairs: Iterable[tuple[str, str]]) -> tuple[str, int]:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    removed = 0
    active_end: str | None = None
    for line in lines:
        if active_end is None:
            match = next(((begin, end) for begin, end in marker_pairs if begin in line), None)
            if match:
                active_end = match[1]
                removed += 1
                continue
            output.append(line)
        elif active_end in line:
            active_end = None
    if active_end is not None:
        raise AgentManagerError("Refusing to modify a file with an unclosed managed block.")
    return "".join(output).strip(), removed


def _render_loader(agent: dict[str, Any], home: Path) -> str:
    root = harness_root()
    command = [str(root / "bin" / "harness"), "export", agent["loader"]["surface"], str(home)]
    environment = os.environ.copy()
    environment["MICK_HARNESS_ROOT"] = str(root)
    environment["MICK_HARNESS_ACTIVITY"] = "0"
    result = subprocess.run(command, check=False, capture_output=True, text=True, env=environment)
    if result.returncode != 0:
        raise AgentManagerError(result.stderr.strip() or "Failed to render Harness loader.")
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    return f"{GLOBAL_BEGIN}\n<!-- Harness-Version: {version} -->\n\n{result.stdout.strip()}\n\n{GLOBAL_END}\n"


def _atomic_write(path: Path, content: str, *, backup: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        backup_path = path.with_name(f"{path.name}.mick-harness.bak")
        shutil.copy2(path, backup_path)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def sync_agents(registry: dict[str, Any], *, home: Path, dry_run: bool, migrate: bool = False) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for agent in registry["agents"]:
        if agent["tier"] != 1 or not agent["loader"].get("managed"):
            continue
        target = home / agent["loader"]["target"]
        current = target.read_text(encoding="utf-8", errors="strict") if target.exists() else ""
        begin_count, end_count = _marker_counts(current, "MICK-HARNESS-GLOBAL:BEGIN", "MICK-HARNESS-GLOBAL:END")
        if begin_count != end_count or begin_count > 1:
            raise AgentManagerError(f"Refusing to modify conflicting managed blocks: {target}")
        pairs = [("MICK-HARNESS-GLOBAL:BEGIN", "MICK-HARNESS-GLOBAL:END")]
        if migrate:
            pairs.extend(LEGACY_MARKERS)
        preserved, removed = _strip_managed_blocks(current, pairs)
        rendered = _render_loader(agent, home)
        desired = f"{rendered}\n{preserved}\n" if preserved else rendered
        changed = desired.encode("utf-8") != current.encode("utf-8")
        changes.append({"agent_id": agent["id"], "target": str(target), "changed": changed, "removed_blocks": removed})
        if changed and not dry_run:
            _atomic_write(target, desired, backup=target.exists())
    return changes


def _hook_command(platform: str) -> str:
    script = harness_root() / "scripts" / "harness-observe-hook.py"
    return f'python3 "{script}" --platform {platform}'


def _has_hook_command(entry: Any, needle: str) -> bool:
    if not isinstance(entry, dict):
        return False
    if needle in str(entry.get("command", "")):
        return True
    return any(_has_hook_command(child, needle) for child in entry.get("hooks", []))


def _merge_lifecycle_hooks(data: dict[str, Any], *, platform: str) -> dict[str, Any]:
    result = json.loads(json.dumps(data))
    raw_hooks = result.get("hooks", {})
    if raw_hooks is not None and not isinstance(raw_hooks, dict):
        raise AgentManagerError("Refusing to replace a non-object hooks configuration.")
    hooks = raw_hooks or {}
    command = _hook_command(platform)
    for event in LIFECYCLE_EVENTS:
        entries = hooks.get(event, [])
        if not isinstance(entries, list):
            raise AgentManagerError(f"Refusing to replace non-list Hook event: {event}")
        if not any(_has_hook_command(entry, "harness-observe-hook.py") for entry in entries):
            entries.append({"hooks": [{"type": "command", "command": command, "timeout": 3}]})
        hooks[event] = entries
    if platform == "claude":
        entries = hooks["SessionStart"]
        session_start = str(harness_root() / "hooks" / "session-start.sh")
        if not any(_has_hook_command(entry, "session-start.sh") for entry in entries):
            entries.append({
                "matcher": "startup|resume|clear|compact",
                "hooks": [{"type": "command", "command": session_start, "description": "Load Mick Harness rules and version"}],
            })
    result["hooks"] = hooks
    return result


def sync_hooks(registry: dict[str, Any], *, home: Path, dry_run: bool) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for agent in registry["agents"]:
        path = _hook_path(agent["id"], home)
        if agent["tier"] != 1 or path is None:
            continue
        try:
            current_data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except json.JSONDecodeError as error:
            raise AgentManagerError(f"Refusing to replace invalid JSON: {path}: {error}") from error
        if not isinstance(current_data, dict):
            raise AgentManagerError(f"Refusing to replace non-object JSON: {path}")
        platform = "claude" if agent["id"] == "claude-code" else "codex"
        desired_data = _merge_lifecycle_hooks(current_data, platform=platform)
        desired = json.dumps(desired_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        changed = desired.encode("utf-8") != current.encode("utf-8")
        changes.append({"agent_id": agent["id"], "target": str(path), "changed": changed})
        if changed and not dry_run:
            _atomic_write(path, desired, backup=path.exists())
    return changes


def _print_human(report: dict[str, Any]) -> None:
    print("Agent Doctor")
    print("============")
    for agent in report["agents"]:
        found = "detected" if agent["detected"] else "not detected"
        print(f"{agent['name']}: {found} · Tier {agent['tier']} · {agent['injection']['status']}")
        for issue in agent["issues"]:
            print(f"  - [{issue['severity']}] {issue['message']} → {issue['repair']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness agents")
    parser.add_argument("command", nargs="?", choices=("scan", "sync", "doctor", "migrate", "hooks"), default="scan")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--home", type=Path, default=Path.home())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = harness_root()
    registry = load_registry(root / "config" / "agent-registry.json")
    home = args.home.expanduser().resolve()
    if args.command in {"scan", "doctor"}:
        report = build_report(registry, home=home)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        elif not args.quiet:
            _print_human(report)
        return 0
    changes = (
        sync_hooks(registry, home=home, dry_run=args.dry_run)
        if args.command == "hooks"
        else sync_agents(registry, home=home, dry_run=args.dry_run, migrate=args.command == "migrate")
    )
    if args.json:
        print(json.dumps({"schema_version": SCHEMA_VERSION, "dry_run": args.dry_run, "changes": changes}, ensure_ascii=False, indent=2, sort_keys=True))
    elif not args.quiet:
        label = "would update" if args.dry_run else "updated"
        for change in changes:
            print(f"{change['agent_id']}: {label if change['changed'] else 'unchanged'} · {change['target']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AgentManagerError as error:
        print(f"harness agents error: {error}", file=sys.stderr)
        raise SystemExit(2)

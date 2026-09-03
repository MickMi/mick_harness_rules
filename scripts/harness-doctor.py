#!/usr/bin/env python3
"""Aggregate Harness installation, project, Agent, Brain, Observer and audit health."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


SCHEMA_VERSION = "1"
ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def harness_root() -> Path:
    configured = os.environ.get("MICK_HARNESS_ROOT")
    return Path(configured).expanduser().resolve() if configured else Path(__file__).resolve().parents[1]


def state_root() -> Path:
    configured = os.environ.get("MICK_HARNESS_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "mick-harness"


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def audit_project(project: Path, root: Path) -> dict[str, Any]:
    script = project / ".harness" / "scripts" / "harness-audit.sh"
    if not script.is_file():
        script = root / "scripts" / "harness-audit.sh"
    if not script.is_file() or not (project / ".git").exists() or not (project / "plan.md").is_file():
        return {"available": False, "exit_code": None, "summary": "当前项目没有可运行的 plan audit"}
    try:
        result = subprocess.run(
            [str(script), "--since", "HEAD"],
            cwd=project,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "MICK_HARNESS_ACTIVITY": "0"},
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"available": True, "exit_code": 1, "summary": str(error)}
    output = ANSI_PATTERN.sub("", result.stdout or result.stderr)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return {
        "available": True,
        "exit_code": result.returncode,
        "summary": lines[-1] if lines else f"exit {result.returncode}",
    }


def collect_dependencies(project: Path, home: Path, root: Path) -> dict[str, Any]:
    manager = load_module(root / "scripts" / "harness-agent-manager.py", "harness_agent_manager_doctor")
    commands = load_module(root / "scripts" / "harness-command.py", "harness_command_doctor")
    observer = load_module(root / "scripts" / "harness-observe.py", "harness_observe_doctor")
    registry = manager.load_registry(root / "config" / "agent-registry.json")
    return {
        "agents": manager.build_report(registry, home=home),
        "brain": commands.brain_status_payload(),
        "observer": observer.service_status(home=home),
        "audit": audit_project(project, root),
    }


def component(component_id: str, label: str, status: str, summary: str, action: str | None = None, **details: Any) -> dict[str, Any]:
    return {
        "id": component_id,
        "label": label,
        "status": status,
        "summary": summary,
        "action": action,
        "details": details,
    }


def installation_component(root: Path) -> dict[str, Any]:
    version_path = root / "VERSION"
    required = (root / "bin" / "harness", root / "scripts" / "harness-observe.py", root / "config" / "agent-registry.json")
    missing = [str(path) for path in required if not path.is_file()]
    version = version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else None
    if missing or not version:
        return component("installation", "Harness 安装", "error", "安装不完整", "harness install", version=version, missing=missing)
    return component("installation", "Harness 安装", "ok", f"v{version} 可用", None, version=version, root=str(root))


def project_component(project: Path, root: Path, registry_root: Path) -> dict[str, Any]:
    if not project.is_dir():
        return component("project", "当前项目", "error", "项目目录不可用", None, path=str(project))
    loader = project / "AGENTS.md"
    mount = project / ".harness"
    issues: list[str] = []
    action: str | None = None
    if not loader.is_file() or loader.stat().st_size == 0 or not mount.exists():
        issues.append("缺少可用的 AGENTS.md 或 .harness 挂载")
        action = f"harness init {project}"
    mount_target = str(mount.resolve()) if mount.exists() else None
    if mount_target and Path(mount_target) != root:
        issues.append(f"项目挂载指向另一份 Harness：{mount_target}")
        action = action or f"harness init {project}"
    registry = registry_root / "registered-projects"
    registered = False
    if registry.is_file():
        for raw in registry.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                if Path(raw).expanduser().resolve() == project:
                    registered = True
                    break
            except OSError:
                continue
    if not registered:
        issues.append("项目未登记到全局工作台")
        action = action or f"harness init {project}"
    status = "error" if any("缺少" in issue for issue in issues) else ("warning" if issues else "ok")
    summary = "已注入并登记" if not issues else "；".join(issues)
    return component("project", "当前项目", status, summary, action, path=str(project), registered=registered, mount=mount_target)


def agents_component(report: dict[str, Any]) -> dict[str, Any]:
    agents = report.get("agents", [])
    detected = [item for item in agents if item.get("detected")]
    managed = [item for item in agents if item.get("adapter", {}).get("support") == "managed" or item.get("tier") == 1]
    errors = [issue for item in agents for issue in item.get("issues", []) if issue.get("severity") == "error"]
    missing = [item for item in managed if item.get("detected") and item.get("injection", {}).get("status") != "injected"]
    if errors:
        status, action = "error", str(errors[0].get("repair") or "harness agents doctor")
    elif missing:
        status, action = "warning", "harness agents sync --dry-run"
    else:
        status, action = "ok", None
    summary = f"发现 {len(detected)} 个 Agent；{len(managed)} 个由 Harness 管理"
    return component("agents", "Code Agent", status, summary, action, detected=len(detected), managed=len(managed), report=report)


def brain_component(payload: dict[str, Any]) -> dict[str, Any]:
    state = str(payload.get("state") or "unknown")
    if state == "disabled":
        return component("brain", "Brain", "optional", "未启用；不会写入或产生待同步", "harness brain configure --mode local --apply", state=payload)
    if state in {"local_ready", "connected"}:
        label = "仅本机可用" if state == "local_ready" else "私有远端已连接"
        return component("brain", "Brain", "ok", label, None, state=payload)
    if state == "not_installed":
        return component("brain", "Brain", "warning", "已配置但尚未建立本地 Brain", "harness brain install", state=payload)
    if state in {"remote_mismatch", "remote_not_connected"}:
        return component("brain", "Brain", "error", "配置仓库与实际连接不一致", "harness brain configure", state=payload)
    return component("brain", "Brain", "warning", f"状态无法确认：{state}", "harness brain status", state=payload)


def observer_component(payload: dict[str, Any]) -> dict[str, Any]:
    port = payload.get("port", 6425)
    if payload.get("healthy"):
        return component("observer", "本地工作服务", "ok", f"127.0.0.1:{port} 正常", None, state=payload)
    action = "harness observe service restart" if payload.get("installed") else "harness observe service install"
    return component("observer", "本地工作服务", "error", f"127.0.0.1:{port} 不可用", action, state=payload)


def audit_component(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("available"):
        return component("audit", "项目审计", "optional", str(payload.get("summary") or "无可运行审计"), None, result=payload)
    if payload.get("exit_code") == 0:
        return component("audit", "项目审计", "ok", str(payload.get("summary") or "通过"), None, result=payload)
    return component("audit", "项目审计", "error", str(payload.get("summary") or "未通过"), "查看 plan.md 与 harness check 输出", result=payload)


def build_report(*, project: Path, home: Path, harness_root: Path, state_root: Path, dependencies: dict[str, Any] | None = None) -> dict[str, Any]:
    selected_project = project.expanduser().resolve()
    selected_root = harness_root.expanduser().resolve()
    inputs = dependencies or collect_dependencies(selected_project, home, selected_root)
    components = [
        installation_component(selected_root),
        project_component(selected_project, selected_root, state_root),
        agents_component(inputs["agents"]),
        brain_component(inputs["brain"]),
        observer_component(inputs["observer"]),
        audit_component(inputs["audit"]),
    ]
    statuses = [item["status"] for item in components]
    overall = "blocked" if "error" in statuses else ("attention" if "warning" in statuses else "ok")
    return {
        "schema_version": SCHEMA_VERSION,
        "overall": overall,
        "project": str(selected_project),
        "harness_root": str(selected_root),
        "components": components,
        "summary": {
            "ok": statuses.count("ok"),
            "optional": statuses.count("optional"),
            "warning": statuses.count("warning"),
            "error": statuses.count("error"),
        },
    }


def print_human(report: dict[str, Any]) -> None:
    marks = {"ok": "✅", "optional": "○", "warning": "⚠", "error": "❌"}
    print("Harness Doctor")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for item in report["components"]:
        print(f"{marks[item['status']]} {item['label']}：{item['summary']}")
        if item.get("action"):
            print(f"   下一步：{item['action']}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"结论：{report['overall']} · {report['summary']['error']} 错误 · {report['summary']['warning']} 提醒")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness doctor", description="一次检查 Harness、项目、Agent、Brain、工作服务与审计。")
    parser.add_argument("project", nargs="?", default=os.getcwd())
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_report(
        project=Path(args.project),
        home=Path.home(),
        harness_root=harness_root(),
        state_root=state_root(),
    )
    if args.json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 1 if report["overall"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())

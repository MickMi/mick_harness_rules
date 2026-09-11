#!/usr/bin/env python3
"""Local session-reporting policy and bounded, content-free diagnostics.

This module never reads transcripts, changes vendor hooks or sends network data.
The global pause is a master switch; project overrides only apply while it is on.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
from typing import Any

MAX_RECORDS = 500
EVENTS = {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"}
REASONS = {
    "reported", "local_fallback", "reporting_paused", "invalid_configuration",
    "invalid_payload", "payload_too_large", "unsupported_event", "project_unresolved",
    "missing_session", "missing_turn", "submission_failed", "workspace_unavailable",
}
RESULTS = {"delivered", "written_local", "skipped", "failed"}


class ReportingError(ValueError):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def root() -> Path:
    # Match the Observer registry exactly, including XDG installations.
    configured = os.environ.get("MICK_HARNESS_STATE_DIR")
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))).expanduser()
    return (Path(configured).expanduser() if configured else base / "mick-harness") / "session-reporting"


def read_json(name: str, default: Any) -> Any:
    path = root() / name
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(name: str, value: Any) -> None:
    directory = root()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".reporting-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, directory / name)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


@contextlib.contextmanager
def locked():
    root().mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(root() / ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,200}", value):
        raise ReportingError("Invalid project identifier")
    return value


def configuration() -> dict[str, Any]:
    default = {"schema_version": 1, "revision": 0, "enabled": True, "projects": {}, "associations": {}, "updated_at": None}
    try:
        value = read_json("configuration.json", default)
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError()
        if type(value.get("enabled")) is not bool or type(value.get("revision")) is not int or value["revision"] < 0:
            raise ValueError()
        for name in ("projects", "associations"):
            if not isinstance(value.get(name), dict):
                raise ValueError()
        for key, flag in value["projects"].items():
            identifier(key)
            if type(flag) is not bool:
                raise ValueError()
        for key, project in value["associations"].items():
            if not re.fullmatch(r"[a-f0-9]{32}", key):
                raise ValueError()
            identifier(project)
        return {**default, **value, "error": None}
    except (OSError, ValueError, TypeError):
        # Never turn reporting back on because a persisted privacy setting broke.
        return {**default, "enabled": False, "error": "invalid_configuration"}


def policy(project_id: str | None = None) -> dict[str, Any]:
    value = configuration()
    if value["error"]:
        return {"enabled": False, "source": "error", "reason": "invalid_configuration"}
    if not value["enabled"]:
        return {"enabled": False, "source": "global", "reason": "reporting_paused"}
    explicit = value["projects"].get(project_id)
    enabled = explicit is not False
    return {"enabled": enabled, "source": "project" if explicit is not None else "global", "reason": "reported" if enabled else "reporting_paused"}


def change_configuration(body: dict[str, Any], known_projects: set[str]) -> dict[str, Any]:
    action = body.get("action")
    allowed = {
        "global": {"action", "revision", "enabled"},
        "project": {"action", "revision", "project_id", "enabled"},
        "associate": {"action", "revision", "workspace_ref", "project_id"},
    }
    if not isinstance(action, str) or action not in allowed or set(body) != allowed[action] or type(body.get("revision")) is not int:
        raise ReportingError("Invalid reporting action")
    with locked():
        value = configuration()
        if value["error"]:
            raise ReportingError("Reporting configuration is unreadable; repair it before changing settings")
        if body["revision"] != value["revision"]:
            raise ReportingError("Settings changed elsewhere; refresh before retrying")
        if action == "global":
            if type(body["enabled"]) is not bool:
                raise ReportingError("enabled must be a boolean")
            value["enabled"] = body["enabled"]
        elif action == "project":
            project = identifier(body["project_id"])
            if project not in known_projects:
                raise ReportingError("Project is not registered")
            if body["enabled"] is None:
                value["projects"].pop(project, None)
            elif type(body["enabled"]) is bool:
                value["projects"][project] = body["enabled"]
            else:
                raise ReportingError("Project override must be boolean or null")
        else:
            workspace_ref = body["workspace_ref"]
            if not isinstance(workspace_ref, str) or not re.fullmatch(r"[a-f0-9]{32}", workspace_ref):
                raise ReportingError("Invalid workspace reference")
            if body["project_id"] is None:
                value["associations"].pop(workspace_ref, None)
            else:
                project = identifier(body["project_id"])
                if project not in known_projects:
                    raise ReportingError("Project is not registered")
                if not any(item.get("workspace_ref") == workspace_ref for item in records()):
                    raise ReportingError("Workspace has not been observed")
                value["associations"][workspace_ref] = project
        value.pop("error", None)
        value["revision"] += 1
        value["updated_at"] = now_iso()
        atomic_json("configuration.json", value)
        return value


def workspace_ref(cwd: Path) -> str:
    return hashlib.sha256(str(cwd.resolve(strict=False)).encode()).hexdigest()[:32]


def associated_project(cwd: Path) -> str | None:
    return configuration()["associations"].get(workspace_ref(cwd))


def safe_path(cwd: Path | None) -> str | None:
    if cwd is None:
        return None
    value = str(cwd).replace(str(Path.home()), "~")
    value = re.sub(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_A-Za-z0-9]{12,}\b", "[REDACTED]", value)
    return "".join(c for c in value if c.isprintable())[:400]


def records() -> list[dict[str, Any]]:
    value = read_json("records.json", [])
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ReportingError("Trigger records are unreadable")
    return value[-MAX_RECORDS:]


def record(*, platform: str, event: str | None, cwd: Path | None, project_id: str | None,
           started_at: str, duration_ms: int, status: str, reason: str) -> None:
    if status not in RESULTS or reason not in REASONS:
        raise ReportingError("Invalid diagnostic outcome")
    item = {
        "trigger_id": uuid.uuid4().hex, "platform": platform if platform in {"codex", "claude"} else "unknown",
        "event": event if isinstance(event, str) and event in EVENTS else "unknown", "workspace_ref": workspace_ref(cwd) if cwd else None,
        "workspace": safe_path(cwd), "project_id": identifier(project_id) if project_id else None,
        "triggered_at": started_at, "finished_at": now_iso(), "duration_ms": max(0, min(duration_ms, 86_400_000)),
        "status": status, "reason": reason,
    }
    with locked():
        atomic_json("records.json", (records() + [item])[-MAX_RECORDS:])


def claude_turn(cwd: Path, session: str, event: str) -> str | None:
    """Claude does not promise turn_id: keep only an opaque per-session turn key."""
    key = hashlib.sha256((str(cwd) + "\0" + session).encode()).hexdigest()
    with locked():
        turns = read_json("turns.json", {})
        if not isinstance(turns, dict):
            raise ReportingError("Turn state is unreadable")
        if event == "UserPromptSubmit":
            turns.pop(key, None)
            turns[key] = uuid.uuid4().hex
        elif event == "SessionEnd":
            turns.pop(key, None)
        if event in {"UserPromptSubmit", "SessionEnd"}:
            atomic_json("turns.json", dict(list(turns.items())[-1000:]))
        return turns.get(key)


def snapshot(projects: list[dict[str, Any]]) -> dict[str, Any]:
    config = configuration()
    history_error = None
    try:
        history = sorted(records(), key=lambda item: item["triggered_at"], reverse=True)
    except (OSError, ValueError, TypeError, KeyError):
        history, history_error = [], "trigger_records_unreadable"
    return {
        "generated_at": now_iso(), "configuration": config,
        "projects": [{"project_id": item["project_id"], "name": item["name"], "validation": item.get("validation", "valid"),
                      "override": config["projects"].get(item["project_id"]), **policy(item["project_id"])} for item in projects],
        "records": history, "record_limit": MAX_RECORDS, "history_error": history_error,
        "last_trigger_at": history[0]["triggered_at"] if history else None,
        "last_delivery_at": next((item["finished_at"] for item in history if item["status"] == "delivered"), None),
        "last_local_write_at": next((item["finished_at"] for item in history if item["status"] == "written_local"), None),
        "collection": "lifecycle_metadata_only", "destination": "local_workbench",
        "host_trust": "not_verified",
    }

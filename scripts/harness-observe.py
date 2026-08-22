#!/usr/bin/env python3
"""Observe-only runtime for Mick Agent Harness.

This module imports existing Harness workflow files into an append-only event
ledger. It never edits plan.md, STATE files, source code, approvals, or Brain.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import hmac
import http.server
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
import uuid


SCHEMA_VERSION = "0.1.0"
INGEST_SCHEMA_VERSION = "0.2.0"
COLLECTOR_VERSION = "0.4.0"
RUNTIME_DIRNAME = ".harness-runtime"
SERVICE_NAME = "Mick Harness Observer"
SERVICE_LABEL = "com.mick.harness.observer"
DEFAULT_PORT = 6425
DEFAULT_SCAN_INTERVAL = 2.0
INGEST_PATH = "/api/v1/events"
BRAIN_STATUS_PATH = "/api/brain/status.json"
BRAIN_CANDIDATES_PATH = "/api/brain/candidates.json"
BRAIN_PROJECT_MEMORY_PATH = "/api/brain/project-memory.json"
BRAIN_SYNC_PATH = "/api/brain/sync"
HARNESS_IMPROVEMENTS_PATH = "/api/harness/improvements.json"
OPERATIONS_PATH = "/api/operations.json"
OPERATION_PREVIEW_PATH = "/api/operations/preview"
SKILLS_STATUS_PATH = "/api/skills.json"
MAX_INGEST_BODY = 64 * 1024
MAX_ARTIFACT_BYTES = 512 * 1024
MAX_OPERATION_BODY = 16 * 1024
OPERATION_LOCK_STALE_SECONDS = 30 * 60
ROLES = {"PM", "Planner", "Executor", "QA", "Reviewer", "Designer", "Orchestrator", "Unknown"}
OFFICE_ROLES = (
    {"role_id": "PM", "label": "PM", "source_roles": ("PM", "Planner", "Orchestrator")},
    {"role_id": "Designer", "label": "设计", "source_roles": ("Designer",)},
    {"role_id": "Executor", "label": "开发", "source_roles": ("Executor",)},
    {"role_id": "QA", "label": "测试", "source_roles": ("QA",)},
    {"role_id": "Reviewer", "label": "Review", "source_roles": ("Reviewer",)},
)
OFFICE_ROLE_BY_SOURCE = {
    source_role: item["role_id"]
    for item in OFFICE_ROLES
    for source_role in item["source_roles"]
}
_BRAIN_BOUNDARY: Any | None = None
_SKILL_MANAGER: Any | None = None
EVENT_TYPES = {
    "run.created",
    "run.status_changed",
    "source.snapshot_imported",
    "plan.summary_observed",
    "workflow.stage_changed",
    "task.discovered",
    "task.status_changed",
    "artifact.observed",
    "verification.observed",
    "block.observed",
    "approval.requested",
    "approval.resolved",
    "audit.finding_observed",
    "agent.session_observed",
    "agent.turn_observed",
    "harness.command_observed",
    "work.round_started",
    "work.round_completed",
    "decision.recorded",
    "handoff.created",
    "collector.warning",
}


def load_brain_boundary() -> Any:
    global _BRAIN_BOUNDARY
    if _BRAIN_BOUNDARY is not None:
        return _BRAIN_BOUNDARY
    path = Path(__file__).resolve().with_name("harness-brain-boundary.py")
    spec = importlib.util.spec_from_file_location("harness_brain_boundary_runtime", path)
    if spec is None or spec.loader is None:
        raise ObserveError(f"Unable to load Brain boundary: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _BRAIN_BOUNDARY = module
    return module


def load_skill_manager() -> Any:
    global _SKILL_MANAGER
    if _SKILL_MANAGER is not None:
        return _SKILL_MANAGER
    path = Path(__file__).resolve().with_name("harness-skill-manager.py")
    spec = importlib.util.spec_from_file_location("harness_skill_manager_runtime", path)
    if spec is None or spec.loader is None:
        raise ObserveError(f"Unable to load Skill manager: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _SKILL_MANAGER = module
    return module
INGEST_EVENT_TYPES = {
    "agent.session_observed",
    "agent.turn_observed",
    "harness.command_observed",
    "work.round_started",
    "work.round_completed",
    "decision.recorded",
    "handoff.created",
    "artifact.observed",
    "verification.observed",
}
INGEST_SUBJECT_KINDS = {
    "agent.session_observed": "agent_session",
    "agent.turn_observed": "agent_turn",
    "harness.command_observed": "harness_command",
    "work.round_started": "work_round",
    "work.round_completed": "work_round",
    "decision.recorded": "decision",
    "handoff.created": "handoff",
    "artifact.observed": "artifact",
    "verification.observed": "verification",
}
RUN_TERMINAL = {"completed", "abandoned"}
PASS_RE = re.compile(r"\bpassed\b|\bpass\b|通过", re.IGNORECASE)
FAIL_RE = re.compile(r"\bfailed\b|\bfailure\b|失败|未通过", re.IGNORECASE)
STEP_RE = re.compile(
    r"^-\s+\[([ x~])\]\s+(\d+[.)])\s+(.+?)\s*$",
    re.MULTILINE,
)
SELFCHECK_RE = re.compile(
    r"^###\s+Step\s+([A-Za-z0-9][A-Za-z0-9._-]*)\b(.*?)(?=^###\s+Step\s+|^##\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
BLOCK_RE = re.compile(
    r"^##\s+阻塞\s+#([A-Za-z0-9._-]+)([^\n]*)\n(.*?)(?=^##\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
NUMBERED_STEP_RE = re.compile(r"^(\d+)[.)]\s+(.+?)\s*$", re.MULTILINE)
CURRENT_STEP_RE = re.compile(
    r"^\*\*Current step:\*\*\s*(\d+)\s*/\s*(\d+)(?:\s*[—-]\s*(.+?))?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
VERSION_HEADING_RE = re.compile(r"^##\s+v?([0-9]+(?:\.[0-9A-Za-z-]+)+)\s*$", re.MULTILINE)
VERSION_FIELD_RE = re.compile(
    r"^-\s+(Status|Branch|Work Branches|Tag|Goal|状态|分支|工作分支|标签|目标)\s*:\s*(.+?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
VERSION_REQUIREMENT_RE = re.compile(r"^-\s+\[([ x~])\]\s+(?:`([^`]+)`\s+)?(.+?)\s*$", re.MULTILINE)
MARKDOWN_STAGE_HEADING_RE = re.compile(r"^(#{2,4})\s+(.+?)\s*$")
STRUCTURED_STAGE_RE = re.compile(
    r"^v(?P<version>[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?)\s*·\s*"
    r"(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})\s*·\s*(?P<title>.+?)\s*$",
    re.IGNORECASE,
)
LEGACY_STAGE_PAREN_RE = re.compile(
    r"^(?P<title>.+?)\s*[（(](?P<meta>[^）)]*[0-9]{4}-[0-9]{2}-[0-9]{2}[^）)]*)[）)]\s*$"
)
LEGACY_STAGE_DASH_RE = re.compile(
    r"^(?P<title>.+?)\s+[—–]\s*(?P<meta>[0-9]{4}-[0-9]{2}-[0-9]{2}.*?)\s*$"
)
ISO_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
ARTIFACT_LANGUAGES = {
    ".md": "markdown", ".markdown": "markdown", ".py": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx", ".jsx": "jsx", ".json": "json",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".sh": "shell",
    ".bash": "shell", ".zsh": "shell", ".html": "html", ".css": "css",
    ".sql": "sql", ".swift": "swift", ".kt": "kotlin", ".java": "java",
    ".go": "go", ".rs": "rust", ".txt": "text",
}
AGENT_PLATFORM_IDS = {
    "claude": "claude-code",
    "claude-code": "claude-code",
    "codex": "codex",
}


class ObserveError(RuntimeError):
    """Deterministic runtime error with a CLI exit code."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def stable_id(prefix: str, value: str, length: int = 16) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def new_id(prefix: str) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}_{stamp}{uuid.uuid4().hex[:10]}"


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_http_body(stream: Any, value: bytes) -> bool:
    try:
        stream.write(value)
        return True
    except (BrokenPipeError, ConnectionResetError):
        return False


def atomic_write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ObserveError(f"Cannot read JSON {path}: {error}") from error


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw_line.strip():
                continue
            try:
                events.append(json.loads(raw_line))
            except json.JSONDecodeError as error:
                raise ObserveError(f"Invalid JSONL at {path}:{line_number}: {error}") from error
    except OSError as error:
        raise ObserveError(f"Cannot read event ledger {path}: {error}") from error
    return events


def resolve_project(value: str | None) -> Path:
    project = Path(value or os.getcwd()).expanduser()
    try:
        project = project.resolve(strict=True)
    except OSError as error:
        raise ObserveError(f"Project directory does not exist: {project}", 64) from error
    if not project.is_dir():
        raise ObserveError(f"Project path is not a directory: {project}", 64)
    return project


def project_id(project: Path) -> str:
    canonical = project.resolve(strict=False)
    return f"{canonical.name}-{hashlib.sha256(str(canonical).encode()).hexdigest()[:10]}"


def default_registry_path() -> Path:
    state_root = os.environ.get("MICK_HARNESS_STATE_DIR")
    if state_root:
        return Path(state_root).expanduser() / "registered-projects"
    xdg_state = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg_state).expanduser() if xdg_state else Path.home() / ".local" / "state"
    return base / "mick-harness" / "registered-projects"


def default_state_root() -> Path:
    return default_registry_path().parent


def ingest_token_path(state_root: Path | None = None) -> Path:
    return (state_root or default_state_root()) / "observer" / "ingest-token"


def ensure_ingest_token(state_root: Path | None = None) -> str:
    path = ingest_token_path(state_root)
    if path.is_file():
        try:
            token = path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise ObserveError(f"Cannot read Observer ingest token: {error}") from error
        if len(token) < 40:
            raise ObserveError(f"Observer ingest token is invalid: {path}")
        with contextlib.suppress(OSError):
            path.chmod(0o600)
        return token
    token = secrets.token_urlsafe(36)
    atomic_write(path, (token + "\n").encode("utf-8"))
    path.chmod(0o600)
    return token


def has_harness_entry(project: Path) -> bool:
    return (project / "AGENTS.md").exists() or (project / ".harness").exists()


def load_registered_projects(registry_path: Path | None = None) -> list[dict[str, Any]]:
    path = registry_path or default_registry_path()
    if not path.is_file():
        return []
    projects: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ObserveError(f"Cannot read project registry {path}: {error}") from error
    for raw_value in lines:
        value = raw_value.strip()
        if not value:
            continue
        candidate = Path(value).expanduser()
        normalized = str(candidate.resolve(strict=False))
        if normalized in seen:
            continue
        seen.add(normalized)
        project = Path(normalized)
        if not project.exists():
            validation, reason = "missing", "Registered directory no longer exists"
        elif not project.is_dir():
            validation, reason = "not_directory", "Registered path is not a directory"
        elif not os.access(project, os.R_OK):
            validation, reason = "unreadable", "Registered directory is not readable"
        elif not has_harness_entry(project):
            validation, reason = "missing_harness", "Harness entry is missing"
        else:
            validation, reason = "valid", None
        projects.append(
            {
                "project_id": project_id(project),
                "name": project.name or normalized,
                "path": normalized,
                "validation": validation,
                "reason": reason,
            }
        )
    return projects


def unregister_project(project_identifier: str, registry_path: Path | None = None) -> dict[str, Any]:
    """Remove an unavailable project from the registry without touching its files."""
    path = registry_path or default_registry_path()
    descriptors = load_registered_projects(path)
    descriptor = next((item for item in descriptors if item["project_id"] == project_identifier), None)
    if descriptor is None:
        raise ObserveError("Registered project was not found", 404)
    if descriptor["validation"] == "valid":
        raise ObserveError("Connected projects cannot be removed from this recovery action", 409)
    remaining = [item["path"] for item in descriptors if item["project_id"] != project_identifier]
    value = "\n".join(remaining)
    atomic_write(path, ((value + "\n") if value else "").encode("utf-8"))
    return {
        "removed": True,
        "project_id": descriptor["project_id"],
        "name": descriptor["name"],
        "path": descriptor["path"],
        "previous_validation": descriptor["validation"],
        "files_deleted": False,
    }


def runtime_root(project: Path) -> Path:
    return project / RUNTIME_DIRNAME


def run_dir(project: Path, run_id: str) -> Path:
    return runtime_root(project) / "runs" / run_id


def relative_source(project: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(project.resolve())
    except ValueError as error:
        raise ObserveError(f"Source path escapes project: {path}") from error
    value = relative.as_posix()
    if value.startswith("/") or ".." in relative.parts:
        raise ObserveError(f"Source path is not project-relative: {value}")
    return value


@contextlib.contextmanager
def ledger_lock(target_run_dir: Path) -> Iterable[None]:
    lock_path = target_run_dir / ".ledger.lock"
    deadline = time.monotonic() + 2.0
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError as error:
            with contextlib.suppress(OSError):
                if time.time() - lock_path.stat().st_mtime > 30:
                    lock_path.unlink()
                    continue
            if time.monotonic() >= deadline:
                raise ObserveError(f"Runtime ledger is busy: {lock_path}", 2) from error
            time.sleep(0.02)
    try:
        os.write(fd, f"pid={os.getpid()}\n".encode("utf-8"))
        os.close(fd)
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock_path.unlink()


def make_candidate(
    event_type: str,
    subject_kind: str,
    subject_id: str,
    source: dict[str, Any],
    payload: dict[str, Any],
    semantic_key: str,
    *,
    parent_id: str | None = None,
    observation_kind: str = "observed",
    confidence: float | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    causation_id: str | None = None,
) -> dict[str, Any]:
    candidate: dict[str, Any] = {
        "type": event_type,
        "observation_kind": observation_kind,
        "source": source,
        "subject": {"kind": subject_kind, "id": subject_id},
        "payload": payload,
        "semantic_key": semantic_key,
    }
    if parent_id:
        candidate["subject"]["parent_id"] = parent_id
    if confidence is not None:
        candidate["confidence"] = confidence
    if evidence_refs:
        candidate["evidence_refs"] = evidence_refs
    if causation_id:
        candidate["causation_id"] = causation_id
    return candidate


def validate_relative_path(value: str) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ObserveError(f"Event contains non-relative path: {value}")


def validate_event(event: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "event_id",
        "run_id",
        "sequence",
        "occurred_at",
        "type",
        "observation_kind",
        "source",
        "subject",
        "payload",
    }
    missing = sorted(required - set(event))
    if missing:
        raise ObserveError(f"Event missing required fields: {', '.join(missing)}")
    if event["schema_version"] != SCHEMA_VERSION:
        raise ObserveError(f"Unsupported event schema: {event['schema_version']}")
    if event["type"] not in EVENT_TYPES:
        raise ObserveError(f"Unknown event type: {event['type']}")
    if event["observation_kind"] not in {"observed", "inferred"}:
        raise ObserveError(f"Invalid observation_kind: {event['observation_kind']}")
    if event["observation_kind"] == "inferred" and "confidence" not in event:
        raise ObserveError("Inferred event is missing confidence")
    if not isinstance(event["sequence"], int) or event["sequence"] < 1:
        raise ObserveError("Event sequence must be a positive integer")
    if not isinstance(event["source"], dict) or not event["source"].get("producer"):
        raise ObserveError("Event source is missing producer")
    if "path" in event["source"]:
        validate_relative_path(str(event["source"]["path"]))
    if not isinstance(event["subject"], dict) or not event["subject"].get("id"):
        raise ObserveError("Event subject is missing id")
    if not isinstance(event["payload"], dict):
        raise ObserveError("Event payload must be an object")


def require_text(value: dict[str, Any], key: str, *, maximum: int, optional: bool = False) -> str | None:
    raw = value.get(key)
    if raw is None and optional:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ObserveError(f"Ingest field '{key}' must be a non-empty string", 422)
    cleaned = raw.strip()
    if len(cleaned) > maximum:
        raise ObserveError(f"Ingest field '{key}' exceeds {maximum} characters", 422)
    return cleaned


def validate_keys(value: dict[str, Any], *, allowed: set[str], required: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    if unknown:
        raise ObserveError(f"{label} contains unsupported fields: {', '.join(unknown)}", 422)
    if missing:
        raise ObserveError(f"{label} is missing fields: {', '.join(missing)}", 422)


def validate_ingest_envelope(envelope: dict[str, Any], expected_project_id: str | None = None) -> None:
    if not isinstance(envelope, dict):
        raise ObserveError("Ingest body must be a JSON object", 422)
    validate_keys(
        envelope,
        allowed={"schema_version", "project_id", "idempotency_key", "type", "source", "subject_id", "parent_id", "payload"},
        required={"project_id", "idempotency_key", "type", "source", "subject_id", "payload"},
        label="Ingest envelope",
    )
    if envelope.get("schema_version") not in {None, "0.1.0", INGEST_SCHEMA_VERSION}:
        raise ObserveError("Unsupported ingest schema_version", 422)
    incoming_project_id = require_text(envelope, "project_id", maximum=160)
    if expected_project_id is not None and incoming_project_id != expected_project_id:
        raise ObserveError("Ingest project id does not match the resolved project", 422)
    require_text(envelope, "idempotency_key", maximum=200)
    event_type = require_text(envelope, "type", maximum=120)
    if event_type not in INGEST_EVENT_TYPES:
        raise ObserveError(f"Unsupported ingest event type: {event_type}", 422)
    require_text(envelope, "subject_id", maximum=200)
    if envelope.get("parent_id") is not None:
        require_text(envelope, "parent_id", maximum=200)

    source = envelope.get("source")
    if not isinstance(source, dict):
        raise ObserveError("Ingest source must be an object", 422)
    validate_keys(
        source,
        allowed={"kind", "producer", "role", "agent_id", "adapter"},
        required={"kind", "producer"},
        label="Ingest source",
    )
    if source.get("kind") not in {"human", "agent", "harness"}:
        raise ObserveError("Ingest source.kind is invalid", 422)
    require_text(source, "producer", maximum=120)
    if source.get("role") is not None and source["role"] not in ROLES:
        raise ObserveError(f"Unsupported role: {source['role']}", 422)
    for key, maximum in (("agent_id", 160), ("adapter", 80)):
        if source.get(key) is not None:
            require_text(source, key, maximum=maximum)

    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise ObserveError("Ingest payload must be an object", 422)
    if event_type in {"work.round_started", "work.round_completed"}:
        validate_keys(
            payload,
            allowed={"role", "objective", "summary", "status", "requirement_id", "next_role", "blocker", "platform", "session_ref", "turn_ref", "artifact_refs", "verification_refs"},
            required={"role", "objective", "status"},
            label="Work round payload",
        )
        if payload["role"] not in ROLES or payload["status"] not in {"active", "completed", "blocked", "verification_pending"}:
            raise ObserveError("Work round role or status is invalid", 422)
        if event_type == "work.round_started" and payload["status"] != "active":
            raise ObserveError("Started work round must have active status", 422)
        if event_type == "work.round_completed" and payload["status"] == "active":
            raise ObserveError("Completed work round cannot have active status", 422)
        require_text(payload, "objective", maximum=2000)
        for key, maximum in (("summary", 4000), ("requirement_id", 200), ("blocker", 2000), ("session_ref", 200), ("turn_ref", 200)):
            if payload.get(key) is not None:
                require_text(payload, key, maximum=maximum)
        if payload.get("next_role") is not None and payload["next_role"] not in ROLES:
            raise ObserveError(f"Unsupported next role: {payload['next_role']}", 422)
        if payload.get("platform") is not None and payload["platform"] not in {"codex", "claude", "cursor", "other"}:
            raise ObserveError("Work round platform is invalid", 422)
        for key in ("artifact_refs", "verification_refs"):
            if payload.get(key) is not None and (
                not isinstance(payload[key], list)
                or len(payload[key]) > 32
                or any(not isinstance(item, str) or not item or len(item) > 200 for item in payload[key])
            ):
                raise ObserveError(f"Work round {key} is invalid", 422)
            if key == "artifact_refs" and payload.get(key) is not None:
                for path_value in payload[key]:
                    validate_relative_path(path_value)
    elif event_type == "decision.recorded":
        validate_keys(
            payload,
            allowed={"title", "summary", "rationale", "role", "requirement_id", "status"},
            required={"title", "summary", "role"},
            label="Decision payload",
        )
        require_text(payload, "title", maximum=200)
        require_text(payload, "summary", maximum=4000)
        if payload["role"] not in ROLES or payload.get("status", "accepted") not in {"accepted", "superseded"}:
            raise ObserveError("Decision role or status is invalid", 422)
        for key, maximum in (("rationale", 4000), ("requirement_id", 200)):
            if payload.get(key) is not None:
                require_text(payload, key, maximum=maximum)
    elif event_type == "handoff.created":
        validate_keys(
            payload,
            allowed={"from_role", "to_role", "summary", "status", "requirement_id", "round_id"},
            required={"from_role", "to_role", "summary", "status"},
            label="Handoff payload",
        )
        if payload["from_role"] not in ROLES or payload["to_role"] not in ROLES or payload["status"] not in {"pending", "accepted", "completed"}:
            raise ObserveError("Handoff role or status is invalid", 422)
        require_text(payload, "summary", maximum=4000)
        for key in ("requirement_id", "round_id"):
            if payload.get(key) is not None:
                require_text(payload, key, maximum=200)
    elif event_type in {"agent.session_observed", "agent.turn_observed"}:
        validate_keys(
            payload,
            allowed={"platform", "state", "session_ref", "turn_ref", "project_id", "rule_version", "role_digest"},
            required={"platform", "state", "session_ref", "project_id"},
            label="Agent activity payload",
        )
        if payload["platform"] not in {"codex", "claude", "cursor", "other"}:
            raise ObserveError("Agent platform is invalid", 422)
        if payload["state"] not in {"session_started", "turn_started", "turn_completed", "session_ended"}:
            raise ObserveError("Agent state is invalid", 422)
        require_text(payload, "session_ref", maximum=200)
        if payload.get("rule_version") is not None:
            require_text(payload, "rule_version", maximum=40)
        if payload.get("role_digest") is not None:
            digest = require_text(payload, "role_digest", maximum=80)
            if not digest or not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
                raise ObserveError("Agent role_digest is invalid", 422)
        if payload.get("turn_ref") is not None:
            require_text(payload, "turn_ref", maximum=200)
    elif event_type == "harness.command_observed":
        validate_keys(
            payload,
            allowed={"command", "state", "project_id", "exit_code"},
            required={"command", "state", "project_id"},
            label="Harness command payload",
        )
        require_text(payload, "command", maximum=80)
        if payload["state"] not in {"started", "completed"}:
            raise ObserveError("Harness command state is invalid", 422)
        if payload["state"] == "completed" and not isinstance(payload.get("exit_code"), int):
            raise ObserveError("Completed Harness command requires integer exit_code", 422)
    elif event_type == "artifact.observed":
        validate_keys(
            payload,
            allowed={"path", "artifact_type", "exists", "digest", "title", "summary", "role", "requirement_id"},
            required={"path", "artifact_type"},
            label="Artifact payload",
        )
        path_value = require_text(payload, "path", maximum=1024)
        validate_relative_path(path_value or "")
    elif event_type == "verification.observed":
        validate_keys(
            payload,
            allowed={"result", "check", "exit_code", "summary", "duration_ms"},
            required={"result", "check"},
            label="Verification payload",
        )
        require_text(payload, "check", maximum=300)
        if payload["result"] not in {"passed", "failed", "unknown", "skipped"}:
            raise ObserveError("Verification result is invalid", 422)


def append_events(target_run_dir: Path, run_id: str, candidates: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    ledger_path = target_run_dir / "events.jsonl"
    with ledger_lock(target_run_dir):
        current = load_events(ledger_path)
        known = {event.get("dedupe_key") for event in current if event.get("dedupe_key")}
        sequence = current[-1]["sequence"] if current else 0
        appended: list[dict[str, Any]] = []
        for candidate in candidates:
            semantic_key = candidate.pop("semantic_key")
            dedupe_key = sha256_text(semantic_key)
            if dedupe_key in known:
                continue
            sequence += 1
            timestamp = now_iso()
            event = {
                "schema_version": SCHEMA_VERSION,
                "event_id": new_id("evt"),
                "run_id": run_id,
                "sequence": sequence,
                "occurred_at": timestamp,
                "ingested_at": timestamp,
                "dedupe_key": dedupe_key,
                **candidate,
            }
            validate_event(event)
            appended.append(event)
            known.add(dedupe_key)
        if appended:
            all_events = current + appended
            content = "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in all_events)
            atomic_write(ledger_path, content.encode("utf-8"))
    return len(appended), appended


def current_run(project: Path) -> tuple[dict[str, Any], Path]:
    index = load_json(runtime_root(project) / "index.json", {}) or {}
    runs = index.get("runs", [])
    if not runs:
        raise ObserveError("No observed run. Run 'harness observe init' first.", 2)
    active = [item for item in runs if item.get("status") not in RUN_TERMINAL]
    selected = active[0] if active else runs[0]
    return selected, run_dir(project, selected["run_id"])


def build_work_envelope(
    project: Path,
    *,
    event_type: str,
    role: str,
    round_ref: str,
    objective: str,
    status: str,
    idempotency_key: str,
    requirement_id: str | None = None,
    summary: str | None = None,
    next_role: str | None = None,
    blocker: str | None = None,
    platform: str | None = None,
    session_ref: str | None = None,
    turn_ref: str | None = None,
    artifact_refs: list[str] | None = None,
    producer: str = "harness-agent",
) -> dict[str, Any]:
    payload = {
        "role": role,
        "objective": objective,
        "status": status,
        **({"requirement_id": requirement_id} if requirement_id else {}),
        **({"summary": summary} if summary else {}),
        **({"next_role": next_role} if next_role else {}),
        **({"blocker": blocker} if blocker else {}),
        **({"platform": platform} if platform else {}),
        **({"session_ref": session_ref} if session_ref else {}),
        **({"turn_ref": turn_ref} if turn_ref else {}),
        **({"artifact_refs": artifact_refs} if artifact_refs else {}),
    }
    envelope = {
        "schema_version": INGEST_SCHEMA_VERSION,
        "project_id": project_id(project),
        "idempotency_key": idempotency_key,
        "type": event_type,
        "source": {
            "kind": "agent",
            "producer": producer,
            "role": role,
            **({"agent_id": session_ref[:160]} if session_ref else {}),
            "adapter": "harness-emit",
        },
        "subject_id": round_ref,
        **({"parent_id": requirement_id} if requirement_id else {}),
        "payload": payload,
    }
    validate_ingest_envelope(envelope, project_id(project))
    return envelope


def build_decision_envelope(
    project: Path,
    *,
    decision_ref: str,
    role: str,
    title: str,
    summary: str,
    idempotency_key: str,
    requirement_id: str | None = None,
    rationale: str | None = None,
    status: str = "accepted",
) -> dict[str, Any]:
    envelope = {
        "schema_version": INGEST_SCHEMA_VERSION,
        "project_id": project_id(project),
        "idempotency_key": idempotency_key,
        "type": "decision.recorded",
        "source": {"kind": "agent", "producer": "harness-agent", "role": role, "adapter": "harness-emit"},
        "subject_id": decision_ref,
        **({"parent_id": requirement_id} if requirement_id else {}),
        "payload": {
            "title": title,
            "summary": summary,
            "role": role,
            "status": status,
            **({"requirement_id": requirement_id} if requirement_id else {}),
            **({"rationale": rationale} if rationale else {}),
        },
    }
    validate_ingest_envelope(envelope, project_id(project))
    return envelope


def build_handoff_envelope(
    project: Path,
    *,
    handoff_ref: str,
    from_role: str,
    to_role: str,
    summary: str,
    status: str,
    idempotency_key: str,
    requirement_id: str | None = None,
    round_ref: str | None = None,
) -> dict[str, Any]:
    envelope = {
        "schema_version": INGEST_SCHEMA_VERSION,
        "project_id": project_id(project),
        "idempotency_key": idempotency_key,
        "type": "handoff.created",
        "source": {"kind": "agent", "producer": "harness-agent", "role": from_role, "adapter": "harness-emit"},
        "subject_id": handoff_ref,
        **({"parent_id": requirement_id} if requirement_id else {}),
        "payload": {
            "from_role": from_role,
            "to_role": to_role,
            "summary": summary,
            "status": status,
            **({"requirement_id": requirement_id} if requirement_id else {}),
            **({"round_id": round_ref} if round_ref else {}),
        },
    }
    validate_ingest_envelope(envelope, project_id(project))
    return envelope


def build_agent_envelope(
    project: Path,
    *,
    platform: str,
    state: str,
    session_ref: str,
    turn_ref: str | None = None,
) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    version_path = root / "VERSION"
    rule_version = version_path.read_text(encoding="utf-8").strip() if version_path.exists() else "unknown"
    role_hasher = hashlib.sha256()
    for role_path in sorted((root / "rules" / "roles").glob("*.md")):
        role_hasher.update(role_path.name.encode("utf-8"))
        role_hasher.update(role_path.read_bytes())
    role_digest = f"sha256:{role_hasher.hexdigest()}"
    is_turn = state.startswith("turn_")
    subject_ref = turn_ref if is_turn else session_ref
    envelope = {
        "schema_version": INGEST_SCHEMA_VERSION,
        "project_id": project_id(project),
        "idempotency_key": f"agent:{platform}:{state}:{session_ref}:{turn_ref or ''}",
        "type": "agent.turn_observed" if is_turn else "agent.session_observed",
        "source": {
            "kind": "agent",
            "producer": f"{platform}-hook",
            "agent_id": session_ref[:160],
            "adapter": "harness-observe-hook",
        },
        "subject_id": stable_id("agent-turn" if is_turn else "agent-session", f"{platform}:{subject_ref}"),
        "parent_id": stable_id("agent-session", f"{platform}:{session_ref}") if is_turn else "run",
        "payload": {
            "platform": platform,
            "state": state,
            "session_ref": session_ref[:200],
            "project_id": project_id(project),
            "rule_version": rule_version[:40],
            "role_digest": role_digest,
            **({"turn_ref": turn_ref[:200]} if turn_ref else {}),
        },
    }
    validate_ingest_envelope(envelope, project_id(project))
    return envelope


def build_harness_command_envelope(
    project: Path,
    *,
    command: str,
    state: str,
    invocation_ref: str,
    exit_code: int | None = None,
) -> dict[str, Any]:
    safe_command = re.sub(r"[^A-Za-z0-9._-]", "-", command.strip())[:80]
    safe_invocation = re.sub(r"[^A-Za-z0-9._-]", "-", invocation_ref.strip())[:160]
    envelope = {
        "schema_version": INGEST_SCHEMA_VERSION,
        "project_id": project_id(project),
        "idempotency_key": f"harness-command:{safe_invocation}:{state}:{exit_code if exit_code is not None else ''}",
        "type": "harness.command_observed",
        "source": {"kind": "harness", "producer": "harness-cli", "adapter": "command-lifecycle"},
        "subject_id": stable_id("harness-command", safe_invocation),
        "parent_id": "run",
        "payload": {
            "command": safe_command,
            "state": state,
            "project_id": project_id(project),
            **({"exit_code": exit_code} if exit_code is not None else {}),
        },
    }
    validate_ingest_envelope(envelope, project_id(project))
    return envelope


def ingest_envelope(project: Path, envelope: dict[str, Any]) -> dict[str, Any]:
    validate_ingest_envelope(envelope, project_id(project))
    init_runtime(project)
    run_record, target_run_dir = current_run(project)
    parent_id = envelope.get("parent_id")
    if parent_id == "run" or not parent_id:
        parent_id = run_record["run_id"]
    candidate = make_candidate(
        envelope["type"],
        INGEST_SUBJECT_KINDS[envelope["type"]],
        envelope["subject_id"],
        dict(envelope["source"]),
        dict(envelope["payload"]),
        f"ingest:{envelope['idempotency_key']}",
        parent_id=parent_id,
    )
    appended, appended_events = append_events(target_run_dir, run_record["run_id"], [candidate])
    snapshot = write_snapshot(project, target_run_dir, load_events(target_run_dir / "events.jsonl"))
    brain_results = record_brain_events(
        project,
        [{**envelope, "event_id": appended_events[0]["event_id"]}] if appended_events else [],
    )
    return {
        "project_id": project_id(project),
        "run_id": run_record["run_id"],
        "appended": appended,
        "event_id": appended_events[0]["event_id"] if appended_events else None,
        "last_sequence": snapshot.get("last_sequence", 0),
        "brain": brain_results[0] if brain_results else None,
    }


def record_brain_events(project: Path, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not events:
        return results
    try:
        brain = load_brain_boundary()
    except Exception as error:
        return [{"action": "error", "error": str(error)[:300]}]
    identifier = project_id(project)
    for event in events:
        try:
            result = brain.process_observer_event(identifier, event)
            if result.get("action") != "ignored":
                results.append(result)
        except Exception as error:
            results.append({"action": "error", "event_id": event.get("event_id"), "error": str(error)[:300]})
    return results


def record_runtime_brain_events(project: Path, target_run_dir: Path) -> list[dict[str, Any]]:
    """Incrementally project the append-only ledger into local project memory."""
    identifier = project_id(project)
    cursor_path = default_state_root() / "brain-event-cursors" / f"{identifier}.json"
    cursor = load_json(cursor_path, {}) or {}
    run_id = target_run_dir.name
    last_sequence = int(cursor.get("last_sequence", 0)) if cursor.get("run_id") == run_id else 0
    events = [event for event in load_events(target_run_dir / "events.jsonl") if int(event.get("sequence", 0)) > last_sequence]
    if not events:
        return []
    results = record_brain_events(project, events)
    if not any(item.get("action") == "error" for item in results):
        atomic_write(
            cursor_path,
            json_bytes({"run_id": run_id, "last_sequence": max(int(event["sequence"]) for event in events), "updated_at": now_iso()}),
        )
    return results


def submit_envelope(
    project: Path,
    envelope: dict[str, Any],
    *,
    port: int | None = None,
    state_root: Path | None = None,
    timeout: float = 0.3,
) -> dict[str, Any]:
    validate_ingest_envelope(envelope, project_id(project))
    queued_path = queue_envelope(project, envelope)
    selected_port = port or int(os.environ.get("MICK_HARNESS_OBSERVER_PORT", DEFAULT_PORT))
    token = ensure_ingest_token(state_root)
    request = Request(
        f"http://127.0.0.1:{selected_port}{INGEST_PATH}",
        data=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        acknowledge_envelope(queued_path)
        return {**result, "transport": "service"}
    except HTTPError as error:
        if error.code in {404, 405} and has_harness_entry(project):
            result = ingest_envelope(project, envelope)
            acknowledge_envelope(queued_path)
            return {**result, "transport": "local-fallback"}
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise ObserveError(f"Observer rejected event ({error.code}): {detail}", 2) from error
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        result = ingest_envelope(project, envelope)
        acknowledge_envelope(queued_path)
        return {**result, "transport": "local-fallback"}


def outbox_root(project: Path) -> Path:
    return runtime_root(project) / "outbox"


def queue_envelope(project: Path, envelope: dict[str, Any]) -> Path:
    key = envelope["idempotency_key"]
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    path = outbox_root(project) / f"{digest}.json"
    if not path.exists():
        atomic_write(path, json_bytes(envelope))
    return path


def acknowledge_envelope(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        path.unlink()


def replay_outbox(project: Path) -> dict[str, Any]:
    root = outbox_root(project)
    queued = sorted(root.glob("*.json")) if root.exists() else []
    replayed = 0
    failed = 0
    for path in queued:
        try:
            envelope = load_json(path)
            validate_ingest_envelope(envelope, project_id(project))
            ingest_envelope(project, envelope)
            acknowledge_envelope(path)
            replayed += 1
        except (ObserveError, OSError, TypeError, ValueError):
            failed += 1
    return {"queued": len(queued), "replayed": replayed, "failed": failed, "remaining": len(list(root.glob('*.json'))) if root.exists() else 0}


def write_index(project: Path, snapshot: dict[str, Any], run_metadata: dict[str, Any] | None = None) -> None:
    root = runtime_root(project)
    index_path = root / "index.json"
    index = load_json(index_path, {}) or {}
    index.setdefault("schema_version", SCHEMA_VERSION)
    index.setdefault("project_id", project_id(project))
    index.setdefault("runs", [])
    run_id = snapshot["run"]["run_id"]
    existing = next((item for item in index["runs"] if item.get("run_id") == run_id), None)
    if existing is None:
        existing = {"run_id": run_id}
        index["runs"].append(existing)
    metadata = run_metadata or {}
    existing.update(
        {
            "name": snapshot["run"].get("name") or metadata.get("name") or project.name,
            "status": snapshot["run"].get("status", "observing"),
            "created_at": metadata.get("created_at") or existing.get("created_at") or now_iso(),
            "updated_at": snapshot.get("updated_at") or now_iso(),
            "last_sequence": snapshot.get("last_sequence", 0),
            "snapshot": f"runs/{run_id}/snapshot.json",
        }
    )
    index["runs"].sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    index["updated_at"] = now_iso()
    atomic_write(index_path, json_bytes(index))


def project_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run": {"run_id": "", "name": "", "status": "observing"},
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
        "work_rounds": {},
        "decisions": {},
        "handoffs": {},
        "collector_warnings": [],
        "last_sequence": 0,
        "updated_at": None,
    }
    for event in sorted(events, key=lambda item: item["sequence"]):
        event_type = event["type"]
        subject = event["subject"]
        payload = event["payload"]
        if event_type == "run.created":
            snapshot["run"].update(
                {
                    "run_id": event["run_id"],
                    "name": payload["name"],
                    "project_id": payload["project_id"],
                    "status": payload.get("initial_status", "observing"),
                    "derived_from_sequence": event["sequence"],
                }
            )
        elif event_type == "run.status_changed":
            snapshot["run"].update(
                {"status": payload["to"], "derived_from_sequence": event["sequence"]}
            )
        elif event_type == "plan.summary_observed":
            snapshot["plan"] = {**payload, "derived_from_sequence": event["sequence"]}
        elif event_type == "workflow.stage_changed":
            snapshot["workflows"][subject["id"]] = {
                **payload,
                "derived_from_sequence": event["sequence"],
            }
        elif event_type == "task.discovered":
            snapshot["tasks"][subject["id"]] = {
                "task_id": subject["id"],
                **payload,
                "derived_from_sequence": event["sequence"],
            }
        elif event_type == "task.status_changed":
            task = snapshot["tasks"].setdefault(
                subject["id"],
                {"task_id": subject["id"], "title": subject["id"], "status": "discovered"},
            )
            task.update({"status": payload["to"], "derived_from_sequence": event["sequence"]})
        elif event_type == "artifact.observed":
            snapshot["artifacts"][subject["id"]] = {
                **payload,
                "derived_from_sequence": event["sequence"],
                "updated_at": event["occurred_at"],
            }
        elif event_type == "verification.observed":
            snapshot["verifications"].append(
                {
                    "verification_id": subject["id"],
                    "task_id": subject.get("parent_id"),
                    **payload,
                    "evidence_refs": event.get("evidence_refs", []),
                    "derived_from_sequence": event["sequence"],
                }
            )
        elif event_type == "block.observed":
            snapshot["blocks"][subject["id"]] = {
                "block_id": subject["id"],
                "task_id": subject.get("parent_id"),
                **payload,
                "derived_from_sequence": event["sequence"],
            }
        elif event_type in {"approval.requested", "approval.resolved"}:
            snapshot["approvals"][subject["id"]] = {
                "approval_id": subject["id"],
                "task_id": subject.get("parent_id"),
                **payload,
                "derived_from_sequence": event["sequence"],
            }
        elif event_type == "audit.finding_observed":
            snapshot["audit_findings"].append({**payload, "derived_from_sequence": event["sequence"]})
        elif event_type == "agent.session_observed":
            snapshot["agent_sessions"][subject["id"]] = {
                "session_id": subject["id"],
                **payload,
                "derived_from_sequence": event["sequence"],
                "updated_at": event["occurred_at"],
            }
        elif event_type == "agent.turn_observed":
            snapshot["agent_turns"][subject["id"]] = {
                "turn_id": subject["id"],
                **payload,
                "derived_from_sequence": event["sequence"],
                "updated_at": event["occurred_at"],
            }
        elif event_type == "harness.command_observed":
            snapshot["harness_commands"][subject["id"]] = {
                "invocation_id": subject["id"],
                **payload,
                "derived_from_sequence": event["sequence"],
                "updated_at": event["occurred_at"],
            }
        elif event_type in {"work.round_started", "work.round_completed"}:
            snapshot["work_rounds"][subject["id"]] = {
                "round_id": subject["id"],
                "task_id": payload.get("requirement_id") or subject.get("parent_id"),
                **payload,
                "derived_from_sequence": event["sequence"],
                "updated_at": event["occurred_at"],
            }
        elif event_type == "decision.recorded":
            snapshot["decisions"][subject["id"]] = {
                "decision_id": subject["id"],
                "task_id": payload.get("requirement_id") or subject.get("parent_id"),
                **payload,
                "derived_from_sequence": event["sequence"],
                "updated_at": event["occurred_at"],
            }
        elif event_type == "handoff.created":
            snapshot["handoffs"][subject["id"]] = {
                "handoff_id": subject["id"],
                "task_id": payload.get("requirement_id") or subject.get("parent_id"),
                **payload,
                "derived_from_sequence": event["sequence"],
                "updated_at": event["occurred_at"],
            }
        elif event_type == "collector.warning":
            snapshot["collector_warnings"].append({**payload, "derived_from_sequence": event["sequence"]})
        snapshot["last_sequence"] = event["sequence"]
        snapshot["updated_at"] = event["occurred_at"]

    tasks = [task for task in snapshot["tasks"].values() if task.get("status") != "abandoned"]
    snapshot["summary"] = {
        "task_total": len(tasks),
        "task_completed": sum(task.get("status") == "completed" for task in tasks),
        "task_blocked": sum(task.get("status") == "blocked" for task in tasks),
        "verification_pending": sum(task.get("status") == "verification_pending" for task in tasks),
        "active_blocks": sum(block.get("active") is True for block in snapshot["blocks"].values()),
        "active_agent_sessions": sum(item.get("state") != "session_ended" for item in snapshot["agent_sessions"].values()),
        "active_agent_turns": sum(item.get("state") == "turn_started" for item in snapshot["agent_turns"].values()),
        "active_harness_commands": sum(item.get("state") == "started" for item in snapshot["harness_commands"].values()),
        "work_round_total": len(snapshot["work_rounds"]),
        "active_work_rounds": sum(item.get("status") == "active" for item in snapshot["work_rounds"].values()),
        "decision_total": len(snapshot["decisions"]),
        "pending_handoffs": sum(item.get("status") == "pending" for item in snapshot["handoffs"].values()),
        "collector_warnings": len(snapshot["collector_warnings"]),
    }
    return snapshot


def write_snapshot(project: Path, target_run_dir: Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot = project_events(events)
    atomic_write(target_run_dir / "snapshot.json", json_bytes(snapshot))
    metadata = load_json(target_run_dir / "run.json", {}) or {}
    write_index(project, snapshot, metadata)
    return snapshot


def init_runtime(project: Path) -> dict[str, Any]:
    root = runtime_root(project)
    root.mkdir(parents=True, exist_ok=True)
    try:
        existing, _ = current_run(project)
        return existing
    except ObserveError:
        pass

    run_id = new_id("run")
    created_at = now_iso()
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "name": project.name,
        "project_id": project_id(project),
        "created_at": created_at,
    }
    target_run_dir = run_dir(project, run_id)
    (target_run_dir / "imports").mkdir(parents=True, exist_ok=True)
    atomic_write(target_run_dir / "run.json", json_bytes(metadata))
    candidate = make_candidate(
        "run.created",
        "run",
        run_id,
        {"kind": "harness", "producer": "observe-init"},
        {"name": project.name, "project_id": project_id(project), "initial_status": "observing"},
        f"run.created:{run_id}",
    )
    append_events(target_run_dir, run_id, [candidate])
    snapshot = write_snapshot(project, target_run_dir, load_events(target_run_dir / "events.jsonl"))
    write_index(project, snapshot, metadata)
    return next(item for item in load_json(root / "index.json")["runs"] if item["run_id"] == run_id)


def clean_step_id(raw: str) -> str:
    return raw.rstrip(".)")


def strip_markdown(value: str) -> str:
    cleaned = re.sub(r"[`*_]", "", value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def plan_section(text: str, names: tuple[str, ...]) -> str:
    labels = "|".join(re.escape(name) for name in names)
    match = re.search(
        rf"^##\s+(?:{labels})\s*$\n(.*?)(?=^##\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def active_plan_steps_body(text: str) -> str:
    """Select the step block containing the declared current progress range."""
    current_match = re.search(r"^>.*?进度\s+([0-9]+)\s*/\s*([0-9]+)", text, re.MULTILINE)
    progress_value = int(current_match.group(1)) if current_match else None
    headings = list(re.finditer(r"^##\s+.+$", text, re.MULTILINE))
    for index in range(len(headings) - 1, -1, -1):
        start = headings[index].start()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        section = text[start:end]
        matches = list(STEP_RE.finditer(section))
        step_numbers = [int(clean_step_id(match.group(2))) for match in matches if clean_step_id(match.group(2)).isdigit()]
        if matches and progress_value is not None and step_numbers and min(step_numbers) <= progress_value <= max(step_numbers):
            return section
    return plan_section(text, ("Steps", "步骤"))


def plan_objective(text: str) -> str:
    body = plan_section(text, ("Objective", "目标"))
    if not body:
        return ""
    paragraph = next((value for value in re.split(r"\n\s*\n", body) if value.strip()), "")
    lines = [re.sub(r"^\s*>\s?", "", line).strip() for line in paragraph.splitlines()]
    return strip_markdown(" ".join(line for line in lines if line))[:2000]


def plan_title(text: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    if not match:
        return "plan.md"
    return re.sub(r"^Plan:\s*", "", strip_markdown(match.group(1)), flags=re.IGNORECASE)[:200]


def step_title(value: str) -> str:
    bold = re.match(r"^\*\*(.+?)\*\*", value.strip())
    title = bold.group(1) if bold else value.strip()
    title = re.sub(
        r"\s*[（(](?:已完成|完成|进行中|in\s+progress|done)[）)]\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    )
    return strip_markdown(title)[:300]


def parse_plan_steps(text: str) -> list[dict[str, Any]]:
    body = active_plan_steps_body(text)
    if not body:
        return []
    checkbox_matches = list(STEP_RE.finditer(body))
    if checkbox_matches:
        first_open = next(
            (clean_step_id(match.group(2)) for match in checkbox_matches if match.group(1) == " "),
            None,
        )
        return [
            {
                "step_id": clean_step_id(match.group(2)),
                "title": step_title(match.group(3)),
                "marker": match.group(1),
                "format": "checkbox",
                "status": (
                    "completed"
                    if match.group(1) == "x"
                    else "skipped"
                    if match.group(1) == "~"
                    else "in_progress"
                    if clean_step_id(match.group(2)) == first_open
                    else "discovered"
                ),
            }
            for match in checkbox_matches
        ]

    current_match = CURRENT_STEP_RE.search(text)
    current_step = int(current_match.group(1)) if current_match else None
    steps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in NUMBERED_STEP_RE.finditer(body):
        step_id = clean_step_id(match.group(1))
        if step_id in seen:
            continue
        seen.add(step_id)
        index = int(step_id)
        raw_title = match.group(2)
        if current_step is not None:
            status = "completed" if index < current_step else "in_progress" if index == current_step else "discovered"
        elif re.search(r"[（(](?:已完成|完成|done)[）)]", raw_title, re.IGNORECASE):
            status = "completed"
        elif re.search(r"[（(](?:进行中|in\s+progress)[）)]", raw_title, re.IGNORECASE):
            status = "in_progress"
        else:
            status = "discovered"
        steps.append(
            {
                "step_id": step_id,
                "title": step_title(raw_title),
                "marker": None,
                "format": "numbered",
                "status": status,
            }
        )
    return steps


def parse_plan_summary(text: str, steps: list[dict[str, Any]], source_path: str) -> dict[str, Any]:
    current_match = CURRENT_STEP_RE.search(text)
    current_step = int(current_match.group(1)) if current_match else None
    current = next(
        (step for step in steps if step["step_id"] == str(current_step)),
        next((step for step in steps if step["status"] in {"in_progress", "verification_pending", "blocked"}), None),
    )
    current_title = step_title(current_match.group(3)) if current_match and current_match.group(3) else None
    if current is not None:
        current_title = current["title"]
        if current_step is None and current["step_id"].isdigit():
            current_step = int(current["step_id"])
    return {
        "title": plan_title(text),
        "objective": plan_objective(text),
        "source_path": source_path,
        "current_task_id": f"task-{current['step_id']}" if current else None,
        "current_title": current_title,
        "current_step": current_step,
        "total_steps": len(steps),
    }


def role_from_text(value: str) -> str:
    lowered = value.lower()
    if "planner" in lowered:
        return "Planner"
    if "reviewer" in lowered or "审查" in value:
        return "Reviewer"
    if "qa" in lowered or "测试" in value:
        return "QA"
    if "pm" in lowered or "需求" in value:
        return "PM"
    if "executor" in lowered or "dev" in lowered or "执行" in value or "实现" in value:
        return "Executor"
    if "designer" in lowered or "设计" in value:
        return "Designer"
    return "Unknown"


def parse_verifications(text: str) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for match in SELFCHECK_RE.finditer(text):
        step_id = clean_step_id(match.group(1))
        body = match.group(2)
        verify_match = re.search(r"^-\s+verify:\s*(.+)$", body, re.MULTILINE)
        if not verify_match:
            continue
        statement = verify_match.group(1).strip()
        result = "passed" if PASS_RE.search(statement) else "failed" if FAIL_RE.search(statement) else "unknown"
        exit_match = re.search(r"exit(?:\s+code)?[=: ]+(-?\d+)", statement, re.IGNORECASE)
        results[step_id] = {
            "result": result,
            "check": f"plan self-check Step {step_id}",
            "summary": statement[:1000],
            **({"exit_code": int(exit_match.group(1))} if exit_match else {}),
        }
    return results


def plan_run_status(text: str) -> str | None:
    status_match = re.search(r"^>\s*🧭\s*状态：([^|\n]+)", text, re.MULTILINE)
    if not status_match:
        return None
    value = status_match.group(1).strip().lower()
    if "完成" in value or "completed" in value or "done" in value:
        return "completed"
    if "阻塞" in value or "blocked" in value:
        return "blocked"
    if "执行" in value or "active" in value or "进行" in value:
        return "active"
    return None


def plan_stage(text: str, steps: list[dict[str, Any]]) -> tuple[str, str, str, bool]:
    title_match = re.search(r"^#\s+Plan:\s*(.+)$", text, re.MULTILINE)
    feature = title_match.group(1).strip()[:160] if title_match else "plan.md"
    header_match = re.search(
        r"^>\s*🧭\s*状态：([^|\n]+).*?当前归属：([^|\n]+)",
        text,
        re.MULTILINE,
    )
    if header_match:
        stage = header_match.group(1).strip()
        owner = header_match.group(2).strip()
        return stage, role_from_text(owner), feature, True
    if steps:
        if all(step["status"] in {"completed", "skipped"} for step in steps):
            return "已完成", "Reviewer", feature, False
        return "执行中", "Executor", feature, False
    return "规划中", "Planner", feature, False


def collect_plan(project: Path, snapshot: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    path = project / "plan.md"
    if not path.is_file():
        return [], [], None
    text = path.read_text(encoding="utf-8")
    digest = sha256_text(text)
    plan_revision = f"collector:{COLLECTOR_VERSION}:{digest}"
    source_path = relative_source(project, path)
    source = {"kind": "importer", "producer": "plan-collector", "path": source_path, "revision": digest}
    candidates: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    existing_tasks = snapshot.get("tasks", {})
    verifications = parse_verifications(text)
    steps = parse_plan_steps(text)
    plan_summary = parse_plan_summary(text, steps, source_path)

    stage, stage_owner, feature, stage_observed = plan_stage(text, steps)
    previous_stage = snapshot.get("workflows", {}).get("workflow-plan", {}).get("to")
    previous_owner = snapshot.get("workflows", {}).get("workflow-plan", {}).get("owner_role")
    if stage != previous_stage or stage_owner != previous_owner:
        candidates.append(
            make_candidate(
                "workflow.stage_changed",
                "workflow",
                "workflow-plan",
                source,
                {"from": previous_stage, "to": stage, "feature": feature, "owner_role": stage_owner},
                f"{plan_revision}:workflow.plan:{stage}:{stage_owner}",
                observation_kind="observed" if stage_observed else "inferred",
                confidence=None if stage_observed else 0.8,
            )
        )

    run_status = plan_run_status(text)
    run_status_observed = run_status is not None
    if run_status is None and steps:
        run_status = "completed" if all(step["status"] in {"completed", "skipped"} for step in steps) else "active"
    current_status = snapshot.get("run", {}).get("status", "observing")
    if run_status and run_status != current_status:
        candidates.append(
            make_candidate(
                "run.status_changed",
                "run",
                snapshot["run"]["run_id"],
                source,
                {"from": current_status, "to": run_status, "reason": "Observed plan status line"},
                f"{plan_revision}:run.status:{run_status}",
                observation_kind="observed" if run_status_observed else "inferred",
                confidence=None if run_status_observed else 0.8,
            )
        )

    for step in steps:
        marker = step["marker"]
        step_id = step["step_id"]
        title = step["title"]
        task_id = f"task-{step_id}"
        raw_status = step["status"]
        verification = verifications.get(step_id)
        desired_status = raw_status
        if step["format"] == "checkbox" and marker == "x" and (not verification or verification["result"] != "passed"):
            desired_status = "verification_pending"

        previous = existing_tasks.get(task_id)
        if previous is None:
            discovery_status = raw_status if raw_status in {"discovered", "in_progress", "skipped", "completed"} else "discovered"
            candidates.append(
                make_candidate(
                    "task.discovered",
                    "task",
                    task_id,
                    source,
                    {
                        "title": title[:300],
                        "status": discovery_status,
                        "role": role_from_text(title) if role_from_text(title) != "Unknown" else "Executor",
                        "depends_on": ([f"task-{int(step_id) - 1}"] if step_id.isdigit() and int(step_id) > 1 else []),
                        "source_anchor": f"Step {step_id}",
                    },
                    f"{plan_revision}:task.discovered:{task_id}:{sha256_text(title)}",
                    parent_id=snapshot["run"]["run_id"],
                )
            )
            previous_status = discovery_status
        else:
            previous_status = previous.get("status", "discovered")
            if previous.get("title") != title[:300]:
                warnings.append(
                    make_candidate(
                        "collector.warning",
                        "collector",
                        stable_id("warning", f"title:{task_id}:{digest}"),
                        source,
                        {"code": "task-title-changed", "summary": f"Task {task_id} title changed; V0 keeps the original title", "recoverable": True},
                        f"{plan_revision}:warning:title:{task_id}",
                    )
                )
        if desired_status != previous_status:
            candidates.append(
                make_candidate(
                    "task.status_changed",
                    "task",
                    task_id,
                    source,
                    {"from": previous_status, "to": desired_status, "reason": "Observed plan step marker and verification evidence"},
                    f"{plan_revision}:task.status:{task_id}:{desired_status}",
                    parent_id=snapshot["run"]["run_id"],
                )
            )
        if verification:
            verification_id = stable_id("verification", f"{task_id}:{digest}")
            candidates.append(
                make_candidate(
                    "verification.observed",
                    "verification",
                    verification_id,
                    source,
                    verification,
                    f"{plan_revision}:verification:{task_id}:{verification['result']}",
                    parent_id=task_id,
                    evidence_refs=[{"kind": "source", "ref": source_path, "label": f"Step {step_id} self-check"}],
                )
            )

    observed_task_ids = {f"task-{step['step_id']}" for step in steps}
    for task_id, previous in existing_tasks.items():
        if task_id.startswith("task-") and task_id not in observed_task_ids and previous.get("status") != "abandoned":
            candidates.append(
                make_candidate(
                    "task.status_changed",
                    "task",
                    task_id,
                    source,
                    {"from": previous.get("status", "unknown"), "to": "abandoned", "reason": "Plan item is no longer a numbered step"},
                    f"{plan_revision}:task.status:{task_id}:abandoned",
                    parent_id=snapshot["run"]["run_id"],
                )
            )

    for block_match in BLOCK_RE.finditer(text):
        block_number, heading, body = block_match.groups()
        step_match = re.search(r"步骤\s+([A-Za-z0-9._-]+)", heading)
        summary_match = re.search(r"^发现：\s*(.+)$", body, re.MULTILINE)
        resolved = bool(
            re.search(r"^(?:Planner\s+回复|解决|Resolved)[：:]?", body, re.MULTILINE | re.IGNORECASE)
            or re.search(
                r"^\*{0,2}状态[：:]\*{0,2}\s*(?:已.*(?:解决|选择|关闭|完成|裁决)|resolved|closed)",
                body,
                re.MULTILINE | re.IGNORECASE,
            )
        )
        step_id = step_match.group(1) if step_match else None
        block_summary = summary_match.group(1) if summary_match else None
        task_id = f"task-{step_id}" if step_id else None
        block_id = f"block-{block_number}"
        candidates.append(
            make_candidate(
                "block.observed",
                "block",
                block_id,
                source,
                {"summary": (block_summary or f"Plan block #{block_number}")[:1000], "active": not resolved, "owner_role": "Planner"},
                f"{plan_revision}:block:{block_id}:{'resolved' if resolved else 'active'}",
                parent_id=task_id,
            )
        )

    candidates.append(
        make_candidate(
            "plan.summary_observed",
            "plan",
            "plan-current",
            source,
            plan_summary,
            f"{plan_revision}:plan.summary",
            parent_id=snapshot["run"]["run_id"],
        )
    )

    candidates.append(
        make_candidate(
            "artifact.observed",
            "artifact",
            stable_id("artifact", source_path),
            source,
            {"path": source_path, "artifact_type": "plan", "exists": True, "digest": digest},
            f"{plan_revision}:artifact:{source_path}",
        )
    )
    return candidates, warnings, digest


def parse_state_file(project: Path, path: Path, snapshot: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    text = path.read_text(encoding="utf-8")
    digest = sha256_text(text)
    source_path = relative_source(project, path)
    source = {"kind": "importer", "producer": "state-collector", "path": source_path, "revision": digest}
    candidates: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    feature_match = re.search(r"^-\s+\*\*Feature 名称\*\*:\s*(.+)$", text, re.MULTILINE)
    feature = re.sub(r"<!--.*?-->", "", feature_match.group(1)).strip() if feature_match else path.stem
    feature = feature or path.stem
    current_line = next((line for line in text.splitlines() if "当前阶段" in line and line.lstrip().startswith("- [")), None)
    if current_line:
        stage_match = re.search(r"\*\*([^*]+)\*\*", current_line)
        stage = stage_match.group(1).strip() if stage_match else current_line.strip()
        workflow_id = stable_id("workflow", source_path)
        previous = snapshot.get("workflows", {}).get(workflow_id, {}).get("to")
        if stage != previous:
            candidates.append(
                make_candidate(
                    "workflow.stage_changed",
                    "workflow",
                    workflow_id,
                    source,
                    {"from": previous, "to": stage, "feature": feature[:160], "owner_role": role_from_text(stage)},
                    f"{digest}:workflow.stage:{workflow_id}:{stage}",
                )
            )
        if "done" in stage.lower() or "完成" in stage:
            current_status = snapshot.get("run", {}).get("status", "observing")
            if current_status != "completed":
                candidates.append(
                    make_candidate(
                        "run.status_changed",
                        "run",
                        snapshot["run"]["run_id"],
                        source,
                        {"from": current_status, "to": "completed", "reason": "Observed STATE Done stage"},
                        f"{digest}:run.status:completed",
                    )
                )
    else:
        warnings.append(
            make_candidate(
                "collector.warning",
                "collector",
                stable_id("warning", f"state-stage:{source_path}:{digest}"),
                source,
                {"code": "state-current-stage-missing", "summary": f"No current stage marker found in {source_path}", "recoverable": True},
                f"{digest}:warning:state-current-stage",
            )
        )
    candidates.append(
        make_candidate(
            "artifact.observed",
            "artifact",
            stable_id("artifact", source_path),
            source,
            {"path": source_path, "artifact_type": "state", "exists": True, "digest": digest},
            f"{digest}:artifact:{source_path}",
        )
    )
    return candidates, warnings, digest


def collect_states(project: Path, snapshot: dict[str, Any]) -> list[tuple[Path, list[dict[str, Any]], list[dict[str, Any]], str]]:
    docs_dir = project / "docs"
    if not docs_dir.is_dir():
        return []
    paths = sorted({*docs_dir.glob("STATE.md"), *docs_dir.glob("STATE-*.md")})
    results = []
    for path in paths:
        candidates, warnings, digest = parse_state_file(project, path, snapshot)
        results.append((path, candidates, warnings, digest))
    return results


def collect_audit(project: Path, snapshot: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    del snapshot
    path = project / "audit-log.md"
    if not path.is_file():
        return [], None
    text = path.read_text(encoding="utf-8")
    digest = sha256_text(text)
    source_path = relative_source(project, path)
    source = {"kind": "importer", "producer": "audit-collector", "path": source_path, "revision": digest}
    candidates: list[dict[str, Any]] = []
    for index, line in enumerate(text.splitlines(), 1):
        match = re.search(r"\b(INFO|WARN|FAIL)\b[\t |:-]+([A-Za-z0-9._-]+)[\t |:-]+(.+)", line)
        if not match:
            continue
        raw_level, tag, summary = match.groups()
        level = {"INFO": "info", "WARN": "warn", "FAIL": "fail"}[raw_level]
        finding_id = stable_id("audit", f"{source_path}:{index}:{tag}:{summary}")
        candidates.append(
            make_candidate(
                "audit.finding_observed",
                "audit",
                finding_id,
                source,
                {"level": level, "tag": tag[:100], "summary": summary[:1000]},
                f"{digest}:audit:{finding_id}",
            )
        )
    return candidates, digest


def imports_index_path(target_run_dir: Path) -> Path:
    return target_run_dir / "imports" / "index.json"


def import_signature(digest: str) -> str:
    return f"collector:{COLLECTOR_VERSION}:{digest}"


def sync_runtime(project: Path) -> dict[str, Any]:
    init_runtime(project)
    run_record, target_run_dir = current_run(project)
    run_id = run_record["run_id"]
    existing_events = load_events(target_run_dir / "events.jsonl")
    snapshot = project_events(existing_events)
    imports = load_json(imports_index_path(target_run_dir), {}) or {}
    batches: list[tuple[str, str, list[dict[str, Any]]]] = []
    source_count = 0

    plan_candidates, plan_warnings, plan_digest = collect_plan(project, snapshot)
    if plan_digest:
        source_count += 1
        if imports.get("plan.md") != import_signature(plan_digest):
            batches.append(("plan.md", plan_digest, plan_candidates + plan_warnings))

    for path, state_candidates, state_warnings, digest in collect_states(project, snapshot):
        source_count += 1
        source_path = relative_source(project, path)
        if imports.get(source_path) != import_signature(digest):
            batches.append((source_path, digest, state_candidates + state_warnings))

    audit_candidates, audit_digest = collect_audit(project, snapshot)
    if audit_digest:
        source_count += 1
        if imports.get("audit-log.md") != import_signature(audit_digest):
            batches.append(("audit-log.md", audit_digest, audit_candidates))

    if source_count == 0:
        warning = make_candidate(
            "collector.warning",
            "collector",
            "collector-no-sources",
            {"kind": "harness", "producer": "observe-sync"},
            {"code": "no-sources", "summary": "No plan.md, docs/STATE*.md, or audit-log.md sources found", "recoverable": True},
            f"collector.warning:no-sources:{run_id}",
        )
        appended_count, _ = append_events(target_run_dir, run_id, [warning])
        snapshot = write_snapshot(project, target_run_dir, load_events(target_run_dir / "events.jsonl"))
        return {"run_id": run_id, "sources": 0, "appended": appended_count, "warning": "no-sources", "snapshot": snapshot}

    appended_total = 0
    for source_path, digest, candidates in batches:
        snapshot_import = make_candidate(
            "source.snapshot_imported",
            "artifact",
            stable_id("source", source_path),
            {"kind": "importer", "producer": "observe-sync", "path": source_path, "revision": digest},
            {"path": source_path, "digest": digest, "collector": candidates[0]["source"]["producer"] if candidates else "observe-sync", "candidate_count": len(candidates)},
            f"{digest}:source.snapshot:{source_path}",
        )
        appended, _ = append_events(target_run_dir, run_id, candidates + [snapshot_import])
        appended_total += appended
        imports[source_path] = import_signature(digest)
        atomic_write(imports_index_path(target_run_dir), json_bytes(imports))
        snapshot = project_events(load_events(target_run_dir / "events.jsonl"))

    snapshot = write_snapshot(project, target_run_dir, load_events(target_run_dir / "events.jsonl"))
    brain_results = record_runtime_brain_events(project, target_run_dir)
    return {
        "run_id": run_id,
        "sources": source_count,
        "appended": appended_total,
        "brain_recorded": sum(item.get("action") == "recorded_project_memory" for item in brain_results),
        "brain_errors": [item for item in brain_results if item.get("action") == "error"],
        "warning": None,
        "snapshot": snapshot,
    }


def replay_runtime(project: Path) -> dict[str, Any]:
    run_record, target_run_dir = current_run(project)
    snapshot_path = target_run_dir / "snapshot.json"
    before = sha256_bytes(snapshot_path.read_bytes()) if snapshot_path.exists() else None
    snapshot = write_snapshot(project, target_run_dir, load_events(target_run_dir / "events.jsonl"))
    after = sha256_bytes(snapshot_path.read_bytes())
    return {"run_id": run_record["run_id"], "before_digest": before, "after_digest": after, "changed": before != after, "snapshot": snapshot}


def status_runtime(project: Path) -> dict[str, Any]:
    run_record, target_run_dir = current_run(project)
    snapshot = load_json(target_run_dir / "snapshot.json")
    if snapshot is None:
        snapshot = replay_runtime(project)["snapshot"]
    return {"run": run_record, "snapshot": snapshot}


def snapshot_stage(snapshot: dict[str, Any]) -> tuple[str, str]:
    work_rounds = sorted(
        snapshot.get("work_rounds", {}).values(),
        key=lambda item: item.get("derived_from_sequence", 0),
    )
    active_rounds = [item for item in work_rounds if item.get("status") == "active"]
    if active_rounds:
        return "角色工作中", active_rounds[-1].get("role", "Unknown")
    if work_rounds:
        latest = work_rounds[-1]
        if latest.get("next_role"):
            return "等待角色接手", latest["next_role"]
        return "最近工作已回写", latest.get("role", "Unknown")
    workflow_items = snapshot.get("workflows", {})
    state_workflows = [value for key, value in workflow_items.items() if key != "workflow-plan"]
    workflows = sorted(
        state_workflows or list(workflow_items.values()),
        key=lambda item: item.get("derived_from_sequence", 0),
    )
    if workflows:
        current = workflows[-1]
        return current.get("to", "unknown"), current.get("owner_role", "Unknown")
    active_turns = [item for item in snapshot.get("agent_turns", {}).values() if item.get("state") == "turn_started"]
    if active_turns:
        return "Agent 执行中", str(active_turns[-1].get("platform", "agent")).title()
    active_sessions = [item for item in snapshot.get("agent_sessions", {}).values() if item.get("state") != "session_ended"]
    if active_sessions:
        return "Agent 会话中", str(active_sessions[-1].get("platform", "agent")).title()
    run_status = snapshot.get("run", {}).get("status", "observing")
    labels = {"completed": "已完成", "blocked": "已阻塞", "active": "执行中", "observing": "观察中"}
    return labels.get(run_status, run_status), "Unknown"


def parse_project_profile(value: str) -> dict[str, str]:
    def first_paragraph(section_names: tuple[str, ...]) -> str:
        body = plan_section(value, section_names)
        if not body:
            return ""
        paragraph = next((part for part in re.split(r"\n\s*\n", body) if part.strip()), "")
        lines = [re.sub(r"^\s*>\s?", "", line).strip() for line in paragraph.splitlines()]
        return strip_markdown(" ".join(line for line in lines if line))[:2000]

    return {
        "goal": first_paragraph(("Goal", "目标")),
        "audience": first_paragraph(("Audience", "用户")),
        "boundary": first_paragraph(("Product Boundary", "产品边界")),
    }


def project_profile_snapshot(project: Path) -> dict[str, Any]:
    source = project / "docs" / "PROJECT.md"
    if not source.is_file():
        return {"source": None, "goal": "", "audience": "", "boundary": ""}
    return {"source": "docs/PROJECT.md", **parse_project_profile(source.read_text(encoding="utf-8"))}


def office_role(value: Any) -> str | None:
    return OFFICE_ROLE_BY_SOURCE.get(value) if isinstance(value, str) else None


def organization_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    rounds = sorted(
        snapshot.get("work_rounds", {}).values(),
        key=lambda item: item.get("derived_from_sequence", 0),
    )
    handoffs = sorted(
        snapshot.get("handoffs", {}).values(),
        key=lambda item: item.get("derived_from_sequence", 0),
    )
    quality_gaps_by_requirement: dict[str, dict[str, Any]] = {}
    transitions: list[dict[str, Any]] = []
    for item in rounds:
        from_role = office_role(item.get("role"))
        to_role = office_role(item.get("next_role"))
        requirement_id = item.get("requirement_id") or item.get("task_id")
        sequence = item.get("derived_from_sequence", 0)
        requires_independent_qa = (
            from_role in {"Designer", "Executor"}
            and item.get("status") == "completed"
            and bool(requirement_id)
        )
        qa_completed_after_delivery = any(
            office_role(candidate.get("role")) == "QA"
            and candidate.get("status") == "completed"
            and (candidate.get("requirement_id") or candidate.get("task_id")) == requirement_id
            and candidate.get("derived_from_sequence", 0) > sequence
            for candidate in rounds
        )
        if requires_independent_qa and not qa_completed_after_delivery:
            quality_gaps_by_requirement[str(requirement_id)] = {
                "requirement_id": requirement_id,
                "delivery_role": from_role,
                "delivery_round_id": item.get("round_id"),
                "delivery_sequence": sequence,
                "summary": "已交付，但尚无 QA 独立验收回合",
            }
            to_role = "QA"
        if item.get("status") != "completed":
            continue
        if not from_role or not to_role or from_role == to_role:
            continue
        transition_kind = "quality_gate" if requires_independent_qa and not qa_completed_after_delivery else "suggested"
        transitions.append(
            {
                "transition_id": f"round:{item.get('round_id', item.get('derived_from_sequence', 'unknown'))}",
                "kind": transition_kind,
                "from_role": from_role,
                "to_role": to_role,
                "status": "pending",
                "summary": (
                    "开发或设计已交付，先由 QA 完成独立验收"
                    if transition_kind == "quality_gate"
                    else item.get("summary") or item.get("objective")
                ),
                "requirement_id": requirement_id,
                "round_id": item.get("round_id"),
                "derived_from_sequence": sequence,
            }
        )
    for item in handoffs:
        from_role = office_role(item.get("from_role"))
        to_role = office_role(item.get("to_role"))
        if not from_role or not to_role or from_role == to_role:
            continue
        transitions.append(
            {
                "transition_id": f"handoff:{item.get('handoff_id', item.get('derived_from_sequence', 'unknown'))}",
                "kind": "handoff",
                "from_role": from_role,
                "to_role": to_role,
                "status": item.get("status", "pending"),
                "summary": item.get("summary"),
                "requirement_id": item.get("requirement_id") or item.get("task_id"),
                "round_id": item.get("round_id"),
                "derived_from_sequence": item.get("derived_from_sequence", 0),
            }
        )
    transitions.sort(key=lambda item: item.get("derived_from_sequence", 0))
    current_transition = transitions[-1] if transitions else None
    active_rounds = [item for item in rounds if item.get("status") == "active" and office_role(item.get("role"))]
    latest_active = active_rounds[-1] if active_rounds else None
    current_role = office_role(latest_active.get("role")) if latest_active else None
    if current_role is None and current_transition is not None:
        current_role = current_transition["to_role"]
    if current_role is None and rounds:
        current_role = office_role(rounds[-1].get("role"))

    quality_gaps = sorted(
        quality_gaps_by_requirement.values(),
        key=lambda item: item.get("delivery_sequence", 0),
        reverse=True,
    )

    def normalized_history(item: dict[str, Any], role_id: str) -> dict[str, Any]:
        requirement_id = item.get("requirement_id") or item.get("task_id")
        history = {
            "round_id": item.get("round_id"),
            "requirement_id": requirement_id,
            "status": item.get("status"),
            "objective": item.get("objective"),
            "summary": item.get("summary"),
            "artifacts": list(dict.fromkeys(item.get("artifact_refs") or [])),
            "verification_refs": list(dict.fromkeys(item.get("verification_refs") or [])),
            "sequence": item.get("derived_from_sequence"),
            "updated_at": item.get("updated_at"),
        }
        if role_id == "Reviewer":
            related = [
                candidate
                for candidate in rounds
                if (candidate.get("requirement_id") or candidate.get("task_id")) == requirement_id
                and candidate.get("derived_from_sequence", 0) <= item.get("derived_from_sequence", 0)
                and office_role(candidate.get("role")) in {"Designer", "Executor", "QA"}
            ]
            artifacts = list(
                dict.fromkeys(
                    artifact
                    for candidate in related
                    for artifact in (candidate.get("artifact_refs") or [])
                )
            )
            verification_refs = list(
                dict.fromkeys(
                    reference
                    for candidate in related
                    for reference in (candidate.get("verification_refs") or [])
                )
            )
            history["review_scope"] = {
                "requirement_id": requirement_id,
                "artifacts": artifacts,
                "verification_refs": verification_refs,
                "recorded": bool(requirement_id and (artifacts or verification_refs)),
            }
        return history

    roles: list[dict[str, Any]] = []
    for definition in OFFICE_ROLES:
        role_id = definition["role_id"]
        role_rounds = [item for item in rounds if office_role(item.get("role")) == role_id]
        role_active = [item for item in role_rounds if item.get("status") == "active"]
        latest = role_rounds[-1] if role_rounds else None
        waiting = bool(current_transition and current_transition["to_role"] == role_id and not role_active)
        missing_qa = role_id == "QA" and not role_rounds and bool(quality_gaps)
        status = "active" if role_active else "waiting" if waiting else "completed" if latest else "missing" if missing_qa else "idle"
        roles.append(
            {
                "role_id": role_id,
                "label": definition["label"],
                "source_roles": list(definition["source_roles"]),
                "status": status,
                "latest_summary": (latest.get("summary") or latest.get("objective")) if latest else None,
                "latest_requirement_id": (latest.get("requirement_id") or latest.get("task_id")) if latest else None,
                "last_sequence": latest.get("derived_from_sequence") if latest else None,
                "participation": (
                    "recorded"
                    if role_rounds
                    else "missing_independent_validation"
                    if missing_qa
                    else "not_recorded"
                ),
                "history": [normalized_history(item, role_id) for item in reversed(role_rounds)],
                "work_rounds": role_rounds,
            }
        )
    return {
        "roles": roles,
        "transitions": transitions,
        "current_transition": current_transition,
        "current_role": current_role,
        "quality_gaps": quality_gaps,
    }


def artifact_language(path: Path) -> str:
    if path.name in {"VERSION", "LICENSE", "Makefile"}:
        return "text"
    return ARTIFACT_LANGUAGES.get(path.suffix.lower(), "text")


def parse_markdown_stages(value: str) -> list[dict[str, Any]]:
    """Parse explicit stage headings without treating body dates as metadata."""
    stages: list[dict[str, Any]] = []
    fence_marker: str | None = None
    for line_number, raw_line in enumerate(value.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1):
        stripped = raw_line.lstrip()
        fence = re.match(r"^(```+|~~~+)", stripped)
        if fence:
            marker = fence.group(1)[0]
            fence_marker = None if fence_marker == marker else marker if fence_marker is None else fence_marker
            continue
        if fence_marker is not None:
            continue
        heading = MARKDOWN_STAGE_HEADING_RE.match(raw_line)
        if not heading:
            continue
        level = len(heading.group(1))
        heading_text = heading.group(2).strip()
        structured = STRUCTURED_STAGE_RE.match(heading_text)
        if structured:
            date_value = structured.group("date")
            try:
                dt.date.fromisoformat(date_value)
            except ValueError:
                continue
            stages.append(
                {
                    "line": line_number,
                    "level": level,
                    "title": structured.group("title").strip(),
                    "version": structured.group("version"),
                    "date": date_value,
                    "dates": [date_value],
                    "format": "structured",
                    "traceable": True,
                }
            )
            continue
        legacy = LEGACY_STAGE_PAREN_RE.match(heading_text) or LEGACY_STAGE_DASH_RE.match(heading_text)
        if not legacy:
            continue
        dates = []
        for date_value in ISO_DATE_RE.findall(legacy.group("meta")):
            try:
                dt.date.fromisoformat(date_value)
            except ValueError:
                continue
            if date_value not in dates:
                dates.append(date_value)
        if not dates:
            continue
        stages.append(
            {
                "line": line_number,
                "level": level,
                "title": legacy.group("title").strip(),
                "version": None,
                "date": dates[-1],
                "dates": dates,
                "format": "legacy",
                "traceable": False,
            }
        )
    return stages


def authorized_artifact_descriptors(project: Path, snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    descriptors: dict[str, dict[str, Any]] = {}
    for item in snapshot.get("artifacts", {}).values():
        path_value = item.get("path")
        if isinstance(path_value, str) and path_value and item.get("exists") is not False:
            descriptors[path_value] = {**item, "records": []}
            if item.get("updated_at"):
                descriptors[path_value]["records"].append(
                    {
                        "record_kind": "observed",
                        "recorded_at": item.get("updated_at"),
                        "sequence": item.get("derived_from_sequence"),
                        "role": item.get("role"),
                        "requirement_id": item.get("requirement_id"),
                        "objective": None,
                        "summary": item.get("summary"),
                    }
                )
    work_rounds = sorted(
        snapshot.get("work_rounds", {}).values(),
        key=lambda item: item.get("derived_from_sequence", 0),
    )
    for work_round in work_rounds:
        for path_value in work_round.get("artifact_refs") or []:
            if isinstance(path_value, str) and path_value:
                descriptor = descriptors.setdefault(
                    path_value,
                    {
                        "path": path_value,
                        "title": Path(path_value).name,
                        "exists": True,
                        "records": [],
                    },
                )
                descriptor.update(
                    {
                        "summary": work_round.get("summary") or work_round.get("objective"),
                        "role": work_round.get("role"),
                        "requirement_id": work_round.get("requirement_id"),
                    }
                )
                descriptor.setdefault("records", []).append(
                    {
                        "record_kind": "work_round",
                        "recorded_at": work_round.get("updated_at"),
                        "sequence": work_round.get("derived_from_sequence"),
                        "round_id": work_round.get("round_id"),
                        "role": work_round.get("role"),
                        "requirement_id": work_round.get("requirement_id"),
                        "objective": work_round.get("objective"),
                        "summary": work_round.get("summary"),
                        "status": work_round.get("status"),
                    }
                )
    versions_path = project / "docs" / "VERSIONS.md"
    if versions_path.is_file():
        descriptor = descriptors.setdefault(
            "docs/VERSIONS.md",
            {
                "path": "docs/VERSIONS.md",
                "exists": True,
                "records": [],
            },
        )
        descriptor.update(
            {
                "title": "版本计划",
                "summary": descriptor.get("summary") or "PM 维护的版本目标、需求归属和分支计划。",
                "role": descriptor.get("role") or "PM",
            }
        )
    project_path = project / "docs" / "PROJECT.md"
    if project_path.is_file():
        descriptor = descriptors.setdefault(
            "docs/PROJECT.md",
            {
                "path": "docs/PROJECT.md",
                "exists": True,
                "records": [],
            },
        )
        descriptor.update(
            {
                "title": "项目说明",
                "summary": descriptor.get("summary") or "PM 维护的稳定项目目标、目标用户和产品边界。",
                "role": descriptor.get("role") or "PM",
            }
        )
    return descriptors


def resolve_authorized_artifact(project: Path, snapshot: dict[str, Any], path_value: str) -> tuple[Path, str, dict[str, Any]]:
    try:
        validate_relative_path(path_value)
    except ObserveError as error:
        raise ObserveError(str(error), 403) from error
    normalized = Path(path_value).as_posix()
    descriptor = authorized_artifact_descriptors(project, snapshot).get(normalized)
    if descriptor is None:
        raise ObserveError("Artifact is not recorded for this project run", 403)
    project_root = project.resolve(strict=True)
    candidate = project_root / normalized
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(project_root)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        raise ObserveError("Artifact path is missing or leaves the project", 404) from error
    if not resolved.is_file():
        raise ObserveError("Artifact is not a readable file", 404)
    return resolved, normalized, descriptor


def artifact_metadata(
    project: Path,
    snapshot: dict[str, Any],
    version_plan: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    version_plan = version_plan or {"items": []}
    version_order = [item.get("version") for item in version_plan.get("items", []) if item.get("version")]
    requirement_versions: dict[str, list[str]] = {}
    for version in version_plan.get("items", []):
        version_value = version.get("version")
        if not version_value:
            continue
        for requirement in version.get("requirements", []):
            requirement_id = requirement.get("requirement_id")
            if requirement_id:
                requirement_versions.setdefault(requirement_id, []).append(version_value)

    items: list[dict[str, Any]] = []
    for path_value, descriptor in sorted(authorized_artifact_descriptors(project, snapshot).items()):
        try:
            resolved, normalized, _ = resolve_authorized_artifact(project, snapshot, path_value)
            stat = resolved.stat()
            size = stat.st_size
            language = artifact_language(resolved)
            modified_at = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc).isoformat(timespec="seconds")
            records: list[dict[str, Any]] = []
            for raw_record in descriptor.get("records", []):
                recorded_at = raw_record.get("recorded_at") or modified_at
                requirement_id = raw_record.get("requirement_id")
                record_versions = list(requirement_versions.get(requirement_id, []))
                if not record_versions and normalized == "docs/VERSIONS.md":
                    record_versions = list(version_order)
                record = {
                    **raw_record,
                    "recorded_at": recorded_at,
                    "date": recorded_at[:10],
                    "versions": record_versions,
                    "requirement_title": snapshot.get("tasks", {}).get(requirement_id, {}).get("title") if requirement_id else None,
                }
                records.append(record)
            if not records:
                records.append(
                    {
                        "record_kind": "file",
                        "recorded_at": modified_at,
                        "date": modified_at[:10],
                        "sequence": descriptor.get("derived_from_sequence"),
                        "role": descriptor.get("role"),
                        "requirement_id": descriptor.get("requirement_id"),
                        "requirement_title": None,
                        "objective": None,
                        "summary": descriptor.get("summary"),
                        "versions": list(version_order) if normalized == "docs/VERSIONS.md" else [],
                    }
                )
            records.sort(
                key=lambda item: (item.get("recorded_at") or "", item.get("sequence") or 0),
                reverse=True,
            )
            artifact_versions = [
                version
                for version in version_order
                if any(version in record.get("versions", []) for record in records)
            ]
            artifact_dates = sorted({record["date"] for record in records if record.get("date")}, reverse=True)
            items.append(
                {
                    "path": normalized,
                    "name": resolved.name,
                    "title": descriptor.get("title") or resolved.name,
                    "summary": descriptor.get("summary"),
                    "role": descriptor.get("role"),
                    "requirement_id": descriptor.get("requirement_id"),
                    "language": language,
                    "kind": "markdown" if language == "markdown" else "code" if language != "text" else "text",
                    "size_bytes": size,
                    "modified_at": modified_at,
                    "latest_recorded_at": records[0].get("recorded_at"),
                    "versions": artifact_versions,
                    "dates": artifact_dates,
                    "records": records,
                    "viewable": size <= MAX_ARTIFACT_BYTES,
                    "reason": None if size <= MAX_ARTIFACT_BYTES else "file-too-large",
                }
            )
        except ObserveError as error:
            items.append(
                {
                    "path": path_value,
                    "name": Path(path_value).name,
                    "title": descriptor.get("title") or Path(path_value).name,
                    "summary": descriptor.get("summary"),
                    "kind": "unknown",
                    "language": "text",
                    "viewable": False,
                    "reason": str(error),
                }
            )
    return items


def read_artifact_content(project: Path, snapshot: dict[str, Any], path_value: str) -> dict[str, Any]:
    resolved, normalized, descriptor = resolve_authorized_artifact(project, snapshot, path_value)
    size = resolved.stat().st_size
    if size > MAX_ARTIFACT_BYTES:
        raise ObserveError(f"Artifact exceeds {MAX_ARTIFACT_BYTES} bytes", 413)
    value = resolved.read_bytes()
    if b"\x00" in value:
        raise ObserveError("Binary artifacts cannot be displayed", 415)
    try:
        content = value.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ObserveError("Artifact is not UTF-8 text", 415) from error
    language = artifact_language(resolved)
    return {
        "path": normalized,
        "name": resolved.name,
        "title": descriptor.get("title") or resolved.name,
        "summary": descriptor.get("summary"),
        "language": language,
        "kind": "markdown" if language == "markdown" else "code" if language != "text" else "text",
        "size_bytes": size,
        "content": content,
        "stages": parse_markdown_stages(content) if language == "markdown" else [],
    }


def run_git(project: Path, arguments: list[str], *, timeout: float = 2.0) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(
        ["git", "-C", str(project), *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=environment,
    )


def _git_worktree_records(project: Path) -> list[dict[str, Any]]:
    result = run_git(project, ["worktree", "list", "--porcelain"])
    if result.returncode != 0:
        return []
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in [*result.stdout.splitlines(), ""]:
        if not line:
            if current.get("path"):
                records.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current["path"] = value
        elif key == "HEAD":
            current["head_full"] = value
            current["head"] = value[:7]
        elif key == "branch":
            current["branch"] = value.removeprefix("refs/heads/")
        elif key == "detached":
            current["detached"] = True
        elif key in {"locked", "prunable"}:
            current[key] = value or True
    return records


def _git_repository_identity(project: Path, worktrees: list[dict[str, Any]]) -> tuple[str, str | None]:
    common_result = run_git(project, ["rev-parse", "--git-common-dir"])
    if common_result.returncode != 0 or not common_result.stdout.strip():
        canonical = project.resolve()
    else:
        common_value = Path(common_result.stdout.strip()).expanduser()
        canonical = common_value.resolve() if common_value.is_absolute() else (project / common_value).resolve()
    repository_id = f"repository-{hashlib.sha256(str(canonical).encode()).hexdigest()[:12]}"
    repository_path = worktrees[0].get("path") if worktrees else None
    return repository_id, repository_path


def git_workspace_snapshot(project: Path) -> dict[str, Any]:
    try:
        inside = run_git(project, ["rev-parse", "--is-inside-work-tree"])
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"available": False, "reason": "git-unavailable", "branches": [], "tags": []}
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return {"available": False, "reason": "not-a-git-project", "branches": [], "tags": []}

    project = project.resolve()
    branch = run_git(project, ["branch", "--show-current"]).stdout.strip() or None
    head_parts = run_git(project, ["show", "-s", "--format=%h%x1f%s", "HEAD"]).stdout.strip().split("\x1f", 1)
    status_lines = [line for line in run_git(project, ["status", "--porcelain=v1"]).stdout.splitlines() if line]
    worktrees = _git_worktree_records(project)
    for worktree in worktrees:
        worktree_path = Path(str(worktree["path"])).resolve()
        worktree["path"] = str(worktree_path)
        worktree["current"] = worktree_path == project
        worktree["primary"] = worktree is worktrees[0]
        if not worktree_path.is_dir():
            worktree.update({"available": False, "clean": None, "dirty_count": None})
            continue
        try:
            worktree_status = [
                line for line in run_git(worktree_path, ["status", "--porcelain=v1"]).stdout.splitlines() if line
            ]
            subject_result = run_git(worktree_path, ["show", "-s", "--format=%s", "HEAD"])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            worktree.update({"available": False, "clean": None, "dirty_count": None})
            continue
        worktree.update(
            {
                "available": True,
                "clean": not worktree_status,
                "dirty_count": len(worktree_status),
                "head_subject": subject_result.stdout.strip() if subject_result.returncode == 0 else None,
            }
        )
    repository_id, repository_path = _git_repository_identity(project, worktrees)
    checked_out_by_branch: dict[str, list[str]] = {}
    for worktree in worktrees:
        if worktree.get("branch"):
            checked_out_by_branch.setdefault(worktree["branch"], []).append(worktree["path"])
    branches: list[dict[str, Any]] = []
    branch_output = run_git(
        project,
        [
            "for-each-ref",
            "--format=%(refname:short)%09%(HEAD)%09%(upstream:short)%09%(upstream:trackshort)%09%(objectname:short)%09%(contents:subject)",
            "refs/heads",
        ],
    )
    for line in branch_output.stdout.splitlines():
        parts = line.split("\t", 5)
        if len(parts) != 6:
            continue
        name, head_marker, upstream, tracking, sha, subject = parts
        branches.append(
            {
                "name": name,
                "current": head_marker == "*",
                "upstream": upstream or None,
                "tracking": tracking or None,
                "sha": sha,
                "subject": subject,
                "checked_out_in": checked_out_by_branch.get(name, []),
            }
        )
    tags = [line for line in run_git(project, ["tag", "--sort=-version:refname"]).stdout.splitlines() if line]
    return {
        "available": True,
        "repository_id": repository_id,
        "repository_path": repository_path,
        "current_branch": branch,
        "detached": branch is None,
        "head": head_parts[0] if head_parts else None,
        "head_subject": head_parts[1] if len(head_parts) > 1 else None,
        "clean": not status_lines,
        "dirty_count": len(status_lines),
        "worktrees": worktrees,
        "branches": branches,
        "tags": tags,
    }


def parse_versions_markdown(value: str) -> list[dict[str, Any]]:
    headings = list(VERSION_HEADING_RE.finditer(value))
    items: list[dict[str, Any]] = []
    field_names = {
        "status": "status", "状态": "status", "branch": "branch", "分支": "branch",
        "work branches": "work_branches", "工作分支": "work_branches",
        "tag": "tag", "标签": "tag", "goal": "goal", "目标": "goal",
    }
    status_names = {
        "released": "released", "已发布": "released", "in_progress": "in_progress",
        "active": "in_progress", "开发中": "in_progress", "planned": "planned", "计划中": "planned",
        "completed": "completed", "delivered": "completed", "已交付": "completed",
        "paused": "paused", "已暂停": "paused",
    }
    for index, heading in enumerate(headings):
        section_end = headings[index + 1].start() if index + 1 < len(headings) else len(value)
        section = value[heading.end():section_end]
        item: dict[str, Any] = {"version": heading.group(1), "status": "planned", "requirements": []}
        for match in VERSION_FIELD_RE.finditer(section):
            key = field_names[match.group(1).lower()]
            field_value = match.group(2).strip()
            if key == "status":
                item[key] = status_names.get(field_value.lower(), field_value)
            elif key == "work_branches":
                item[key] = [part.strip() for part in re.split(r"[,，]", field_value) if part.strip()]
            else:
                item[key] = field_value
        requirements_section = section.split("### Requirements", 1)
        requirement_value = requirements_section[1] if len(requirements_section) == 2 else section
        for match in VERSION_REQUIREMENT_RE.finditer(requirement_value):
            marker, requirement_id, title = match.groups()
            item["requirements"].append(
                {
                    "requirement_id": requirement_id,
                    "title": title.strip(),
                    "status": "completed" if marker == "x" else "skipped" if marker == "~" else "planned",
                }
            )
        items.append(item)
    return items


def version_sort_key(value: Any) -> tuple[Any, ...]:
    """Sort dotted versions newest-first without treating 0.10 as older than 0.9."""
    raw = str(value or "").strip().lstrip("vV")
    base, separator, prerelease = raw.partition("-")
    numbers = tuple(int(part) for part in re.findall(r"\d+", base))[:6]
    padded = numbers + (0,) * (6 - len(numbers))
    return (*padded, 1 if not separator else 0, prerelease.lower())


def version_plan_snapshot(project: Path, snapshot: dict[str, Any], git: dict[str, Any]) -> dict[str, Any]:
    source = project / "docs" / "VERSIONS.md"
    planned = parse_versions_markdown(source.read_text(encoding="utf-8")) if source.is_file() else []
    branch_names = {item.get("name") for item in git.get("branches", [])}
    checked_out_branches = {item.get("branch") for item in git.get("worktrees", []) if item.get("branch")}
    tags = set(git.get("tags", []))
    referenced: set[str] = set()
    for version in planned:
        version.setdefault("work_branches", [])
        version["branch_exists"] = bool(version.get("branch") and version["branch"] in branch_names)
        version["work_branch_states"] = [
            {
                "name": branch_name,
                "exists": branch_name in branch_names,
                "checked_out": branch_name in checked_out_branches,
            }
            for branch_name in version["work_branches"]
        ]
        version["checked_out_work_branches"] = [
            branch_name for branch_name in version["work_branches"] if branch_name in checked_out_branches
        ]
        version["tag_exists"] = bool(version.get("tag") and version["tag"] in tags)
        version["is_current_branch"] = bool(version.get("branch") and version["branch"] == git.get("current_branch"))
        version["is_current_work_branch"] = git.get("current_branch") in version["work_branches"]
        version["branch_mismatch"] = bool(
            version.get("status") == "in_progress"
            and version.get("branch")
            and git.get("current_branch")
            and version["branch"] != git["current_branch"]
            and git["current_branch"] not in version["work_branches"]
        )
        for requirement in version["requirements"]:
            requirement_id = requirement.get("requirement_id")
            if requirement_id:
                referenced.add(requirement_id)
                task = snapshot.get("tasks", {}).get(requirement_id)
                if task and task.get("status") != "abandoned":
                    requirement["observed_status"] = task.get("status")
    planned.sort(key=lambda item: version_sort_key(item.get("version")), reverse=True)
    unassigned = [
        {"requirement_id": task_id, "title": task.get("title"), "status": task.get("status")}
        for task_id, task in snapshot.get("tasks", {}).items()
        if task.get("status") != "abandoned" and task_id not in referenced
    ]
    return {
        "source": "docs/VERSIONS.md" if source.is_file() else None,
        "items": planned,
        "unassigned_requirements": unassigned,
    }


def evidence_reference_label(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("label") or value.get("ref") or value.get("kind") or "未命名证据")
    return str(value)


def current_version_snapshot(snapshot: dict[str, Any], versions: dict[str, Any]) -> dict[str, Any] | None:
    """Project the active version requirement-by-requirement from matching runtime evidence."""
    version_items = versions.get("items", [])
    current = next((item for item in version_items if item.get("status") == "in_progress"), None)
    if current is None:
        current = next((item for item in version_items if item.get("status") == "planned"), None)
    if current is None and version_items:
        current = version_items[0]
    if current is None:
        return None

    all_rounds = list(snapshot.get("work_rounds", {}).values())
    all_handoffs = list(snapshot.get("handoffs", {}).values())
    all_verifications = list(snapshot.get("verifications", []))
    all_blocks = list(snapshot.get("blocks", {}).values())
    projected: list[dict[str, Any]] = []

    for planned in current.get("requirements", []):
        requirement_id = planned.get("requirement_id")
        rounds = sorted(
            (
                item
                for item in all_rounds
                if (item.get("requirement_id") or item.get("task_id")) == requirement_id
            ),
            key=lambda item: item.get("derived_from_sequence", 0),
        )
        handoffs = sorted(
            (
                item
                for item in all_handoffs
                if (item.get("requirement_id") or item.get("task_id")) == requirement_id
            ),
            key=lambda item: item.get("derived_from_sequence", 0),
        )
        candidate_verifications = sorted(
            (item for item in all_verifications if item.get("task_id") == requirement_id),
            key=lambda item: item.get("derived_from_sequence", 0),
        )
        blocks = sorted(
            (item for item in all_blocks if item.get("task_id") == requirement_id and item.get("active") is True),
            key=lambda item: item.get("derived_from_sequence", 0),
        )
        active_rounds = [item for item in rounds if item.get("status") == "active"]
        latest_round = active_rounds[-1] if active_rounds else rounds[-1] if rounds else None
        latest_handoff = handoffs[-1] if handoffs else None
        waiting_role = office_role(latest_handoff.get("to_role")) if latest_handoff else None
        current_role = (
            office_role(active_rounds[-1].get("role"))
            if active_rounds
            else waiting_role
            if waiting_role
            else office_role(latest_round.get("role"))
            if latest_round
            else None
        )
        observed_status = planned.get("observed_status") or snapshot.get("tasks", {}).get(requirement_id, {}).get("status")

        if blocks:
            effective_status = "blocked"
        elif planned.get("status") == "completed":
            effective_status = "completed"
        elif active_rounds or rounds or observed_status in {"active", "in_progress", "verification_pending"}:
            effective_status = "in_progress"
        else:
            effective_status = "planned"
        if effective_status == "completed":
            current_role = None

        role_entries: dict[str, dict[str, Any]] = {}
        role_order: list[str] = []
        for item in rounds:
            role_id = office_role(item.get("role"))
            if not role_id:
                continue
            if role_id not in role_entries:
                role_order.append(role_id)
            role_entries[role_id] = {
                "role": role_id,
                "status": item.get("status") or "completed",
                "objective": item.get("objective"),
                "summary": item.get("summary"),
                "round_id": item.get("round_id"),
                "sequence": item.get("derived_from_sequence"),
            }
        for handoff in handoffs:
            for field, status in (("from_role", "completed"), ("to_role", "waiting")):
                role_id = office_role(handoff.get(field))
                if not role_id or role_id in role_entries:
                    continue
                role_order.append(role_id)
                role_entries[role_id] = {
                    "role": role_id,
                    "status": status,
                    "objective": None,
                    "summary": handoff.get("summary"),
                    "round_id": handoff.get("round_id"),
                    "sequence": handoff.get("derived_from_sequence"),
                }
        role_path = [role_entries[role_id] for role_id in role_order]

        qa_rounds = [item for item in rounds if office_role(item.get("role")) == "QA"]
        qa_latest = qa_rounds[-1] if qa_rounds else None
        qa_references = list(
            dict.fromkeys(
                evidence_reference_label(reference)
                for item in qa_rounds
                for reference in (item.get("verification_refs") or [])
            )
        )
        verifications = [
            item
            for item in candidate_verifications
            if any(
                reference in {
                    str(item.get("verification_id") or ""),
                    str(item.get("check") or ""),
                    str(item.get("summary") or ""),
                }
                for reference in qa_references
            )
        ]
        verification_evidence = list(
            dict.fromkeys(
                evidence_reference_label(reference)
                for item in verifications
                for reference in (item.get("evidence_refs") or [])
            )
        )
        fallback_qa_evidence = []
        if (
            qa_latest
            and qa_latest.get("status") == "completed"
            and qa_latest.get("summary")
            and not qa_references
            and not verifications
            and not verification_evidence
        ):
            fallback_qa_evidence = [f"QA 回写：{str(qa_latest['summary'])[:300]}"]
        if qa_latest:
            scope = qa_latest.get("objective") or qa_latest.get("summary") or "测试范围未记录"
            test_status = "active" if qa_latest.get("status") == "active" else "completed"
            test_message = "正在独立测试" if test_status == "active" else "独立测试已回写"
            if scope == "测试范围未记录":
                test_message = scope
        else:
            scope = None
            test_status = "not_started"
            test_message = "尚未进入独立测试"
        test_snapshot = {
            "status": test_status,
            "scope": scope,
            "summary": qa_latest.get("summary") if qa_latest else None,
            "message": test_message,
            "verification_refs": qa_references,
            "verifications": [
                {
                    "verification_id": item.get("verification_id"),
                    "result": item.get("result"),
                    "check": item.get("check"),
                    "summary": item.get("summary"),
                    "evidence_refs": [evidence_reference_label(value) for value in (item.get("evidence_refs") or [])],
                }
                for item in verifications
            ],
            "evidence_refs": [*verification_evidence, *fallback_qa_evidence],
            "evidence_count": (
                len(qa_references) + len(verifications) + len(verification_evidence) + len(fallback_qa_evidence)
            ),
        }

        if blocks:
            next_step = f"先处理阻塞：{blocks[-1].get('summary') or blocks[-1].get('reason') or '未记录阻塞说明'}"
        elif effective_status == "completed":
            next_step = "需求已完成"
        elif active_rounds:
            next_step = active_rounds[-1].get("objective") or active_rounds[-1].get("summary") or "继续当前工作"
        elif latest_handoff and office_role(latest_handoff.get("to_role")):
            next_step = f"等待 {office_role(latest_handoff.get('to_role'))} 接手"
        elif rounds:
            next_step = "等待下一角色或完成确认"
        else:
            next_step = "等待开始"

        artifacts = list(
            dict.fromkeys(
                artifact
                for item in rounds
                for artifact in (item.get("artifact_refs") or [])
            )
        )
        projected.append(
            {
                **planned,
                "planned_status": planned.get("status"),
                "observed_status": observed_status,
                "effective_status": effective_status,
                "current_role": current_role,
                "current_work": (
                    {
                        "role": current_role,
                        "status": active_rounds[-1].get("status"),
                        "objective": active_rounds[-1].get("objective"),
                        "summary": active_rounds[-1].get("summary"),
                        "updated_at": active_rounds[-1].get("updated_at"),
                    }
                    if active_rounds
                    else None
                ),
                "role_path": role_path,
                "test": test_snapshot,
                "blocks": blocks,
                "artifacts": artifacts,
                "next_step": next_step,
                "history": [
                    {
                        "round_id": item.get("round_id"),
                        "role": office_role(item.get("role")),
                        "status": item.get("status"),
                        "objective": item.get("objective"),
                        "summary": item.get("summary"),
                        "sequence": item.get("derived_from_sequence"),
                    }
                    for item in reversed(rounds)
                ],
            }
        )

    counts = {
        status: sum(item["effective_status"] == status for item in projected)
        for status in ("completed", "in_progress", "planned", "blocked")
    }
    return {
        "version": current.get("version"),
        "status": current.get("status"),
        "goal": current.get("goal"),
        "branch": current.get("branch"),
        "total": len(projected),
        "counts": counts,
        "requirements": projected,
    }


def project_workspace_snapshot(project: Path, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    if snapshot is None:
        snapshot = status_runtime(project)["snapshot"]
    git = git_workspace_snapshot(project)
    versions = version_plan_snapshot(project, snapshot, git)
    return {
        "project_id": project_id(project),
        "generated_at": now_iso(),
        "project": project_profile_snapshot(project),
        "organization": organization_snapshot(snapshot),
        "artifacts": artifact_metadata(project, snapshot, versions),
        "git": git,
        "versions": versions,
        "current_version": current_version_snapshot(snapshot, versions),
    }


def portfolio_project_record(descriptor: dict[str, Any], *, sync: bool = True) -> dict[str, Any]:
    record = dict(descriptor)
    record.update(
        {
            "stage": "不可用" if descriptor["validation"] != "valid" else "尚未同步",
            "owner_role": "Unknown",
            "run_status": "unavailable" if descriptor["validation"] != "valid" else "observing",
            "summary": {
                "task_total": 0,
                "task_completed": 0,
                "task_blocked": 0,
                "verification_pending": 0,
                "active_blocks": 0,
                "active_agent_sessions": 0,
            },
            "runs": [],
            "recent_work": None,
        }
    )
    if descriptor["validation"] != "valid":
        return record
    project = Path(descriptor["path"])
    try:
        if sync:
            sync_runtime(project)
        status = status_runtime(project)
        index = load_json(runtime_root(project) / "index.json", {}) or {}
        stage, owner_role = snapshot_stage(status["snapshot"])
        record.update(
            {
                "stage": stage,
                "owner_role": owner_role,
                "run_status": status["snapshot"].get("run", {}).get("status", "observing"),
                "summary": status["snapshot"].get("summary", record["summary"]),
                "runs": index.get("runs", []),
                "updated_at": status["snapshot"].get("updated_at"),
                "recent_work": next(
                    iter(
                        sorted(
                            status["snapshot"].get("work_rounds", {}).values(),
                            key=lambda item: item.get("derived_from_sequence", 0),
                            reverse=True,
                        )
                    ),
                    None,
                ),
            }
        )
    except ObserveError as error:
        record.update({"validation": "error", "reason": str(error), "stage": "同步失败", "run_status": "error"})
    return record


def portfolio_snapshot(registry_path: Path | None = None, *, sync: bool = True) -> dict[str, Any]:
    projects = [portfolio_project_record(item, sync=sync) for item in load_registered_projects(registry_path)]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso(),
        "projects": projects,
        "summary": {
            "project_total": len(projects),
            "project_valid": sum(item["validation"] == "valid" for item in projects),
            "project_invalid": sum(item["validation"] != "valid" for item in projects),
            "task_total": sum(item["summary"].get("task_total", 0) for item in projects),
            "task_completed": sum(item["summary"].get("task_completed", 0) for item in projects),
            "active_blocks": sum(item["summary"].get("active_blocks", 0) for item in projects),
            "active_agent_sessions": sum(item["summary"].get("active_agent_sessions", 0) for item in projects),
            "active_harness_commands": sum(item["summary"].get("active_harness_commands", 0) for item in projects),
        },
    }


def skill_status_snapshot(registry_path: Path | None = None) -> dict[str, Any]:
    """Return a read-only Skill inventory without exposing file contents or arbitrary paths."""
    projects = [
        {"project_id": item["project_id"], "name": item["name"], "path": item["path"]}
        for item in load_registered_projects(registry_path)
        if item["validation"] == "valid"
    ]
    harness_root = Path(os.environ.get("MICK_HARNESS_ROOT") or Path(__file__).resolve().parents[1])
    return load_skill_manager().skill_snapshot(
        harness_root=harness_root,
        home=Path.home(),
        projects=projects,
    )


def _agent_manager_report(home: Path | None = None) -> dict[str, Any]:
    script = Path(__file__).resolve().with_name("harness-agent-manager.py")
    command = [sys.executable, str(script), "doctor", "--json", "--quiet"]
    if home is not None:
        command.extend(["--home", str(home)])
    environment = os.environ.copy()
    environment["MICK_HARNESS_ACTIVITY"] = "0"
    result = subprocess.run(command, check=False, capture_output=True, text=True, env=environment)
    if result.returncode != 0:
        raise ObserveError(result.stderr.strip() or "Cannot inspect local Code Agents")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ObserveError(f"Cannot decode Agent inspection: {error}") from error


def agent_status_snapshot(
    registry_path: Path | None = None,
    *,
    manager_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return privacy-safe five-layer Agent status backed by runtime evidence."""
    report = manager_report or _agent_manager_report()
    evidence: dict[str, dict[str, Any]] = {}
    for descriptor in load_registered_projects(registry_path):
        if descriptor["validation"] != "valid":
            continue
        try:
            snapshot = status_runtime(Path(descriptor["path"]))["snapshot"]
        except ObserveError:
            continue
        activity = list(snapshot.get("agent_sessions", {}).values()) + list(snapshot.get("agent_turns", {}).values())
        for item in activity:
            agent_id = AGENT_PLATFORM_IDS.get(str(item.get("platform", "")).lower())
            if not agent_id:
                continue
            bucket = evidence.setdefault(agent_id, {"events": 0, "loaded": 0, "projects": set(), "last_seen_at": None})
            bucket["events"] += 1
            bucket["projects"].add(descriptor["name"])
            if item.get("rule_version") == report.get("harness_version"):
                bucket["loaded"] += 1
            updated_at = item.get("updated_at")
            if updated_at and (bucket["last_seen_at"] is None or updated_at > bucket["last_seen_at"]):
                bucket["last_seen_at"] = updated_at

    agents: list[dict[str, Any]] = []
    for source in report.get("agents", []):
        runtime = evidence.get(source["id"], {"events": 0, "loaded": 0, "projects": set(), "last_seen_at": None})
        injection_status = source.get("injection", {}).get("status", "unverified")
        hook_status = source.get("loading", {}).get("status", "unverified")
        loaded_status = "verified" if runtime["loaded"] else ("configured" if hook_status == "hook_configured" else "unverified")
        layers = {
            "discovered": {"status": "verified" if source.get("detected") else "not_detected"},
            "injected": {
                "status": "verified" if injection_status == "injected" else ("blocked" if injection_status == "conflict" else "unverified")
            },
            "loaded": {"status": loaded_status},
            "execution": {"status": source.get("execution", {}).get("status", "unverified")},
            "feedback": {"status": "verified" if runtime["events"] else "unverified"},
        }
        issues = [
            issue for issue in source.get("issues", [])
            if not (runtime["loaded"] and issue.get("code") == "load-proof-missing")
        ]
        agents.append({
            "id": source["id"],
            "name": source["name"],
            "tier": source["tier"],
            "detected_by": sorted({signal["kind"] for signal in source.get("signals", []) if signal.get("found")}),
            "layers": layers,
            "evidence": {
                "event_count": runtime["events"],
                "load_proof_count": runtime["loaded"],
                "projects": sorted(runtime["projects"]),
                "last_seen_at": runtime["last_seen_at"],
            },
            "issues": [
                {key: issue.get(key) for key in ("code", "severity", "message", "repair")}
                for issue in issues
            ],
            "limitations": source.get("limitations", []),
        })
    return {
        "schema_version": "1",
        "generated_at": now_iso(),
        "harness_version": report.get("harness_version"),
        "agents": agents,
        "summary": {
            "registered": len(agents),
            "detected": sum(agent["layers"]["discovered"]["status"] == "verified" for agent in agents),
            "loaded": sum(agent["layers"]["loaded"]["status"] == "verified" for agent in agents),
            "feedback": sum(agent["layers"]["feedback"]["status"] == "verified" for agent in agents),
        },
    }


def record_agent_activity(
    project: Path,
    *,
    platform: str,
    state: str,
    session_ref: str,
    turn_ref: str | None = None,
) -> int:
    if platform not in {"codex", "claude", "cursor", "other"}:
        raise ObserveError(f"Unsupported agent platform: {platform}", 64)
    allowed_states = {"session_started", "turn_started", "turn_completed", "session_ended"}
    if state not in allowed_states:
        raise ObserveError(f"Unsupported agent activity state: {state}", 64)
    if state.startswith("turn_") and not turn_ref:
        raise ObserveError("Turn activity requires turn_ref", 64)
    envelope = build_agent_envelope(
        project,
        platform=platform,
        state=state,
        session_ref=session_ref,
        turn_ref=turn_ref,
    )
    return ingest_envelope(project, envelope)["appended"]


def submit_agent_activity(
    project: Path,
    *,
    platform: str,
    state: str,
    session_ref: str,
    turn_ref: str | None = None,
) -> dict[str, Any]:
    return submit_envelope(
        project,
        build_agent_envelope(
            project,
            platform=platform,
            state=state,
            session_ref=session_ref,
            turn_ref=turn_ref,
        ),
    )


def record_harness_command_activity(
    project: Path,
    *,
    command: str,
    state: str,
    invocation_ref: str,
    exit_code: int | None = None,
) -> int:
    if state not in {"started", "completed"}:
        raise ObserveError(f"Unsupported Harness command state: {state}", 64)
    if state == "started" and exit_code is not None:
        raise ObserveError("Started Harness command cannot include an exit code", 64)
    if state == "completed" and exit_code is None:
        raise ObserveError("Completed Harness command requires an exit code", 64)
    envelope = build_harness_command_envelope(
        project,
        command=command,
        state=state,
        invocation_ref=invocation_ref,
        exit_code=exit_code,
    )
    return ingest_envelope(project, envelope)["appended"]


def submit_harness_command_activity(
    project: Path,
    *,
    command: str,
    state: str,
    invocation_ref: str,
    exit_code: int | None = None,
) -> dict[str, Any]:
    return submit_envelope(
        project,
        build_harness_command_envelope(
            project,
            command=command,
            state=state,
            invocation_ref=invocation_ref,
            exit_code=exit_code,
        ),
    )


def codex_hook_config(platform: str = "codex") -> dict[str, Any]:
    hook_script = Path(__file__).resolve().with_name("harness-observe-hook.py")
    command = f'python3 "{hook_script}" --platform {platform}'
    handler = {"type": "command", "command": command, "timeout": 3}
    return {
        "description": f"Record redacted {platform} lifecycle activity in Harness projects.",
        "hooks": {
            event: [{"hooks": [dict(handler)]}]
            for event in ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd")
        },
    }


OPERATION_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "action": "harness-update",
        "label": "更新 Harness",
        "description": "拉取已发布版本，刷新所有已登记项目，并恢复唯一的 6425 工作服务。",
        "parameter": None,
        "confirmation": "更新本机 Harness",
    },
    {
        "action": "project-init",
        "label": "注入或升级项目",
        "description": "为一个本机项目挂载当前 Harness 规则并加入全局项目登记。",
        "parameter": "project_path",
        "confirmation": "写入项目规则入口",
    },
    {
        "action": "agent-sync",
        "label": "修复 Agent 接入",
        "description": "重新生成并同步受支持 Code Agent 的全局加载器与 Hook 配置。",
        "parameter": None,
        "confirmation": "同步 Agent 接入配置",
    },
)
OPERATION_BY_ACTION = {item["action"]: item for item in OPERATION_DEFINITIONS}


def operation_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in OPERATION_DEFINITIONS]


def operations_root(state_root: Path | None = None) -> Path:
    return (state_root or default_state_root()) / "operations"


def operation_path(operation_id: str, state_root: Path | None = None) -> Path:
    if not re.fullmatch(r"op_[A-Za-z0-9]{16,40}", operation_id):
        raise ObserveError("Invalid operation id", 400)
    return operations_root(state_root) / f"{operation_id}.json"


def load_operation(operation_id: str, state_root: Path | None = None) -> dict[str, Any]:
    value = load_json(operation_path(operation_id, state_root))
    if not isinstance(value, dict):
        raise ObserveError("Operation not found", 404)
    return value


def public_operation(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if key not in {"confirmation_token", "fingerprint"}
    }


def operation_snapshot(*, state_root: Path | None = None) -> dict[str, Any]:
    root = operations_root(state_root)
    items: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(root.glob("op_*.json"), reverse=True):
            try:
                value = load_json(path)
            except ObserveError:
                continue
            if isinstance(value, dict):
                items.append(public_operation(value))
    active = next((item for item in items if item.get("status") in {"queued", "running"}), None)
    return {
        "schema_version": "1",
        "generated_at": now_iso(),
        "catalog": operation_catalog(),
        "active": active,
        "items": items[:20],
    }


def normalized_operation_parameters(action: str, parameters: dict[str, Any] | None) -> dict[str, Any]:
    if action not in OPERATION_BY_ACTION:
        raise ObserveError(f"Unsupported operation: {action}", 400)
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, dict):
        raise ObserveError("Operation parameters must be an object", 400)
    allowed = {"project_path", "full"} if action == "project-init" else set()
    unknown = set(parameters) - allowed
    if unknown:
        raise ObserveError(f"Unsupported operation parameters: {', '.join(sorted(unknown))}", 400)
    if action != "project-init":
        return {}

    raw_path = parameters.get("project_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ObserveError("Project path is required", 400)
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        raise ObserveError("Project path must be absolute", 400)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ObserveError(f"Project path does not exist: {candidate}", 400) from error
    if not resolved.is_dir():
        raise ObserveError(f"Project path is not a directory: {resolved}", 400)
    full = parameters.get("full", False)
    if not isinstance(full, bool):
        raise ObserveError("Project full mode must be true or false", 400)
    return {"project_path": str(resolved), "full": full}


def operation_preflight(
    action: str,
    parameters: dict[str, Any],
    *,
    harness_root: Path | None = None,
) -> dict[str, Any]:
    configured_root = os.environ.get("MICK_HARNESS_ROOT")
    selected_root = (harness_root or (Path(configured_root) if configured_root else Path(__file__).resolve().parents[1])).resolve()
    definition = OPERATION_BY_ACTION[action]
    can_execute = True
    blockers: list[str] = []
    effects: list[str]
    target: str
    mode: str | None = None
    if action == "harness-update":
        target = str(selected_root)
        effects = ["拉取 main 的最新已发布代码", "刷新已登记项目的规则入口", "重启并确认 6425 服务健康"]
        if not (selected_root / ".git").is_dir():
            can_execute = False
            blockers.append("当前 Harness 不是 Git 安装，不能在线更新")
    elif action == "project-init":
        target_path = Path(parameters["project_path"])
        target = str(target_path)
        already_injected = (target_path / ".harness").exists() or (target_path / "AGENTS.md").is_file()
        mode = "upgrade" if already_injected else "init"
        effects = [
            "刷新项目的 Harness 规则入口" if already_injected else "创建项目的 Harness 规则入口",
            "把项目加入本机全局工作台",
            "保留项目现有业务文件与 Git 历史",
        ]
        if parameters.get("full"):
            effects.append("同时检查 Brain 与扩展配置")
    else:
        target = "本机受支持的 Code Agent"
        effects = ["重新生成 Agent 加载器", "同步受支持的 Hook 配置", "刷新工作台的 Agent 接入诊断"]
        if not (selected_root / "scripts" / "harness-agent-manager.py").is_file():
            can_execute = False
            blockers.append("Agent 管理器不存在")
    return {
        "label": definition["label"],
        "description": definition["description"],
        "confirmation": definition["confirmation"],
        "target": target,
        "mode": mode,
        "effects": effects,
        "blockers": blockers,
        "can_execute": can_execute,
        "recovery": "失败会保留可重试记录；服务更新复用幂等安装与旧配置恢复。",
    }


def prepare_operation(
    action: str,
    parameters: dict[str, Any] | None,
    *,
    state_root: Path | None = None,
    harness_root: Path | None = None,
) -> dict[str, Any]:
    normalized = normalized_operation_parameters(action, parameters)
    fingerprint = sha256_text(json.dumps({"action": action, "parameters": normalized}, sort_keys=True))
    root = operations_root(state_root)
    root.mkdir(parents=True, exist_ok=True)
    for path in sorted(root.glob("op_*.json"), reverse=True):
        value = load_json(path)
        if not isinstance(value, dict) or value.get("fingerprint") != fingerprint:
            continue
        if value.get("status") in {"prepared", "queued", "running"}:
            return {**value, "reused": True}

    preflight = operation_preflight(action, normalized, harness_root=harness_root)
    operation_id = new_id("op")
    value = {
        "operation_id": operation_id,
        "action": action,
        "status": "prepared",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "parameters": normalized,
        "fingerprint": fingerprint,
        "confirmation_token": secrets.token_urlsafe(24),
        "reused": False,
        **preflight,
    }
    atomic_write(operation_path(operation_id, state_root), json_bytes(value))
    append_operation_audit(value, "prepared", state_root=state_root)
    return value


def append_operation_audit(value: dict[str, Any], event: str, *, state_root: Path | None = None) -> None:
    path = operations_root(state_root) / "audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": now_iso(),
        "event": event,
        "operation_id": value.get("operation_id"),
        "action": value.get("action"),
        "status": value.get("status"),
        "target": value.get("target"),
        "exit_code": value.get("exit_code"),
    }
    with path.open("ab") as handle:
        handle.write(json_bytes(entry).replace(b"\n", b"") + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def confirm_operation(
    operation_id: str,
    confirmation_token: str,
    *,
    state_root: Path | None = None,
    spawn_worker: bool = True,
) -> dict[str, Any]:
    value = load_operation(operation_id, state_root)
    if value.get("status") != "prepared":
        raise ObserveError("Operation was already confirmed", 409)
    expected = str(value.get("confirmation_token") or "")
    if not expected or not hmac.compare_digest(str(confirmation_token), expected):
        raise ObserveError("Invalid operation confirmation", 403)
    if not value.get("can_execute"):
        raise ObserveError("Operation preflight is blocked", 409)
    value.pop("confirmation_token", None)
    value["status"] = "queued"
    value["confirmed_at"] = now_iso()
    value["updated_at"] = now_iso()
    atomic_write(operation_path(operation_id, state_root), json_bytes(value))
    append_operation_audit(value, "confirmed", state_root=state_root)
    if spawn_worker:
        environment = os.environ.copy()
        environment["MICK_HARNESS_STATE_DIR"] = str(state_root or default_state_root())
        environment["MICK_HARNESS_STATE_ROOT"] = str(state_root or default_state_root())
        environment["MICK_HARNESS_ACTIVITY"] = "0"
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "operation-worker", operation_id],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
            env=environment,
        )
    return public_operation(value)


@contextlib.contextmanager
def operation_mutex(*, state_root: Path | None = None) -> Iterable[None]:
    path = operations_root(state_root) / "mutation.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and time.time() - path.stat().st_mtime > OPERATION_LOCK_STALE_SECONDS:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ObserveError("Another Harness operation is already running", 409) from error
    try:
        os.write(fd, f"{os.getpid()} {now_iso()}\n".encode("utf-8"))
        os.close(fd)
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


def operation_commands(value: dict[str, Any], *, harness_root: Path | None = None) -> list[list[str]]:
    configured_root = os.environ.get("MICK_HARNESS_ROOT")
    selected_root = (harness_root or (Path(configured_root) if configured_root else Path(__file__).resolve().parents[1])).resolve()
    harness = str(selected_root / "bin" / "harness")
    action = value.get("action")
    if action == "harness-update":
        return [[harness, "update"], [harness, "observe", "service", "restart"]]
    if action == "project-init":
        command = [harness, "init", str(value.get("parameters", {}).get("project_path"))]
        if value.get("parameters", {}).get("full"):
            command.append("--full")
        return [command]
    if action == "agent-sync":
        return [[harness, "agents", "sync", "--quiet"]]
    raise ObserveError(f"Unsupported operation: {action}", 400)


def redacted_operation_error(value: str) -> str:
    compact = " ".join(value.split())[:500]
    compact = re.sub(r"(?i)(token|password|secret|authorization)[=: ]+[^ ]+", r"\1=[redacted]", compact)
    return compact or "操作失败，未返回可读错误。"


def run_operation_worker(
    operation_id: str,
    *,
    state_root: Path | None = None,
    harness_root: Path | None = None,
) -> dict[str, Any]:
    path = operation_path(operation_id, state_root)
    value = load_operation(operation_id, state_root)
    if value.get("status") not in {"queued", "running"}:
        raise ObserveError("Operation is not queued", 409)
    try:
        with operation_mutex(state_root=state_root):
            value["status"] = "running"
            value["started_at"] = now_iso()
            value["updated_at"] = now_iso()
            atomic_write(path, json_bytes(value))
            append_operation_audit(value, "started", state_root=state_root)
            environment = os.environ.copy()
            environment["MICK_HARNESS_ACTIVITY"] = "0"
            for command in operation_commands(value, harness_root=harness_root):
                result = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=900,
                    env=environment,
                )
                if result.returncode != 0:
                    detail = redacted_operation_error(result.stderr or result.stdout)
                    raise ObserveError(detail, result.returncode or 1)
            value["status"] = "succeeded"
            value["exit_code"] = 0
            value["summary"] = f"{value.get('label', 'Harness 操作')}已完成。"
    except (OSError, ObserveError, subprocess.TimeoutExpired) as error:
        value["status"] = "failed"
        value["exit_code"] = getattr(error, "exit_code", 1)
        value["summary"] = redacted_operation_error(str(error))
    value["finished_at"] = now_iso()
    value["updated_at"] = now_iso()
    atomic_write(path, json_bytes(value))
    append_operation_audit(value, "finished", state_root=state_root)
    return public_operation(value)


def safe_run_id(value: str) -> bool:
    return bool(re.fullmatch(r"run_[A-Za-z0-9._-]{8,}", value))


def launch_agent_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"


def build_launch_agent_plist(harness_root: Path, state_root: Path, *, port: int = DEFAULT_PORT) -> dict[str, Any]:
    if port < 1 or port > 65535:
        raise ObserveError(f"Invalid port: {port}", 64)
    observer_dir = state_root / "observer"
    script = harness_root / "scripts" / "harness-observe.py"
    return {
        "Label": SERVICE_LABEL,
        "ProgramArguments": [
            sys.executable,
            str(script),
            "watch",
            "--all",
            "--port",
            str(port),
        ],
        "WorkingDirectory": str(harness_root),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 5,
        "ProcessType": "Background",
        "EnvironmentVariables": {
            "MICK_HARNESS_ROOT": str(harness_root),
            "MICK_HARNESS_STATE_DIR": str(state_root),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        "StandardOutPath": str(observer_dir / "service.log"),
        "StandardErrorPath": str(observer_dir / "service.error.log"),
    }


def installed_service_port(plist_path: Path) -> int:
    try:
        config = plistlib.loads(plist_path.read_bytes())
    except (OSError, plistlib.InvalidFileException) as error:
        raise ObserveError(f"Cannot read Observer LaunchAgent {plist_path}: {error}") from error
    arguments = config.get("ProgramArguments", [])
    try:
        return int(arguments[arguments.index("--port") + 1])
    except (ValueError, IndexError, TypeError) as error:
        raise ObserveError(f"Observer LaunchAgent does not contain a valid --port: {plist_path}") from error


def launchctl_target() -> str:
    return f"gui/{os.getuid()}/{SERVICE_LABEL}"


def launchctl_domain() -> str:
    return f"gui/{os.getuid()}"


def run_launchctl(arguments: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["/bin/launchctl", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or f"exit {result.returncode}"
        raise ObserveError(f"launchctl {' '.join(arguments)} failed: {detail}")
    return result


def launch_agent_loaded() -> bool:
    if sys.platform != "darwin":
        return False
    return run_launchctl(["print", launchctl_target()], check=False).returncode == 0


def observer_health(port: int, *, timeout: float = 0.5) -> dict[str, Any] | None:
    try:
        with urlopen(f"http://127.0.0.1:{port}/healthz", timeout=timeout) as response:
            if response.status != 200:
                return None
            value = json.loads(response.read())
            return value if value.get("service_name") == SERVICE_NAME else None
    except (OSError, URLError, json.JSONDecodeError, TimeoutError):
        return None


def service_status(*, home: Path | None = None, port: int | None = None) -> dict[str, Any]:
    plist_path = launch_agent_path(home)
    selected_port = port
    if selected_port is None and plist_path.is_file():
        with contextlib.suppress(ObserveError):
            selected_port = installed_service_port(plist_path)
    selected_port = selected_port or DEFAULT_PORT
    health = observer_health(selected_port)
    return {
        "service_name": SERVICE_NAME,
        "label": SERVICE_LABEL,
        "installed": plist_path.is_file(),
        "loaded": launch_agent_loaded(),
        "healthy": health is not None,
        "port": selected_port,
        "url": f"http://127.0.0.1:{selected_port}/",
        "plist": str(plist_path),
        "health": health,
    }


def wait_for_observer(port: int, *, timeout: float = 8.0) -> dict[str, Any] | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        health = observer_health(port)
        if health is not None:
            return health
        time.sleep(0.1)
    return None


def restore_previous_service(
    plist_path: Path,
    previous_plist: bytes | None,
    *,
    previous_loaded: bool,
    previous_port: int | None,
    previous_healthy: bool,
) -> str:
    run_launchctl(["bootout", launchctl_target()], check=False)
    if previous_plist is None:
        with contextlib.suppress(FileNotFoundError):
            plist_path.unlink()
        return "removed failed service config; no previous service existed"

    atomic_write(plist_path, previous_plist)
    if not previous_loaded:
        return "restored previous service config; previous service was not loaded"

    run_launchctl(["bootstrap", launchctl_domain(), str(plist_path)])
    run_launchctl(["enable", launchctl_target()], check=False)
    run_launchctl(["kickstart", "-k", launchctl_target()])
    if previous_healthy and (previous_port is None or wait_for_observer(previous_port) is None):
        raise ObserveError("previous service config was restored but did not become healthy")
    return "restored and restarted previous service"


def install_service(*, port: int = DEFAULT_PORT, home: Path | None = None) -> dict[str, Any]:
    if sys.platform != "darwin":
        raise ObserveError("Mick Harness Observer service installation currently requires macOS", 64)
    harness_root = Path(__file__).resolve().parents[1]
    state_root = default_state_root()
    observer_dir = state_root / "observer"
    observer_dir.mkdir(parents=True, exist_ok=True)
    plist_path = launch_agent_path(home)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    config = build_launch_agent_plist(harness_root, state_root, port=port)
    desired_plist = plistlib.dumps(config, fmt=plistlib.FMT_XML, sort_keys=True)
    previous_plist = plist_path.read_bytes() if plist_path.is_file() else None
    previous_loaded = launch_agent_loaded()
    previous_port: int | None = None
    if previous_plist is not None:
        with contextlib.suppress(ObserveError):
            previous_port = installed_service_port(plist_path)
    previous_healthy = bool(previous_port is not None and observer_health(previous_port) is not None)

    if previous_plist == desired_plist:
        if previous_loaded and previous_healthy:
            return service_status(home=home, port=port)
        return start_service(home=home)

    atomic_write(plist_path, desired_plist)
    try:
        if previous_loaded:
            run_launchctl(["bootout", launchctl_target()], check=False)
        run_launchctl(["bootstrap", launchctl_domain(), str(plist_path)])
        run_launchctl(["enable", launchctl_target()], check=False)
        run_launchctl(["kickstart", "-k", launchctl_target()])
        health = wait_for_observer(port)
        if health is None:
            raise ObserveError(f"{SERVICE_NAME} was installed but did not become healthy on 127.0.0.1:{port}")
    except (OSError, ObserveError) as error:
        try:
            rollback = restore_previous_service(
                plist_path,
                previous_plist,
                previous_loaded=previous_loaded,
                previous_port=previous_port,
                previous_healthy=previous_healthy,
            )
        except (OSError, ObserveError) as rollback_error:
            raise ObserveError(f"{error}; rollback failed: {rollback_error}") from error
        raise ObserveError(f"{error}; rollback succeeded: {rollback}") from error
    return service_status(home=home, port=port)


def start_service(*, home: Path | None = None) -> dict[str, Any]:
    plist_path = launch_agent_path(home)
    if not plist_path.is_file():
        raise ObserveError("Observer service is not installed. Run 'harness observe service install' first.", 2)
    port = installed_service_port(plist_path)
    if not launch_agent_loaded():
        run_launchctl(["bootstrap", launchctl_domain(), str(plist_path)])
    run_launchctl(["enable", launchctl_target()], check=False)
    run_launchctl(["kickstart", "-k", launchctl_target()])
    if wait_for_observer(port) is None:
        raise ObserveError(f"{SERVICE_NAME} did not become healthy on 127.0.0.1:{port}")
    return service_status(home=home, port=port)


def stop_service(*, home: Path | None = None) -> dict[str, Any]:
    plist_path = launch_agent_path(home)
    port = installed_service_port(plist_path) if plist_path.is_file() else DEFAULT_PORT
    run_launchctl(["bootout", launchctl_target()], check=False)
    return service_status(home=home, port=port)


def restart_service(*, home: Path | None = None) -> dict[str, Any]:
    stop_service(home=home)
    return start_service(home=home)


def uninstall_service(*, home: Path | None = None) -> dict[str, Any]:
    plist_path = launch_agent_path(home)
    port = installed_service_port(plist_path) if plist_path.is_file() else DEFAULT_PORT
    run_launchctl(["bootout", launchctl_target()], check=False)
    with contextlib.suppress(FileNotFoundError):
        plist_path.unlink()
    return service_status(home=home, port=port)


def service_logs(*, lines: int = 80) -> dict[str, Any]:
    observer_dir = default_state_root() / "observer"
    values: dict[str, Any] = {"directory": str(observer_dir), "logs": {}}
    for name in ("service.log", "service.error.log"):
        path = observer_dir / name
        if path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace").splitlines()
            values["logs"][name] = content[-lines:]
        else:
            values["logs"][name] = []
    return values


def scan_registered_projects(registry_path: Path) -> dict[str, Any]:
    descriptors = load_registered_projects(registry_path)
    errors: list[str] = []
    synced = 0
    for descriptor in descriptors:
        if descriptor["validation"] != "valid":
            continue
        try:
            sync_runtime(Path(descriptor["path"]))
            synced += 1
        except ObserveError as error:
            errors.append(f"{descriptor['name']}: {error}")
    return {
        "project_count": len(descriptors),
        "valid_project_count": sum(item["validation"] == "valid" for item in descriptors),
        "synced_project_count": synced,
        "last_scan_error": "; ".join(errors) if errors else None,
    }


def serve_runtime(
    project: Path | None,
    port: int,
    *,
    registry_path: Path | None = None,
    scan_interval: float = DEFAULT_SCAN_INTERVAL,
) -> None:
    if port < 1 or port > 65535:
        raise ObserveError(f"Invalid port: {port}", 64)
    if scan_interval <= 0:
        raise ObserveError(f"Invalid scan interval: {scan_interval}", 64)
    harness_root = Path(__file__).resolve().parents[1]
    dashboard_path = harness_root / "web" / "observe-dashboard.html"
    if not dashboard_path.is_file():
        raise ObserveError(f"Dashboard asset missing: {dashboard_path}")

    def descriptors() -> list[dict[str, Any]]:
        if registry_path is not None:
            return load_registered_projects(registry_path)
        if project is None:
            return []
        return [
            {
                "project_id": project_id(project),
                "name": project.name,
                "path": str(project),
                "validation": "valid",
                "reason": None,
            }
        ]

    def resolve_api_project(value: str) -> Path | None:
        descriptor = next((item for item in descriptors() if item["project_id"] == value), None)
        if descriptor is None or descriptor["validation"] != "valid":
            return None
        return Path(descriptor["path"])

    started_at = now_iso()
    started_monotonic = time.monotonic()
    ingest_token = ensure_ingest_token()
    action_token = secrets.token_urlsafe(32)
    stop_event = threading.Event()
    service_state_lock = threading.Lock()
    service_state: dict[str, Any] = {
        "last_scan_at": None,
        "last_scan_duration_ms": None,
        "last_scan_error": None,
        "project_count": 1 if project is not None else 0,
        "valid_project_count": 1 if project is not None else 0,
        "synced_project_count": 0,
        "ingest_enabled": True,
        "ingested_event_count": 0,
        "last_ingest_at": None,
    }

    def scan_once() -> None:
        scan_started = time.monotonic()
        try:
            if registry_path is not None:
                result = scan_registered_projects(registry_path)
                replayed = [
                    replay_outbox(Path(item["path"]))
                    for item in load_registered_projects(registry_path)
                    if item["validation"] == "valid"
                ]
                result["outbox_remaining"] = sum(item["remaining"] for item in replayed)
                result["outbox_replayed"] = sum(item["replayed"] for item in replayed)
            elif project is not None:
                sync_runtime(project)
                replayed = replay_outbox(project)
                result = {
                    "project_count": 1,
                    "valid_project_count": 1,
                    "synced_project_count": 1,
                    "last_scan_error": None,
                    "outbox_remaining": replayed["remaining"],
                    "outbox_replayed": replayed["replayed"],
                }
            else:
                result = {
                    "project_count": 0,
                    "valid_project_count": 0,
                    "synced_project_count": 0,
                    "last_scan_error": None,
                }
        except ObserveError as error:
            result = {
                "project_count": service_state.get("project_count", 0),
                "valid_project_count": service_state.get("valid_project_count", 0),
                "synced_project_count": 0,
                "last_scan_error": str(error),
            }
        with service_state_lock:
            service_state.update(result)
            service_state["last_scan_at"] = now_iso()
            service_state["last_scan_duration_ms"] = int((time.monotonic() - scan_started) * 1000)

    def monitor_loop() -> None:
        while not stop_event.wait(scan_interval):
            scan_once()

    def health_payload() -> dict[str, Any]:
        with service_state_lock:
            scan_state = dict(service_state)
        return {
            "status": "degraded" if scan_state.get("last_scan_error") else "ok",
            "service_name": SERVICE_NAME,
            "service_label": SERVICE_LABEL,
            "mode": "portfolio" if registry_path is not None else "project",
            "host": "127.0.0.1",
            "port": port,
            "pid": os.getpid(),
            "started_at": started_at,
            "uptime_seconds": round(time.monotonic() - started_monotonic, 3),
            "scan_interval_seconds": scan_interval,
            **scan_state,
        }

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "MickHarnessObserver/0.4"

        def _send_bytes(self, status: int, content_type: str, value: bytes, *, head_only: bool = False) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(value)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'")
            self.end_headers()
            if not head_only:
                write_http_body(self.wfile, value)

        def _route(self, head_only: bool = False) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                if path in {"/", "/index.html"}:
                    self._send_bytes(200, "text/html; charset=utf-8", dashboard_path.read_bytes(), head_only=head_only)
                    return
                if path == "/healthz":
                    self._send_bytes(
                        200,
                        "application/json",
                        json_bytes(health_payload()),
                        head_only=head_only,
                    )
                    return
                if path == "/api/portfolio.json":
                    value = (
                        portfolio_snapshot(registry_path, sync=False)
                        if registry_path is not None
                        else {
                            "schema_version": SCHEMA_VERSION,
                            "generated_at": now_iso(),
                            "projects": [portfolio_project_record(descriptors()[0])] if descriptors() else [],
                        }
                    )
                    self._send_bytes(200, "application/json", json_bytes(value), head_only=head_only)
                    return
                if path == "/api/agents.json":
                    self._send_bytes(
                        200,
                        "application/json",
                        json_bytes(agent_status_snapshot(registry_path)),
                        head_only=head_only,
                    )
                    return
                if path == SKILLS_STATUS_PATH:
                    if parsed.query:
                        self._send_bytes(
                            400,
                            "application/json",
                            json_bytes({"error": "skill-inventory-does-not-accept-paths"}),
                            head_only=head_only,
                        )
                        return
                    self._send_bytes(
                        200,
                        "application/json",
                        json_bytes(skill_status_snapshot(registry_path)),
                        head_only=head_only,
                    )
                    return
                if path == OPERATIONS_PATH:
                    value = operation_snapshot()
                    value["action_token"] = action_token
                    self._send_bytes(200, "application/json", json_bytes(value), head_only=head_only)
                    return
                operation_status_match = re.fullmatch(r"/api/operations/(op_[A-Za-z0-9]{16,40})\.json", path)
                if operation_status_match:
                    self._send_bytes(
                        200,
                        "application/json",
                        json_bytes(public_operation(load_operation(operation_status_match.group(1)))),
                        head_only=head_only,
                    )
                    return
                if path == BRAIN_STATUS_PATH:
                    value = load_brain_boundary().health_snapshot()
                    value["action_token"] = action_token
                    self._send_bytes(200, "application/json", json_bytes(value), head_only=head_only)
                    return
                if path == BRAIN_CANDIDATES_PATH:
                    value = {"items": load_brain_boundary().list_candidates()}
                    self._send_bytes(200, "application/json", json_bytes(value), head_only=head_only)
                    return
                if path == BRAIN_PROJECT_MEMORY_PATH:
                    query = parse_qs(parsed.query)
                    selected = (query.get("project") or [None])[0]
                    value = {"items": load_brain_boundary().list_project_memories(project=selected)}
                    self._send_bytes(200, "application/json", json_bytes(value), head_only=head_only)
                    return
                if path == HARNESS_IMPROVEMENTS_PATH:
                    value = {"items": load_brain_boundary().list_harness_improvements()}
                    self._send_bytes(200, "application/json", json_bytes(value), head_only=head_only)
                    return
                if path == "/api/index.json" and project is not None and registry_path is None:
                    sync_runtime(project)
                    self._send_bytes(200, "application/json", (runtime_root(project) / "index.json").read_bytes(), head_only=head_only)
                    return
                project_index_match = re.fullmatch(r"/api/projects/([A-Za-z0-9._-]+)/index\.json", path)
                if project_index_match:
                    selected_project = resolve_api_project(project_index_match.group(1))
                    if selected_project is None:
                        self._send_bytes(404, "application/json", json_bytes({"error": "project-not-found"}), head_only=head_only)
                        return
                    if registry_path is None:
                        sync_runtime(selected_project)
                    target = runtime_root(selected_project) / "index.json"
                    self._send_bytes(200, "application/json", target.read_bytes(), head_only=head_only)
                    return
                project_workspace_match = re.fullmatch(r"/api/projects/([A-Za-z0-9._-]+)/workspace\.json", path)
                if project_workspace_match:
                    selected_project = resolve_api_project(project_workspace_match.group(1))
                    if selected_project is None:
                        self._send_bytes(404, "application/json", json_bytes({"error": "project-not-found"}), head_only=head_only)
                        return
                    try:
                        selected_snapshot = status_runtime(selected_project)["snapshot"]
                    except ObserveError:
                        init_runtime(selected_project)
                        selected_snapshot = sync_runtime(selected_project)["snapshot"]
                    self._send_bytes(
                        200,
                        "application/json",
                        json_bytes(project_workspace_snapshot(selected_project, selected_snapshot)),
                        head_only=head_only,
                    )
                    return
                project_artifact_match = re.fullmatch(r"/api/projects/([A-Za-z0-9._-]+)/artifact", path)
                if project_artifact_match:
                    selected_project = resolve_api_project(project_artifact_match.group(1))
                    if selected_project is None:
                        self._send_bytes(404, "application/json", json_bytes({"error": "project-not-found"}), head_only=head_only)
                        return
                    query = parse_qs(parsed.query)
                    path_value = (query.get("path") or [""])[0]
                    if not path_value:
                        self._send_bytes(400, "application/json", json_bytes({"error": "artifact-path-required"}), head_only=head_only)
                        return
                    run_value = (query.get("run") or [""])[0]
                    if run_value:
                        if not safe_run_id(run_value):
                            self._send_bytes(400, "application/json", json_bytes({"error": "invalid-run-id"}), head_only=head_only)
                            return
                        snapshot_path = run_dir(selected_project, run_value) / "snapshot.json"
                        selected_snapshot = load_json(snapshot_path)
                        if selected_snapshot is None:
                            self._send_bytes(404, "application/json", json_bytes({"error": "run-not-found"}), head_only=head_only)
                            return
                    else:
                        selected_snapshot = status_runtime(selected_project)["snapshot"]
                    self._send_bytes(
                        200,
                        "application/json",
                        json_bytes(read_artifact_content(selected_project, selected_snapshot, path_value)),
                        head_only=head_only,
                    )
                    return
                project_run_match = re.fullmatch(
                    r"/api/projects/([A-Za-z0-9._-]+)/runs/(run_[A-Za-z0-9._-]+)/(?P<name>snapshot\.json|events\.jsonl)",
                    path,
                )
                if project_run_match and safe_run_id(project_run_match.group(2)):
                    selected_project = resolve_api_project(project_run_match.group(1))
                    if selected_project is None:
                        self._send_bytes(404, "application/json", json_bytes({"error": "project-not-found"}), head_only=head_only)
                        return
                    target = run_dir(selected_project, project_run_match.group(2)) / project_run_match.group("name")
                    if not target.is_file():
                        self._send_bytes(404, "application/json", json_bytes({"error": "not-found"}), head_only=head_only)
                        return
                    content_type = "application/json" if target.name.endswith(".json") else "application/x-ndjson"
                    self._send_bytes(200, content_type, target.read_bytes(), head_only=head_only)
                    return
                legacy_run_match = re.fullmatch(r"/api/runs/(run_[A-Za-z0-9._-]+)/(?P<name>snapshot\.json|events\.jsonl)", path)
                if legacy_run_match and project is not None and registry_path is None and safe_run_id(legacy_run_match.group(1)):
                    target = run_dir(project, legacy_run_match.group(1)) / legacy_run_match.group("name")
                    if not target.is_file():
                        self._send_bytes(404, "application/json", json_bytes({"error": "not-found"}), head_only=head_only)
                        return
                    content_type = "application/json" if target.name.endswith(".json") else "application/x-ndjson"
                    self._send_bytes(200, content_type, target.read_bytes(), head_only=head_only)
                    return
                if path == "/api/query":
                    query = parse_qs(parsed.query)
                    self._send_bytes(200, "application/json", json_bytes({"query": query}), head_only=head_only)
                    return
                self._send_bytes(404, "application/json", json_bytes({"error": "not-found"}), head_only=head_only)
            except ObserveError as error:
                status = error.exit_code if error.exit_code in {400, 403, 404, 409, 413, 415, 422} else 500
                self._send_bytes(status, "application/json", json_bytes({"error": str(error)}), head_only=head_only)

        def do_GET(self) -> None:  # noqa: N802
            self._route(False)

        def do_HEAD(self) -> None:  # noqa: N802
            self._route(True)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            project_unregister = re.fullmatch(
                r"/api/projects/([A-Za-z0-9._-]+)/unregister", parsed.path
            )
            if project_unregister:
                supplied_action_token = self.headers.get("X-Harness-Action-Token", "")
                if not supplied_action_token or not hmac.compare_digest(supplied_action_token, action_token):
                    self._send_bytes(401, "application/json", json_bytes({"error": "unauthorized-action"}))
                    return
                if registry_path is None:
                    self._send_bytes(409, "application/json", json_bytes({"error": "portfolio-registry-required"}))
                    return
                content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if content_type != "application/json":
                    self._send_bytes(415, "application/json", json_bytes({"error": "content-type-must-be-application-json"}))
                    return
                try:
                    content_length = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(content_length).decode("utf-8")) if content_length else {}
                    if not isinstance(body, dict) or body.get("confirmed") is not True:
                        raise ObserveError("Project removal requires explicit confirmation", 400)
                    result = unregister_project(project_unregister.group(1), registry_path)
                    scan_once()
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                    self._send_bytes(400, "application/json", json_bytes({"error": "invalid-json"}))
                    return
                except ObserveError as error:
                    status = error.exit_code if error.exit_code in {400, 403, 404, 409, 413, 415, 422} else 500
                    self._send_bytes(status, "application/json", json_bytes({"error": str(error)}))
                    return
                self._send_bytes(200, "application/json", json_bytes(result))
                return
            operation_execute = re.fullmatch(r"/api/operations/(op_[A-Za-z0-9]{16,40})/execute", parsed.path)
            operation_action = parsed.path == OPERATION_PREVIEW_PATH or operation_execute is not None
            if operation_action:
                supplied_action_token = self.headers.get("X-Harness-Action-Token", "")
                if not supplied_action_token or not hmac.compare_digest(supplied_action_token, action_token):
                    self._send_bytes(401, "application/json", json_bytes({"error": "unauthorized-action"}))
                    return
                content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if content_type != "application/json":
                    self._send_bytes(415, "application/json", json_bytes({"error": "content-type-must-be-application-json"}))
                    return
                try:
                    content_length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self._send_bytes(400, "application/json", json_bytes({"error": "invalid-content-length"}))
                    return
                if content_length > MAX_OPERATION_BODY:
                    self._send_bytes(413, "application/json", json_bytes({"error": "body-too-large"}))
                    return
                try:
                    body = json.loads(self.rfile.read(content_length).decode("utf-8")) if content_length else {}
                    if not isinstance(body, dict):
                        raise ObserveError("Operation body must be an object", 400)
                    if parsed.path == OPERATION_PREVIEW_PATH:
                        result = prepare_operation(str(body.get("action") or ""), body.get("parameters"))
                    else:
                        result = confirm_operation(
                            operation_execute.group(1),
                            str(body.get("confirmation_token") or ""),
                        )
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._send_bytes(400, "application/json", json_bytes({"error": "invalid-json"}))
                    return
                except ObserveError as error:
                    status = error.exit_code if error.exit_code in {400, 403, 404, 409, 413, 415, 422} else 500
                    self._send_bytes(status, "application/json", json_bytes({"error": str(error)}))
                    return
                self._send_bytes(200, "application/json", json_bytes(result))
                return
            brain_candidate_action = re.fullmatch(
                r"/api/brain/candidates/(memory_[a-f0-9]{20})/(approve|reject|retry|update|merge|ignore-similar)", parsed.path
            )
            project_memory_action = re.fullmatch(
                r"/api/brain/project-memory/(project_memory_[a-f0-9]{20})/(correct|undo|promote)", parsed.path
            )
            project_memory_merge_action = parsed.path == "/api/brain/project-memory/merge"
            brain_sync_action = parsed.path == BRAIN_SYNC_PATH
            harness_improvement_create = parsed.path == "/api/harness/improvements"
            harness_improvement_action = re.fullmatch(
                r"/api/harness/improvements/(improvement_[a-f0-9]{20})/(update|merge|submit|approve|reject|mark-implemented|verify-effect)",
                parsed.path,
            )
            if (
                brain_candidate_action or project_memory_action or project_memory_merge_action or brain_sync_action
                or harness_improvement_create or harness_improvement_action
            ):
                supplied_action_token = self.headers.get("X-Harness-Action-Token", "")
                if not supplied_action_token or not hmac.compare_digest(supplied_action_token, action_token):
                    self._send_bytes(401, "application/json", json_bytes({"error": "unauthorized-action"}))
                    return
                content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if content_type != "application/json":
                    self._send_bytes(415, "application/json", json_bytes({"error": "content-type-must-be-application-json"}))
                    return
                try:
                    content_length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self._send_bytes(400, "application/json", json_bytes({"error": "invalid-content-length"}))
                    return
                if content_length < 0:
                    self._send_bytes(400, "application/json", json_bytes({"error": "invalid-content-length"}))
                    return
                if content_length > MAX_OPERATION_BODY:
                    self._send_bytes(413, "application/json", json_bytes({"error": "body-too-large"}))
                    return
                try:
                    body = json.loads(self.rfile.read(content_length).decode("utf-8")) if content_length else {}
                    if not isinstance(body, dict):
                        raise ValueError("body-must-be-object")
                    brain = load_brain_boundary()
                    if harness_improvement_create:
                        result = brain.create_harness_improvement(
                            str(body.get("memory_id") or ""),
                            target=str(body.get("target") or ""),
                            summary=body.get("summary"),
                        )
                    elif harness_improvement_action:
                        identifier, action = harness_improvement_action.groups()
                        if action == "update":
                            result = brain.update_harness_improvement(
                                identifier, target=body.get("target"), summary=body.get("summary")
                            )
                        elif action == "merge":
                            duplicate_ids = body.get("improvement_ids")
                            if not isinstance(duplicate_ids, list) or not all(isinstance(value, str) for value in duplicate_ids):
                                raise ValueError("improvement_ids-must-be-string-list")
                            result = brain.merge_harness_improvements(
                                identifier, duplicate_ids, summary=body.get("summary")
                            )
                        elif action == "submit":
                            result = brain.submit_harness_improvement(
                                identifier, force=body.get("confirmed") is True
                            )
                        elif action == "approve":
                            result = brain.approve_harness_improvement(identifier)
                        elif action == "reject":
                            result = brain.reject_harness_improvement(identifier, reason=body.get("reason"))
                        elif action == "mark-implemented":
                            result = brain.mark_harness_improvement_implemented(
                                identifier,
                                artifact_path=str(body.get("artifact_path") or ""),
                                baseline_count=body.get("baseline_count"),
                            )
                        else:
                            result = brain.verify_harness_improvement_effect(
                                identifier,
                                result=str(body.get("result") or ""),
                                current_count=body.get("current_count"),
                                note=str(body.get("note") or ""),
                            )
                    elif brain_sync_action:
                        result = brain.sync_pending(
                            confirmed=body.get("confirmed") is True,
                            dry_run=body.get("dry_run") is True,
                        )
                    elif project_memory_merge_action:
                        memory_ids = body.get("memory_ids")
                        if not isinstance(memory_ids, list) or not all(isinstance(value, str) for value in memory_ids):
                            raise ValueError("memory_ids-must-be-string-list")
                        result = brain.merge_project_memories(memory_ids, summary=str(body.get("summary") or ""))
                    elif brain_candidate_action:
                        identifier, action = brain_candidate_action.groups()
                        if action == "approve":
                            if body.get("summary") is not None or body.get("layer") is not None or body.get("profile") is not None:
                                brain.update_candidate(
                                    identifier, summary=body.get("summary"), layer=body.get("layer"), profile=body.get("profile")
                                )
                            result = brain.approve(identifier, yes=True, dry_run=False)
                        elif action == "reject":
                            result = brain.reject(identifier, reason=body.get("reason"))
                        elif action == "retry":
                            result = brain.retry(identifier)
                        elif action == "update":
                            result = brain.update_candidate(
                                identifier, summary=body.get("summary"), layer=body.get("layer"), profile=body.get("profile")
                            )
                        elif action == "merge":
                            duplicate_ids = body.get("candidate_ids")
                            if not isinstance(duplicate_ids, list) or not all(isinstance(value, str) for value in duplicate_ids):
                                raise ValueError("candidate_ids-must-be-string-list")
                            result = brain.merge_candidates(
                                identifier, duplicate_ids, summary=body.get("summary"),
                                layer=body.get("layer"), profile=body.get("profile"),
                            )
                        else:
                            result = brain.ignore_similar_candidates(identifier)
                    else:
                        identifier, action = project_memory_action.groups()
                        if action == "correct":
                            result = brain.correct_project_memory(identifier, summary=str(body.get("summary") or ""))
                        elif action == "undo":
                            result = brain.undo_project_memory(identifier)
                        else:
                            result = brain.promote_project_memory(identifier)
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
                    self._send_bytes(400, "application/json", json_bytes({"error": str(error)}))
                    return
                except Exception as error:
                    self._send_bytes(422, "application/json", json_bytes({"error": str(error)[:500]}))
                    return
                self._send_bytes(200, "application/json", json_bytes(result))
                return
            if parsed.path != INGEST_PATH:
                self._method_not_allowed()
                return
            authorization = self.headers.get("Authorization", "")
            supplied_token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
            if not supplied_token or not hmac.compare_digest(supplied_token, ingest_token):
                self._send_bytes(401, "application/json", json_bytes({"error": "unauthorized"}))
                return
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                self._send_bytes(415, "application/json", json_bytes({"error": "content-type-must-be-application-json"}))
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_bytes(400, "application/json", json_bytes({"error": "invalid-content-length"}))
                return
            if content_length < 1:
                self._send_bytes(400, "application/json", json_bytes({"error": "empty-body"}))
                return
            if content_length > MAX_INGEST_BODY:
                self._send_bytes(413, "application/json", json_bytes({"error": "body-too-large"}))
                return
            try:
                envelope = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_bytes(400, "application/json", json_bytes({"error": "invalid-json"}))
                return
            if not isinstance(envelope, dict):
                self._send_bytes(422, "application/json", json_bytes({"error": "body-must-be-object"}))
                return
            selected_project = resolve_api_project(str(envelope.get("project_id", "")))
            if selected_project is None:
                self._send_bytes(404, "application/json", json_bytes({"error": "project-not-found"}))
                return
            try:
                result = ingest_envelope(selected_project, envelope)
            except ObserveError as error:
                self._send_bytes(422, "application/json", json_bytes({"error": str(error)}))
                return
            with service_state_lock:
                service_state["ingested_event_count"] += result["appended"]
                service_state["last_ingest_at"] = now_iso()
            self._send_bytes(200, "application/json", json_bytes(result))

        def _method_not_allowed(self) -> None:
            self._send_bytes(405, "application/json", json_bytes({"error": "method-not-allowed"}))

        do_PUT = _method_not_allowed
        do_PATCH = _method_not_allowed
        do_DELETE = _method_not_allowed

        def log_message(self, format_string: str, *args: Any) -> None:
            print(f"observe: {self.address_string()} - {format_string % args}", file=sys.stderr)

    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as error:
        raise ObserveError(f"Cannot bind 127.0.0.1:{port}: {error}") from error
    server.daemon_threads = True
    scan_once()
    monitor_thread = threading.Thread(target=monitor_loop, name="harness-observer-monitor", daemon=True)
    monitor_thread.start()
    print(f"{SERVICE_NAME}: http://127.0.0.1:{port}/")
    print("Local work server; press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        monitor_thread.join(timeout=max(1.0, scan_interval + 0.5))
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness observe", description="Observe Harness workflow state without mutating it.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "sync", "status", "replay"):
        child = subparsers.add_parser(command)
        child.add_argument("project", nargs="?", help="Project directory (default: current directory)")
    watch = subparsers.add_parser("watch")
    watch.add_argument("project", nargs="?", help="Project directory (default: current directory)")
    watch.add_argument("--port", type=int, default=DEFAULT_PORT)
    watch.add_argument("--all", action="store_true", dest="all_projects", help="Observe all projects in the Harness registry")
    watch.add_argument("--scan-interval", type=float, default=DEFAULT_SCAN_INTERVAL, help="Background scan interval in seconds")
    service = subparsers.add_parser("service", help=f"Manage the {SERVICE_NAME} background service")
    service.add_argument("action", choices=("install", "start", "stop", "restart", "status", "logs", "uninstall"))
    service.add_argument("--port", type=int, help=f"Service port for install (default: {DEFAULT_PORT})")
    service.add_argument("--lines", type=int, default=80, help="Number of log lines to show")
    activity = subparsers.add_parser("activity", help=argparse.SUPPRESS)
    activity.add_argument("--project", required=True)
    activity.add_argument("--command", dest="activity_command", required=True)
    activity.add_argument("--state", required=True, choices=("started", "completed"))
    activity.add_argument("--invocation", required=True)
    activity.add_argument("--exit-code", type=int)
    operation_worker = subparsers.add_parser("operation-worker", help=argparse.SUPPRESS)
    operation_worker.add_argument("operation_id")
    emit = subparsers.add_parser("emit", help="Write a structured Agent work event to the local Harness server")
    emit.add_argument("event_type", choices=("work.round_started", "work.round_completed", "decision.recorded", "handoff.created"))
    emit.add_argument("--project", default=os.getcwd(), help="Injected project directory (default: current directory)")
    emit.add_argument("--ref", required=True, help="Stable round, decision, or handoff reference")
    emit.add_argument("--idempotency-key", help="Stable retry key (default: event type + ref)")
    emit.add_argument("--role", choices=sorted(ROLES))
    emit.add_argument("--objective")
    emit.add_argument("--summary")
    emit.add_argument("--status")
    emit.add_argument("--requirement", dest="requirement_id")
    emit.add_argument("--next-role", choices=sorted(ROLES))
    emit.add_argument("--blocker")
    emit.add_argument("--title")
    emit.add_argument("--rationale")
    emit.add_argument("--from-role", choices=sorted(ROLES))
    emit.add_argument("--to-role", choices=sorted(ROLES))
    emit.add_argument("--round", dest="round_ref")
    emit.add_argument("--artifact", dest="artifact_refs", action="append", default=[], help="Project-relative deliverable path (repeatable)")
    hook_config = subparsers.add_parser("hook-config")
    hook_config.add_argument("platform", choices=("codex", "claude"), help="Agent platform to configure")
    return parser


def print_status(result: dict[str, Any]) -> None:
    run = result["run"]
    snapshot = result["snapshot"]
    summary = snapshot.get("summary", {})
    workflows = list(snapshot.get("workflows", {}).values())
    stage = workflows[-1].get("to") if workflows else "unknown"
    print("Company Runtime V0")
    print(f"  Run       : {run['run_id']}")
    print(f"  Status    : {snapshot['run'].get('status', 'observing')}")
    print(f"  Stage     : {stage}")
    print(f"  Tasks     : {summary.get('task_completed', 0)}/{summary.get('task_total', 0)} completed")
    print(f"  Blocked   : {summary.get('active_blocks', 0)}")
    print(f"  Unverified: {summary.get('verification_pending', 0)}")
    print(f"  Sequence  : {snapshot.get('last_sequence', 0)}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "operation-worker":
            value = run_operation_worker(args.operation_id)
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return 0 if value.get("status") == "succeeded" else 1
        if args.command == "hook-config":
            print(json.dumps(codex_hook_config(args.platform), ensure_ascii=False, indent=2))
            return 0
        if args.command == "service":
            if args.action == "install":
                value = install_service(port=args.port or DEFAULT_PORT)
            elif args.action == "start":
                value = start_service()
            elif args.action == "stop":
                value = stop_service()
            elif args.action == "restart":
                value = restart_service()
            elif args.action == "uninstall":
                value = uninstall_service()
            elif args.action == "logs":
                value = service_logs(lines=max(1, args.lines))
            else:
                value = service_status(port=args.port)
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return 0 if args.action != "status" or value.get("healthy") else 2
        if args.command == "activity":
            project = resolve_project(args.project)
            if not has_harness_entry(project):
                return 0
            submit_harness_command_activity(
                project,
                command=args.activity_command,
                state=args.state,
                invocation_ref=args.invocation,
                exit_code=args.exit_code,
            )
            return 0
        if args.command == "emit":
            project = resolve_project(args.project)
            if not has_harness_entry(project):
                raise ObserveError("Project does not contain an injected Harness entry", 64)
            idempotency_key = args.idempotency_key or f"emit:{args.event_type}:{args.ref}"
            if args.event_type in {"work.round_started", "work.round_completed"}:
                if not args.role or not args.objective:
                    raise ObserveError("Work round emit requires --role and --objective", 64)
                envelope = build_work_envelope(
                    project,
                    event_type=args.event_type,
                    role=args.role,
                    round_ref=args.ref,
                    requirement_id=args.requirement_id,
                    objective=args.objective,
                    summary=args.summary,
                    status=args.status or ("active" if args.event_type == "work.round_started" else "completed"),
                    next_role=args.next_role,
                    blocker=args.blocker,
                    artifact_refs=args.artifact_refs,
                    idempotency_key=idempotency_key,
                )
            elif args.event_type == "decision.recorded":
                if not args.role or not args.title or not args.summary:
                    raise ObserveError("Decision emit requires --role, --title and --summary", 64)
                envelope = build_decision_envelope(
                    project,
                    decision_ref=args.ref,
                    role=args.role,
                    title=args.title,
                    summary=args.summary,
                    rationale=args.rationale,
                    requirement_id=args.requirement_id,
                    status=args.status or "accepted",
                    idempotency_key=idempotency_key,
                )
            else:
                if not args.from_role or not args.to_role or not args.summary:
                    raise ObserveError("Handoff emit requires --from-role, --to-role and --summary", 64)
                envelope = build_handoff_envelope(
                    project,
                    handoff_ref=args.ref,
                    from_role=args.from_role,
                    to_role=args.to_role,
                    summary=args.summary,
                    status=args.status or "pending",
                    requirement_id=args.requirement_id,
                    round_ref=args.round_ref,
                    idempotency_key=idempotency_key,
                )
            result = submit_envelope(project, envelope)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "watch" and args.all_projects:
            if args.project:
                raise ObserveError("Do not pass a project directory together with --all", 64)
            serve_runtime(None, args.port, registry_path=default_registry_path(), scan_interval=args.scan_interval)
            return 0
        project = resolve_project(args.project)
        if args.command == "init":
            init_runtime(project)
            summary = sync_runtime(project)
            print(f"Observed run {summary['run_id']}: {summary['appended']} event(s) appended")
            return 2 if summary.get("warning") else 0
        if args.command == "sync":
            summary = sync_runtime(project)
            print(f"Observed run {summary['run_id']}: {summary['appended']} event(s) appended from {summary['sources']} source(s)")
            return 2 if summary.get("warning") else 0
        if args.command == "status":
            print_status(status_runtime(project))
            return 0
        if args.command == "replay":
            summary = replay_runtime(project)
            print(f"Replayed {summary['run_id']}: snapshot digest {summary['after_digest']} (changed={str(summary['changed']).lower()})")
            return 0
        if args.command == "watch":
            serve_runtime(project, args.port, scan_interval=args.scan_interval)
            return 0
    except ObserveError as error:
        print(f"observe error: {error}", file=sys.stderr)
        return error.exit_code
    return 64


if __name__ == "__main__":
    raise SystemExit(main())

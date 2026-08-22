#!/usr/bin/env python3
"""Local-first Brain boundary for Harness events and approved global memory.

Project facts are written automatically after a structured Harness event proves
they are confirmed. Global preferences and versioned Profiles remain candidates
until the user approves them. Private text never enters a project event ledger.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any


SECRET_PATTERNS = (
    re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_A-Za-z0-9]{12,}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
)
KINDS = {
    "artifact", "decision", "gotcha", "handoff", "preference", "profile",
    "requirement", "result", "stage", "verification", "env",
}
LAYERS = {"session", "project", "global", "profile"}
PENDING_STATUSES = {"pending_confirmation", "write_failed", "sync_failed"}
HARNESS_IMPROVEMENT_TARGETS = {"rule", "skill", "checker", "profile"}
CONFIRMED_EVENT_TYPES = {
    "work.round_completed", "decision.recorded", "handoff.created",
    "artifact.observed", "verification.observed", "task.discovered",
    "task.status_changed", "workflow.stage_changed", "run.status_changed",
}


class BrainBoundaryError(RuntimeError):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def state_root() -> Path:
    configured = os.environ.get("MICK_HARNESS_STATE_ROOT") or os.environ.get("MICK_HARNESS_STATE_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".local" / "state" / "mick-harness"


def brain_root() -> Path:
    configured = os.environ.get("MICK_BRAIN_ROOT") or os.environ.get("BRAIN_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".mick-brain"


def candidate_root() -> Path:
    return state_root() / "brain-candidates"


def suppression_root() -> Path:
    return state_root() / "brain-suppressions"


def project_memory_root() -> Path:
    return state_root() / "brain-project-memory"


def harness_improvement_root() -> Path:
    return state_root() / "harness-improvements"


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")[:120]
    if not slug:
        raise BrainBoundaryError("Project or Profile identifier is empty after normalization.")
    return slug


def redact(value: str) -> str:
    cleaned = value.strip()
    for pattern in SECRET_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    home = str(Path.home())
    if home and home != "/":
        cleaned = cleaned.replace(home, "~")
    return re.sub(r"\s+", " ", cleaned).strip()


def validate_summary(summary: str) -> str:
    cleaned = redact(summary)
    if not cleaned or len(cleaned) > 2000:
        raise BrainBoundaryError("Memory summary must contain 1-2000 characters.")
    return cleaned


def normalized_similarity(left: str, right: str) -> float:
    def normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", value.lower())

    first, second = normalize(left), normalize(right)
    if not first or not second:
        return 0.0
    return difflib.SequenceMatcher(a=first, b=second, autojunk=False).ratio()


def summaries_are_similar(left: str, right: str) -> bool:
    return normalized_similarity(left, right) >= 0.62


def stable_candidate_id(kind: str, layer: str, project: str | None, summary: str) -> str:
    material = json.dumps([kind, layer, project or "", summary], ensure_ascii=False, separators=(",", ":"))
    return f"memory_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"


def active_suppressions() -> list[dict[str, Any]]:
    if not suppression_root().exists():
        return []
    values: list[dict[str, Any]] = []
    for path in suppression_root().glob("*.json"):
        with contextlib.suppress(OSError, json.JSONDecodeError):
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("status") == "active":
                values.append(value)
    return values


def matching_suppression(*, kind: str, layer: str, profile: str | None, summary: str) -> dict[str, Any] | None:
    for value in active_suppressions():
        if value.get("kind") != kind or value.get("layer") != layer:
            continue
        if layer == "profile" and value.get("profile") != profile:
            continue
        if summaries_are_similar(str(value.get("summary") or ""), summary):
            return value
    return None


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


@contextlib.contextmanager
def simple_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 2
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            break
        except FileExistsError as error:
            if time.monotonic() >= deadline:
                raise BrainBoundaryError(f"Brain memory is busy: {path}") from error
            time.sleep(0.02)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


def create_candidate(
    *, kind: str, layer: str, summary: str, project: str | None = None,
    profile: str | None = None, source: str = "harness-agent",
) -> dict[str, Any]:
    if kind not in KINDS or layer not in LAYERS:
        raise BrainBoundaryError("Unsupported memory kind or layer.")
    if layer == "profile" and not profile:
        raise BrainBoundaryError("Profile candidates require a profile identifier.")
    cleaned = validate_summary(summary)
    identifier = stable_candidate_id(kind, layer, project or profile, cleaned)
    path = candidate_root() / f"{identifier}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    timestamp = now_iso()
    suppression = matching_suppression(kind=kind, layer=layer, profile=profile, summary=cleaned)
    record = {
        "schema_version": "2",
        "candidate_id": identifier,
        "kind": kind,
        "layer": layer,
        "project": project,
        "profile": profile,
        "summary": cleaned,
        "summary_digest": f"sha256:{hashlib.sha256(cleaned.encode('utf-8')).hexdigest()}",
        "status": "ignored_similar" if suppression else "pending_confirmation",
        "source": source,
        "created_at": timestamp,
        "updated_at": timestamp,
        "attempt_count": 0,
        "last_error": None,
    }
    if suppression:
        record["suppression_id"] = suppression.get("suppression_id")
        record["ignored_at"] = timestamp
    atomic_json(path, record)
    return record


def candidate_path(identifier: str) -> Path:
    if not re.fullmatch(r"memory_[a-f0-9]{20}", identifier):
        raise BrainBoundaryError("Invalid candidate identifier.")
    return candidate_root() / f"{identifier}.json"


def get_candidate(identifier: str) -> dict[str, Any]:
    path = candidate_path(identifier)
    if not path.is_file():
        raise BrainBoundaryError(f"Unknown candidate: {identifier}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_candidate(record: dict[str, Any]) -> dict[str, Any]:
    record["updated_at"] = now_iso()
    atomic_json(candidate_path(str(record["candidate_id"])), record)
    return record


def public_metadata(record: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "candidate_id", "kind", "layer", "project", "profile", "summary_digest",
        "status", "source", "created_at", "updated_at", "attempt_count", "last_error",
        "occurrence_count", "merged_from", "merged_into", "suppression_id",
    )
    return {key: record.get(key) for key in keys}


def candidate_view(record: dict[str, Any]) -> dict[str, Any]:
    """Private localhost view. Never use this in a project event ledger."""
    value = {**public_metadata(record), "summary": record.get("summary", "")}
    if record.get("layer") == "profile" and record.get("profile"):
        with contextlib.suppress(BrainBoundaryError):
            value["profile_preview"] = profile_candidate_preview(record)
    return value


def list_candidates(*, statuses: set[str] | None = None) -> list[dict[str, Any]]:
    if not candidate_root().exists():
        return []
    records = [json.loads(path.read_text(encoding="utf-8")) for path in candidate_root().glob("*.json")]
    if statuses is not None:
        records = [record for record in records if record.get("status") in statuses]
    views = [candidate_view(record) for record in records]
    for current in views:
        current["similar_candidate_ids"] = [
            other["candidate_id"]
            for other in views
            if other["candidate_id"] != current["candidate_id"]
            and other.get("kind") == current.get("kind")
            and other.get("layer") == current.get("layer")
            and other.get("status") in PENDING_STATUSES | {"rejected"}
            and current.get("status") in PENDING_STATUSES | {"rejected"}
            and summaries_are_similar(str(current.get("summary") or ""), str(other.get("summary") or ""))
        ]
    return sorted(views, key=lambda item: item.get("updated_at") or "", reverse=True)


def update_candidate(
    identifier: str, *, summary: str | None = None, layer: str | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    record = get_candidate(identifier)
    if layer is not None:
        if layer not in {"global", "profile"}:
            raise BrainBoundaryError("Workbench candidates may only target global or profile layers.")
        record["layer"] = layer
    if record.get("layer") == "profile":
        resolved_profile = profile or record.get("profile")
        if not resolved_profile:
            raise BrainBoundaryError("Profile candidates require a profile identifier.")
        record["profile"] = safe_slug(str(resolved_profile))
    elif layer == "global":
        record["profile"] = None
    if summary is not None:
        record["summary"] = validate_summary(summary)
        record["summary_digest"] = f"sha256:{hashlib.sha256(record['summary'].encode('utf-8')).hexdigest()}"
    record["status"] = "pending_confirmation"
    record["last_error"] = None
    return candidate_view(save_candidate(record))


def merge_candidates(
    identifier: str, duplicate_ids: list[str], *, summary: str | None = None,
    layer: str | None = None, profile: str | None = None,
) -> dict[str, Any]:
    primary = get_candidate(identifier)
    identifiers = list(dict.fromkeys(value for value in duplicate_ids if value != identifier))
    if not identifiers:
        raise BrainBoundaryError("Merging candidates requires at least one other candidate.")
    if len(identifiers) > 20:
        raise BrainBoundaryError("A single merge may include at most 20 candidates.")
    duplicates = [get_candidate(value) for value in identifiers]
    for record in [primary, *duplicates]:
        if record.get("status") == "written_local":
            raise BrainBoundaryError("Published candidates cannot be merged.")
    if any(record.get("kind") != primary.get("kind") for record in duplicates):
        raise BrainBoundaryError("Only candidates of the same kind can be merged.")

    if summary is not None or layer is not None or profile is not None:
        update_candidate(identifier, summary=summary, layer=layer, profile=profile)
        primary = get_candidate(identifier)
    timestamp = now_iso()
    merged_from = list(dict.fromkeys([
        *primary.get("merged_from", []),
        *identifiers,
        *(item for record in duplicates for item in record.get("merged_from", [])),
    ]))
    primary["merged_from"] = merged_from
    primary["occurrence_count"] = 1 + len(merged_from)
    primary["status"] = "pending_confirmation"
    primary["last_error"] = None
    primary["updated_at"] = timestamp
    save_candidate(primary)
    for record in duplicates:
        record["status"] = "merged"
        record["merged_into"] = identifier
        record["updated_at"] = timestamp
        save_candidate(record)
    return candidate_view(primary)


def ignore_similar_candidates(identifier: str) -> dict[str, Any]:
    record = get_candidate(identifier)
    if record.get("status") == "written_local":
        raise BrainBoundaryError("Published candidates cannot be ignored retroactively.")
    timestamp = now_iso()
    material = json.dumps(
        [record.get("kind"), record.get("layer"), record.get("profile"), record.get("summary")],
        ensure_ascii=False,
    )
    suppression_id = f"suppression_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"
    suppression = {
        "schema_version": "1",
        "suppression_id": suppression_id,
        "kind": record.get("kind"),
        "layer": record.get("layer"),
        "profile": record.get("profile"),
        "summary": record.get("summary"),
        "summary_digest": record.get("summary_digest"),
        "status": "active",
        "created_at": timestamp,
        "source_candidate_id": identifier,
    }
    atomic_json(suppression_root() / f"{suppression_id}.json", suppression)
    record["status"] = "ignored_similar"
    record["suppression_id"] = suppression_id
    record["ignored_at"] = timestamp
    return candidate_view(save_candidate(record))


def reject(identifier: str, *, reason: str | None = None) -> dict[str, Any]:
    record = get_candidate(identifier)
    record["status"] = "rejected"
    record["rejection_reason"] = redact(reason or "")[:500] or None
    return candidate_view(save_candidate(record))


def retry(identifier: str) -> dict[str, Any]:
    record = get_candidate(identifier)
    if record.get("status") not in {"rejected", "write_failed", "sync_failed"}:
        raise BrainBoundaryError("Only rejected or failed candidates can be retried.")
    record["status"] = "pending_confirmation"
    record["last_error"] = None
    return candidate_view(save_candidate(record))


def approve(identifier: str, *, yes: bool, dry_run: bool) -> dict[str, Any]:
    if not yes:
        raise BrainBoundaryError("Approval requires --yes; global and Profile candidates are never auto-written.")
    record = get_candidate(identifier)
    if record.get("status") == "written_local":
        return public_metadata(record)
    root = Path(__file__).resolve().parents[1]
    layer = record["layer"]
    if layer == "profile":
        preview = profile_candidate_preview(record)
        if dry_run:
            return {**public_metadata(record), "status": "approved_dry_run", "profile_preview": preview}
        record["attempt_count"] = int(record.get("attempt_count") or 0) + 1
        try:
            publish_profile_candidate(record, preview=preview)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            record["status"] = "write_failed"
            record["last_error"] = redact(str(error))[:500]
            save_candidate(record)
            raise BrainBoundaryError(record["last_error"]) from error
        record["status"] = "written_local"
        record["written_at"] = now_iso()
        record["sync_status"] = "pending"
        record["published_version"] = preview["proposed_version"]
        return public_metadata(save_candidate(record))
    command = [
        str(root / "scripts" / "brain-push.sh"), "--layer", layer,
        "--source", "harness-confirmed", "--no-sync",
    ]
    if record.get("project"):
        command.extend(["--project", record["project"]])
    command.append(f"{record['kind']}: {record['summary']}")
    if dry_run:
        return {**public_metadata(record), "status": "approved_dry_run", "command": command[:-1] + ["<redacted-summary>"]}
    record["attempt_count"] = int(record.get("attempt_count") or 0) + 1
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        record["status"] = "write_failed"
        record["last_error"] = redact(result.stderr.strip() or "Brain write failed.")[:500]
        save_candidate(record)
        raise BrainBoundaryError(record["last_error"])
    record["status"] = "written_local"
    record["written_at"] = now_iso()
    record["sync_status"] = "pending"
    return public_metadata(save_candidate(record))


def event_memory(event: dict[str, Any]) -> tuple[str, str] | None:
    event_type = str(event.get("type", ""))
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    if event_type not in CONFIRMED_EVENT_TYPES:
        return None
    if event.get("observation_kind") == "inferred":
        return None
    if event_type == "work.round_completed":
        if payload.get("status") != "completed" or not payload.get("summary"):
            return None
        prefix = f"{payload.get('requirement_id')}: " if payload.get("requirement_id") else ""
        artifacts = payload.get("artifact_refs") or []
        suffix = f"；产物：{', '.join(map(str, artifacts))}" if artifacts else ""
        return "result", f"{prefix}{payload.get('objective', '')} — {payload['summary']}{suffix}"
    if event_type == "decision.recorded":
        if payload.get("status") not in {"accepted", "confirmed", "completed"}:
            return None
        return "decision", f"{payload.get('title', '项目决策')}：{payload.get('summary', '')}"
    if event_type == "handoff.created":
        if payload.get("status") not in {"completed", "accepted"}:
            return None
        return "handoff", f"{payload.get('from_role', 'Unknown')} → {payload.get('to_role', 'Unknown')}：{payload.get('summary', '')}"
    if event_type == "verification.observed":
        result = str(payload.get("result", "")).lower()
        if result not in {"passed", "pass", "success", "通过"}:
            return None
        return "verification", str(payload.get("summary") or payload.get("check") or "项目验证通过")
    if event_type == "artifact.observed":
        path = payload.get("path")
        if not path:
            return None
        return "artifact", f"已交付项目产物：{path}"
    if event_type == "task.discovered":
        title = payload.get("title")
        if not title:
            return None
        subject = event.get("subject") if isinstance(event.get("subject"), dict) else {}
        task_id = subject.get("id") or event.get("subject_id") or "需求"
        return "requirement", f"{task_id}：{title}（{payload.get('status', 'discovered')}）"
    if event_type == "task.status_changed":
        if payload.get("to") != "completed":
            return None
        subject = event.get("subject") if isinstance(event.get("subject"), dict) else {}
        task_id = subject.get("id") or event.get("subject_id") or "需求"
        return "result", f"{task_id} 状态变为 {payload.get('to')}"
    if event_type == "workflow.stage_changed":
        if not payload.get("to"):
            return None
        return "stage", f"{payload.get('feature', '项目')}：{payload.get('from') or '未记录'} → {payload['to']}；当前归属 {payload.get('owner_role', 'Unknown')}"
    if event_type == "run.status_changed":
        if payload.get("to") != "completed":
            return None
        return "stage", "项目运行阶段已完成"
    return None


def project_record_path(project: str, identifier: str) -> Path:
    return project_memory_root() / safe_slug(project) / f"{identifier}.json"


def append_project_brain(record: dict[str, Any], *, brain: Path | None = None) -> Path:
    root = brain or brain_root()
    target = root / "projects" / safe_slug(str(record["project"])) / "learnings.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    line = f"- [{record['created_at'][:10]}] {record['kind']}: {record['summary']} <!-- {record['memory_id']} -->\n"
    with simple_lock(target.parent / ".harness-memory.lock"):
        current = target.read_text(encoding="utf-8") if target.is_file() else f"# Project: {record['project']} — Learnings\n\n"
        if record["memory_id"] not in current:
            target.write_text(current + line, encoding="utf-8")
    return target


def process_observer_event(project: str, event: dict[str, Any]) -> dict[str, Any]:
    if not project or str(event.get("project_id") or project) != project:
        return {"action": "ignored", "reason": "project-mismatch"}
    extracted = event_memory(event)
    if extracted is None:
        return {"action": "ignored", "reason": "not-confirmed-or-not-memory-worthy"}
    kind, summary = extracted
    cleaned = validate_summary(summary)
    material = f"{project}\0{kind}\0{cleaned}"
    identifier = f"project_memory_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"
    path = project_record_path(project, identifier)
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        return {"action": "duplicate", **project_memory_view(existing)}
    timestamp = now_iso()
    record = {
        "schema_version": "1",
        "memory_id": identifier,
        "project": project,
        "kind": kind,
        "summary": cleaned,
        "summary_digest": f"sha256:{hashlib.sha256(cleaned.encode('utf-8')).hexdigest()}",
        "status": "written_local",
        "sync_status": "pending",
        "source_event_type": event.get("type"),
        "source_event_id": event.get("event_id") or event.get("idempotency_key"),
        "source_agent": (event.get("source") or {}).get("producer"),
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    target = append_project_brain(record)
    record["brain_path"] = str(target.relative_to(brain_root()))
    atomic_json(path, record)
    return {"action": "recorded_project_memory", **project_memory_view(record)}


def project_memory_view(record: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "memory_id", "project", "kind", "summary", "status", "sync_status",
        "source_event_type", "source_event_id", "source_agent", "created_at", "updated_at", "brain_path",
        "occurrence_count", "merged_from", "merged_into", "similar_memory_ids",
    )
    return {key: record.get(key) for key in keys}


def list_project_memories(*, project: str | None = None) -> list[dict[str, Any]]:
    root = project_memory_root()
    paths = (root / safe_slug(project)).glob("*.json") if project else root.glob("*/*.json")
    records = [json.loads(path.read_text(encoding="utf-8")) for path in paths] if root.exists() else []
    grouped: dict[str, dict[str, Any]] = {}
    for record in (value for value in records if value.get("status") != "merged"):
        semantic = hashlib.sha256(
            f"{record.get('project', '')}\0{record.get('kind', '')}\0{record.get('summary', '')}".encode("utf-8")
        ).hexdigest()
        current = grouped.get(semantic)
        if current is None or (record.get("created_at") or "") > (current.get("created_at") or ""):
            record["occurrence_count"] = int(current.get("occurrence_count", 0)) + 1 if current else 1
            grouped[semantic] = record
        else:
            current["occurrence_count"] = int(current.get("occurrence_count", 1)) + 1
    values = list(grouped.values())
    for current in values:
        current["similar_memory_ids"] = [
            other["memory_id"]
            for other in values
            if other["memory_id"] != current["memory_id"]
            and other.get("project") == current.get("project")
            and other.get("kind") == current.get("kind")
            and summaries_are_similar(str(current.get("summary") or ""), str(other.get("summary") or ""))
        ]
    return sorted((project_memory_view(record) for record in values), key=lambda item: item.get("created_at") or "", reverse=True)


def undo_project_memory(identifier: str) -> dict[str, Any]:
    matches = list(project_memory_root().glob(f"*/{identifier}.json"))
    if len(matches) != 1:
        raise BrainBoundaryError(f"Unknown project memory: {identifier}")
    record = json.loads(matches[0].read_text(encoding="utf-8"))
    if record.get("status") != "reverted":
        record["status"] = "reverted"
        record["updated_at"] = now_iso()
        target = brain_root() / str(record["brain_path"])
        with target.open("a", encoding="utf-8") as stream:
            stream.write(f"- [{record['updated_at'][:10]}] 撤销：{record['memory_id']}\n")
        atomic_json(matches[0], record)
    return project_memory_view(record)


def correct_project_memory(identifier: str, *, summary: str) -> dict[str, Any]:
    matches = list(project_memory_root().glob(f"*/{identifier}.json"))
    if len(matches) != 1:
        raise BrainBoundaryError(f"Unknown project memory: {identifier}")
    original = json.loads(matches[0].read_text(encoding="utf-8"))
    cleaned = validate_summary(summary)
    material = f"{identifier}\0{cleaned}"
    correction_id = f"project_memory_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"
    correction_path = project_record_path(str(original["project"]), correction_id)
    if correction_path.is_file():
        return project_memory_view(json.loads(correction_path.read_text(encoding="utf-8")))
    timestamp = now_iso()
    original["status"] = "corrected"
    original["corrected_by"] = correction_id
    original["updated_at"] = timestamp
    atomic_json(matches[0], original)
    record = {
        **{key: original.get(key) for key in ("schema_version", "project", "kind", "source_event_type", "source_event_id", "source_agent")},
        "memory_id": correction_id,
        "summary": cleaned,
        "status": "written_local",
        "sync_status": "pending",
        "corrects": identifier,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    target = append_project_brain(record)
    record["brain_path"] = str(target.relative_to(brain_root()))
    with target.open("a", encoding="utf-8") as stream:
        stream.write(f"- [{timestamp[:10]}] 更正 {identifier} → {correction_id}\n")
    atomic_json(correction_path, record)
    return project_memory_view(record)


def promote_project_memory(identifier: str) -> dict[str, Any]:
    matches = list(project_memory_root().glob(f"*/{identifier}.json"))
    if len(matches) != 1:
        raise BrainBoundaryError(f"Unknown project memory: {identifier}")
    record = json.loads(matches[0].read_text(encoding="utf-8"))
    candidate = create_candidate(
        kind=record.get("kind") if record.get("kind") in KINDS else "gotcha",
        layer="global", project=record.get("project"), summary=record["summary"],
        source=f"project-memory:{identifier}",
    )
    return candidate_view(candidate)


def merge_project_memories(identifiers: list[str], *, summary: str) -> dict[str, Any]:
    unique = list(dict.fromkeys(identifiers))
    if len(unique) < 2:
        raise BrainBoundaryError("Merging project memories requires at least two records.")
    if len(unique) > 20:
        raise BrainBoundaryError("A single merge may include at most 20 project memories.")
    records: list[tuple[Path, dict[str, Any]]] = []
    for identifier in unique:
        if not re.fullmatch(r"project_memory_[a-f0-9]{20}", identifier):
            raise BrainBoundaryError("Invalid project memory identifier.")
        matches = list(project_memory_root().glob(f"*/{identifier}.json"))
        if len(matches) != 1:
            raise BrainBoundaryError(f"Unknown project memory: {identifier}")
        records.append((matches[0], json.loads(matches[0].read_text(encoding="utf-8"))))
    projects = {record.get("project") for _, record in records}
    kinds = {record.get("kind") for _, record in records}
    if len(projects) != 1 or len(kinds) != 1:
        raise BrainBoundaryError("Only project memories from the same project and kind can be merged.")

    cleaned = validate_summary(summary)
    project = str(records[0][1]["project"])
    kind = str(records[0][1]["kind"])
    material = json.dumps([project, kind, sorted(unique), cleaned], ensure_ascii=False, separators=(",", ":"))
    merged_id = f"project_memory_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"
    merged_path = project_record_path(project, merged_id)
    if merged_path.is_file():
        return project_memory_view(json.loads(merged_path.read_text(encoding="utf-8")))

    timestamp = now_iso()
    merged = {
        "schema_version": "1",
        "memory_id": merged_id,
        "project": project,
        "kind": kind,
        "summary": cleaned,
        "summary_digest": f"sha256:{hashlib.sha256(cleaned.encode('utf-8')).hexdigest()}",
        "status": "written_local",
        "sync_status": "pending",
        "source_event_type": "project-memory.merge",
        "source_event_id": merged_id,
        "source_agent": "harness-workbench",
        "merged_from": unique,
        "occurrence_count": len(unique),
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    target = append_project_brain(merged)
    merged["brain_path"] = str(target.relative_to(brain_root()))
    with target.open("a", encoding="utf-8") as stream:
        stream.write(f"- [{timestamp[:10]}] 合并 {', '.join(unique)} → {merged_id}\n")
    atomic_json(merged_path, merged)
    for path, record in records:
        record["status"] = "merged"
        record["merged_into"] = merged_id
        record["updated_at"] = timestamp
        atomic_json(path, record)
    return project_memory_view(merged)


def project_memory_record(identifier: str) -> dict[str, Any]:
    if not re.fullmatch(r"project_memory_[a-f0-9]{20}", identifier):
        raise BrainBoundaryError("Invalid project memory identifier.")
    matches = list(project_memory_root().glob(f"*/{identifier}.json"))
    if len(matches) != 1:
        raise BrainBoundaryError(f"Unknown project memory: {identifier}")
    record = json.loads(matches[0].read_text(encoding="utf-8"))
    if record.get("status") in {"reverted", "merged"}:
        raise BrainBoundaryError("Reverted or merged project memory cannot become a Harness improvement.")
    return record


def harness_improvement_path(identifier: str) -> Path:
    if not re.fullmatch(r"improvement_[a-f0-9]{20}", identifier):
        raise BrainBoundaryError("Invalid Harness improvement identifier.")
    return harness_improvement_root() / f"{identifier}.json"


def get_harness_improvement(identifier: str) -> dict[str, Any]:
    path = harness_improvement_path(identifier)
    if not path.is_file():
        raise BrainBoundaryError(f"Unknown Harness improvement: {identifier}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_harness_improvement(record: dict[str, Any]) -> dict[str, Any]:
    record["updated_at"] = now_iso()
    atomic_json(harness_improvement_path(str(record["improvement_id"])), record)
    return record


def raw_harness_improvements() -> list[dict[str, Any]]:
    root = harness_improvement_root()
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in root.glob("improvement_*.json"):
        with contextlib.suppress(OSError, json.JSONDecodeError):
            records.append(json.loads(path.read_text(encoding="utf-8")))
    return records


def harness_improvement_view(record: dict[str, Any], records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    records = records if records is not None else raw_harness_improvements()
    sources = list(record.get("sources") or [])
    projects = sorted({str(item.get("project")) for item in sources if item.get("project")})
    occurrence_count = max(int(record.get("occurrence_count") or 0), len(sources), 1)
    eligible = len(projects) >= 2 or occurrence_count >= 3
    active_statuses = {"observed", "pending_approval"}
    similar = [
        item["improvement_id"]
        for item in records
        if item.get("improvement_id") != record.get("improvement_id")
        and item.get("target") == record.get("target")
        and item.get("status") in active_statuses
        and record.get("status") in active_statuses
        and summaries_are_similar(str(item.get("summary") or ""), str(record.get("summary") or ""))
    ]
    return {
        **record,
        "sources": sources,
        "source_projects": projects,
        "project_count": len(projects),
        "occurrence_count": occurrence_count,
        "eligible_for_approval": eligible,
        "similar_improvement_ids": similar,
    }


def list_harness_improvements() -> list[dict[str, Any]]:
    records = raw_harness_improvements()
    visible = [record for record in records if record.get("status") != "merged"]
    return sorted(
        (harness_improvement_view(record, records) for record in visible),
        key=lambda item: item.get("updated_at") or "",
        reverse=True,
    )


def create_harness_improvement(
    memory_id: str, *, target: str, summary: str | None = None,
) -> dict[str, Any]:
    if target not in HARNESS_IMPROVEMENT_TARGETS:
        raise BrainBoundaryError("Harness improvement target must be rule, skill, checker, or profile.")
    with simple_lock(harness_improvement_root() / ".write.lock"):
        memory = project_memory_record(memory_id)
        cleaned = validate_summary(summary or str(memory.get("summary") or ""))
        material = json.dumps([memory_id, target, cleaned], ensure_ascii=False, separators=(",", ":"))
        identifier = f"improvement_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"
        path = harness_improvement_path(identifier)
        if path.is_file():
            return harness_improvement_view(json.loads(path.read_text(encoding="utf-8")))
        timestamp = now_iso()
        record = {
            "schema_version": "1",
            "improvement_id": identifier,
            "target": target,
            "summary": cleaned,
            "status": "observed",
            "sources": [{
                "memory_id": memory_id,
                "project": memory.get("project"),
                "kind": memory.get("kind"),
                "source_agent": memory.get("source_agent"),
                "summary_digest": memory.get("summary_digest"),
            }],
            "occurrence_count": max(int(memory.get("occurrence_count") or 1), 1),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        atomic_json(path, record)
        return harness_improvement_view(record)


def update_harness_improvement(
    identifier: str, *, target: str | None = None, summary: str | None = None,
) -> dict[str, Any]:
    with simple_lock(harness_improvement_root() / ".write.lock"):
        record = get_harness_improvement(identifier)
        if record.get("status") not in {"observed", "pending_approval", "rejected"}:
            raise BrainBoundaryError("Only observed, pending, or rejected improvements can be edited.")
        if target is not None:
            if target not in HARNESS_IMPROVEMENT_TARGETS:
                raise BrainBoundaryError("Harness improvement target must be rule, skill, checker, or profile.")
            record["target"] = target
        if summary is not None:
            record["summary"] = validate_summary(summary)
        if record.get("status") == "rejected":
            record["status"] = "observed"
        return harness_improvement_view(save_harness_improvement(record))


def merge_harness_improvements(
    identifier: str, duplicate_ids: list[str], *, summary: str | None = None,
) -> dict[str, Any]:
    with simple_lock(harness_improvement_root() / ".write.lock"):
        primary = get_harness_improvement(identifier)
        identifiers = list(dict.fromkeys(value for value in duplicate_ids if value != identifier))
        if not identifiers:
            raise BrainBoundaryError("Merging Harness improvements requires at least one other candidate.")
        if len(identifiers) > 20:
            raise BrainBoundaryError("A single merge may include at most 20 Harness improvements.")
        duplicates = [get_harness_improvement(value) for value in identifiers]
        for record in [primary, *duplicates]:
            if record.get("status") not in {"observed", "pending_approval", "rejected"}:
                raise BrainBoundaryError("Approved or implemented improvements cannot be merged.")
            if record.get("target") != primary.get("target"):
                raise BrainBoundaryError("Only Harness improvements with the same target can be merged.")
        sources = []
        seen_memories: set[str] = set()
        for record in [primary, *duplicates]:
            for source in record.get("sources") or []:
                memory_id = str(source.get("memory_id") or "")
                if memory_id and memory_id not in seen_memories:
                    sources.append(source)
                    seen_memories.add(memory_id)
        primary["sources"] = sources
        primary["merged_from"] = list(dict.fromkeys([*primary.get("merged_from", []), *identifiers]))
        primary["occurrence_count"] = sum(max(int(item.get("occurrence_count") or 1), 1) for item in [primary, *duplicates])
        if summary is not None:
            primary["summary"] = validate_summary(summary)
        projects = {item.get("project") for item in sources if item.get("project")}
        primary["status"] = "pending_approval" if len(projects) >= 2 or primary["occurrence_count"] >= 3 else "observed"
        save_harness_improvement(primary)
        for record in duplicates:
            record["status"] = "merged"
            record["merged_into"] = identifier
            save_harness_improvement(record)
        return harness_improvement_view(primary)


def submit_harness_improvement(identifier: str, *, force: bool = False) -> dict[str, Any]:
    with simple_lock(harness_improvement_root() / ".write.lock"):
        record = get_harness_improvement(identifier)
        view = harness_improvement_view(record)
        if record.get("status") == "pending_approval":
            return view
        if record.get("status") not in {"observed", "rejected"}:
            raise BrainBoundaryError("Only observed or rejected improvements can enter approval.")
        if not view["eligible_for_approval"] and not force:
            raise BrainBoundaryError("Single-project signal stays in observation unless the user explicitly confirms submission.")
        record["status"] = "pending_approval"
        record["submitted_by_override"] = bool(force and not view["eligible_for_approval"])
        return harness_improvement_view(save_harness_improvement(record))


def harness_improvement_proposal(record: dict[str, Any]) -> tuple[Path, str]:
    target_labels = {"rule": "Rule", "skill": "Skill", "checker": "Checker", "profile": "Profile"}
    view = harness_improvement_view(record)
    relative = Path("harness-improvements") / "proposals" / f"{record['improvement_id']}.md"
    projects = "、".join(view["source_projects"]) or "未记录"
    content = (
        f"# Harness 改进提案 · {record['improvement_id']}\n\n"
        f"> 本提案由用户审批生成，不会自动修改中央 Harness。\n\n"
        f"- 目标类型：{target_labels[record['target']]}\n"
        f"- 问题摘要：{record['summary']}\n"
        f"- 来源项目：{projects}\n"
        f"- 项目数：{view['project_count']}\n"
        f"- 出现次数：{view['occurrence_count']}\n"
        f"- 审批时间：{now_iso()}\n\n"
        "## 后续落地\n\n"
        "由受控开发回合确定具体文件、验证方式和回滚边界；落地前不得把本提案视为已生效。\n"
    )
    return relative, content


def approve_harness_improvement(identifier: str) -> dict[str, Any]:
    with simple_lock(harness_improvement_root() / ".write.lock"):
        record = get_harness_improvement(identifier)
        if record.get("status") == "approved":
            return harness_improvement_view(record)
        if record.get("status") != "pending_approval":
            raise BrainBoundaryError("Harness improvement must enter approval before it can be approved.")
        relative, content = harness_improvement_proposal(record)
        atomic_text(state_root() / relative, content)
        record["status"] = "approved"
        record["approved_at"] = now_iso()
        record["proposal_path"] = relative.as_posix()
        return harness_improvement_view(save_harness_improvement(record))


def reject_harness_improvement(identifier: str, *, reason: str | None = None) -> dict[str, Any]:
    with simple_lock(harness_improvement_root() / ".write.lock"):
        record = get_harness_improvement(identifier)
        if record.get("status") not in {"observed", "pending_approval"}:
            raise BrainBoundaryError("Only observed or pending improvements can be rejected.")
        record["status"] = "rejected"
        record["rejection_reason"] = redact(reason or "")[:500] or None
        return harness_improvement_view(save_harness_improvement(record))


def validate_artifact_path(value: str) -> str:
    path = Path(value.strip())
    if not value.strip() or path.is_absolute() or ".." in path.parts:
        raise BrainBoundaryError("Implemented artifact must be a project-relative path.")
    return path.as_posix()


def mark_harness_improvement_implemented(
    identifier: str, *, artifact_path: str, baseline_count: int,
) -> dict[str, Any]:
    with simple_lock(harness_improvement_root() / ".write.lock"):
        record = get_harness_improvement(identifier)
        if record.get("status") != "approved":
            raise BrainBoundaryError("Only approved Harness improvements can be marked implemented.")
        if not isinstance(baseline_count, int) or baseline_count < 0:
            raise BrainBoundaryError("Baseline count must be a non-negative integer.")
        record["status"] = "implemented"
        record["implementation"] = {
            "artifact_path": validate_artifact_path(artifact_path),
            "baseline_count": baseline_count,
            "implemented_at": now_iso(),
        }
        return harness_improvement_view(save_harness_improvement(record))


def verify_harness_improvement_effect(
    identifier: str, *, result: str, current_count: int, note: str = "",
) -> dict[str, Any]:
    with simple_lock(harness_improvement_root() / ".write.lock"):
        record = get_harness_improvement(identifier)
        if record.get("status") not in {"implemented", "needs_followup"}:
            raise BrainBoundaryError("Only implemented Harness improvements can be effect-verified.")
        if result not in {"improved", "unchanged", "regressed"}:
            raise BrainBoundaryError("Effect result must be improved, unchanged, or regressed.")
        if not isinstance(current_count, int) or current_count < 0:
            raise BrainBoundaryError("Current count must be a non-negative integer.")
        record["status"] = "verified" if result == "improved" else "needs_followup"
        record["effect"] = {
            "result": result,
            "current_count": current_count,
            "note": redact(note)[:1000],
            "verified_at": now_iso(),
        }
        return harness_improvement_view(save_harness_improvement(record))


def profile_metadata(*, brain: Path | None = None) -> list[dict[str, Any]]:
    root = (brain or brain_root()) / "global" / "profiles"
    if not root.is_dir():
        return []
    result: list[dict[str, Any]] = []
    for pointer in sorted(root.glob("*/current.json")):
        with contextlib.suppress(OSError, json.JSONDecodeError):
            value = json.loads(pointer.read_text(encoding="utf-8"))
            result.append({
                "profile": pointer.parent.name,
                "version": value.get("version"),
                "source": value.get("source") or "private_brain",
                "updated_at": value.get("updated_at"),
            })
    return result


def next_patch_version(value: str) -> str:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value or "")
    if not match:
        raise BrainBoundaryError(f"Profile version is not semantic: {value}")
    major, minor, patch = (int(part) for part in match.groups())
    return f"{major}.{minor}.{patch + 1}"


def profile_candidate_preview(record: dict[str, Any], *, brain: Path | None = None) -> dict[str, Any]:
    profile = safe_slug(str(record.get("profile") or ""))
    directory = (brain or brain_root()) / "global" / "profiles" / profile
    pointer_path = directory / "current.json"
    if not pointer_path.is_file():
        raise BrainBoundaryError(f"Unknown versioned Profile: {profile}")
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    current_version = str(pointer.get("version") or "")
    source = directory / str(pointer.get("file") or f"v{current_version}.md")
    if not source.is_file():
        raise BrainBoundaryError(f"Profile source is missing: {source.name}")
    return {
        "profile": profile,
        "current_version": current_version,
        "proposed_version": next_patch_version(current_version),
        "change": f"+ {record['summary']}",
        "source_file": source.name,
    }


def publish_profile_candidate(
    record: dict[str, Any], *, preview: dict[str, Any] | None = None, brain: Path | None = None,
) -> dict[str, Any]:
    root = brain or brain_root()
    preview = preview or profile_candidate_preview(record, brain=root)
    directory = root / "global" / "profiles" / preview["profile"]
    pointer_path = directory / "current.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    source = directory / str(pointer.get("file") or preview["source_file"])
    current = source.read_text(encoding="utf-8")
    version = preview["proposed_version"]
    today = now_iso()[:10]
    updated = re.sub(r"(?m)^version:\s*[^\n]+$", f"version: {version}", current, count=1)
    updated = re.sub(r"(?m)^updated:\s*[^\n]+$", f"updated: {today}", updated, count=1)
    heading = "## Confirmed amendments"
    addition = f"- {record['summary']} <!-- {record['candidate_id']} -->"
    if heading in updated:
        updated = updated.rstrip() + "\n" + addition + "\n"
    else:
        updated = updated.rstrip() + f"\n\n{heading}\n\n{addition}\n"
    target = directory / f"v{version}.md"
    atomic_text(target, updated)
    atomic_json(pointer_path, {
        **pointer,
        "version": version,
        "file": target.name,
        "updated_at": now_iso(),
        "source": "harness-approved-candidate",
    })
    return {"profile": preview["profile"], "version": version, "file": target.name}


def git_counts(root: Path) -> tuple[int | None, int | None, str | None]:
    if not (root / ".git").exists():
        return None, None, None
    result = subprocess.run(
        ["git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
        cwd=root, check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None, None, redact(result.stderr.strip())[:300] or "upstream unavailable"
    ahead, behind = (int(value) for value in result.stdout.split())
    return ahead, behind, None


def git_value(root: Path, *args: str) -> str | None:
    result = subprocess.run(["git", *args], cwd=root, check=False, capture_output=True, text=True)
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def display_path(path: Path) -> str:
    home = Path.home()
    try:
        return f"~/{path.resolve().relative_to(home.resolve())}"
    except (OSError, ValueError):
        return str(path)


def sanitize_remote_url(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"^(https?://)[^/@]+@", r"\1", value.strip())


def configured_brain_remote() -> str | None:
    config = Path(__file__).resolve().parents[1] / "config" / ".brain-config.yaml"
    if not config.is_file():
        return None
    with contextlib.suppress(OSError):
        match = re.search(r'(?m)^\s*remote:\s*["\']?([^"\'\n]+)', config.read_text(encoding="utf-8"))
        if match:
            return sanitize_remote_url(match.group(1).strip())
    return None


def repository_snapshot(root: Path) -> dict[str, Any]:
    is_git = (root / ".git").exists()
    actual_remote = sanitize_remote_url(git_value(root, "remote", "get-url", "origin")) if is_git else None
    configured_remote = configured_brain_remote()
    branch = git_value(root, "branch", "--show-current") if is_git else None
    upstream = git_value(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}") if is_git else None
    status = git_value(root, "status", "--porcelain") if is_git else None
    return {
        "exists": root.is_dir(),
        "path": display_path(root),
        "git": is_git,
        "configured_remote": configured_remote,
        "remote": actual_remote,
        "remote_matches_config": bool(actual_remote and configured_remote and actual_remote.rstrip("/").removesuffix(".git") == configured_remote.rstrip("/").removesuffix(".git")),
        "branch": branch,
        "upstream": upstream,
        "head": git_value(root, "rev-parse", "--short", "HEAD") if is_git else None,
        "clean": status is None if is_git else None,
    }


def pending_git_commits(root: Path, upstream: str) -> list[dict[str, Any]]:
    """List every local commit that a plain `git push` would send."""
    output = git_value(root, "log", "--format=%h%x1f%s%x1f%cI", f"{upstream}..HEAD") or ""
    commits: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = line.split("\x1f", 2)
        if len(parts) != 3:
            continue
        sha, subject, committed_at = parts
        files = git_value(root, "diff-tree", "--no-commit-id", "--name-only", "-r", sha) or ""
        commits.append(
            {
                "sha": sha,
                "subject": redact(subject)[:240],
                "committed_at": committed_at,
                "files": sorted(filter(None, files.splitlines())),
            }
        )
    return commits


def sync_item_summary(value: Any) -> str:
    return re.sub(r"^\s*(?:[-*•—–]\s*)+", "", redact(str(value or ""))).strip()[:500]


def raw_project_memories() -> list[tuple[Path, dict[str, Any]]]:
    root = project_memory_root()
    if not root.exists():
        return []
    result: list[tuple[Path, dict[str, Any]]] = []
    for path in root.glob("*/*.json"):
        with contextlib.suppress(OSError, json.JSONDecodeError):
            result.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return result


def write_routes_snapshot(root: Path) -> list[dict[str, Any]]:
    memories = [record for _, record in raw_project_memories()]
    source_counts: dict[str, int] = {}
    for record in memories:
        source = str(record.get("source_agent") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
    candidates = []
    for path in candidate_root().glob("*.json") if candidate_root().exists() else []:
        with contextlib.suppress(OSError, json.JSONDecodeError):
            candidates.append(json.loads(path.read_text(encoding="utf-8")))
    return [
        {
            "route_id": "project-memory",
            "label": "项目自动记忆",
            "destination": "projects/",
            "absolute_destination": display_path(root / "projects"),
            "sources": [{"name": name, "records": count} for name, count in sorted(source_counts.items())],
            "records": len(memories),
            "approval": "免审批",
            "approval_scope": "无需审批：已确认的项目事实自动记录",
        },
        {
            "route_id": "global-memory",
            "label": "全局偏好与经验",
            "destination": "global/",
            "absolute_destination": display_path(root / "global"),
            "sources": [{"name": "用户批准的候选", "records": sum(item.get("layer") == "global" and item.get("status") == "written_local" for item in candidates)}],
            "records": sum(item.get("layer") == "global" and item.get("status") == "written_local" for item in candidates),
            "approval": "需要审批",
            "approval_scope": "跨项目稳定偏好与可复用经验",
        },
        {
            "route_id": "profile-memory",
            "label": "版本化 Profile",
            "destination": "global/profiles/",
            "absolute_destination": display_path(root / "global" / "profiles"),
            "sources": [{"name": "用户批准的 Profile 候选", "records": sum(item.get("layer") == "profile" and item.get("status") == "written_local" for item in candidates)}],
            "records": len(profile_metadata(brain=root)),
            "approval": "需要审批",
            "approval_scope": "Profile 规则或风格的版本变化",
        },
        {
            "route_id": "session-memory",
            "label": "会话补漏",
            "destination": "sessions/",
            "absolute_destination": display_path(root / "sessions"),
            "sources": [{"name": "可选 SessionEnd / daily", "records": 0}],
            "records": 0,
            "approval": "默认关闭",
            "approval_scope": "不进入审批箱：仅作可选补漏输入",
        },
    ]


def sync_state_path() -> Path:
    return state_root() / "brain-sync-state.json"


def save_sync_state(value: dict[str, Any]) -> None:
    atomic_json(sync_state_path(), value)


def sync_pending(*, confirmed: bool, dry_run: bool = False, brain: Path | None = None) -> dict[str, Any]:
    root = brain or brain_root()
    repository = repository_snapshot(root)
    if not repository["git"]:
        raise BrainBoundaryError("Brain 本地目录不是 Git 仓库，无法同步。")
    if not repository["remote"]:
        raise BrainBoundaryError("Brain 仓库没有 origin，无法确认写入目标。")
    if repository["configured_remote"] and not repository["remote_matches_config"]:
        raise BrainBoundaryError("Brain 配置仓库与实际 origin 不一致；请先确认目标，工作台不会自动选择其一。")
    if not repository["branch"] or not repository["upstream"]:
        raise BrainBoundaryError("Brain 当前分支没有 upstream，请先在命令行建立上游分支。")
    ahead, behind, git_error = git_counts(root)
    if git_error:
        raise BrainBoundaryError(git_error)
    if behind:
        raise BrainBoundaryError(f"远端领先 {behind} 个提交；为避免自动 rebase，请先在命令行处理后再同步。")

    pending_memories = [(path, record) for path, record in raw_project_memories() if record.get("sync_status") == "pending"]
    pending_candidates: list[tuple[Path, dict[str, Any]]] = []
    for path in candidate_root().glob("*.json") if candidate_root().exists() else []:
        with contextlib.suppress(OSError, json.JSONDecodeError):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") == "written_local" and record.get("sync_status") == "pending":
                pending_candidates.append((path, record))

    owned_paths: set[str] = set()
    for _, record in pending_memories:
        relative = Path(str(record.get("brain_path") or ""))
        if relative.parts and not relative.is_absolute() and ".." not in relative.parts and (root / relative).exists():
            owned_paths.add(str(relative))
    for _, record in pending_candidates:
        if record.get("layer") == "profile" and record.get("profile"):
            directory = root / "global" / "profiles" / safe_slug(str(record["profile"]))
            if directory.is_dir():
                owned_paths.update(str(path.relative_to(root)) for path in directory.rglob("*") if path.is_file())

    staged_before = set(filter(None, (git_value(root, "diff", "--cached", "--name-only") or "").splitlines()))
    unexpected_staged = staged_before - owned_paths
    if unexpected_staged:
        names = "、".join(sorted(unexpected_staged)[:5])
        raise BrainBoundaryError(f"Brain 仓库存在 Harness 管理范围外的已暂存文件：{names}。请先处理后再同步。")

    items: list[dict[str, Any]] = []
    for _, record in pending_memories:
        destination = str(record.get("brain_path") or "projects/")
        items.append(
            {
                "scope": "project",
                "project": record.get("project") or "unknown",
                "kind": record.get("kind") or "project_fact",
                "summary": sync_item_summary(record.get("summary")),
                "destination": destination,
                "source": record.get("source_agent") or "unknown",
                "created_at": record.get("created_at") or record.get("updated_at"),
            }
        )
    for _, record in pending_candidates:
        scope = str(record.get("layer") or "global")
        if scope == "profile" and record.get("profile"):
            destination = f"global/profiles/{safe_slug(str(record['profile']))}/"
        else:
            destination = "global/"
        items.append(
            {
                "scope": scope,
                "project": record.get("project"),
                "kind": record.get("kind") or "approved_candidate",
                "summary": sync_item_summary(record.get("summary")),
                "destination": destination,
                "source": record.get("source_agent") or "approved_candidate",
                "created_at": record.get("created_at") or record.get("updated_at"),
            }
        )

    groups = {
        "project": len(pending_memories),
        "global": sum(record.get("layer") == "global" for _, record in pending_candidates),
        "profile": sum(record.get("layer") == "profile" for _, record in pending_candidates),
        "session": 0,
    }
    pending_commits = pending_git_commits(root, str(repository["upstream"]))

    preview = {
        "status": "preview",
        "repository": repository,
        "destination": {
            "remote": repository["remote"],
            "configured_remote": repository["configured_remote"],
            "branch": repository["branch"],
            "upstream": repository["upstream"],
            "privacy": "未验证：仓库地址本身不能证明远端仓库是私有的。",
        },
        "pending_records": len(pending_memories),
        "pending_candidates": len(pending_candidates),
        "groups": groups,
        "items": items,
        "owned_paths": sorted(owned_paths),
        "pending_files": sorted(owned_paths),
        "pending_commits": pending_commits,
        "push_scope_note": "Git 会推送当前分支全部领先提交；不只是在页面中显示的待同步记录。请在确认前核对下方提交清单。",
        "excluded_content": [
            "原始聊天全文",
            "Prompt、模型私有推理和工具完整日志",
            "源代码文件正文（只记录经确认的项目事实与产物路径）",
            "凭据、令牌、环境变量和检测到的敏感值",
            "默认关闭的 Session 会话补漏内容",
        ],
        "can_sync": True,
        "blockers": [],
        "ahead": ahead or 0,
        "behind": behind or 0,
    }
    if dry_run:
        return preview
    if not confirmed:
        raise BrainBoundaryError("同步需要用户确认。")

    started_at = now_iso()
    with simple_lock(state_root() / "brain-sync.lock"):
        save_sync_state({**preview, "status": "syncing", "last_attempt_at": started_at, "last_error": None})
        try:
            staged_before = set(filter(None, (git_value(root, "diff", "--cached", "--name-only") or "").splitlines()))
            unexpected_staged = staged_before - owned_paths
            if unexpected_staged:
                names = "、".join(sorted(unexpected_staged)[:5])
                raise BrainBoundaryError(f"Brain 仓库存在 Harness 管理范围外的已暂存文件：{names}。请先处理后再同步。")
            if owned_paths:
                add = subprocess.run(["git", "add", "--", *sorted(owned_paths)], cwd=root, check=False, capture_output=True, text=True)
                if add.returncode != 0:
                    raise BrainBoundaryError(redact(add.stderr.strip()) or "Brain 文件暂存失败。")
            staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=root, check=False)
            if staged.returncode == 1:
                commit = subprocess.run(["git", "commit", "-m", "chore(brain): sync Harness memory"], cwd=root, check=False, capture_output=True, text=True)
                if commit.returncode != 0:
                    raise BrainBoundaryError(redact(commit.stderr.strip() or commit.stdout.strip()) or "Brain 本地提交失败。")
            elif staged.returncode != 0:
                raise BrainBoundaryError("无法检查 Brain 待提交内容。")
            push = subprocess.run(["git", "push", "--quiet"], cwd=root, check=False, capture_output=True, text=True)
            if push.returncode != 0:
                raise BrainBoundaryError(redact(push.stderr.strip()) or "Brain 远端推送失败。")
        except Exception as error:
            message = redact(str(error))[:500]
            save_sync_state({**preview, "status": "error", "last_attempt_at": started_at, "last_error": message})
            raise BrainBoundaryError(message) from error

        synced_at = now_iso()
        for path, record in pending_memories:
            record["sync_status"] = "synced"
            record["synced_at"] = synced_at
            record["updated_at"] = synced_at
            atomic_json(path, record)
        for path, record in pending_candidates:
            record["sync_status"] = "synced"
            record["synced_at"] = synced_at
            atomic_json(path, record)
        result = {**preview, "status": "synced", "synced_records": len(pending_memories), "synced_candidates": len(pending_candidates), "last_attempt_at": started_at, "last_success_at": synced_at, "last_error": None}
        save_sync_state(result)
        return result


def legacy_backfill_snapshot() -> dict[str, Any]:
    settings = Path.home() / ".claude" / "settings.json"
    installed = False
    if settings.is_file():
        with contextlib.suppress(OSError):
            installed = "brain-sync" in settings.read_text(encoding="utf-8", errors="replace")
    launch_agent = Path.home() / "Library" / "LaunchAgents" / "com.mick.brain-sync-daily.plist"
    log_paths = [
        Path.home() / ".claude" / "logs" / "brain-sync.log",
        Path.home() / ".claude" / "logs" / "brain-sync-daily.log",
    ]
    latest_line = None
    latest_mtime = 0.0
    for path in log_paths:
        with contextlib.suppress(OSError):
            stat = path.stat()
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            if lines and stat.st_mtime >= latest_mtime:
                latest_line = redact(lines[-1])[:500]
                latest_mtime = stat.st_mtime
    failed = bool(latest_line and re.search(r"failed|not found|error|returned empty", latest_line, re.IGNORECASE))
    return {
        "role": "optional_backfill",
        "enabled_by_default": False,
        "legacy_hook_installed": installed,
        "daily_job_installed": launch_agent.is_file(),
        "status": "degraded" if failed else ("installed" if installed or launch_agent.is_file() else "disabled"),
        "last_log_at": dt.datetime.fromtimestamp(latest_mtime, dt.timezone.utc).isoformat() if latest_mtime else None,
        "last_log": latest_line,
    }


def health_snapshot(*, brain: Path | None = None) -> dict[str, Any]:
    root = brain or brain_root()
    memories = list_project_memories()
    memory_records = [record for _, record in raw_project_memories()]
    candidates = list_candidates()
    ahead, behind, git_error = git_counts(root)
    repository = repository_snapshot(root)
    repository_exists = repository["exists"]
    pending_sync = sum(item.get("sync_status") == "pending" for item in memory_records)
    sync_state = {}
    with contextlib.suppress(OSError, json.JSONDecodeError):
        if sync_state_path().is_file():
            sync_state = json.loads(sync_state_path().read_text(encoding="utf-8"))
    sync_error = sync_state.get("last_error")
    return {
        "generated_at": now_iso(),
        "repository": repository,
        "local_write": {
            "status": "ready" if repository_exists else "unavailable",
            "project_memory_count": len(memories),
            "project_memory_record_count": len(memory_records),
            "last_write_at": memories[0].get("created_at") if memories else None,
        },
        "remote_sync": {
            "status": "error" if git_error or sync_error else ("pending" if ahead or pending_sync else ("synced" if ahead is not None else "not_configured")),
            "ahead": ahead,
            "behind": behind,
            "pending_local_records": pending_sync,
            "last_attempt_at": sync_state.get("last_attempt_at"),
            "last_success_at": sync_state.get("last_success_at"),
            "last_error": git_error or sync_error,
        },
        "approval_inbox": {
            "pending": sum(item.get("status") in PENDING_STATUSES for item in candidates),
            "failed": sum(item.get("status") in {"write_failed", "sync_failed"} for item in candidates),
        },
        "structured_events": {
            "status": "active",
            "source_agents": sorted({item.get("source_agent") for item in memories if item.get("source_agent")}),
            "auto_project_types": sorted(CONFIRMED_EVENT_TYPES),
        },
        "write_routes": write_routes_snapshot(root),
        "profiles": profile_metadata(brain=root),
        "legacy_backfill": legacy_backfill_snapshot(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness brain-memory")
    sub = parser.add_subparsers(dest="command", required=True)
    candidate = sub.add_parser("candidate")
    candidate.add_argument("--kind", choices=sorted(KINDS), required=True)
    candidate.add_argument("--layer", choices=sorted(LAYERS), required=True)
    candidate.add_argument("--summary", required=True)
    candidate.add_argument("--project")
    candidate.add_argument("--profile")
    approve_parser = sub.add_parser("approve")
    approve_parser.add_argument("candidate_id")
    approve_parser.add_argument("--yes", action="store_true")
    approve_parser.add_argument("--dry-run", action="store_true")
    reject_parser = sub.add_parser("reject")
    reject_parser.add_argument("candidate_id")
    reject_parser.add_argument("--reason")
    retry_parser = sub.add_parser("retry")
    retry_parser.add_argument("candidate_id")
    sub.add_parser("list")
    project_list = sub.add_parser("project-list")
    project_list.add_argument("--project")
    sub.add_parser("health")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "candidate":
        result = public_metadata(create_candidate(
            kind=args.kind, layer=args.layer, summary=args.summary,
            project=args.project, profile=args.profile,
        ))
    elif args.command == "approve":
        result = approve(args.candidate_id, yes=args.yes, dry_run=args.dry_run)
    elif args.command == "reject":
        result = public_metadata(reject(args.candidate_id, reason=args.reason))
    elif args.command == "retry":
        result = public_metadata(retry(args.candidate_id))
    elif args.command == "project-list":
        result = list_project_memories(project=args.project)
    elif args.command == "health":
        result = health_snapshot()
    else:
        result = [public_metadata(record) for record in (json.loads(path.read_text(encoding="utf-8")) for path in sorted(candidate_root().glob("*.json")))] if candidate_root().exists() else []
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrainBoundaryError as error:
        print(f"brain boundary error: {error}", file=sys.stderr)
        raise SystemExit(2)

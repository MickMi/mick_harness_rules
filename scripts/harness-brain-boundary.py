#!/usr/bin/env python3
"""Consent boundary for Harness → Brain writes.

Candidate text stays in the user's private Harness state. Project ledgers only
receive metadata through the observer and never receive the candidate body.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


SECRET_PATTERNS = (
    re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_A-Za-z0-9]{12,}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
)
KINDS = {"gotcha", "decision", "preference", "env"}
LAYERS = {"session", "project", "global"}


class BrainBoundaryError(RuntimeError):
    pass


def state_root() -> Path:
    configured = os.environ.get("MICK_HARNESS_STATE_ROOT")
    return Path(configured).expanduser() if configured else Path.home() / ".mick-harness" / "state"


def candidate_root() -> Path:
    return state_root() / "brain-candidates"


def redact(value: str) -> str:
    cleaned = value.strip()
    for pattern in SECRET_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    home = str(Path.home())
    if home and home != "/":
        cleaned = cleaned.replace(home, "~")
    return cleaned


def stable_candidate_id(kind: str, layer: str, project: str | None, summary: str) -> str:
    material = json.dumps([kind, layer, project or "", summary], ensure_ascii=False, separators=(",", ":"))
    return f"memory_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"


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
        if temporary.exists():
            temporary.unlink()


def create_candidate(*, kind: str, layer: str, summary: str, project: str | None = None) -> dict[str, Any]:
    if kind not in KINDS or layer not in LAYERS:
        raise BrainBoundaryError("Unsupported memory kind or layer.")
    cleaned = redact(summary)
    if not cleaned or len(cleaned) > 2000:
        raise BrainBoundaryError("Candidate summary must contain 1-2000 characters.")
    identifier = stable_candidate_id(kind, layer, project, cleaned)
    path = candidate_root() / f"{identifier}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    record = {
        "schema_version": "1",
        "candidate_id": identifier,
        "kind": kind,
        "layer": layer,
        "project": project,
        "summary": cleaned,
        "summary_digest": f"sha256:{hashlib.sha256(cleaned.encode('utf-8')).hexdigest()}",
        "status": "pending_confirmation",
        "source": "harness-agent",
    }
    atomic_json(path, record)
    return record


def public_metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record.get(key) for key in ("candidate_id", "kind", "layer", "project", "summary_digest", "status", "source")}


def approve(identifier: str, *, yes: bool, dry_run: bool) -> dict[str, Any]:
    if not yes:
        raise BrainBoundaryError("Approval requires --yes; candidates are never auto-written to Brain.")
    path = candidate_root() / f"{identifier}.json"
    if not path.is_file():
        raise BrainBoundaryError(f"Unknown candidate: {identifier}")
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("status") == "written":
        return public_metadata(record)
    root = Path(__file__).resolve().parents[1]
    command = [
        str(root / "scripts" / "brain-push.sh"),
        "--layer", record["layer"],
        "--source", "harness-confirmed",
        "--no-sync",
    ]
    if record.get("project"):
        command.extend(["--project", record["project"]])
    command.append(f"{record['kind']}: {record['summary']}")
    if dry_run:
        return {**public_metadata(record), "status": "approved_dry_run", "command": command[:-1] + ["<redacted-summary>"]}
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise BrainBoundaryError(result.stderr.strip() or "Brain write failed.")
    record["status"] = "written"
    atomic_json(path, record)
    return public_metadata(record)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness brain-memory")
    sub = parser.add_subparsers(dest="command", required=True)
    candidate = sub.add_parser("candidate")
    candidate.add_argument("--kind", choices=sorted(KINDS), required=True)
    candidate.add_argument("--layer", choices=sorted(LAYERS), required=True)
    candidate.add_argument("--summary", required=True)
    candidate.add_argument("--project")
    approve_parser = sub.add_parser("approve")
    approve_parser.add_argument("candidate_id")
    approve_parser.add_argument("--yes", action="store_true")
    approve_parser.add_argument("--dry-run", action="store_true")
    sub.add_parser("list")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "candidate":
        result = public_metadata(create_candidate(kind=args.kind, layer=args.layer, summary=args.summary, project=args.project))
    elif args.command == "approve":
        result = approve(args.candidate_id, yes=args.yes, dry_run=args.dry_run)
    else:
        result = [public_metadata(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(candidate_root().glob("*.json"))] if candidate_root().exists() else []
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrainBoundaryError as error:
        print(f"brain boundary error: {error}", file=sys.stderr)
        raise SystemExit(2)

#!/usr/bin/env python3
"""Redacted lifecycle adapter from Codex hooks to Harness observe events."""

from __future__ import annotations

import importlib.util
import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any


MAX_INPUT_BYTES = 1_048_576
EVENT_STATES = {
    "SessionStart": "session_started",
    "UserPromptSubmit": "turn_started",
    "Stop": "turn_completed",
    "SessionEnd": "session_ended",
}


def load_observer() -> Any:
    path = Path(__file__).resolve().with_name("harness-observe.py")
    spec = importlib.util.spec_from_file_location("harness_observe_hook_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load observer runtime: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stop_response(event_name: str | None) -> None:
    if event_name == "Stop":
        print(json.dumps({"continue": True}))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--platform", choices=("codex", "claude"), default=os.environ.get("MICK_HARNESS_AGENT", "codex"))
    args, _ = parser.parse_known_args(argv)
    started = time.monotonic()
    event_name = None
    session_directory = None
    project_id = None
    reporting = None
    status, reason = "failed", "submission_failed"
    try:
        observer = load_observer()
        reporting = observer.load_reporting()
        started_at = reporting.now_iso()
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            status, reason = "skipped", "payload_too_large"
            return 0
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            status, reason = "skipped", "invalid_payload"
            return 0
        if not isinstance(payload, dict):
            status, reason = "skipped", "invalid_payload"
            return 0
        event_name = payload.get("hook_event_name")
        # A malformed event name must not break dictionary lookup or leak input.
        state = EVENT_STATES.get(event_name) if isinstance(event_name, str) else None
        if state is None:
            status, reason = "skipped", "unsupported_event"
            return 0
        cwd, session_ref, turn_ref = payload.get("cwd"), payload.get("session_id"), payload.get("turn_id")
        if not isinstance(cwd, str) or not isinstance(session_ref, str) or not session_ref:
            status, reason = "skipped", "missing_session"
            return 0
        try:
            session_directory = Path(cwd).expanduser().resolve(strict=True)
            if not session_directory.is_dir():
                raise OSError()
        except (OSError, ValueError):
            status, reason = "skipped", "workspace_unavailable"
            return 0
        global_policy = reporting.policy()
        if not global_policy["enabled"]:
            status, reason = "skipped", global_policy["reason"]
            if args.platform == "claude":
                reporting.claude_turn(session_directory, session_ref, "SessionEnd")
            return 0
        project = observer.resolve_agent_project(session_directory)
        if project is None:
            status, reason = "skipped", "project_unresolved"
            return 0
        project_id = observer.project_id(project)
        project_policy = reporting.policy(project_id)
        if not project_policy["enabled"]:
            status, reason = "skipped", project_policy["reason"]
            if args.platform == "claude":
                reporting.claude_turn(session_directory, session_ref, "SessionEnd")
            return 0
        if args.platform == "claude" and not isinstance(turn_ref, str):
            turn_ref = reporting.claude_turn(session_directory, session_ref, event_name)
        if state.startswith("turn_") and not turn_ref:
            status, reason = "skipped", "missing_turn"
            return 0
        result = observer.submit_agent_activity(
            project,
            platform=args.platform,
            state=state,
            session_ref=session_ref,
            turn_ref=turn_ref if isinstance(turn_ref, str) else None,
            source_project=session_directory,
        )
        if result.get("skipped"):
            status, reason = "skipped", result["reason"]
        elif result.get("transport") == "service":
            status, reason = "delivered", "reported"
        else:
            status, reason = "written_local", "local_fallback"
    except Exception:  # Hooks never break the turn or print raw inputs/errors.
        status, reason = "failed", "submission_failed"
        print("harness observe hook warning: lifecycle reporting failed; inspect local trigger records", file=sys.stderr)
    finally:
        if reporting is not None:
            try:
                reporting.record(platform=args.platform, event=event_name, cwd=session_directory, project_id=project_id,
                                 started_at=started_at, duration_ms=int((time.monotonic() - started) * 1000),
                                 status=status, reason=reason)
            except Exception:
                print("harness observe hook warning: unable to save local trigger diagnostic", file=sys.stderr)
        stop_response(event_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

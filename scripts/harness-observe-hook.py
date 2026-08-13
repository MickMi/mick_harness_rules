#!/usr/bin/env python3
"""Redacted lifecycle adapter from Codex hooks to Harness observe events."""

from __future__ import annotations

import importlib.util
import argparse
import json
import os
from pathlib import Path
import sys
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
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        return 0
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    event_name = payload.get("hook_event_name")
    state = EVENT_STATES.get(event_name)
    if state is None:
        stop_response(event_name)
        return 0
    cwd = payload.get("cwd")
    session_ref = payload.get("session_id")
    turn_ref = payload.get("turn_id")
    if not isinstance(cwd, str) or not isinstance(session_ref, str):
        stop_response(event_name)
        return 0
    if state.startswith("turn_") and not isinstance(turn_ref, str):
        stop_response(event_name)
        return 0
    try:
        project = Path(cwd).expanduser().resolve(strict=True)
        observer = load_observer()
        if project.is_dir() and observer.has_harness_entry(project):
            observer.submit_agent_activity(
                project,
                platform=args.platform,
                state=state,
                session_ref=session_ref,
                turn_ref=turn_ref if isinstance(turn_ref, str) else None,
            )
    except Exception as error:  # Hooks must never break the Codex turn.
        print(f"harness observe hook warning: {error}", file=sys.stderr)
    stop_response(event_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

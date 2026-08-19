#!/usr/bin/env python3
"""Cost-aware verification tiers with exact-fingerprint gate reuse."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from typing import Any


SUBSYSTEMS = {"brain", "observe", "prd", "agents", "roles"}


def command_plan(tier: str, subsystem: str | None) -> list[list[str]]:
    python = sys.executable
    fast = {
        "brain": [[python, "-m", "unittest", "tests.test_harness_agents.BrainBoundaryTests"]],
        "observe": [[python, "-m", "unittest", "tests.test_harness_observe.ObserveRuntimeTests.test_dashboard_has_brain_health_activity_and_approval_workbench"]],
        "prd": [[python, "-m", "unittest", "tests.test_prd_for_humans"]],
        "agents": [[python, "-m", "unittest", "tests.test_harness_agents.AgentRegistryTests", "tests.test_harness_agents.AgentManagerTests"]],
        "roles": [[python, "-m", "unittest", "tests.test_role_contracts"]],
    }
    expanded = {
        "brain": [
            [python, "-m", "unittest", "tests.test_harness_agents", "tests.test_prd_for_humans"],
            [python, "-m", "unittest", "tests.test_harness_observe.ObserveRuntimeTests.test_http_ingest_is_authenticated_scoped_and_idempotent"],
        ],
        "observe": [
            [python, "-m", "unittest", "tests.test_harness_observe"],
            [python, "-m", "unittest", "tests.test_harness_agents.AgentManagerTests"],
        ],
        "prd": [
            [python, "-m", "unittest", "tests.test_prd_for_humans"],
            [python, "-m", "unittest", "tests.test_harness_agents.BrainBoundaryTests.test_profile_candidate_previews_and_publishes_a_new_patch_version"],
        ],
        "agents": [
            [python, "-m", "unittest", "tests.test_harness_agents"],
            [python, "-m", "unittest", "tests.test_role_contracts"],
        ],
        "roles": [
            [python, "-m", "unittest", "tests.test_role_contracts"],
            [python, "-m", "unittest", "tests.test_harness_agents.AgentManagerTests"],
        ],
    }
    if tier == "release":
        return [
            [python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
            ["./generate.sh", "--check"],
            ["git", "diff", "--check"],
        ]
    selected = subsystem or "brain"
    if selected not in SUBSYSTEMS:
        raise ValueError(f"unknown subsystem: {selected}")
    if tier == "fast":
        return fast[selected]
    if tier == "subsystem":
        return expanded[selected]
    raise ValueError(f"unknown verification tier: {tier}")


def git_material(root: Path) -> bytes:
    chunks: list[bytes] = []
    for command in (
        ["git", "status", "--porcelain=v1"],
        ["git", "diff", "--binary", "HEAD"],
        ["git", "diff", "--binary", "--cached"],
    ):
        result = subprocess.run(command, cwd=root, check=False, capture_output=True)
        chunks.extend([" ".join(command).encode("utf-8"), result.stdout, result.stderr])
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=root, check=False, capture_output=True,
    )
    chunks.append(untracked.stdout)
    for raw in filter(None, untracked.stdout.split(b"\0")):
        path = root / raw.decode("utf-8", errors="surrogateescape")
        if path.is_file():
            chunks.append(raw)
            chunks.append(path.read_bytes())
    return b"\0".join(chunks)


def environment_signature() -> str:
    return "|".join((platform.system(), platform.machine(), platform.release(), sys.version.split()[0]))


def verification_fingerprint(root: Path, commands: list[list[str]], *, environment: str | None = None) -> str:
    digest = hashlib.sha256()
    digest.update(git_material(root))
    digest.update(json.dumps(commands, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    digest.update((environment or environment_signature()).encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


def gate_name(tier: str, subsystem: str | None) -> str:
    return f"{tier}:{subsystem or 'all'}"


def load_cache(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": "1", "gates": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": "1", "gates": {}}
    if not isinstance(value, dict) or not isinstance(value.get("gates"), dict):
        return {"schema_version": "1", "gates": {}}
    return value


def save_gate(path: Path, *, key: str, tier: str, subsystem: str | None, commands: list[list[str]]) -> None:
    value = load_cache(path)
    value["gates"][gate_name(tier, subsystem)] = {
        "status": "passed",
        "fingerprint": key,
        "tier": tier,
        "subsystem": subsystem,
        "commands": commands,
        "environment": environment_signature(),
        "verified_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def reusable_gate(path: Path, *, key: str, tier: str, subsystem: str | None, commands: list[list[str]]) -> bool:
    gate = load_cache(path).get("gates", {}).get(gate_name(tier, subsystem), {})
    return bool(
        gate.get("status") == "passed"
        and gate.get("fingerprint") == key
        and gate.get("tier") == tier
        and gate.get("subsystem") == subsystem
        and gate.get("commands") == commands
    )


def run_plan(root: Path, commands: list[list[str]]) -> int:
    for index, command in enumerate(commands, start=1):
        started = time.monotonic()
        result = subprocess.run(command, cwd=root, check=False, capture_output=True, text=True)
        elapsed = time.monotonic() - started
        label = " ".join(command)
        if result.returncode == 0:
            print(f"PASS {index}/{len(commands)} · {elapsed:.1f}s · {label}")
            continue
        print(f"FAIL {index}/{len(commands)} · exit {result.returncode} · {label}", file=sys.stderr)
        combined = "\n".join(filter(None, (result.stdout.strip(), result.stderr.strip())))
        if combined:
            print(combined[-12000:], file=sys.stderr)
        return result.returncode or 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness-verify")
    parser.add_argument("tier", choices=("fast", "subsystem", "release"))
    parser.add_argument("--subsystem", choices=sorted(SUBSYSTEMS))
    parser.add_argument("--force", action="store_true", help="Ignore a matching successful Gate and run again.")
    parser.add_argument("--state", type=Path, help="Override the local Gate cache path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    subsystem = None if args.tier == "release" else (args.subsystem or "brain")
    commands = command_plan(args.tier, subsystem)
    fingerprint = verification_fingerprint(root, commands)
    state_path = args.state or Path(os.environ.get("MICK_HARNESS_VERIFY_STATE", root / ".harness-runtime" / "verification-gates.json"))
    if not args.force and reusable_gate(
        state_path, key=fingerprint, tier=args.tier, subsystem=subsystem, commands=commands
    ):
        print(f"REUSED {gate_name(args.tier, subsystem)} · {fingerprint} · 相同代码、环境与命令集已通过")
        return 0
    result = run_plan(root, commands)
    if result == 0:
        save_gate(state_path, key=fingerprint, tier=args.tier, subsystem=subsystem, commands=commands)
        print(f"VERIFIED {gate_name(args.tier, subsystem)} · {fingerprint}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())

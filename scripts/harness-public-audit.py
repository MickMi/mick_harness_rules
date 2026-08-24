#!/usr/bin/env python3
"""Fail a public Harness release that contains private instance defaults."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess


LEGACY_BRAIN = ".mick" + "-brain"
PERSONAL_OWNER = "Mick" + "Mi"
PERSONAL_USER = "mick" + "mi"
PERSONAL_BRAIN_REMOTE = f"{PERSONAL_OWNER}/" + "mick_brain"
PERSONAL_PROJECT = "Rali" + "Tennis"
PERSONAL_CAPSULE_SENTENCE = "Mick " + "是懂技术的产品经理"

LEGACY_ALLOWLIST = {
    "bin/harness",
    "rules/skills/prd-for-humans/scripts/resolve_profile.py",
    "scripts/brain-init.sh",
    "scripts/brain-resolve.sh",
    "scripts/harness-brain-boundary.py",
    "scripts/harness-public-audit.py",
    "scripts/harness-skill-manager.py",
}

SECRET_PATTERNS = (
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
)


def candidate_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [root / value for value in result.stdout.splitlines() if (root / value).is_file()]


def audit_root(root: Path) -> list[str]:
    root = root.resolve()
    issues: list[str] = []
    if (root / ".brain-owner").exists():
        issues.append(".brain-owner: private instance identity must not be tracked")

    for path in candidate_files(root):
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if f"/Users/{PERSONAL_USER}" in text:
            issues.append(f"{relative}: personal absolute home path")
        if PERSONAL_BRAIN_REMOTE in text:
            issues.append(f"{relative}: personal Brain remote")
        if PERSONAL_PROJECT in text:
            issues.append(f"{relative}: personal project name")
        if PERSONAL_CAPSULE_SENTENCE in text:
            issues.append(f"{relative}: hard-coded personal identity profile")
        if re.search(rf"(?m)^owner:\s*{re.escape(PERSONAL_OWNER)}\s*$", text):
            issues.append(f"{relative}: personal owner identity")
        if re.search(rf"(?m)^system_user:\s*{re.escape(PERSONAL_USER)}\s*$", text):
            issues.append(f"{relative}: personal system user")
        if LEGACY_BRAIN in text and relative not in LEGACY_ALLOWLIST:
            issues.append(f"{relative}: legacy Brain name outside compatibility code")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                issues.append(f"{relative}: credential-shaped content")
                break

    required = {
        "config/.brain-config.yaml": 'local_path: "~/.brain"',
        "config/.harness-config.template.yaml": 'path: "~/.brain"',
    }
    for relative, marker in required.items():
        path = root / relative
        if not path.is_file() or marker not in path.read_text(encoding="utf-8"):
            issues.append(f"{relative}: public Brain default is not ~/.brain")
    return sorted(set(issues))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    issues = audit_root(args.root)
    if issues:
        print("Public release audit: FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Public release audit: PASS — generic Brain defaults, no private instance data found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

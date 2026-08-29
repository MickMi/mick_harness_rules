#!/usr/bin/env python3
"""Resolve versioned PRD Profiles without exposing private profile content."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys


SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
FRONTMATTER = re.compile(r"\A---\n(?P<body>.*?)\n---(?:\n|\Z)", re.DOTALL)


class ProfileError(RuntimeError):
    pass


def parse_frontmatter(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ProfileError(f"Profile not found: {path}")
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ProfileError(f"Profile frontmatter missing: {path}")
    values: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"\'')
    if values.get("profile") != "prd-for-humans":
        raise ProfileError(f"Unexpected profile type: {path}")
    if not SEMVER.fullmatch(values.get("version", "")):
        raise ProfileError(f"Invalid profile version: {path}")
    if values.get("status") != "active":
        raise ProfileError(f"Profile is not active: {path}")
    return values


def layer(path: Path, source: str) -> dict[str, str]:
    metadata = parse_frontmatter(path)
    return {"source": source, "version": metadata["version"], "path": str(path)}


def private_layer(brain: Path) -> dict[str, str] | None:
    directory = brain / "global" / "profiles" / "prd"
    pointer_path = directory / "current.json"
    if not pointer_path.is_file():
        return None
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ProfileError(f"Invalid private profile pointer: {error}") from error
    if pointer.get("schema_version") != "1" or pointer.get("profile") != "prd-for-humans":
        raise ProfileError("Unsupported private profile pointer")
    filename = pointer.get("file")
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise ProfileError("Private profile file must be a basename")
    result = layer(directory / filename, "private_brain")
    if result["version"] != pointer.get("version"):
        raise ProfileError("Private profile pointer version does not match its file")
    return result


def resolve_profile(*, project: Path, brain: Path, skill_root: Path) -> dict[str, object]:
    layers: list[dict[str, str]] = []
    diagnostics: list[dict[str, str]] = []
    project_path = project / "docs" / "PRD-PROFILE.md"
    if project_path.is_file():
        try:
            layers.append(layer(project_path, "project"))
        except ProfileError as error:
            diagnostics.append({"source": "project", "status": "invalid", "message": str(error)})
    try:
        private = private_layer(brain)
        if private:
            layers.append(private)
    except ProfileError as error:
        diagnostics.append({"source": "private_brain", "status": "invalid", "message": str(error)})
    layers.append(layer(skill_root / "references" / "default-profile.md", "generic"))
    return {"schema_version": "1", "active": layers[0], "layers": layers, "diagnostics": diagnostics}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    preferred = Path.home() / ".brain"
    legacy = Path.home() / ".mick-brain"
    default_brain = legacy if not preferred.exists() and legacy.exists() else preferred
    parser.add_argument(
        "--brain",
        type=Path,
        default=Path(os.environ.get("BRAIN_DIR") or os.environ.get("MICK_BRAIN_DIR") or default_brain),
    )
    parser.add_argument("--path-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    skill_root = Path(__file__).resolve().parents[1]
    try:
        result = resolve_profile(project=args.project.resolve(), brain=args.brain.expanduser(), skill_root=skill_root)
    except ProfileError as error:
        print(f"PRD profile error: {error}", file=sys.stderr)
        return 2
    if args.path_only:
        print(result["active"]["path"])
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

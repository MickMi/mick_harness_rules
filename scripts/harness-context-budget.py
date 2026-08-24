#!/usr/bin/env python3
"""Enforce auditable byte budgets for always-loaded Harness context."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


DEFAULT_BUDGETS = {
    "core": 10 * 1024,
    "project_loader": 16 * 1024,
    "global_loader": 12 * 1024,
    "combined": 28 * 1024,
}
REQUIRED_KERNEL_MARKERS = (
    "改动前必须先读",
    "改动文件前先查 plan.md",
    "没验证 ≠ 完成",
    "Debug Card",
    "回合卡片",
    "rules/extended.md",
)


def measure(root: Path) -> dict[str, object]:
    core = root / "rules" / "core.md"
    missing = [str(path) for path in (core, root / "rules" / "extended.md", root / "generate.sh") if not path.is_file()]
    if missing:
        raise RuntimeError(f"Missing context source file(s): {', '.join(missing)}")

    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        isolated_root = temporary / "harness"
        (isolated_root / "rules").mkdir(parents=True)
        (isolated_root / "scripts").mkdir()
        (isolated_root / "dist").mkdir()
        shutil.copy2(root / "generate.sh", isolated_root / "generate.sh")
        shutil.copy2(core, isolated_root / "rules" / "core.md")
        shutil.copy2(root / "rules" / "extended.md", isolated_root / "rules" / "extended.md")
        shutil.copy2(root / "scripts" / "brain-resolve.sh", isolated_root / "scripts" / "brain-resolve.sh")

        home = temporary / "home"
        home.mkdir()
        brain = home / ".mick-brain"
        (brain / ".git").mkdir(parents=True)
        (brain / "global").mkdir()
        (brain / "global" / "agent-capsule.md").write_text("A" * 4096, encoding="utf-8")
        config = temporary / "config"
        config.mkdir()
        (config / "brain.json").write_text(
            '{"mode":"local","local_path":"~/.mick-brain","remote":null}\n',
            encoding="utf-8",
        )
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(home),
                "MICK_HARNESS_ROOT": str(root),
                "MICK_HARNESS_ACTIVITY": "0",
                "MICK_HARNESS_CONFIG_DIR": str(config),
                "MICK_HARNESS_BRAIN_LEGACY_CONFIG": str(temporary / "missing-brain.yaml"),
            }
        )
        generated = subprocess.run(
            [str(isolated_root / "generate.sh")],
            check=False,
            capture_output=True,
            env=environment,
        )
        if generated.returncode != 0:
            raise RuntimeError(generated.stderr.decode("utf-8", errors="replace").strip() or "Project loader generation failed")
        project_bytes = (isolated_root / "dist" / "AGENTS.md").read_bytes()
        result = subprocess.run(
            [str(root / "bin" / "harness"), "export", "codex", str(home)],
            check=False,
            capture_output=True,
            env=environment,
        )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip() or "Loader export failed")

    core_bytes = core.read_bytes()
    global_bytes = result.stdout
    missing_markers = [marker for marker in REQUIRED_KERNEL_MARKERS if marker not in core_bytes.decode("utf-8")]
    sizes = {
        "core": len(core_bytes),
        "project_loader": len(project_bytes),
        "global_loader": len(global_bytes),
        "combined": len(project_bytes) + len(global_bytes),
    }
    failures = [
        {"name": name, "actual": actual, "budget": DEFAULT_BUDGETS[name]}
        for name, actual in sizes.items()
        if actual > DEFAULT_BUDGETS[name]
    ]
    return {
        "schema_version": "1",
        "sizes_bytes": sizes,
        "approx_tokens": {name: (value + 3) // 4 for name, value in sizes.items()},
        "budgets_bytes": DEFAULT_BUDGETS,
        "required_kernel_markers": {"missing": missing_markers, "retained": not missing_markers},
        "failures": failures,
        "status": "passed" if not failures and not missing_markers else "failed",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the always-loaded Harness context budget.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = measure(args.root.expanduser().resolve())
    except RuntimeError as error:
        print(f"context budget error: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        sizes = report["sizes_bytes"]
        budgets = report["budgets_bytes"]
        for name in ("core", "project_loader", "global_loader", "combined"):
            print(f"{name}: {sizes[name]} / {budgets[name]} bytes")
        print(f"status: {report['status']}")
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())

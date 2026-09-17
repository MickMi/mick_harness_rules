#!/usr/bin/env python3
"""Detect technical delivery content that does not belong in a human PRD."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


RULES = (
    (
        "file-path",
        "Source or implementation file path",
        re.compile(r"(?i)(?:`|\b)(?:src|app|lib|packages?|components?|server|client|tests?)/[^`\s]+"),
    ),
    (
        "implementation",
        "Implementation, storage, interface, styling, or framework detail",
        re.compile(
            r"(?i)(?:函数名?|类名|组件树|新增.{0,20}组件|接口字段|数据库字段|REST\s*API|GraphQL|"
            r"PostgreSQL|MySQL|MongoDB|Redis|数据库|数据表|SQL\b|CSS\b|\d+(?:\.\d+)?\s*px\b|"
            r"框架版本|React\b|Vue\b|SwiftUI\b|class\s+[A-Z]|function\s+\w+|[A-Za-z_]\w*\(\))"
        ),
    ),
    (
        "ai-contract",
        "Prompt, model, machine-output, or Agent execution contract",
        re.compile(
            r"(?i)(?:System\s*Prompt|Reasoning\s*Pipeline|Data\s*Contract|Capability\s*Contract|"
            r"JSON\s*Schema|模型参数|机器输出格式|Agent\s*(?:操作|执行)步骤|提示词工程|Prompt\s*设计)"
        ),
    ),
    (
        "code-block",
        "Executable code block",
        re.compile(r"^```(?:bash|sh|zsh|python|javascript|typescript|tsx|jsx|sql|json)\s*$", re.IGNORECASE),
    ),
)


def scan_text(text: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for code, message, pattern in RULES:
            match = pattern.search(line)
            if match:
                findings.append(
                    {
                        "code": code,
                        "line": line_number,
                        "message": message,
                        "evidence": match.group(0)[:120],
                    }
                )
    return findings


class ImageReferences(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.targets: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img":
            self.targets.append((self.getpos()[0], dict(attrs).get("src") or ""))


def scan_document(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    findings = scan_text(text)
    parser = ImageReferences()
    parser.feed(text)
    targets = list(parser.targets)
    # Inline Markdown and HTML images; no network requests or chapter/style grading.
    pattern = re.compile(r'!\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+["\'][^\n]*?["\'])?\s*\)')
    for match in pattern.finditer(text):
        targets.append((text.count("\n", 0, match.start()) + 1, match.group(1) or match.group(2)))
    for line, target in sorted(targets):
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue  # Remote/data targets are explicitly outside this local check.
        local = Path(unquote(parsed.path)).expanduser()
        resolved = local if local.is_absolute() else path.parent / local
        if not target or not resolved.is_file():
            findings.append({
                "code": "missing-image", "line": line,
                "message": "Referenced local design image does not exist",
                "evidence": target[:120],
            })
    return sorted(findings, key=lambda finding: int(finding["line"]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.path.is_file():
        print(f"PRD not found: {args.path}", file=sys.stderr)
        return 2
    findings = scan_document(args.path)
    payload = {
        "path": str(args.path),
        "summary": {"violations": len(findings)},
        "findings": findings,
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif findings:
        for finding in findings:
            print(f"{args.path}:{finding['line']}: {finding['code']}: {finding['message']}")
    else:
        print(f"PRD boundary clean: {args.path}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

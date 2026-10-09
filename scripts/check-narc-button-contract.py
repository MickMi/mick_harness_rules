"""Read-only guard for the current NARC search buttons, NOT a visual UI test.

Protects existing single-line declarations and the compact action fallback.
Deliberately scoped to these views; not a general Swift parser or all-app audit.
Run explicitly with a NARC checkout; never writes project or personal data.
"""
import argparse
from pathlib import Path
import re
import sys

VIEW = "NARC/Sources/Views/InstantQuestionView.swift"
SETTINGS = "NARC/Sources/Views/InstantQuestionSettingsView.swift"
SINGLE_LINE = r"\s*\.lineLimit\(\s*1\s*\)\s*\.fixedSize\(\s*horizontal:\s*true,\s*vertical:\s*false\s*\)"


def code_only(text):
    # Keep Swift strings, discard comments so commented-out guards cannot pass.
    return re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/',
                  lambda match: match[0] if match[0].startswith('"') else " ", text)


def check_sources(view, settings):
    view, settings = code_only(view), code_only(settings)
    checks = []
    for title, label in (("已保存问答", r'Label\(\s*"已保存问答",\s*systemImage:\s*"tray\.full"\s*\)'),
                         ("模式工具栏动作", r'Label\(\s*mode\.toolbarActionTitle,\s*systemImage:\s*mode\.toolbarActionSystemImage\s*\)'),
                         ("发送", r'Label\(\s*"发送",\s*systemImage:\s*"arrow\.up"\s*\)')):
        checks.append((f"{title}：保留单行保护", bool(re.search(label + SINGLE_LINE, view))))
    checks.append(("共享保存/复制按钮：保留单行保护", bool(re.search(
        r'private func actionButton\([^\n]+\)[^{]*\{\s*Button\(action:\s*action\)\s*\{\s*'
        r'Label\(title,\s*systemImage:\s*icon\)' + SINGLE_LINE, view))))
    checks.append(("回答操作区：保留窄空间纯图标替代", bool(re.search(
        r'private var answerActions:[\s\S]*?ViewThatFits\(in:\s*\.horizontal\)[\s\S]*?'
        r'iconAction\([\s\S]*?"bookmark"[\s\S]*?iconAction\("复制本轮回答"', view))))
    checks.append(("纯图标替代：保留提示与可访问名称", bool(re.search(
        r'private func iconAction\([^\n]+\)[^{]*\{\s*Button\(action:\s*action\)\s*'
        r'\{\s*Image\(systemName:\s*icon\)\s*\}\s*\.help\(help\)\s*\.accessibilityLabel\(help\)', view))))
    checks.append(("连接验证按钮：加载态与正常态共享单行保护", bool(re.search(
        r'Label\(controller\.isCheckingConnection\s*\?\s*"验证中"\s*:\s*"验证连接",\s*systemImage:\s*"network"\)'
        + SINGLE_LINE, settings))))
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Explicit NARC checkout (read only)")
    args = parser.parse_args()
    try:
        checks = check_sources((args.project / VIEW).read_text(), (args.project / SETTINGS).read_text())
    except (OSError, UnicodeError) as error:
        print(f"未检查：无法读取目标源码（{type(error).__name__}）")
        return 2
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'} {name}")
    failed = sum(not passed for _, passed in checks)
    print(f"源码保护检查 {len(checks) - failed}/{len(checks)}；不证明真实尺寸、溢出或点击验收通过。")
    return int(bool(failed))


if __name__ == "__main__":
    sys.exit(main())

"""Synthetic negative controls; no changes to the real NARC application."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("narc_button_contract", Path(__file__).resolve().parents[1] / "scripts/check-narc-button-contract.py")
CHECK = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CHECK)
GUARD = '.lineLimit(1).fixedSize(horizontal: true, vertical: false)'
VIEW = '\n'.join(f'Label("{title}", systemImage: "{icon}"){GUARD}' for title, icon in (
    ("已保存问答", "tray.full"), ("发送", "arrow.up"))) + '\nLabel(mode.toolbarActionTitle, systemImage: mode.toolbarActionSystemImage)' + GUARD + '''
private func actionButton(_ title: String, icon: String, action: @escaping () -> Void) -> some View {
    Button(action: action) { Label(title, systemImage: icon) GUARD }
}
private var answerActions: some View {
    ViewThatFits(in: .horizontal) {
        HStack { actionButton("保存本次对话", icon: "bookmark", action: {}) }
        HStack { iconAction("保存本次对话", icon: "bookmark", action: {})
                 iconAction("复制本轮回答", icon: "doc.on.doc", action: {}) }
    }
}
private func iconAction(_ help: String, icon: String, action: @escaping () -> Void) -> some View {
    Button(action: action) { Image(systemName: icon) }.help(help).accessibilityLabel(help)
}
'''.replace('GUARD', GUARD)
SETTINGS = 'Label(controller.isCheckingConnection ? "验证中" : "验证连接", systemImage: "network")' + GUARD


class ButtonContractTests(unittest.TestCase):
    def test_current_contract_shape(self):
        checks = CHECK.check_sources(VIEW, SETTINGS)
        self.assertEqual(len(checks), 7)
        self.assertTrue(all(passed for _, passed in checks))

    def test_removed_changed_or_commented_line_protection_is_rejected(self):
        for replacement in ('', '.lineLimit(2)', '// .lineLimit(1)\n', '/* .lineLimit(1) */'):
            with self.subTest(replacement=replacement):
                changed = VIEW.replace('.lineLimit(1)', replacement, 1)
                self.assertFalse(CHECK.check_sources(changed, SETTINGS)[0][1])
        self.assertFalse(CHECK.check_sources(VIEW.replace('horizontal: true', 'horizontal: false'), SETTINGS)[3][1])

    def test_compact_fallback_and_its_help_cannot_be_removed(self):
        for before, after, index in (('ViewThatFits', 'VStack', 4), ('.help(help)', '', 5),
                                     ('.accessibilityLabel(help)', '', 5)):
            with self.subTest(before=before):
                self.assertFalse(CHECK.check_sources(VIEW.replace(before, after), SETTINGS)[index][1])
        self.assertFalse(CHECK.check_sources(VIEW, SETTINGS.replace(GUARD, ''))[6][1])

    def test_missing_view_never_counts_as_success(self):
        self.assertFalse(any(passed for _, passed in CHECK.check_sources('', '')))


if __name__ == '__main__':
    unittest.main()

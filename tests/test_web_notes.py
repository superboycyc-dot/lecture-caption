"""Real offline WebEngine/Vditor regression with synthetic documents only."""

import os
import tempfile
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer, QCoreApplication, QEvent
from web_notes import WebMarkdownEdit, editor_markdown, javascript
from notes_editor import NotesPane, export_pdf
import core
from test_pipeline import Signals

SAMPLE = (
    "# 保持时间\n\n公式 "
    + r"$t_{cd}^{src}=0$ ns。"
    + "\n\n"
    + r"\[\Delta_{\text{hold}}=t_{cd}^{dst}-\bigl(t_{cd}^{src}+t_{\text{logic}}^{\min}+t_{skew}\bigr)\]"
    + "\n\n|步骤|计算内容|结果|\n|---|---|---|\n|初始|$t_{cd}^{src}=0$ ns|0|\n|下一步|$a=b$|1|\n"
)


class WebNotesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_for(self, predicate, timeout=12):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(0.01)
        self.fail("Offline editor timed out")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = patch.object(core, "DATA_ROOT", self.root)
        self.patch.start()
        self.engine = core.Engine(Signals(), {"notes_interval": 3600})
        self.pane = NotesPane(self.engine, core.ASSET_ROOT, self.root)
        self.pane.resize(900, 650)
        self.pane.show()
        self.editor = self.pane.preview
        self.wait_for(lambda: self.editor.ready)

    def tearDown(self):
        self.pane.close()
        self.pane.deleteLater()
        self.engine.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.patch.stop()
        self.temp.cleanup()

    def test_formula_table_layout_and_lossless_edit(self):
        self.pane.set_document(SAMPLE)
        self.wait_for(lambda: javascript(self.editor.page(), "document.querySelectorAll('.katex').length") == 4)
        state = javascript(
            self.editor.page(),
            "(()=>{const math=document.querySelector('.katex');return {tables:document.querySelectorAll('table').length,rows:document.querySelectorAll('tr').length,font:parseFloat(getComputedStyle(math).fontSize),body:parseFloat(getComputedStyle(math.closest('.vditor-reset')).fontSize),errors:document.querySelectorAll('.katex-error').length};})()",
        )
        self.assertEqual((state["tables"], state["rows"], state["errors"]), (1, 3, 0))
        self.assertAlmostEqual(state["font"], state["body"], delta=1)
        # Looking at a history note must not create a new session or rewrite it.
        self.assertTrue(self.pane.flush_edits())
        self.assertFalse(self.pane.dirty)
        self.assertIsNone(self.engine.session_dir)
        javascript(
            self.editor.page(), "(()=>{editor.focus();editor.insertValue('人工补充',true);notify();return true;})()"
        )
        self.assertTrue(self.pane.flush_edits())
        self.assertIn("人工补充", self.pane.original)
        self.assertIn(r"\Delta_{\text{hold}}", self.pane.original)
        self.assertIn("$t_{cd}^{src}=0$", self.pane.original)
        self.assertNotIn("LCMATH", self.pane.original)
        self.assertEqual(self.editor.interceptor.blocked, [])
        self.pane.source_action.setChecked(True)
        self.assertIn("人工补充", self.pane.source.toPlainText())
        self.pane.source_action.setChecked(False)
        self.assertIn("人工补充", self.pane.original)

    def test_native_key_protects_text_before_renderer_callback(self):
        self.pane.set_document("# 标题\n\nSynthetic words")
        javascript(
            self.editor.page(),
            "(()=>{editor.focus();const node=document.querySelector('.vditor-ir p').firstChild;const range=document.createRange();range.selectNodeContents(node);range.collapse(false);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);return true;})()",
        )
        self.editor.setFocus()
        self.app.processEvents()
        QTest.keyClicks(self.editor.focusProxy(), "x")
        self.assertTrue(self.pane.dirty)
        self.assertTrue(self.engine.notes_editing)
        self.pane.update("# 过时更新\n\n替换内容", "notes.md")
        self.assertNotIn("过时更新", self.pane.original)
        self.wait_for(lambda: "x" in javascript(self.editor.page(), "editor.getValue()"))
        self.assertTrue(self.pane.flush_edits())
        self.assertIn("x", self.pane.original)

    def test_toolbar_formats_selection_and_heading(self):
        self.pane.set_document("# 标题\n\nSynthetic words")
        javascript(
            self.editor.page(),
            "(()=>{const node=document.querySelector('.vditor-ir p').firstChild;const range=document.createRange();range.setStart(node,0);range.setEnd(node,9);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);window.command('bold');return true;})()",
        )
        self.assertTrue(self.pane.flush_edits())
        self.assertIn("**Synthetic**", self.pane.original)
        javascript(self.editor.page(), "(()=>{window.command('h2');return true;})()")
        self.assertTrue(self.pane.flush_edits())
        self.assertIn("## ", self.pane.original)

    def test_stale_bridge_and_ime_cannot_overwrite_document(self):
        self.pane.set_document("# 新主题\n\n新内容")
        old = self.editor.epoch - 1
        self.editor.receive(old, "过时内容")
        self.assertNotIn("过时", self.editor.value)
        javascript(self.editor.page(), "(()=>{composing=true;return true;})()")
        self.assertFalse(self.pane.flush_edits())
        javascript(self.editor.page(), "(()=>{composing=false;return true;})()")
        self.assertTrue(self.pane.flush_edits())

    def test_no_cloud_request_when_editing_becomes_idle(self):
        self.engine.pending = [("00:00", "synthetic")]
        self.engine.force_notes.clear()
        self.pane.resume_after_edit()
        self.assertFalse(self.engine.force_notes.is_set())

    def test_legacy_delimiters_preserve_code(self):
        text = r"`\[code\]`" + "\n\n```tex\n" + r"\[code\]" + "\n```\n\n" + r"\(x\)"
        result = editor_markdown(text)
        self.assertIn(r"`\[code\]`", result)
        self.assertIn("```tex\n" + r"\[code\]", result)
        self.assertTrue(result.endswith("$x$"))

import os
import tempfile
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

os.environ["LECTURE_CAPTION_NO_ONBOARDING"] = "1"
os.environ["LECTURE_CAPTION_NO_UPDATE"] = "1"
from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import core
import notes_editor
from test_pipeline import Signals


class EditorTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = patch.object(core, "DATA_ROOT", self.root)
        self.patch.start()
        self.engine = core.Engine(Signals(), {"notes_interval": 3600})
        self.pane = notes_editor.NotesPane(self.engine, core.ASSET_ROOT, self.root)
        self.pane.resize(650, 500)
        self.pane.show()

    def tearDown(self):
        self.pane.end_editing()
        self.pane.close()
        self.engine.shutdown = True
        self.engine.force_notes.set()
        time.sleep(0.01)
        self.patch.stop()
        self.temp.cleanup()
        from PySide6.QtCore import QCoreApplication, QEvent

        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_highlight_roundtrip_and_code_examples_stay_literal(self):
        source = '# 主题\n\n==重点 **加粗**== 与 `==代码==`\n\n```python\nx = "==literal=="\n```\n'
        self.pane.set_document(source)
        self.assertEqual(self.pane.markdown(), source)
        cursor = self.pane.preview.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText("\n新内容")
        self.assertTrue(self.pane.flush_edits())
        result = self.pane.original
        self.assertIn("==重点 **加粗**==", result)
        self.assertIn("`==代码==`", result)
        self.assertIn('x = "==literal=="', result)
        self.assertIn("新内容", (self.engine.session_dir / "notes.md").read_text())

    def test_toolbar_shortcuts_and_source_mode_edit_in_place(self):
        self.pane.set_document("# 主题\n\nImportant words")
        cursor = self.pane.preview.document().find("Important")
        self.pane.preview.setTextCursor(cursor)
        self.pane.preview.setFocus()
        QTest.keyClick(self.pane.preview, Qt.Key_H, Qt.ControlModifier)
        self.assertIn("==Important==", self.pane.markdown())
        QTest.keyClick(self.pane.preview, Qt.Key_B, Qt.ControlModifier)
        self.assertIn("**Important**", self.pane.markdown())
        self.pane.source_action.setChecked(True)
        self.pane.source.setPlainText("# 新标题\n\n==高亮==\n\n~~划掉~~")
        self.pane.source_action.setChecked(False)
        self.assertEqual(self.pane.title.text(), "新标题")
        self.assertNotIn("==", self.pane.preview.toPlainText())
        self.assertIn("~~划掉~~", self.pane.original)
        self.assertEqual(
            [action.text() for action in self.pane.menu.actions()], ["查看源代码", "立即整理", "打开文件夹"]
        )

    def test_markdown_typing_and_paste_become_rich_text(self):
        self.pane.set_document("# 主题\n\n")
        self.pane.preview.setFocus()
        QTest.keyClicks(self.pane.preview, "==focus==")
        self.assertEqual(self.pane.preview.toPlainText(), "focus")
        self.assertIn("==focus==", self.pane.markdown())
        mime = QMimeData()
        mime.setText("\n## Definition\n\n**Invariant** holds.")
        self.pane.preview.insertFromMimeData(mime)
        self.assertNotIn("**Invariant**", self.pane.preview.toPlainText())
        self.assertIn("**Invariant**", self.pane.markdown())

    def test_focus_without_edit_does_not_block_notes_and_idle_edit_resumes(self):
        self.pane.preview.setFocus()
        self.app.processEvents()
        self.assertFalse(self.engine.notes_editing)
        self.pane.preview.insertPlainText("synthetic addition")
        self.assertTrue(self.engine.notes_editing)
        self.engine.pending = [("12:00", "synthetic lecture")]
        self.engine.force_notes.clear()
        self.pane.resume_after_edit()
        self.assertFalse(self.engine.notes_editing)
        self.assertFalse(self.pane.dirty)
        self.assertIn("synthetic addition", self.pane.original)

    def test_ai_is_deferred_while_editing_and_does_not_override_unsaved_content(self):
        self.engine.replace_document("# 原笔记\n\n原定义")
        self.pane.set_document("# 原笔记\n\n原定义")
        self.pane.preview.insertPlainText("人工补充")
        self.assertTrue(self.engine.notes_editing)
        self.pane.update("# 过时模型结果", "notes.md")
        self.assertIn("人工补充", self.pane.preview.toPlainText())
        self.engine.pending = [("12:00", "new material")]
        self.engine.process_notes()
        self.assertEqual(self.engine.pending, [("12:00", "new material")])
        self.assertTrue(self.pane.end_editing())
        self.assertFalse(self.engine.notes_editing)
        self.assertIn("人工补充", (self.engine.session_dir / "notes.md").read_text())

    def test_pdf_export_contains_rendered_document_and_is_nonempty(self):
        output = self.root / "notes.pdf"
        notes_editor.export_pdf("# 二叉树\n\n==重点== **加粗**\n\n|项目|定义|\n|---|---|\n|BST|有序|\n", output)
        self.assertTrue(output.read_bytes().startswith(b"%PDF-"))
        self.assertGreater(output.stat().st_size, 1000)

    def test_literal_highlight_delimiters_and_code_are_preserved_after_edit(self):
        self.pane.set_document("# 标题\n\n\\==literal== 与 `==code==`\n\n```\n==code block==\n```\n\nEnd")
        cursor = self.pane.preview.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(" added")
        result = self.pane.markdown()
        self.assertIn(r"\==literal", result)
        self.assertIn("`==code==`", result)
        self.assertIn("==code block==", result)
        loaded = notes_editor.markdown_document(result)
        found = loaded.find("literal")
        self.assertNotEqual(found.charFormat().background().color().name().upper(), notes_editor.HIGHLIGHT)

    def test_heading_and_code_typing_keep_markdown_semantics(self):
        self.pane.set_document("# 标题\n\n")
        self.pane.preview.setFocus()
        QTest.keyClicks(self.pane.preview, "## Definition")
        self.assertIn("## Definition", self.pane.markdown())
        self.pane.set_document("# 标题\n\n```\ncode\n```\n")
        cursor = self.pane.preview.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.pane.preview.setTextCursor(cursor)
        QTest.keyClicks(self.pane.preview, " ==literal==")
        self.assertIn("==literal==", self.pane.preview.toPlainText())
        self.assertIn("```", self.pane.markdown())

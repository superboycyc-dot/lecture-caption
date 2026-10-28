import os
import tempfile
from pathlib import Path
from unittest import TestCase

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from recent_notes import recent_notes, read_note, RecentNotesPopup


class RecentNotesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_metadata_sort_preview_and_invalid_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in (
                ("a", "# 第一课\n\n**一二三四五六七八九十甲乙丙丁戊己**"),
                ("b", "# 第二课\n\n新内容"),
                ("empty", "# 课堂笔记\n"),
            ):
                folder = root / "sessions" / name
                folder.mkdir(parents=True)
                (folder / "notes.md").write_text(content)
            os.utime(root / "sessions/a/notes.md", (1, 1))
            notes = recent_notes(root)
            self.assertEqual([n.title for n in notes], ["第二课", "第一课"])
            self.assertEqual(notes[1].preview, "一二三四五六七八九十甲乙丙丁戊")
            (root / "sessions/b/notes.md").write_bytes(b"\xff")
            self.assertEqual(len(recent_notes(root)), 1)
            with self.assertRaises(ValueError):
                read_note(root, root / "outside.md")
            (root / "sessions/link").symlink_to(root / "sessions/a", target_is_directory=True)
            self.assertEqual(len(recent_notes(root)), 1)

    def test_popup_select_and_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "sessions/a"
            folder.mkdir(parents=True)
            (folder / "notes.md").write_text("# 示例课程\n\n课堂内容预览")
            parent = QWidget()
            popup = RecentNotesPopup(parent)
            popup.populate(recent_notes(root))
            selected = []
            popup.note_selected.connect(selected.append)
            popup.show()
            self.app.processEvents()
            QTest.keyClick(popup.list, Qt.Key_Return)
            self.assertEqual(selected, [str(folder / "notes.md")])
            self.assertFalse(popup.isVisible())
            popup.show()
            QTest.keyClick(popup, Qt.Key_Escape)
            self.assertFalse(popup.isVisible())
            popup.populate([])
            popup.show()
            self.assertTrue(popup.empty.isVisible())
            popup.show()
            parent.show()
            self.app.processEvents()
            from PySide6.QtCore import QPoint

            parent.move(600, 600)
            QTest.mouseClick(parent, Qt.LeftButton, pos=QPoint(2, 2))
            self.assertFalse(popup.isVisible())
            popup.close()
            parent.close()

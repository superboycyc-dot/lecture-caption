import os
import time
from unittest import TestCase
from unittest.mock import patch

os.environ["LECTURE_CAPTION_NO_ONBOARDING"] = "1"
os.environ["LECTURE_CAPTION_NO_UPDATE"] = "1"
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
import caption
from test_ui import FakeStore


class TourTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_spotlight_blocks_recording_and_moves_targets_on_next_skip_and_resize(self):
        with patch.object(caption, "CredentialStore", FakeStore):
            win = caption.Controls()
            win.show()
            win.start_tour()
            tour = win.tour
            self.app.processEvents()
            self.assertEqual(tour.counter.text(), "Step 1 / 10")
            self.assertTrue(
                tour.target_rect().contains(tour.mapFromGlobal(win.start.mapToGlobal(win.start.rect().center())))
            )
            with patch.object(win.engine, "start") as record:
                QTest.mouseClick(
                    tour, Qt.LeftButton, pos=tour.mapFromGlobal(win.start.mapToGlobal(win.start.rect().center()))
                )
                win.toggle()
                win.focusNextPrevChild(True)
                self.assertTrue(tour.next_button.hasFocus())
                record.assert_not_called()
            tour.advance()
            self.assertEqual(tour.counter.text(), "Step 2 / 10")
            win.resize(1000, 700)
            self.app.processEvents()
            self.assertEqual(tour.size(), win.rect().size())
            self.assertTrue(tour.rect().contains(tour.card.geometry()))
            tour.skip.click()
            self.assertFalse(tour.isVisible())
            self.assertFalse(win.engine.active)
            win.close()

    def test_advanced_disclosure_and_left_aligned_menu_have_no_checkmark_gutter(self):
        with patch.object(caption, "CredentialStore", FakeStore):
            win = caption.Controls()
            self.assertEqual(win.settings_custom.text(), "高级设置")
            self.assertFalse(win.settings_custom.isChecked())
            win.settings_custom.click()
            self.assertEqual(win.settings_custom.arrowType(), Qt.DownArrow)
            self.assertTrue(win.auto_update.isChecked())
            self.assertEqual(
                [action.text() for action in win.notes.menu.actions()],
                ["查看源代码", "立即整理" if win.notes_on.isChecked() else "立即整理（自动笔记已关闭）", "打开文件夹"],
            )
            for action in win.notes.menu.actions():
                self.assertIn("text-align:left", action.defaultWidget().styleSheet())
            self.assertFalse(win.notes.tools["highlight"].icon().isNull())
            win.close()

    def test_update_default_migration_preserves_later_opt_out(self):
        import json
        import tempfile
        from pathlib import Path

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(caption, "DATA_ROOT", Path(folder)),
            patch.object(caption, "CredentialStore", FakeStore),
        ):
            config = Path(folder) / "config.json"
            config.write_text(json.dumps({"auto_update": False}))
            win = caption.Controls()
            self.assertTrue(win.auto_update.isChecked())
            win.auto_update.setChecked(False)
            win.save_preferences()
            self.assertEqual(json.loads(config.read_text())["auto_update_schema"], 1)
            win.close()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            win = caption.Controls()
            self.assertFalse(win.auto_update.isChecked())
            win.close()

    def test_menu_buttons_trigger_source_and_summary(self):
        with patch.object(caption, "CredentialStore", FakeStore):
            win = caption.Controls()
            source = win.notes.source_action
            source.defaultWidget().click()
            self.assertTrue(source.isChecked())
            self.assertEqual(source.defaultWidget().text(), "返回阅读编辑")
            source.defaultWidget().click()
            self.assertFalse(source.isChecked())
            win.notes.summary_requested.disconnect()
            from PySide6.QtTest import QSignalSpy

            spy = QSignalSpy(win.notes.summary_requested)
            win.notes.summary_action.defaultWidget().click()
            self.assertEqual(spy.count(), 1)
            win.close()

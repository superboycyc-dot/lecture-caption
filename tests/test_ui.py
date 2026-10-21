import os
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["LECTURE_CAPTION_NO_UPDATE"] = "1"
os.environ["LECTURE_CAPTION_NO_ONBOARDING"] = "1"
_tmp = tempfile.TemporaryDirectory()
os.environ.setdefault("LECTURE_CAPTION_DATA_DIR", _tmp.name)
os.environ.pop("GROQ_API_KEY", None)
from PySide6.QtWidgets import QApplication, QLineEdit
import caption


class FakeStore:
    value = "synthetic-test-key"

    def __init__(self, *a):
        pass

    def load(self):
        return self.value

    def save(self, key):
        self.value = key

    def delete(self):
        self.value = ""


class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        export = patch.object(caption, "choose_export_format", return_value="md")
        export.start()
        self.addCleanup(export.stop)

    def tearDown(self):
        from PySide6.QtCore import QCoreApplication, QEvent

        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def wait(self, predicate=None):
        # Cold CI font initialization can consume the first event-loop pass.
        # Wait for the asynchronous state, rather than assuming a 100ms timer.
        until = time.monotonic() + 5
        passes = 0
        while time.monotonic() < until:
            self.app.processEvents()
            passes += 1
            if (predicate is not None and predicate()) or (predicate is None and passes >= 30):
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for UI state")

    def test_compact_workspace_opacity_and_credential_lifecycle(self):
        with patch.object(caption, "CredentialStore", FakeStore):
            win = caption.Controls()
            win.show()
            self.wait(lambda: win.key.text() == "synthetic-test-key")
            self.assertEqual(win.key.text(), "synthetic-test-key")
            self.assertEqual(win.key.echoMode(), QLineEdit.Password)
            self.assertFalse(win.settings.isVisible())
            self.assertFalse(win.notes.isWindow())
            self.assertFalse(win.history.isWindow())
            self.assertFalse(hasattr(win, "pin_button"))
            self.assertEqual(win.status.parentWidget(), win.notes)
            self.assertEqual(win.quota.parentWidget(), win)
            win.set_server_quota("Groq 最近响应 · model · 当日请求剩余 100 / 200 · 本分钟 token 剩余 300 · 12:00:00")
            self.assertIn("当日余量：100 / 200", win.quota.text())
            self.assertIn("本机24h语音请求", win.quota.text())
            self.assertNotIn("分钟", win.quota.text())
            self.assertNotIn("12:00:00", win.quota.text())
            self.assertLess(abs(win.level.geometry().center().y() - win.quota.geometry().center().y()), 3)
            self.assertEqual(win.stt_backend.window(), win)
            self.assertEqual(win.translation_backend.window(), win)
            self.assertFalse(win.notes.has_content)
            self.assertEqual(win.notes.stack.currentIndex(), 0)
            win.opacity_slider.setValue(65)
            self.assertAlmostEqual(win.windowOpacity(), 0.65, places=2)
            win.show_settings()
            self.assertTrue(win.settings.isVisible())
            win.settings.accept()
            self.assertFalse(win.settings.isVisible())
            win.notes.update("# 课堂笔记", "empty-session")
            self.assertFalse(win.notes.has_content)
            win.engine.sections.append("## Definition\n- Invariant")
            win.notes.update("# 课堂笔记\n\n## Definition\n- Invariant", "synthetic.md")
            self.assertTrue(win.notes.has_content)
            self.assertTrue(win.notes.preview.toPlainText())
            win.key.setText("synthetic-replacement")
            win.tested(True, "success")
            self.wait(lambda: not win.credential_busy)
            self.assertEqual(win.credentials.value, "synthetic-replacement")
            win.credential_action("delete")
            self.wait(lambda: not win.credential_busy)
            self.assertEqual(win.key.text(), "")
            self.assertFalse(win.remember_key.isChecked())
            win.save_preferences()
            from core import DATA_ROOT

            self.assertNotIn("synthetic-replacement", (DATA_ROOT / "config.json").read_text())
            win.close()

    def test_history_upsert_highlight_and_reader_position(self):
        panel = caption.CaptionHistory()
        panel.resize(450, 300)
        panel.show()
        panel.append(1, "first", "翻译中")
        panel.append(1, "first", "第一句")
        self.assertEqual(len(panel.entries), 1)
        self.assertEqual(panel.entries[1][2].text(), "第一句")
        panel.append(1, "first sentence continued", "", 100, 105)
        self.assertEqual(panel.entries[1][2].text(), "第一句")
        panel.append(1, "first", "第一句", 100, 110)
        self.assertEqual(len(panel.entries), 1)
        panel.append(2, "second", "第二句")
        self.assertEqual(panel.current, 2)
        self.assertNotIn("background:#FFFFFF", panel.entries[2][0].styleSheet())
        self.assertIn("#1C1C1E", panel.entries[2][1].styleSheet())
        self.assertIn(" – ", panel.timestamps[2].text())
        self.assertIn("#3A3A3C", panel.entries[1][1].styleSheet())
        panel.set_display_mode("english")
        self.assertFalse(panel.entries[1][1].isHidden())
        self.assertTrue(panel.entries[1][2].isHidden())
        panel.set_display_mode("chinese")
        self.assertTrue(panel.entries[1][1].isHidden())
        self.assertFalse(panel.entries[1][2].isHidden())
        panel.set_display_mode("bilingual")
        self.assertFalse(panel.entries[1][1].isHidden())
        self.assertFalse(panel.entries[1][2].isHidden())
        viewport_height = panel.scroll.viewport().height()
        for i in range(3, 25):
            panel.append(i, "a long sentence " * 8, "翻译内容" * 10)
        self.wait(lambda: panel.scroll.verticalScrollBar().maximum() > 0)
        panel.reader_scrolled()
        panel.scroll.verticalScrollBar().setValue(0)
        self.wait()
        self.assertFalse(panel.follow)
        self.assertTrue(panel.latest.isVisible())
        self.assertEqual(panel.latest.parentWidget(), panel.scroll.viewport())
        self.assertEqual(panel.scroll.viewport().height(), viewport_height)
        self.assertEqual(panel.scroll.verticalScrollBar().value(), 0)
        panel.scroll.verticalScrollBar().setValue(panel.scroll.verticalScrollBar().maximum())
        self.app.processEvents()
        self.assertTrue(panel.follow)
        self.assertFalse(panel.latest.isVisible())
        panel.resume_follow()
        self.assertTrue(panel.follow)
        panel.append(1, "stale", "stale")
        self.assertEqual(panel.entries[1][1].text(), "first")
        panel.close()

    def test_pause_resume_and_stop_buttons(self):
        with patch.object(caption, "CredentialStore", FakeStore):
            win = caption.Controls()
            self.wait()

            def start(_):
                win.engine.active = True

            def stop():
                win.engine.active = False

            with (
                patch.object(win.engine, "start", side_effect=start),
                patch.object(win.engine, "stop", side_effect=stop),
            ):
                win.start.click()
                self.assertTrue(win.engine.active)
                self.assertIn("暂停", win.start.text())
                self.assertTrue(win.input.isEnabled())
                win.start.click()
                self.assertFalse(win.engine.active)
                self.assertTrue(win.paused)
                self.assertIn("继续", win.start.text())
                win.start.click()
                self.assertTrue(win.engine.active)
                win.stop_button.click()
                self.assertFalse(win.engine.active)
                self.assertFalse(win.paused)
                self.assertIn("开始", win.start.text())
                self.assertTrue(win.input.isEnabled())
            win.close()

    def test_indicator_and_live_switch_coalescing(self):
        with patch.object(caption, "CredentialStore", FakeStore):
            win = caption.Controls()
            self.wait(lambda: bool(win.key.text()))
            self.assertEqual(win._capture_state, "idle")
            win.engine.active = True
            win.sig.capture_state.emit(win.engine.gen, "recording", "")
            win.sig.status.emit("● 收音中")
            self.assertEqual(win._capture_state, "recording")
            self.assertEqual(win.status.text(), "")

            def stop():
                win.engine.active = False
                win.engine.gen += 1

            def start(device):
                win.engine.active = True
                win.engine.gen += 1
                win.sig.capture_state.emit(win.engine.gen, "recording", "")

            with (
                patch.object(win.engine, "stop", side_effect=stop) as stop_mock,
                patch.object(win.engine, "start", side_effect=start) as start_mock,
            ):
                win.stt_backend.setCurrentIndex(1 - win.stt_backend.currentIndex())
                win.translation_backend.setCurrentIndex(1 - win.translation_backend.currentIndex())
                win.input.addItem("Synthetic microphone", 999)
                win.input.setCurrentIndex(win.input.count() - 1)
                self.wait(lambda: start_mock.call_count == 1)
                self.assertEqual(stop_mock.call_count, 1)
                self.assertEqual(start_mock.call_args.args, (999,))
                self.assertTrue(win.engine.active)
                self.assertEqual(win._capture_state, "recording")
                win.sig.capture_state.emit(win.engine.gen - 1, "error", "stale input warning")
                win.sig.input_failed.emit(win.engine.gen - 1, "stale input failure")
                self.assertEqual(win._capture_state, "recording")
                self.assertTrue(win.engine.active)
                self.assertTrue(win.input.isEnabled())
                self.assertTrue(win.stt_backend.isEnabled())
                self.assertTrue(win.translation_backend.isEnabled())
                with patch.object(win, "error"):
                    win.audio_input_failed("Synthetic device disconnected")
                self.assertEqual(win.capture_indicator.text(), "!")
                self.assertEqual(win._capture_state, "error")
                win.stop_capture()
                self.assertEqual(win._capture_state, "idle")
                with patch.object(caption.QFileDialog, "getSaveFileName", return_value=("", "")):
                    self.wait(lambda: not win.finishing)
            win.close()

    def test_translation_switch_keeps_input_open(self):
        with patch.object(caption, "CredentialStore", FakeStore):
            win = caption.Controls()
            self.wait(lambda: bool(win.key.text()))
            win.engine.active = True
            win.engine.device = win.input.currentData()
            win.engine.config["stt_backend"] = win.stt_backend.currentData()
            with patch.object(win.engine, "stop") as stop, patch.object(win.engine, "start") as start:
                win.translation_backend.setCurrentIndex(1 - win.translation_backend.currentIndex())
                self.wait(lambda: not win.switch_timer.isActive())
                stop.assert_not_called()
                start.assert_not_called()
                self.assertEqual(win.engine.config["translation_backend"], win.translation_backend.currentData())
            win.engine.active = False
            win.close()

    def test_pure_local_start_does_not_require_api_key(self):
        with patch.object(caption, "CredentialStore", FakeStore):
            win = caption.Controls()
            self.wait()
            win.key.clear()
            win.stt_backend.setCurrentIndex(1)
            win.translation_backend.setCurrentIndex(1)
            win.notes_on.setChecked(False)
            with patch.object(win.engine, "start") as start, patch.object(win, "error") as error:
                win.toggle()
                start.assert_called_once()
                error.assert_not_called()
            self.assertEqual(win.engine.config["stt_backend"], "apple")
            self.assertFalse(win.engine.notes_enabled)
            win.close()

    def test_import_edit_and_export_remember_directory_without_touching_original(self):
        from pathlib import Path
        from PySide6.QtWidgets import QPlainTextEdit, QPushButton

        with tempfile.TemporaryDirectory() as tmp, patch.object(caption, "CredentialStore", FakeStore):
            root = Path(tmp)
            original = root / "previous.md"
            original.write_text("# 上节课\n- 定义")
            win = caption.Controls()
            self.wait(lambda: bool(win.key.text()))
            with patch.object(caption.QFileDialog, "getOpenFileName", return_value=(str(original), "")):
                win.import_notes()
            self.assertIn("上节课", win.engine.sections[0])
            win.notes.source_action.setChecked(True)
            win.notes.source.setPlainText("# 二叉树与不变量\n- 修改后的定义")
            self.assertTrue(win.notes.flush_edits())
            win.notes.end_editing()
            self.assertFalse(hasattr(win, "editor"))
            self.assertEqual(original.read_text(), "# 上节课\n- 定义")
            exported = root / "next.md"
            backup = win.engine.session_dir / "notes.md"
            with patch.object(caption.QFileDialog, "getSaveFileName", return_value=(str(exported), "")) as save:
                win.finish_ready(True, str(backup))
            self.assertEqual(exported.read_text(), backup.read_text())
            self.assertEqual(win.last_export_dir, str(root))
            self.assertIn("二叉树与不变量.md", save.call_args.args[2])
            with patch.object(caption.QFileDialog, "getSaveFileName", return_value=("", "")) as save:
                win.finish_ready(True, str(backup))
            self.assertTrue(save.call_args.args[2].startswith(str(root)))
            self.assertTrue(backup.exists())
            win.close()

    def test_update_defaults_about_and_active_capture_prevent_install(self):
        with patch.object(caption, "CredentialStore", FakeStore):
            win = caption.Controls()
            self.wait(lambda: bool(win.key.text()))
            self.assertTrue(win.auto_update.isChecked())
            win.show_about()
            self.assertTrue(win.about.isVisible())
            win.engine.active = True
            with patch.object(caption.updater, "launch_installer") as install, patch.object(win, "error") as error:
                win.install_update()
                install.assert_not_called()
                error.assert_called_once()
            win.engine.active = False
            win.about.close()
            win.close()

    def test_finish_pdf_choice_and_cancel_preserve_internal_markdown(self):
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp, patch.object(caption, "CredentialStore", FakeStore):
            root = Path(tmp)
            win = caption.Controls()
            self.wait(lambda: bool(win.key.text()))
            win.engine.replace_document("# 课程主题\n\n==重点== **内容**")
            backup = win.engine.session_dir / "notes.md"
            original = backup.read_bytes()
            pdf = root / "export.pdf"
            with (
                patch.object(caption, "choose_export_format", return_value="pdf"),
                patch.object(caption.QFileDialog, "getSaveFileName", return_value=(str(pdf), "PDF (*.pdf)")) as choose,
            ):
                win.finish_ready(True, str(backup))
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
            self.assertTrue(choose.call_args.args[2].endswith(".pdf"))
            self.assertEqual(backup.read_bytes(), original)
            with (
                patch.object(caption, "choose_export_format", return_value=None),
                patch.object(caption.QFileDialog, "getSaveFileName") as choose,
            ):
                win.finish_ready(True, str(backup))
                choose.assert_not_called()
            self.assertEqual(backup.read_bytes(), original)
            win.close()

    def test_manual_summary_does_not_enable_automatic_cloud_notes(self):
        with patch.object(caption, "CredentialStore", FakeStore):
            win = caption.Controls()
            self.wait(lambda: bool(win.key.text()))
            win.engine.replace_document("# 手写笔记\n\n需要整理的内容")
            win.notes_on.setChecked(False)
            with patch.object(win.engine, "configure"):
                win.summarise_now()
            self.assertFalse(win.notes_on.isChecked())
            self.assertFalse(win.engine.notes_enabled)
            self.assertTrue(win.engine.manual_summary.is_set())
            self.assertIn("需要整理的内容", win.engine.pending[0][1])
            self.assertTrue(win.stop_button.isEnabled())
            win.close()


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
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
            self.assertTrue(win.notes.status.isHidden() or not win.notes.status.isVisible())
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


if __name__ == "__main__":
    unittest.main()

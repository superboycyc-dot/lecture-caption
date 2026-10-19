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

    def wait(self):
        until = time.monotonic() + 0.1
        while time.monotonic() < until:
            self.app.processEvents()
            time.sleep(0.005)

    def test_pin_opacity_and_credential_lifecycle(self):
        with patch.object(caption, "CredentialStore", FakeStore):
            win = caption.Controls()
            win.show()
            self.wait()
            self.assertEqual(win.key.text(), "synthetic-test-key")
            self.assertEqual(win.key.echoMode(), QLineEdit.Password)
            for panel in (win.overlay, win.notes):
                self.assertTrue(panel.pin_button.isChecked())
                panel.opacity_slider.setValue(65)
                self.assertAlmostEqual(panel.windowOpacity(), 0.65, places=2)
                panel.pin_button.setChecked(False)
                self.assertFalse(panel._pinned)
            win.key.setText("synthetic-replacement")
            win.tested(True, "success")
            self.wait()
            self.assertEqual(win.credentials.value, "synthetic-replacement")
            win.credential_action("delete")
            self.wait()
            self.assertEqual(win.key.text(), "")
            self.assertFalse(win.remember_key.isChecked())
            win.close()


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import time
from unittest import TestCase
from unittest.mock import Mock, patch

os.environ["LECTURE_CAPTION_NO_ONBOARDING"] = "1"
os.environ["LECTURE_CAPTION_NO_UPDATE"] = "1"
from PySide6.QtWidgets import QApplication
import caption
import onboarding
import local_services
from test_ui import FakeStore


class OnboardingTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.store = patch.object(caption, "CredentialStore", FakeStore)
        self.store.start()
        self.win = caption.Controls()
        self.win.show()
        self.wait(lambda: not self.win.credential_busy)

    def tearDown(self):
        self.win.setup_busy = False
        self.win.notes.end_editing()
        if self.win.onboarding:
            self.win.onboarding.set_busy(False)
            self.win.onboarding.reject()
        self.win.close()
        self.store.stop()
        from PySide6.QtCore import QCoreApplication, QEvent

        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def wait(self, predicate):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(0.01)
        self.fail("Timed out waiting for setup")

    def test_local_one_action_prepares_permissions_and_resources_without_capture(self):
        self.win.show_setup()
        wizard = self.win.onboarding
        wizard.source.setCurrentIndex(0)
        if self.win.input.count() == 1:
            self.win.input.addItem("Synthetic microphone", 999)
        with (
            patch.object(onboarding, "request_microphone", side_effect=lambda _, cb: cb(True)) as permission,
            patch.object(local_services, "prepare_local_resources") as resources,
            patch.object(self.win.engine, "start") as capture,
        ):
            wizard.begin_local()
            self.wait(lambda: not wizard.busy)
            permission.assert_called_once()
            resources.assert_called_once_with(speech=True, translation=True)
            capture.assert_not_called()
        self.assertEqual(self.win.stt_backend.currentData(), "apple")
        self.assertEqual(self.win.translation_backend.currentData(), "apple")
        self.assertFalse(self.win.notes_on.isChecked())
        self.assertEqual(self.win.interval.currentData(), 8)
        self.assertEqual(wizard.pages.currentWidget(), wizard.ready)
        wizard.finish()
        self.assertTrue(self.win.onboarding_seen)

    def test_cloud_paste_validates_saves_and_prepares_current_input(self):
        self.win.show_setup()
        wizard = self.win.onboarding
        wizard.source.setCurrentIndex(1)
        self.win.key.clear()
        with patch.object(wizard, "open_account") as account:
            wizard.begin_cloud()
            account.assert_called_once()
        wizard.key.setText("synthetic-onboarding-key")
        with (
            patch.object(onboarding, "validate_groq_key") as validate,
            patch.object(local_services, "request_system_audio_permission") as permission,
        ):
            wizard.submit_key()
            self.wait(lambda: not wizard.busy)
            validate.assert_called_once()
            permission.assert_called_once()
        self.assertEqual(self.win.credentials.value, "synthetic-onboarding-key")
        self.assertEqual(wizard.pages.currentWidget(), wizard.ready)
        self.assertTrue(self.win.notes_on.isChecked())
        self.assertFalse(self.win.engine.active)

    def test_failed_permission_retries_without_key_validation_and_never_records(self):
        self.win.show_setup()
        wizard = self.win.onboarding
        wizard.source.setCurrentIndex(1)
        wizard.begin_cloud()
        wizard.key.setText("synthetic-onboarding-key")
        with (
            patch.object(onboarding, "validate_groq_key") as validate,
            patch.object(
                local_services, "request_system_audio_permission", side_effect=RuntimeError("permission denied")
            ),
            patch.object(self.win.engine, "start") as capture,
        ):
            wizard.submit_key()
            self.wait(lambda: not wizard.busy)
            self.assertNotEqual(wizard.pages.currentWidget(), wizard.ready)
            with patch.object(local_services, "request_system_audio_permission"):
                wizard.submit_key()
                self.wait(lambda: not wizard.busy)
            self.assertEqual(validate.call_count, 1)
            capture.assert_not_called()

    def test_default_settings_hide_customize_and_keep_source_mode_when_preparing_permissions(self):
        self.assertFalse(self.win.settings_custom.isChecked())
        self.win.stt_backend.setCurrentIndex(self.win.stt_backend.findData("cloud"))
        self.win.translation_backend.setCurrentIndex(self.win.translation_backend.findData("apple"))
        self.win.input.setCurrentIndex(self.win.input.findData("system"))
        with (
            patch.object(local_services, "request_system_audio_permission") as permission,
            patch.object(local_services, "prepare_local_resources") as resources,
        ):
            self.win.show_setup("permissions")
            self.wait(lambda: not self.win.setup_busy)
            permission.assert_called_once()
            resources.assert_called_once_with(speech=False, translation=True)
        self.assertEqual(self.win.stt_backend.currentData(), "cloud")
        self.assertEqual(self.win.translation_backend.currentData(), "apple")

    def test_model_validation_uses_only_official_models_endpoint_and_hides_response_body(self):
        response = Mock(ok=False, status_code=401, text="private provider body")
        with patch.object(onboarding.requests, "get", return_value=response) as request:
            with self.assertRaises(RuntimeError) as error:
                onboarding.validate_groq_key("synthetic-key", ["model"])
        self.assertNotIn("private provider body", str(error.exception))
        self.assertEqual(request.call_args.args[0], "https://api.groq.com/openai/v1/models")
        self.assertNotIn("json", request.call_args.kwargs)

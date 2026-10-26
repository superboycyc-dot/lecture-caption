"""Mandatory use-rule acceptance is separate from default-off numeric sharing."""

import json
import tempfile
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
import caption
import core
import onboarding
import usage_sync
from software_rules import RULES_VERSION
from test_ui import FakeStore


class RulesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for target, name, value in (
            (caption, "DATA_ROOT", self.root),
            (core, "DATA_ROOT", self.root),
            (caption, "CredentialStore", FakeStore),
            (usage_sync, "PUBLIC_UPLOAD_READY", False),
        ):
            context = patch.object(target, name, value)
            context.start()
            self.addCleanup(context.stop)
        self.win = caption.Controls()
        self.win.show()
        self.win.show_setup()
        self.wizard = self.win.onboarding
        self.app.processEvents()

    def tearDown(self):
        if self.win.rules_dialog:
            self.win.rules_dialog.close()
        self.win.onboarding.set_busy(False)
        self.win.onboarding.reject()
        self.win.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.temp.cleanup()

    def test_unchecked_blocks_both_routes_and_programmatic_permission_entry(self):
        self.assertFalse(self.wizard.terms_checkbox.isChecked())
        self.assertFalse(self.wizard.cloud_button.isEnabled())
        self.assertFalse(self.wizard.local_button.isEnabled())
        with (
            patch.object(onboarding, "request_microphone") as microphone,
            patch.object(self.win, "apply_setup_profile") as profile,
        ):
            self.wizard.begin_cloud()
            self.wizard.begin_local()
            self.win.show_setup("permissions")
            microphone.assert_not_called()
            profile.assert_not_called()
        self.assertEqual(self.wizard.pages.currentWidget(), self.wizard.welcome)
        self.assertIn("同意", self.wizard.message.text())

    def test_opening_link_does_not_accept_or_enable_sharing(self):
        self.wizard.terms_link.linkActivated.emit("rules")
        self.app.processEvents()
        dialog = self.win.rules_dialog
        self.assertTrue(dialog.isVisible())
        self.assertIn("用量分享", dialog.rules_view.toPlainText())
        self.assertIn("无需另行勾选", dialog.rules_view.toPlainText())
        self.assertFalse(hasattr(dialog, "usage_choice"))
        self.assertFalse(self.win.has_rules())
        self.assertFalse(self.win.engine.usage_reporter.enabled)

    def test_explicit_combined_agreement_enables_metrics(self):
        self.wizard.terms_checkbox.click()
        self.assertTrue(self.win.has_rules())
        self.assertTrue(self.wizard.cloud_button.isEnabled())
        self.assertTrue(self.wizard.local_button.isEnabled())
        self.assertTrue(self.win.usage_sharing.isChecked())
        self.assertTrue(self.win.engine.usage_reporter.enabled)
        stored = json.loads((self.root / "config.json").read_text())
        self.assertEqual(stored["rules_accepted_version"], RULES_VERSION)
        self.assertTrue(stored["usage_sharing"])

    def test_combined_consent_can_later_be_withdrawn_in_settings(self):
        self.assertFalse(self.win.engine.usage_reporter.enabled)
        self.assertFalse((self.root / "usage-sync/queue.sqlite3").exists())
        self.wizard.terms_checkbox.click()
        self.assertTrue(self.win.engine.usage_reporter.enabled)
        self.win.usage_sharing.setChecked(False)
        self.assertTrue(self.win.has_rules())
        self.assertFalse(self.win.engine.usage_reporter.enabled)
        self.assertTrue(self.wizard.cloud_button.isEnabled())

    def test_rules_row_is_only_on_first_page_and_permission_flow_stays_one_action(self):
        self.wizard.terms_checkbox.click()
        self.win.key.clear()
        with (
            patch.object(onboarding, "request_microphone", side_effect=lambda _, cb: cb(True)),
            patch.object(onboarding.local_services, "prepare_local_resources"),
            patch.object(self.wizard, "open_account"),
        ):
            self.wizard.begin_cloud()
            deadline = time.monotonic() + 3
            while self.wizard.busy and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
            self.assertFalse(self.wizard.busy)
        self.assertEqual(self.wizard.pages.currentWidget(), self.wizard.cloud)
        self.assertFalse(self.wizard.terms_checkbox.isVisible())
        self.wizard.pages.setCurrentWidget(self.wizard.ready)
        self.assertFalse(self.wizard.terms_checkbox.isVisible())

    def test_close_wizard_does_not_bypass_capture_gate(self):
        self.wizard.reject()
        with patch.object(self.win.engine, "start") as start:
            self.win.toggle()
            start.assert_not_called()
        self.assertTrue(self.wizard.isVisible())
        self.assertFalse(self.win.has_rules())

    def test_unchecking_and_busy_reset_do_not_reenable_routes(self):
        self.wizard.terms_checkbox.click()
        self.wizard.terms_checkbox.click()
        self.wizard.set_busy(True)
        self.wizard.set_busy(False)
        self.assertFalse(self.wizard.cloud_button.isEnabled())
        self.assertFalse(self.wizard.local_button.isEnabled())
        self.assertFalse(self.win.has_rules())

    def test_persisted_usage_choice_is_held_when_rules_version_is_missing(self):
        self.wizard.reject()
        self.win.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        config = json.loads((self.root / "config.json").read_text())
        config["usage_sharing"] = True
        config["rules_accepted_version"] = "old-version"
        (self.root / "config.json").write_text(json.dumps(config))
        self.win = caption.Controls()
        self.win.show()
        self.win.show_setup()
        self.wizard = self.win.onboarding
        self.assertTrue(self.win.usage_sharing.isChecked())
        self.assertFalse(self.win.has_rules())
        self.assertFalse(self.win.engine.usage_reporter.enabled)
        self.assertIsNone(self.win.engine.usage_reporter.worker)
        self.assertFalse(self.wizard.terms_checkbox.isChecked())
        self.wizard.terms_checkbox.click()
        self.assertTrue(self.win.has_rules())
        self.assertTrue(self.win.engine.usage_reporter.enabled)

    def test_published_rules_document_matches_dialog_text(self):
        from software_rules import RULES_TEXT

        self.assertEqual((caption.ROOT / "docs/SOFTWARE_RULES.zh-CN.md").read_text(), RULES_TEXT)
        self.assertIn(RULES_VERSION, RULES_TEXT)

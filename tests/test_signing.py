"""Signing paths use Keychain identity/profile references, never exported secrets."""

import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from scripts import build_native, notarize_app, build_app


class SigningTests(unittest.TestCase):
    def test_webengine_rights_are_confined_to_helper_and_enclosing_seals_refreshed(self):
        identity = "Developer ID Application: Synthetic (TESTTEAM12)"
        with patch.object(Path, "is_file", return_value=True), patch.object(build_app.subprocess, "run") as run:
            build_app.sign_webengine(Path("/synthetic/App.app"), identity)
        self.assertEqual(run.call_count, 3)
        helper, framework, app = [call.args[0] for call in run.call_args_list]
        self.assertIn("--timestamp", helper)
        self.assertTrue(helper[-1].endswith("QtWebEngineProcess.app"))
        self.assertTrue(helper[-2].endswith("QtWebEngineProcess.entitlements"))
        self.assertNotIn("--deep", framework)
        self.assertNotIn("--entitlements", framework)
        self.assertTrue(app[-2].endswith("native/Release.entitlements"))
        with patch.object(build_app.subprocess, "run") as run:
            build_app.sign_webengine(Path("/synthetic/App.app"), "")
            run.assert_not_called()

    def test_native_release_uses_identity_timestamp_and_runtime(self):
        with (
            patch.dict(os.environ, {"LECTURE_CODESIGN_IDENTITY": "Developer ID Application: Synthetic (TESTTEAM12)"}),
            patch.object(build_native.subprocess, "run") as run,
        ):
            build_native.sign_native(Path("/synthetic/tool"), "local.lecturecaption.synthetic")
        args = run.call_args.args[0]
        self.assertIn("--timestamp", args)
        self.assertIn("runtime", args)
        self.assertNotIn("-", args)

    def test_native_ci_stays_ad_hoc_without_credential(self):
        with (
            patch.dict(os.environ, {"LECTURE_CODESIGN_IDENTITY": ""}),
            patch.object(build_native.subprocess, "run") as run,
        ):
            build_native.sign_native(Path("/synthetic/tool"), "local.lecturecaption.synthetic")
        self.assertIn("-", run.call_args.args[0])
        self.assertNotIn("--timestamp", run.call_args.args[0])

    def test_notarization_refuses_ad_hoc_unsigned_or_missing_runtime(self):
        for metadata in [
            "Signature=adhoc",
            "Authority=Developer ID Application: Synthetic\nTimestamp=test",
            "Authority=Developer ID Application: Synthetic\nflags=runtime",
        ]:
            with patch.object(notarize_app.subprocess, "run", return_value=Mock(stderr=metadata)):
                with self.assertRaises(ValueError):
                    notarize_app.signed_app(Path("/synthetic/app"))
        with patch.object(
            notarize_app.subprocess,
            "run",
            return_value=Mock(stderr="Authority=Developer ID Application: Synthetic\nflags=runtime\nTimestamp=test"),
        ):
            notarize_app.signed_app(Path("/synthetic/app"))

    def test_signed_updater_rejects_other_team_or_unsigned_release(self):
        import updater
        import app_install

        for incoming in [("OTHERTEAM1", True), ("TEAMTEST01", False)]:
            with (
                patch.object(updater.sys, "frozen", True, create=True),
                patch.object(app_install, "running_bundle", return_value=Path("/Applications/Test.app")),
                patch.object(updater, "signing_publisher", side_effect=[("TEAMTEST01", True), incoming]),
                patch.object(updater.subprocess, "run") as run,
            ):
                with self.assertRaises(ValueError):
                    updater.verify_update_publisher(Path("/staged/Test.app"))
                run.assert_not_called()

    def test_signed_updater_checks_ticket_and_gatekeeper_for_same_team(self):
        import updater
        import app_install

        with (
            patch.object(updater.sys, "frozen", True, create=True),
            patch.object(app_install, "running_bundle", return_value=Path("/Applications/Test.app")),
            patch.object(updater, "signing_publisher", side_effect=[("TEAMTEST01", True), ("TEAMTEST01", True)]),
            patch.object(updater.subprocess, "run") as run,
        ):
            updater.verify_update_publisher(Path("/staged/Test.app"))
        self.assertEqual(run.call_count, 2)
        self.assertIn("stapler", run.call_args_list[0].args[0])
        self.assertEqual(run.call_args_list[1].args[0][0], "spctl")

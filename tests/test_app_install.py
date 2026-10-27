import os
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch
import app_install


class AppInstallTests(unittest.TestCase):
    def test_only_canonical_applications_locations_are_installed(self):
        self.assertTrue(app_install.installed_location(Path("/Applications/Lecture Caption.app")))
        self.assertTrue(app_install.installed_location(Path.home() / "Applications/Lecture Caption.app"))
        self.assertFalse(app_install.installed_location(Path("/tmp/Lecture Caption.app")))
        self.assertTrue(app_install.installed_location(Path("/Applications/Lecture Caption 2.app")))
        self.assertTrue(app_install.installed_location(Path("/Applications/Study/Lecture Caption.app")))
        self.assertTrue(app_install.installed_location(Path("/System/Volumes/Data/Applications/Lecture Caption.app")))
        self.assertIsNone(app_install.running_bundle())
        self.assertTrue(app_install.ensure_installed())

    def test_copy_validation_failure_existing_target_and_success_keep_source(self):
        with tempfile.TemporaryDirectory(prefix="install ' test ") as tmp:
            root = Path(tmp)
            tools = root / "tools"
            tools.mkdir()
            for name, body in {"ditto": '/bin/cp -R "$1" "$2"', "codesign": 'exit "${TEST_SIGNATURE_FAIL:-0}"'}.items():
                path = tools / name
                path.write_text("#!/bin/sh\n" + body + "\n")
                path.chmod(0o700)
            source = root / "Downloaded app.app"
            (source / "Contents").mkdir(parents=True)
            (source / "Contents/Info.plist").write_bytes(
                plistlib.dumps({"CFBundleIdentifier": "local.lecturecaption.desktop"})
            )
            target = root / "Lecture Caption.app"
            with patch.dict(os.environ, {"PATH": str(tools) + ":/usr/bin:/bin", "TEST_SIGNATURE_FAIL": "1"}):
                with self.assertRaises(Exception):
                    app_install.copy_to_applications(source, target)
            self.assertTrue(source.exists())
            self.assertFalse(target.exists())
            self.assertFalse(list(root.glob(".LectureCaption-install-*.app")))
            with patch.dict(os.environ, {"PATH": str(tools) + ":/usr/bin:/bin", "TEST_SIGNATURE_FAIL": "0"}):
                app_install.copy_to_applications(source, target)
                (target / "keep").write_text("existing")
                with self.assertRaises(Exception):
                    app_install.copy_to_applications(source, target)
            self.assertEqual((target / "keep").read_text(), "existing")
            self.assertTrue(source.exists())

    def test_admin_prompt_uses_system_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.app"
            (source / "Contents").mkdir(parents=True)
            (source / "Contents/Info.plist").write_bytes(
                plistlib.dumps({"CFBundleIdentifier": "local.lecturecaption.desktop"})
            )
            with (
                patch.object(app_install.os, "access", return_value=False),
                patch.object(app_install.subprocess, "run") as run,
            ):
                app_install.copy_to_applications(source, Path(tmp) / "target.app")
            args = run.call_args.args[0]
            self.assertEqual(args[0], "osascript")
            self.assertIn("with administrator privileges", args[-1])

    def test_reopen_waits_for_download_process_to_exit(self):
        with patch.object(app_install.subprocess, "Popen") as launch:
            app_install.launch_installed(Path("/Applications/Lecture Caption.app"))
        command = launch.call_args.args[0][-1]
        self.assertIn("kill -0", command)
        self.assertIn("exec /usr/bin/open '/Applications/Lecture Caption.app'", command)
        self.assertTrue(launch.call_args.kwargs["start_new_session"])

    def test_translocated_installed_app_skips_dialog_and_reopen_guard_stops_loop(self):
        from unittest.mock import Mock

        executable = (
            "/private/var/folders/test/AppTranslocation/uuid/d/Lecture Caption.app/Contents/MacOS/Lecture Caption"
        )
        with (
            patch.object(app_install.sys, "frozen", True, create=True),
            patch.object(app_install.sys, "executable", executable),
            patch.object(app_install, "original_bundle_path", return_value=Path("/Applications/Lecture Caption.app")),
        ):
            self.assertEqual(app_install.running_bundle(), Path("/Applications/Lecture Caption.app"))
            with patch("PySide6.QtWidgets.QMessageBox") as dialog:
                self.assertTrue(app_install.ensure_installed())
                dialog.assert_not_called()
        with (
            patch.object(app_install, "running_bundle", return_value=Path(executable).parents[2]),
            patch.object(app_install.sys, "argv", ["app", "--lecture-installed-launch"]),
            patch("PySide6.QtWidgets.QMessageBox") as dialog,
        ):
            self.assertTrue(app_install.ensure_installed())
            dialog.assert_not_called()

    def test_untranslocated_download_is_not_mistaken_for_installed(self):
        path = Path("/tmp/Downloads/Lecture Caption.app")
        self.assertEqual(app_install.original_bundle_path(path), path)
        self.assertFalse(app_install.installed_location(path))

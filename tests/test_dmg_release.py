"""Installer packaging must preserve stapled images and choose the correct Gatekeeper policy."""

import json
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch
from scripts import package_release, notarize_app


class DmgReleaseTests(TestCase):
    def test_packaging_preserves_existing_stapled_dmg_and_hashes_every_asset(self):
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text('[project]\nversion="3.0.0"\n')
            release = root / "release"
            release.mkdir()
            dmg = release / "LectureCaption-3.0.0-macOS-arm64.dmg"
            original = b"synthetic signed and stapled image"
            dmg.write_bytes(original)

            def run(command, **kwargs):
                if command[0] == "ditto":
                    Path(command[-1]).write_bytes(b"synthetic updater ZIP")
                elif command[0] == "git":
                    output = next(arg for arg in command if arg.startswith("--output="))
                    Path(output.split("=", 1)[1]).write_bytes(b"synthetic tagged source ZIP")

            with (
                patch.object(package_release, "ROOT", root),
                patch.object(package_release.subprocess, "run", side_effect=run),
                patch.object(package_release, "build_dmg") as build,
            ):
                package_release.main()
            build.assert_not_called()
            self.assertEqual(dmg.read_bytes(), original)
            lines = (release / "SHA256SUMS.txt").read_text().splitlines()
            self.assertEqual(len(lines), 3)
            for line in lines:
                expected, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256((release / name).read_bytes()).hexdigest(), expected)

    def test_dmg_notarization_submits_image_directly_and_uses_open_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dmg = root / "LectureCaption-3.0.0.dmg"
            dmg.write_bytes(b"synthetic image")
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                if command[:2] == ["codesign", "-dv"]:
                    return Mock(stderr="Authority=Developer ID Application: Synthetic\nTimestamp=test")
                if command[:3] == ["xcrun", "notarytool", "submit"]:
                    return Mock(stdout=json.dumps({"id": "synthetic-submission"}))
                if command[:3] == ["xcrun", "notarytool", "wait"]:
                    return Mock(stdout=json.dumps({"status": "Accepted"}))
                return Mock(returncode=0)

            with (
                patch.object(notarize_app, "ROOT", root),
                patch("sys.argv", ["notarize_app.py", "--profile", "synthetic-profile", "--artifact", str(dmg)]),
                patch.object(notarize_app.subprocess, "run", side_effect=run),
            ):
                notarize_app.main()
            submit = next(c for c in calls if c[:3] == ["xcrun", "notarytool", "submit"])
            self.assertEqual(submit[3], str(dmg.resolve()))
            self.assertFalse(any(c[0] == "ditto" for c in calls))
            assessment = next(c for c in calls if c[0] == "spctl")
            self.assertIn("open", assessment)
            self.assertIn("context:primary-signature", assessment)
            self.assertNotIn("execute", assessment)
            self.assertEqual(
                json.loads((root / "build/notarization-dmg/status.json").read_text())["status"], "Accepted"
            )

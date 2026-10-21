import hashlib
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch, Mock
import zipfile
import updater


class UpdaterTests(TestCase):
    def test_stable_versions_and_official_assets_only(self):
        self.assertGreater(updater.version_tuple("v2.1.0"), updater.version_tuple("2.0.9"))
        for version in ("v2.1.0-beta", "../../2.1.0", "latest"):
            with self.assertRaises(ValueError):
                updater.version_tuple(version)
        release = {
            "tag_name": "v2.1.0",
            "assets": [{"name": "app.zip", "browser_download_url": "https://other.invalid/app.zip"}],
        }
        with self.assertRaises(ValueError):
            updater.asset_url(release, "app.zip")

    def test_tampered_zip_and_traversal_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("../outside", "test")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                updater.verify_archive(path, "0" * 64)
            with self.assertRaisesRegex(ValueError, "非法路径"):
                updater.verify_archive(path, digest)

    def test_download_is_bounded(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = [b"1234", b"5678"]
        with tempfile.TemporaryDirectory() as tmp, patch.object(updater.requests, "get", return_value=response):
            with self.assertRaises(ValueError):
                updater.download("https://github.com/test", Path(tmp) / "download", 5)

    def test_no_downgrade_and_source_mode_cannot_install(self):
        with patch.object(updater, "current_version", return_value="2.1.0"):
            with self.assertRaisesRegex(ValueError, "降级"):
                updater.stage_release({"tag_name": "v2.0.0"}, Path("/unused"))
        with self.assertRaisesRegex(ValueError, "源码"):
            updater.launch_installer(Path("/unused"))

    def test_installer_swap_and_failed_signature_keep_original(self):
        import os
        import subprocess

        with tempfile.TemporaryDirectory(prefix="update shell ' ") as tmp:
            root = Path(tmp)
            tools = root / "tools"
            tools.mkdir()
            for command, body in {
                "ditto": '/bin/cp -R "$1" "$2"',
                "codesign": 'exit "${TEST_CODESIGN_FAILURE:-0}"',
                "open": "exit 0",
                "id": "echo 501",
                "mv": 'case "$1" in *update.app) if [ "${TEST_MV_FAILURE:-0}" = 1 ]; then exit 1; fi ;; esac; exec /bin/mv "$@"',
            }.items():
                file = tools / command
                file.write_text("#!/bin/sh\n" + body + "\n")
                file.chmod(0o700)
            target = root / "Lecture Caption.app"
            stage = root / "staged.app"
            stage.mkdir()
            (stage / "version").write_text("new")
            target.mkdir()
            (target / "version").write_text("old")
            script = root / "install.sh"
            script.write_text(updater.installer_script(stage, target, 2147483647))
            env = {**os.environ, "PATH": str(tools) + ":/usr/bin:/bin", "TEST_CODESIGN_FAILURE": "1"}
            result = subprocess.run(["/bin/sh", str(script)], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((target / "version").read_text(), "old")
            self.assertFalse(target.with_name("Lecture Caption.update.app").exists())
            env["TEST_CODESIGN_FAILURE"] = "0"
            env["TEST_MV_FAILURE"] = "1"
            result = subprocess.run(["/bin/sh", str(script)], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((target / "version").read_text(), "old")
            self.assertFalse(target.with_name("Lecture Caption.update.app").exists())
            env["TEST_MV_FAILURE"] = "0"
            subprocess.run(["/bin/sh", str(script)], env=env, check=True, capture_output=True)
            self.assertEqual((target / "version").read_text(), "new")
            self.assertFalse(target.with_name("Lecture Caption.rollback.app").exists())

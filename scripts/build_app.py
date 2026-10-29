"""Build a macOS app; optional Developer ID identity stays in the local Keychain."""

from pathlib import Path
import subprocess
import sys
import os
import re

ROOT = Path(__file__).resolve().parents[1]


def sign_webengine(app, identity):
    """Keep Qt's required Chromium exceptions on the helper, not the main app."""
    if not identity:
        return
    framework = app / "Contents/Frameworks/PySide6/Qt/lib/QtWebEngineCore.framework"
    helper = framework / "Versions/A/Helpers/QtWebEngineProcess.app"
    entitlements = helper / "Contents/Resources/QtWebEngineProcess.entitlements"
    if not entitlements.is_file():
        raise RuntimeError("Missing upstream Qt WebEngine helper entitlements")
    common = ["codesign", "--force", "--sign", identity, "--timestamp", "--options", "runtime"]
    subprocess.run(common + ["--entitlements", str(entitlements), str(helper)], check=True)
    # Refresh enclosing resource seals without recursively replacing helper rights.
    subprocess.run(common + [str(framework)], check=True)
    subprocess.run(common + ["--entitlements", str(ROOT / "native/Release.entitlements"), str(app)], check=True)


def main():
    identity = os.environ.get("LECTURE_CODESIGN_IDENTITY", "")
    if identity and not (
        identity.startswith("Developer ID Application:") or re.fullmatch(r"[A-Fa-f0-9]{40}", identity)
    ):
        raise SystemExit(
            "Use a Developer ID Application identity or its SHA-1 fingerprint, never a password/private key."
        )
    subprocess.run([sys.executable, str(ROOT / "scripts/collect_licenses.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/build_native.py")], check=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(ROOT / "build"),
            str(ROOT / "LectureCaption.spec"),
        ],
        check=True,
        cwd=ROOT,
    )
    app = ROOT / "dist/Lecture Caption.app"
    sign_webengine(app, identity)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    print(app)


if __name__ == "__main__":
    main()

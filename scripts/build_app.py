"""Build a macOS app; optional Developer ID identity stays in the local Keychain."""

from pathlib import Path
import subprocess
import sys
import os
import re

ROOT = Path(__file__).resolve().parents[1]


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
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    print(app)


if __name__ == "__main__":
    main()

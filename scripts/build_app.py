"""Build a self-contained, ad-hoc signed macOS application from source."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
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

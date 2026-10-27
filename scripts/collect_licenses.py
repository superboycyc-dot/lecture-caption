"""Retain licenses from the exact installed distributions used in a build."""

from pathlib import Path
from importlib import metadata
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = [
    "matplotlib",
    "contourpy",
    "cycler",
    "fonttools",
    "kiwisolver",
    "packaging",
    "pillow",
    "pyparsing",
    "python-dateutil",
    "six",
    "certifi",
    "cffi",
    "charset-normalizer",
    "idna",
    "numpy",
    "pycparser",
    "PySide6-Essentials",
    "requests",
    "scipy",
    "shiboken6",
    "sounddevice",
    "urllib3",
    "pyinstaller",
]


def main():
    output = ROOT / "licenses"
    output.mkdir(exist_ok=True)
    index = []
    for package in PACKAGES:
        dist = metadata.distribution(package)
        folder = output / f"{dist.metadata['Name']}-{dist.version}"
        count = 0
        for record in dist.files or []:
            path = Path(str(record))
            if ".dist-info" not in str(path) and package not in ["PySide6-Essentials", "sounddevice", "shiboken6"]:
                continue
            if not any(
                part.lower().startswith(("license", "licence", "copying", "notice", "copyright")) for part in path.parts
            ):
                continue
            src = Path(dist.locate_file(record))
            if not src.is_file() or src.suffix.lower() in (".py", ".pyc", ".so", ".dylib"):
                continue
            target = folder / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            count += 1
        index.append(
            f"- {dist.metadata['Name']} {dist.version}: "
            + (
                f"{count} distribution license/notice files retained."
                if count
                else "LGPL/GPL alternative; see root LGPL-3.0.txt and GPL-3.0.txt and THIRD_PARTY_NOTICES.md."
            )
        )
    for name in ["LICENSE.txt", "LICENSE"]:
        path = Path(sys.base_prefix) / name
        if path.exists():
            shutil.copy2(path, output / "Python-LICENSE.txt")
            break
    (output / "README.md").write_text(
        "# Bundled component notices\n\nGenerated from installed distribution metadata. Each component retains its own terms.\n\n"
        + "\n".join(index)
        + "\n\nQt/PySide corresponding sources: https://code.qt.io/pyside/pyside-setup.git/ and https://code.qt.io/qt/qtbase.git/ (matching release tags). See THIRD_PARTY_NOTICES.md and docs/RELEASING.md.\n"
    )
    print("\n".join(index))


if __name__ == "__main__":
    main()

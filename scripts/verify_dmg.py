"""Verify installer contents/layout and, for official builds, notarization."""

from pathlib import Path
import argparse
import os
import plistlib
import subprocess
from ds_store import DSStore


def verify(image, *, layout_only=False, expected_version=None):
    subprocess.run(["hdiutil", "verify", str(image)], check=True)
    mounted = subprocess.run(
        ["hdiutil", "attach", "-readonly", "-nobrowse", "-plist", str(image)], check=True, capture_output=True
    )
    entities = plistlib.loads(mounted.stdout)["system-entities"]
    volume = Path(next(entry["mount-point"] for entry in entities if "mount-point" in entry))
    try:
        shortcut = volume / "Applications"
        if not shortcut.is_symlink() or os.readlink(shortcut) != "/Applications":
            raise ValueError("Installer Applications shortcut is missing or invalid")
        app = volume / "Lecture Caption.app"
        info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
        if info.get("CFBundleIdentifier") != "local.lecturecaption.desktop":
            raise ValueError("Unexpected application identity")
        if expected_version and info.get("CFBundleShortVersionString") != expected_version:
            raise ValueError("Installer app version does not match release")
        with DSStore.open(str(volume / ".DS_Store"), "r") as store:
            if store["Lecture Caption.app"]["Iloc"] != (180, 235) or store["Applications"]["Iloc"] != (540, 235):
                raise ValueError("Installer drag layout is missing")
            if store["."]["icvp"]["backgroundType"] != 2:
                raise ValueError("Installer instruction background is missing")
        if not list(volume.glob(".background*")):
            raise ValueError("Installer background file is missing")
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
        if not layout_only:
            subprocess.run(["codesign", "--verify", "--strict", str(image)], check=True)
            for artifact in (image, app):
                subprocess.run(["xcrun", "stapler", "validate", str(artifact)], check=True)
            subprocess.run(
                ["spctl", "--assess", "--type", "open", "--context", "context:primary-signature", str(image)],
                check=True,
            )
            subprocess.run(["spctl", "--assess", "--type", "execute", str(app)], check=True)
        print(
            "DMG app version, Applications link, Finder layout and signatures verified:",
            info["CFBundleShortVersionString"],
        )
    finally:
        subprocess.run(["hdiutil", "detach", str(volume)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--layout-only", action="store_true", help="CI: skip notarization policy checks")
    parser.add_argument("--version")
    args = parser.parse_args()
    verify(args.image.resolve(), layout_only=args.layout_only, expected_version=args.version)

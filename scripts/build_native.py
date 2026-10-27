"""Compile native helpers for macOS Apple Silicon; no secrets or model downloads."""

from pathlib import Path
import platform
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sign_native(path, identifier):
    identity = os.environ.get("LECTURE_CODESIGN_IDENTITY") or "-"
    command = ["codesign", "--force", "--sign", identity, "--identifier", identifier]
    if identity != "-":
        command += ["--timestamp", "--options", "runtime"]
    subprocess.run(command + [str(path)], check=True)


def main():
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("Build requires an Apple Silicon Mac and Xcode Command Line Tools.")
    output = ROOT / "native" / "bin"
    output.mkdir(parents=True, exist_ok=True)
    for name, frameworks in [
        ("Keychain", ["Security"]),
        ("GroqSetup", ["AppKit", "WebKit"]),
        ("LocalSpeech", ["Speech", "AVFoundation"]),
        ("LocalTranslate", ["Translation", "SwiftUI", "AppKit"]),
        ("SystemAudio", ["ScreenCaptureKit", "CoreMedia", "AudioToolbox", "CoreGraphics"]),
    ]:
        command = [
            "xcrun",
            "swiftc",
            "-module-cache-path",
            str(ROOT / "build/swift-cache"),
            "-target",
            "arm64-apple-macosx14.0",
            str(ROOT / "native" / f"{name}.swift"),
            "-o",
            str(output / name),
        ]
        if name == "LocalSpeech":
            command += [
                "-Xlinker",
                "-sectcreate",
                "-Xlinker",
                "__TEXT",
                "-Xlinker",
                "__info_plist",
                "-Xlinker",
                str(ROOT / "native/SpeechInfo.plist"),
            ]
        for framework in frameworks:
            command += ["-framework", framework]
        subprocess.run(command, check=True)
        sign_native(output / name, f"local.lecturecaption.{name.lower()}")

    permissions = output / "Permissions.dylib"
    subprocess.run(
        [
            "xcrun",
            "swiftc",
            "-module-cache-path",
            str(ROOT / "build/swift-cache"),
            "-target",
            "arm64-apple-macosx14.0",
            "-emit-library",
            str(ROOT / "native/Permissions.swift"),
            "-framework",
            "AVFoundation",
            "-o",
            str(permissions),
        ],
        check=True,
    )
    sign_native(permissions, "local.lecturecaption.permissions")


if __name__ == "__main__":
    main()

"""Compile native helpers for macOS Apple Silicon; no secrets or model downloads."""

from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("Build requires an Apple Silicon Mac and Xcode Command Line Tools.")
    output = ROOT / "native" / "bin"
    output.mkdir(parents=True, exist_ok=True)
    for name, frameworks in [
        ("Keychain", ["Security"]),
        ("LocalSpeech", ["Speech", "AVFoundation"]),
        ("LocalTranslate", ["Translation", "SwiftUI", "AppKit"]),
        ("SystemAudio", ["ScreenCaptureKit", "CoreMedia", "AudioToolbox"]),
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
        subprocess.run(
            [
                "codesign",
                "--force",
                "--sign",
                "-",
                "--identifier",
                f"local.lecturecaption.{name.lower()}",
                str(output / name),
            ],
            check=True,
        )


if __name__ == "__main__":
    main()

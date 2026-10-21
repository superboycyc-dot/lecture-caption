"""Fail a release on accidental local data, credentials or missing inputs."""

import argparse
from pathlib import Path
import re
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def files():
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    if result.returncode == 0 and result.stdout:
        return [ROOT / p for p in result.stdout.decode().split("\0") if p]
    excluded = {".git", ".venv", "build", "dist", "release", "__pycache__"}
    return [p for p in ROOT.rglob("*") if p.is_file() and not any(x in excluded for x in p.relative_to(ROOT).parts)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if args.tag and args.tag != "v" + version:
        raise SystemExit("Tag/version mismatch")
    required = [
        "LICENSE",
        "README.md",
        "README.zh-CN.md",
        "THIRD_PARTY_NOTICES.md",
        "vendor/LICENSE",
        "vendor/UPSTREAM_COMMIT",
        "assets/AppIcon.icns",
        "native/Keychain.swift",
        "native/SystemAudio.swift",
        "native/LocalSpeech.swift",
        "native/LocalTranslate.swift",
        "local_services.py",
        "utterances.py",
        "docs/releases/v" + version + ".md",
        "licenses/LGPL-3.0.txt",
        "licenses/GPL-3.0.txt",
    ]
    for name in required:
        if not (ROOT / name).is_file():
            raise SystemExit("Missing release input: " + name)
    patterns = [
        re.compile(r"gsk_[A-Za-z0-9_-]{20,}"),
        re.compile(r"gh[pousr]_[A-Za-z0-9_]{30,}"),
        re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
        re.compile(r"-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile("/" + "Users" + r"/[A-Za-z0-9_.-]+/"),
    ]
    problems = []
    for path in files():
        relative = path.relative_to(ROOT)
        if (
            relative.name in {".env", "config.json"}
            or {"sessions", "logs"}.intersection(relative.parts)
            or path.suffix in {".jsonl", ".wav", ".aiff", ".m4a", ".mp3", ".log"}
        ):
            problems.append(str(relative) + " (private/runtime data)")
            continue
        if path.stat().st_size > 20_000_000:
            problems.append(str(relative) + " (large file belongs in release assets)")
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(pattern.search(text) for pattern in patterns):
            problems.append(str(relative) + " (possible credential or personal path)")
    if problems:
        raise SystemExit("Release check failed:\n" + "\n".join(problems))
    print(f"Release inputs and source privacy checks passed for v{version}. No live credentials were accessed.")


if __name__ == "__main__":
    main()

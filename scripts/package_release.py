"""Create the release ZIP, source archive, and SHA-256 checksums."""

from pathlib import Path
import hashlib
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    app = ROOT / "dist/Lecture Caption.app"
    target = release / f"LectureCaption-{version}-macOS-arm64.zip"
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(target)], check=True)
    source = release / f"LectureCaption-{version}-source.zip"
    subprocess.run(
        ["git", "archive", "--format=zip", f"--prefix=lecture-caption-{version}/", f"--output={source}", "HEAD"],
        cwd=ROOT,
        check=True,
    )
    lines = []
    for path in (target, source):
        digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
        lines.append(f"{digest}  {path.name}")
    (release / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

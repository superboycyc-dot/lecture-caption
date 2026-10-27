"""Official GitHub releases only; bounded downloads, checksum and bundle validation."""

from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import plistlib
import re
import shlex
import subprocess
import sys
import tempfile
import zipfile
import requests

REPOSITORY = "https://github.com/superboycyc-dot/lecture-caption"
LATEST_API = "https://api.github.com/repos/superboycyc-dot/lecture-caption/releases/latest"


def current_version():
    if getattr(sys, "frozen", False):
        info = Path(sys.executable).resolve().parents[1] / "Info.plist"
        return plistlib.loads(info.read_bytes())["CFBundleShortVersionString"]
    import tomllib

    return tomllib.loads((Path(__file__).parent / "pyproject.toml").read_text())["project"]["version"]


def version_tuple(version):
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", version):
        raise ValueError("不支持的正式版本号")
    return tuple(map(int, version.removeprefix("v").split(".")))


def latest_release():
    response = requests.get(LATEST_API, headers={"Accept": "application/vnd.github+json"}, timeout=(8, 20))
    response.raise_for_status()
    release = response.json()
    if release.get("draft") or release.get("prerelease"):
        raise ValueError("忽略非正式版本")
    version_tuple(release["tag_name"])
    return release


def asset_url(release, name):
    prefix = REPOSITORY + "/releases/download/" + release["tag_name"] + "/"
    for asset in release["assets"]:
        if asset["name"] == name and asset["browser_download_url"] == prefix + name:
            return asset["browser_download_url"]
    raise ValueError("官方发布缺少安装包或校验文件")


def download(url, destination, maximum):
    size = 0
    with requests.get(url, stream=True, timeout=(8, 40)) as response:
        response.raise_for_status()
        with destination.open("wb") as output:
            for block in response.iter_content(128 * 1024):
                size += len(block)
                if size > maximum:
                    raise ValueError("下载文件超过大小限制")
                output.write(block)


def verify_archive(path, expected):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != expected:
        raise ValueError("安装包 SHA-256 校验失败")
    with zipfile.ZipFile(path) as archive:
        size = 0
        for item in archive.infolist():
            name = PurePosixPath(item.filename)
            if name.is_absolute() or ".." in name.parts or not name.parts:
                raise ValueError("安装包包含非法路径")
            if name.parts[0] not in ("Lecture Caption.app", "__MACOSX"):
                raise ValueError("安装包包含非预期内容")
            # macOS framework symlinks are relative and may not escape the app.
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                link = PurePosixPath(archive.read(item).decode())
                depth = len(name.parts) - 1
                if link.is_absolute():
                    raise ValueError("安装包包含绝对链接")
                for part in link.parts:
                    depth += -1 if part == ".." else 0 if part == "." else 1
                    if depth < 1:
                        raise ValueError("安装包链接越界")
            size += item.file_size
            if size > 900_000_000:
                raise ValueError("安装包解压大小异常")


def signing_publisher(app):
    metadata = subprocess.run(
        ["codesign", "-dv", "--verbose=4", str(app)], check=True, capture_output=True, text=True
    ).stderr
    match = re.search(r"^TeamIdentifier=([A-Z0-9]{10})$", metadata, re.MULTILINE)
    return (match.group(1) if match else None, "Authority=Developer ID Application:" in metadata)


def verify_update_publisher(app):
    if not getattr(sys, "frozen", False):
        return
    from app_install import running_bundle

    current = running_bundle()
    if current is None:
        raise ValueError("无法确认当前应用身份")
    team, developer_id = signing_publisher(current)
    if not developer_id:
        return  # One-time migration from older ad-hoc releases uses GitHub + checksums.
    incoming_team, incoming_developer_id = signing_publisher(app)
    if not team or incoming_team != team or not incoming_developer_id:
        raise ValueError("新版开发者签名与当前应用不匹配")
    subprocess.run(["xcrun", "stapler", "validate", str(app)], check=True, capture_output=True)
    subprocess.run(["spctl", "--assess", "--type", "execute", str(app)], check=True, capture_output=True)


def stage_release(release, cache):
    version = release["tag_name"].removeprefix("v")
    if version_tuple(version) <= version_tuple(current_version()):
        raise ValueError("不会降级或重复安装当前版本")
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder = Path(tempfile.mkdtemp(prefix="update-", dir=cache))
    try:
        name = f"LectureCaption-{version}-macOS-arm64.zip"
        checks = folder / "SHA256SUMS.txt"
        package = folder / name
        download(asset_url(release, "SHA256SUMS.txt"), checks, 16_384)
        sums = {line.split()[1]: line.split()[0] for line in checks.read_text().splitlines() if len(line.split()) == 2}
        expected = sums.get(name, "")
        if not re.fullmatch("[a-f0-9]{64}", expected):
            raise ValueError("发布校验文件格式异常")
        download(asset_url(release, name), package, 250_000_000)
        verify_archive(package, expected)
        subprocess.run(["ditto", "-x", "-k", str(package), str(folder / "extracted")], check=True, capture_output=True)
        app = folder / "extracted/Lecture Caption.app"
        info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
        if (
            info.get("CFBundleIdentifier") != "local.lecturecaption.desktop"
            or info.get("CFBundleShortVersionString") != version
        ):
            raise ValueError("安装包身份或版本不匹配")
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True, capture_output=True)
        verify_update_publisher(app)
        return app
    except Exception:
        import shutil

        shutil.rmtree(folder)
        raise


def installer_script(staged, target, parent_pid):
    """Generate a transactional installer; paths are shell-quoted, never evaluated."""
    import getpass

    q = lambda path: shlex.quote(str(path))
    new = target.with_name("Lecture Caption.update.app")
    backup = target.with_name("Lecture Caption.rollback.app")
    reopen = f"if [ $(id -u) = 0 ]; then sudo -u {q(getpass.getuser())} open {q(target)}; else open {q(target)}; fi"
    return (
        "#!/bin/sh\nset -eu\ncreated=0\n"
        + f"for i in $(seq 1 120); do kill -0 {int(parent_pid)} 2>/dev/null || break; sleep 1; done\n"
        + f"if kill -0 {int(parent_pid)} 2>/dev/null; then exit 1; fi\n"
        + "recover() {\n"
        + f"if [ ! -e {q(target)} ] && [ -e {q(backup)} ]; then mv {q(backup)} {q(target)}; fi\n"
        + f'if [ "$created" = 1 ] && [ -e {q(new)} ]; then rm -rf {q(new)}; fi\n'
        + reopen
        + "\n}\ntrap recover EXIT\n"
        + f"test ! -e {q(new)}\ntest ! -e {q(backup)}\ncreated=1\n"
        + f"ditto {q(staged)} {q(new)}\n"
        + f"codesign --verify --deep --strict {q(new)}\n"
        + f"mv {q(target)} {q(backup)}\n"
        + f"mv {q(new)} {q(target)}\n"
        + f"rm -rf {q(backup)}\n"
    )


def launch_installer(staged):
    if not getattr(sys, "frozen", False):
        raise ValueError("源码运行模式不替换应用，请使用打包版本")
    from app_install import running_bundle, installed_location

    target = running_bundle()
    if target is None or not installed_location(target):
        raise ValueError("请先将应用移入“应用程序”后更新")
    # A separate process waits for normal application exit before swapping bundles.
    folder = staged.parents[1]
    script = folder / "install.sh"
    script.write_text(installer_script(staged, target, os.getpid()), encoding="utf-8")
    q = shlex.quote
    script.chmod(0o700)
    command = "/bin/sh " + q(str(script))
    if os.access(target.parent, os.W_OK) and os.access(target, os.W_OK):
        subprocess.Popen(
            ["/bin/sh", str(script)], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    else:
        # macOS owns the password prompt; no password passes through the app.
        subprocess.Popen(
            [
                "osascript",
                "-e",
                "try\n do shell script "
                + json.dumps(command)
                + " with administrator privileges\non error\n do shell script "
                + json.dumps("/usr/bin/open " + q(str(target)))
                + "\nend try",
            ],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

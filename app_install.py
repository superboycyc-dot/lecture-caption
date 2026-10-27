"""First-launch installation before capture, setup or update workers start."""

import json
import os
from pathlib import Path
import plistlib
import shlex
import subprocess
import sys
import uuid


def original_bundle_path(bundle):
    """Resolve App Translocation using Apple's original-path lookup, when available.

    Reference: apple-oss-distributions/Security, SecTranslocate.h.
    Failure leaves the path unchanged; reopening also has a one-launch loop guard.
    """
    if sys.platform != "darwin" or "AppTranslocation" not in bundle.parts:
        return bundle
    import ctypes

    cf = original = url = error = None
    try:
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        security = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
        cf.CFURLCreateFromFileSystemRepresentation.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_long,
            ctypes.c_bool,
        ]
        cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
        cf.CFURLGetFileSystemRepresentation.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_void_p, ctypes.c_long]
        cf.CFURLGetFileSystemRepresentation.restype = ctypes.c_bool
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        cf.CFRelease.restype = None
        resolver = security.SecTranslocateCreateOriginalPathForURL
        resolver.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        resolver.restype = ctypes.c_void_p
        encoded = os.fsencode(bundle)
        url = cf.CFURLCreateFromFileSystemRepresentation(None, encoded, len(encoded), True)
        if not url:
            return bundle
        error = ctypes.c_void_p()
        original = resolver(url, ctypes.byref(error))
        if original:
            buffer = ctypes.create_string_buffer(32768)
            if cf.CFURLGetFileSystemRepresentation(original, True, buffer, len(buffer)):
                return Path(os.fsdecode(buffer.value))
    except (OSError, AttributeError, ValueError):
        pass
    finally:
        if cf:
            for value in (original, url, error.value if error else None):
                if value:
                    cf.CFRelease(value)
    return bundle


def running_bundle():
    if not getattr(sys, "frozen", False):
        return None
    return original_bundle_path(Path(sys.executable).resolve().parents[2])


def installed_location(bundle):
    # A renamed app or an app in an Applications subfolder is already installed.
    path = bundle.resolve()
    return path.suffix == ".app" and any(
        root.resolve() in path.parents for root in (Path("/Applications"), Path.home() / "Applications")
    )


def copy_to_applications(source, target):
    info = plistlib.loads((source / "Contents/Info.plist").read_bytes())
    if info.get("CFBundleIdentifier") != "local.lecturecaption.desktop":
        raise ValueError("应用标识不正确")
    stage = target.parent / (".LectureCaption-install-" + uuid.uuid4().hex + ".app")
    q = lambda path: shlex.quote(str(path))
    # Only our unique staging directory may be removed. Never replace an existing app.
    command = (
        "set -eu\n"
        + f"test ! -e {q(target)}\ntest ! -e {q(stage)}\n"
        + f"cleanup() {{ rm -rf {q(stage)}; }}\ntrap cleanup EXIT\n"
        + f"ditto {q(source)} {q(stage)}\n"
        + f"codesign --verify --deep --strict {q(stage)}\n"
        + f"test ! -e {q(target)}\nmv -n {q(stage)} {q(target)}\ntest ! -e {q(stage)}\n"
    )
    if os.access(target.parent, os.W_OK):
        subprocess.run(["/bin/sh", "-c", command], check=True, timeout=180, capture_output=True)
    else:
        subprocess.run(
            ["osascript", "-e", "do shell script " + json.dumps(command) + " with administrator privileges"],
            check=True,
            timeout=240,
            capture_output=True,
        )


def launch_installed(target):
    # Wait until this Downloads/Translocation copy exits, otherwise LaunchServices
    # may simply activate this process instead of opening the installed bundle.
    pid = os.getpid()
    command = (
        f"for i in $(seq 1 120); do kill -0 {pid} 2>/dev/null || break; sleep 1; done; "
        f"kill -0 {pid} 2>/dev/null && exit 1; exec /usr/bin/open "
        + shlex.quote(str(target))
        + " --args --lecture-installed-launch"
    )
    subprocess.Popen(
        ["/bin/sh", "-c", command], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def ensure_installed():
    """Return True to continue here, False after handing off to an installed copy."""
    source = running_bundle()
    if (
        source is None
        or installed_location(source)
        or "--preview" in sys.argv
        or "--lecture-installed-launch" in sys.argv
    ):
        return True
    from PySide6.QtWidgets import QMessageBox

    target = Path("/Applications/Lecture Caption.app")
    dialog = QMessageBox()
    dialog.setWindowTitle("安装 Lecture Caption")
    dialog.setText("安装到“应用程序”，以后可直接打开并自动更新。")
    dialog.setInformativeText(
        "点击即可完成安装，无需手动拖动。不会开始录音或更改笔记与设置；原下载副本会保留。"
        if not target.exists()
        else "检测到已安装的版本。请打开它并在关于窗口检查更新；不会覆盖正在使用的程序。"
    )
    install = dialog.addButton("打开已安装版本" if target.exists() else "安装到应用程序并打开", QMessageBox.AcceptRole)
    dialog.addButton("稍后（继续使用）", QMessageBox.RejectRole)
    dialog.setDefaultButton(install)
    dialog.exec()
    if dialog.clickedButton() is not install:
        return True
    try:
        if not target.exists():
            copy_to_applications(source, target)
        info = plistlib.loads((target / "Contents/Info.plist").read_bytes())
        if info.get("CFBundleIdentifier") != "local.lecturecaption.desktop":
            raise ValueError("目标应用标识不正确")
        launch_installed(target)
        return False
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        QMessageBox.warning(
            None,
            "安装尚未完成",
            "未能完成安装或授权已取消。原程序仍保留，可继续使用，也可手动拖到“应用程序”后重新打开。",
        )
        return True

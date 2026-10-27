"""Build a Finder drag-to-Applications DMG without Finder automation."""

from pathlib import Path
import os
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def background_image(target):
    from PIL import Image, ImageDraw, ImageFont

    scale = 2
    image = Image.new("RGB", (720 * scale, 440 * scale), "#F3F7FF")
    draw = ImageDraw.Draw(image)
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
    ]
    font_path = str(next(Path(path) for path in candidates if Path(path).is_file()))

    def text(value, xy, size, color):
        font = ImageFont.truetype(font_path, size * scale)
        draw.text((xy[0] * scale, xy[1] * scale), value, fill=color, font=font, anchor="mm")

    text("Lecture Caption", (360, 52), 28, "#183658")
    text("将应用拖到右侧“应用程序”即可安装", (360, 104), 18, "#506681")
    text("Drag the app to Applications", (360, 135), 13, "#73849A")
    draw.rounded_rectangle((315 * scale, 231 * scale, 382 * scale, 239 * scale), radius=4 * scale, fill="#3984ED")
    draw.polygon([(376 * scale, 218 * scale), (397 * scale, 235 * scale), (376 * scale, 252 * scale)], fill="#3984ED")
    text("安装后，从“应用程序”打开 Lecture Caption", (360, 350), 15, "#506681")
    text("Install • Eject • Start learning", (360, 380), 12, "#73849A")
    # A TIFF tagged at 144dpi keeps Finder's 720×440 point layout crisp on Retina displays.
    image.save(target, dpi=(144, 144), compression="tiff_lzw")


def settings(app, background):
    return {
        "format": "UDZO",
        "filesystem": "HFS+",
        "files": [str(app)],
        "symlinks": {"Applications": "/Applications"},
        "icon": str(ROOT / "assets/AppIcon.icns"),
        "background": str(background),
        "window_rect": ((160, 160), (720, 440)),
        "icon_locations": {"Lecture Caption.app": (180, 235), "Applications": (540, 235)},
        "default_view": "icon-view",
        "icon_size": 112,
        "text_size": 15,
        "show_toolbar": False,
        "show_status_bar": False,
        "show_sidebar": False,
        "show_pathbar": False,
        "show_tab_view": False,
        "include_icon_view_settings": True,
        "include_list_view_settings": False,
        "hide_extensions": [],
    }


def build(app=None, target=None):
    import dmgbuild

    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    app = app or ROOT / "dist/Lecture Caption.app"
    target = target or ROOT / "release" / f"LectureCaption-{version}-macOS-arm64.dmg"
    target.parent.mkdir(parents=True, exist_ok=True)
    workspace = ROOT / "build/dmg"
    workspace.mkdir(parents=True, exist_ok=True)
    background = workspace / "installer-background.tiff"
    background_image(background)
    dmgbuild.build_dmg(str(target), f"Lecture Caption {version}", settings=settings(app, background))
    identity = os.environ.get("LECTURE_CODESIGN_IDENTITY")
    if identity:
        subprocess.run(["codesign", "--force", "--sign", identity, "--timestamp", str(target)], check=True)
        subprocess.run(["codesign", "--verify", "--strict", str(target)], check=True)
    subprocess.run(["hdiutil", "verify", str(target)], check=True)
    return target


if __name__ == "__main__":
    print(build())

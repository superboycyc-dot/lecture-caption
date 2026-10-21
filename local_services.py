"""Apple system services. No network fallback and no audio files on disk."""

import json
import platform
import subprocess
from core import NATIVE_ROOT, ApiError


def run_helper(name, payload, timeout=30, arguments=()):
    helper = NATIVE_ROOT / name
    if platform.system() != "Darwin" or not helper.exists():
        raise ApiError("Apple 本地组件不可用，请使用已打包的 Mac App，或先编译 native helpers。")
    if name == "LocalTranslate" and int(platform.mac_ver()[0].split(".")[0]) < 15:
        raise ApiError("Apple 本地翻译需要 macOS 15 或更新版本。")
    try:
        result = subprocess.run([str(helper), *arguments], input=payload, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ApiError("Apple 本地处理超时，请检查系统语言资源和权限后重试。") from None
    try:
        response = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise ApiError("Apple 本地组件未返回有效结果，请检查系统语言资源和语音识别权限。") from None
    if result.returncode or "error" in response:
        # Only fixed helper-authored messages, never raw stderr/audio/provider bodies.
        raise ApiError(response.get("error", "Apple 本地处理失败。"))
    return response.get("text", "").strip()


def transcribe(audio):
    return run_helper("LocalSpeech", audio.astype("<f4").tobytes(), timeout=45)


def translate(text):
    return run_helper("LocalTranslate", json.dumps({"text": text}).encode(), timeout=35)


def prepare_translation():
    helper = NATIVE_ROOT / "LocalTranslate"
    if platform.system() != "Darwin" or int(platform.mac_ver()[0].split(".")[0]) < 15 or not helper.exists():
        raise RuntimeError("Apple 翻译需要 macOS 15+，以及已编译的 LocalTranslate 组件。")
    subprocess.Popen(
        [str(helper), "--prepare"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def prepare_speech():
    if platform.system() != "Darwin" or int(platform.mac_ver()[0].split(".")[0]) < 26:
        raise ApiError("新的 Apple 英文语音资源管理需要 macOS 26+；旧系统请使用 Groq 或系统英文听写。")
    return run_helper("LocalSpeech", b"", timeout=600, arguments=("--prepare",))

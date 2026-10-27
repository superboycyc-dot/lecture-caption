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


def request_system_audio_permission():
    return run_helper("SystemAudio", b"", timeout=120, arguments=("--permissions",))


DICTATION_SETTINGS = "x-apple.systempreferences:com.apple.Keyboard-Settings.extension"


def prepare_local_resources(speech=True, translation=True):
    if platform.system() != "Darwin" or int(platform.mac_ver()[0].split(".")[0]) < 15:
        raise ApiError("一键本地模式需要 macOS 15+；旧系统可选择 Groq。")
    errors = []
    completed = []
    if speech:
        try:
            if int(platform.mac_ver()[0].split(".")[0]) >= 26:
                prepare_speech()
            else:
                run_helper("LocalSpeech", b"", timeout=120, arguments=("--authorize",))
                supported = run_helper("LocalSpeech", b"", arguments=("--check",))
                if supported != "supported":
                    raise ApiError("请打开系统设置 → 键盘 → 听写，启用并添加英语（美国），等待资源下载后重试。")
            completed.append("英文识别已就绪")
        except RuntimeError as error:
            errors.append("英文识别：" + str(error))
    # Always attempt the independent translation download even if speech failed.
    if translation:
        try:
            run_helper("LocalTranslate", b"", timeout=600, arguments=("--prepare-and-exit",))
            completed.append("英中翻译已就绪")
        except RuntimeError as error:
            errors.append("英中翻译：" + str(error))
    if errors:
        raise ApiError("；".join(completed + errors))
    return "；".join(completed) + "。无需 API key。"


def open_groq_setup():
    helper = NATIVE_ROOT / "GroqSetup"
    if platform.system() != "Darwin" or not helper.exists():
        return False
    subprocess.Popen([str(helper)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True

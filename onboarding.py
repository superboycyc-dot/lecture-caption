"""Short first-run setup; no capture, clipboard watching or account credential access."""

import threading
import ctypes
import uuid
import requests
from PySide6.QtCore import Qt, Signal, QUrl, QObject, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QStackedWidget,
)
import local_services

GROQ_KEYS = "https://console.groq.com/keys"


def validate_groq_key(key, models):
    """Connection/model availability only: never audio or completion requests."""
    try:
        response = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": "Bearer " + key},
            timeout=(8, 15),
        )
        if not response.ok:
            raise RuntimeError(f"验证返回 HTTP {response.status_code}。请检查 key 后重试。")
        available = {item["id"] for item in response.json()["data"]}
        if set(models) - available:
            raise RuntimeError("账号暂未开放默认模型。请到 Customize 选择账号可用的模型。")
    except requests.RequestException:
        raise RuntimeError("网络未连接或请求超时，请稍后重试。") from None
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("Groq 响应格式异常，请稍后重试。") from None


class PermissionBridge(QObject):
    done = Signal(bool)


_permission_requests = {}


def request_microphone(context, callback):
    # The native library runs in the main bundle's process and only requests consent.
    # No stream/device is opened, and UI results are marshalled onto the Qt thread.
    from core import NATIVE_ROOT

    library = ctypes.CDLL(str(NATIVE_ROOT / "Permissions.dylib"))
    bridge = PermissionBridge(context)
    ident = uuid.uuid4().hex
    c_callback = ctypes.CFUNCTYPE(None, ctypes.c_int32)(lambda allowed: bridge.done.emit(bool(allowed)))

    def finished(allowed):
        callback(allowed)

        def cleanup():
            _permission_requests.pop(ident, None)
            bridge.deleteLater()

        QTimer.singleShot(1000, cleanup)

    bridge.done.connect(finished, Qt.QueuedConnection)
    _permission_requests[ident] = (library, bridge, c_callback)
    library.lecture_request_microphone.argtypes = [type(c_callback)]
    library.lecture_request_microphone.restype = None
    library.lecture_request_microphone(c_callback)


class SetupWizard(QDialog):
    step_done = Signal(str, bool, str)

    def __init__(self, controls):
        super().__init__(controls)
        self.controls = controls
        self.busy = False
        self.profile = None
        self.verified_key = None
        self.setWindowTitle("Lecture Caption · 首次使用指南")
        self.setWindowModality(Qt.WindowModal)
        self.resize(650, 560)
        body = QVBoxLayout(self)
        body.setContentsMargins(26, 22, 26, 22)
        body.setSpacing(14)
        title = QLabel("几步准备好，专心听课")
        title.setStyleSheet("font-size:26px;font-weight:700;color:#233956;")
        body.addWidget(title)
        subtitle = QLabel("识别 → 翻译 → 整理笔记。设置时不会录音，进入课堂后点「开始」才收音。")
        subtitle.setWordWrap(True)
        body.addWidget(subtitle)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        self.welcome = QWidget()
        welcome = QVBoxLayout(self.welcome)
        welcome.setContentsMargins(0, 0, 0, 0)
        welcome.addWidget(QLabel("这次主要听什么？"))
        self.source = QComboBox()
        self.source.addItem("教室上课 · 麦克风", "microphone")
        self.source.addItem("线上会议 / 视频 · 电脑声音", "system")
        if controls.input.currentData() == "system":
            self.source.setCurrentIndex(1)
        welcome.addWidget(self.source)
        self.local_button = QPushButton("一键本地字幕\n不需要账号或 key · 首次准备 Apple 语言资源")
        self.local_button.clicked.connect(self.begin_local)
        welcome.addWidget(self.local_button)
        self.cloud_button = QPushButton("Groq 字幕 + 自动笔记（推荐）\n适合完整课堂记录 · 有免费额度，需注册并创建 key")
        self.cloud_button.setObjectName("primary")
        self.cloud_button.clicked.connect(self.begin_cloud)
        welcome.addWidget(self.cloud_button)
        hint = QLabel(
            "本地模式只做识别和翻译；自动笔记仍需 Groq。\n秒数、噪声门槛和模型参数已使用默认值，不必逐项设置。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#6C829D;")
        welcome.addWidget(hint)
        welcome.addStretch()
        self.pages.addWidget(self.welcome)
        self.cloud = QWidget()
        cloud = QVBoxLayout(self.cloud)
        cloud.setContentsMargins(0, 0, 0, 0)
        cloud.addWidget(QLabel("只需要把 Groq API key 交给软件"))
        steps = QLabel(
            "① 在官方页面登录 / 注册。\n② 点击 Create API Key，任意命名，创建后复制 key。\n③ 回到这里粘贴；软件自动验证、保存并准备权限。"
        )
        steps.setWordWrap(True)
        cloud.addWidget(steps)
        self.account = QPushButton("打开官方注册 / 创建 key 页面")
        self.account.clicked.connect(self.open_account)
        cloud.addWidget(self.account)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("粘贴刚复制的 API key")
        self.key.setText(controls.key.text())
        cloud.addWidget(self.key)
        self.connect = QPushButton("粘贴并完成配置")
        self.connect.setObjectName("primary")
        self.connect.clicked.connect(self.submit_key)
        cloud.addWidget(self.connect)
        privacy = QLabel(
            "只验证连接，不上传音频。验证后存入 macOS 钥匙串，下次无需重填。\nGroq 模式开始收音后会发送音频、原文和笔记到 Groq。"
        )
        privacy.setWordWrap(True)
        privacy.setStyleSheet("color:#6C829D;")
        cloud.addWidget(privacy)
        cloud.addStretch()
        self.pages.addWidget(self.cloud)
        self.ready = QWidget()
        ready = QVBoxLayout(self.ready)
        ready.setContentsMargins(0, 0, 0, 0)
        ready.addWidget(QLabel("记住这几个入口就够了"))
        for text in (
            "▶ 顶部「开始」收音，再点变暂停；「结束」后可保存 MD 或导出 PDF。",
            "⋯ 笔记右上角「立刻 Summary」：不用等自动整理（需 Groq）。",
            "⇥ 笔记左上角导入 .md 续课；直接在笔记中编辑，工具栏可加粗 / 高亮。",
            "⌄ 顶部第一项切换麦克风 / 电脑声音，录音中也能切。",
            "⌄ 顶部「识别」「翻译」切换本地 / Groq；双语栏切换显示。",
            "⚙ 更换具体模型或调整参数，在设置的 Customize 中展开。",
        ):
            label = QLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet("padding:8px;background:white;border-radius:7px;")
            ready.addWidget(label)
        self.finish_button = QPushButton("准备好了，进入课堂")
        self.finish_button.setObjectName("primary")
        self.finish_button.clicked.connect(self.finish)
        ready.addWidget(self.finish_button)
        self.pages.addWidget(self.ready)
        self.message = QLabel("")
        self.message.setWordWrap(True)
        self.message.setOpenExternalLinks(True)
        self.message.setStyleSheet("color:#346DAF;")
        body.addWidget(self.message)
        footer = QHBoxLayout()
        self.back = QPushButton("返回选择")
        self.back.clicked.connect(lambda: self.pages.setCurrentWidget(self.welcome))
        footer.addWidget(self.back)
        self.custom = QPushButton("Customize / 自定义")
        self.custom.clicked.connect(self.customize)
        footer.addWidget(self.custom)
        later = QPushButton("稍后设置")
        later.clicked.connect(self.reject)
        footer.addWidget(later)
        body.addLayout(footer)
        self.step_done.connect(self.on_step)
        self.pages.currentChanged.connect(
            lambda _: self.back.setVisible(self.pages.currentWidget() is not self.welcome)
        )
        self.back.hide()

    def set_busy(self, busy):
        self.busy = self.controls.setup_busy = busy
        for widget in (
            self.local_button,
            self.cloud_button,
            self.source,
            self.connect,
            self.key,
            self.back,
            self.custom,
        ):
            widget.setEnabled(not busy)
        self.controls.start.setEnabled(not busy)

    def select_source(self):
        if self.source.currentData() == "system":
            self.controls.input.setCurrentIndex(self.controls.input.findData("system"))
        elif self.controls.input.currentData() == "system":
            for index in range(self.controls.input.count()):
                if self.controls.input.itemData(index) != "system":
                    self.controls.input.setCurrentIndex(index)
                    return True
            self.message.setText("没有检测到麦克风。请连接设备，或选择「电脑声音」。")
            return False
        return True

    def begin_local(self):
        if self.busy or not self.select_source():
            return
        if not self.controls.apply_setup_profile("local"):
            return
        self.profile = "local"
        self.set_busy(True)
        self.message.setText("正在一键准备所需权限与 Apple 语言资源，首次下载可能需要几分钟…")
        self.prepare_permissions()

    def begin_cloud(self):
        if self.busy or not self.select_source():
            return
        if not self.controls.apply_setup_profile("cloud"):
            return
        self.profile = "cloud"
        self.key.setText(self.controls.key.text())
        self.pages.setCurrentWidget(self.cloud)
        self.message.setText("已有 key 可以直接粘贴；已保存的 key 可以直接点完成。")
        if self.controls.key.text().strip():
            self.connect.setText("使用现有 key 并完成配置")
        else:
            self.open_account()

    def open_account(self):
        try:
            if not local_services.open_groq_setup():
                QDesktopServices.openUrl(QUrl(GROQ_KEYS))
        except OSError:
            QDesktopServices.openUrl(QUrl(GROQ_KEYS))

    def submit_key(self):
        if self.busy:
            return
        # Clipboard access is strictly an explicit Paste button action.
        key = self.key.text().strip()
        if not key:
            key = QApplication.clipboard().text().strip()
            self.key.setText(key)
        if not key or len(key) > 1024 or any(char.isspace() for char in key):
            self.message.setText("请复制 API key（不是网址）后再点此按钮，或直接粘贴到输入框。")
            return
        self.controls.key.setText(key)
        self.set_busy(True)
        self.message.setText("正在验证并保存 key，随后自动准备权限…")
        if self.verified_key == key:
            self.prepare_permissions()
            return
        store = self.controls.credentials
        models = [
            self.controls.engine.config["stt_model"],
            self.controls.translation.currentText(),
            self.controls.note_model.currentText(),
        ]

        def run():
            try:
                validate_groq_key(key, models)
                message = "API 已验证并保存到钥匙串。"
                try:
                    store.save(key)
                except RuntimeError:
                    message = "API 已验证；钥匙串未能保存，本次仍可使用，下次需重新粘贴。"
                self.step_done.emit("key", True, message)
            except RuntimeError as error:
                self.step_done.emit("key", False, str(error))

        threading.Thread(target=run, daemon=True).start()

    def prepare_permissions(self):
        if self.controls.input.currentData() == "system":
            self.prepare_resources(True)
        else:
            try:
                request_microphone(self, self.prepare_resources)
            except (RuntimeError, OSError, AttributeError):
                self.on_step("ready", False, "麦克风权限组件不可用，请使用完整打包的 Mac 应用后重试。")

    def prepare_resources(self, microphone_allowed):
        if not microphone_allowed:
            self.on_step(
                "ready",
                False,
                '麦克风未授权。<a href="x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone">打开系统麦克风权限</a> 后点一次重试。',
            )
            return
        system = self.controls.input.currentData() == "system"
        speech = self.controls.stt_backend.currentData() == "apple"
        translation = self.controls.translation_backend.currentData() == "apple"

        def run():
            try:
                if system:
                    local_services.request_system_audio_permission()
                if speech or translation:
                    local_services.prepare_local_resources(speech=speech, translation=translation)
                self.step_done.emit("ready", True, "配置完成。权限和资源已准备，不会自动开始录音。")
            except RuntimeError as error:
                self.step_done.emit("ready", False, str(error))

        threading.Thread(target=run, daemon=True).start()

    def on_step(self, stage, ok, message):
        self.message.setText(message)
        self.controls.status.setText(message)
        if stage == "key" and ok:
            self.verified_key = self.key.text().strip()
            self.controls.key_status.setText(message)
            self.prepare_permissions()
            return
        self.set_busy(False)
        if stage == "ready" and ok:
            self.controls.save_preferences()
            self.pages.setCurrentWidget(self.ready)
        elif not ok:
            self.connect.setText("重试并完成配置")

    def finish(self):
        self.controls.onboarding_seen = True
        self.controls.save_preferences()
        self.accept()
        self.key.clear()
        self.controls.start.setFocus()
        self.controls.status.setText("准备就绪 · 点击顶部「开始」收音")

    def customize(self):
        self.hide()
        self.controls.onboarding_seen = True
        self.controls.settings_custom.setChecked(True)
        self.controls.show_settings()

    def done(self, result):
        self.controls.onboarding_seen = True
        self.controls.save_preferences()
        super().done(result)

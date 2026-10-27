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
    QCheckBox,
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
            raise RuntimeError("账号暂未开放默认模型。请到高级设置选择账号可用的模型。")
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
        self.apple_prepared = False
        self.preparing_initial = False
        self.setWindowTitle("Lecture Caption · 首次设置")
        self.setWindowModality(Qt.WindowModal)
        self.resize(600, 540)
        body = QVBoxLayout(self)
        body.setContentsMargins(28, 24, 28, 24)
        body.setSpacing(16)
        title = QLabel("让 AI 帮你听课、翻译和整理笔记")
        title.setWordWrap(True)
        title.setStyleSheet("font-size:24px;font-weight:700;color:#233956;")
        body.addWidget(title)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        self.welcome = QWidget()
        welcome = QVBoxLayout(self.welcome)
        welcome.setContentsMargins(0, 0, 0, 0)
        intro = QLabel("我们需要使用 AI 模型（由 Groq 提供免费额度），来识别课堂内容、翻译并整理成连贯笔记。")
        intro.setWordWrap(True)
        welcome.addWidget(intro)
        detail = QLabel("软件会先自动准备 Apple 本地能力，作为 Groq 不可用时的备用。设置时不会开始录音。")
        detail.setWordWrap(True)
        detail.setStyleSheet("color:#72849B;")
        welcome.addWidget(detail)
        welcome.addStretch()
        terms_row = QHBoxLayout()
        terms_row.setSpacing(2)
        self.terms_checkbox = QCheckBox("同意")
        self.terms_checkbox.setStyleSheet(controls.usage_sharing.styleSheet())
        self.terms_checkbox.setChecked(controls.has_rules())
        self.terms_link = QLabel(
            '<a href="rules" style="color:#2877E1;text-decoration:underline;">《软件使用规则》</a>并分享用量统计'
        )
        self.terms_link.setTextInteractionFlags(Qt.LinksAccessibleByMouse | Qt.LinksAccessibleByKeyboard)
        self.terms_link.linkActivated.connect(lambda _: controls.show_rules(self))
        terms_row.addWidget(self.terms_checkbox)
        terms_row.addWidget(self.terms_link)
        terms_row.addStretch()
        welcome.addLayout(terms_row)
        disclosure = QLabel("仅同步录音次数、时长及词数/字数，不上传录音或文本；联网后自动重试，可在设置中关闭。")
        disclosure.setWordWrap(True)
        disclosure.setStyleSheet("font-size:12px;color:#72849B;")
        welcome.addWidget(disclosure)
        self.cloud_button = QPushButton("连接至 Groq 取得 API")
        self.cloud_button.setObjectName("primary")
        self.cloud_button.clicked.connect(self.begin_cloud)
        welcome.addWidget(self.cloud_button)
        self.local_button = QPushButton("跳过（无法使用笔记功能）")
        self.local_button.clicked.connect(self.begin_local)
        welcome.addWidget(self.local_button)
        self.pages.addWidget(self.welcome)
        self.cloud = QWidget()
        cloud = QVBoxLayout(self.cloud)
        cloud.setContentsMargins(0, 0, 0, 0)
        steps = QLabel(
            "请按照以下步骤完成 Groq 配置：\n"
            "① 登录 / 注册 → 点击 Create API Key\n"
            "② Display Name 填：Lecture Caption\n"
            "③ Expiration 保持 No expiration，再点 Submit / Create API Key\n"
            "④ 一定要复制完整 key，再回到这里点下一步。"
        )
        steps.setStyleSheet("font-size:18px;font-weight:600;color:#233956;")
        steps.setWordWrap(True)
        cloud.addWidget(steps)
        self.account = QPushButton("打开 Groq 注册 / API 页面")
        self.account.clicked.connect(self.open_account)
        cloud.addWidget(self.account)
        self.key = QLineEdit(controls.key.text())
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("粘贴 API key，或复制后直接点下一步")
        cloud.addWidget(self.key)
        self.connect = QPushButton("下一步：验证并保存 key")
        self.connect.setObjectName("primary")
        self.connect.clicked.connect(self.submit_key)
        cloud.addWidget(self.connect)
        privacy = QLabel("key 保存到 macOS 钥匙串。注册和验证不会上传课堂内容；开始后使用 Groq 处理音频、翻译和笔记。")
        privacy.setWordWrap(True)
        privacy.setStyleSheet("color:#72849B;")
        cloud.addWidget(privacy)
        cloud.addStretch()
        self.pages.addWidget(self.cloud)
        self.ready = QWidget()
        ready = QVBoxLayout(self.ready)
        ready.setContentsMargins(0, 0, 0, 0)
        self.ready_label = QLabel("配置已完成。接下来直接在主窗口看看每个按钮的用途。")
        self.ready_label.setWordWrap(True)
        ready.addWidget(self.ready_label)
        self.backup_label = QLabel(
            "Apple 本地备用需要分别准备英文识别资源和英中翻译语言包；下载提示出现时，请点下载并等待完成。"
        )
        self.backup_label.setWordWrap(True)
        self.backup_label.setStyleSheet("font-size:16px;color:#233956;")
        ready.addWidget(self.backup_label)
        self.backup_button = QPushButton("检查 / 下载 Apple 识别与翻译资源")
        self.backup_button.clicked.connect(self.prepare_apple_backup)
        ready.addWidget(self.backup_button)
        self.dictation_button = QPushButton("打开系统听写设置（旧系统英文识别资源）")
        self.dictation_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(local_services.DICTATION_SETTINGS)))
        ready.addWidget(self.dictation_button)
        ready.addStretch()
        self.finish_button = QPushButton("下一步")
        self.finish_button.setObjectName("primary")
        self.finish_button.clicked.connect(self.finish)
        ready.addWidget(self.finish_button)
        self.pages.addWidget(self.ready)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setOpenExternalLinks(True)
        self.message.setStyleSheet("color:#346DAF;")
        body.addWidget(self.message)
        self.back = QPushButton("返回")
        self.back.clicked.connect(lambda: self.pages.setCurrentWidget(self.welcome))
        body.addWidget(self.back)
        self.back.hide()
        self.terms_checkbox.toggled.connect(self.terms_changed)
        self.update_entry_buttons()
        self.step_done.connect(self.on_step)
        self.pages.currentChanged.connect(
            lambda _: self.back.setVisible(self.pages.currentWidget() is not self.welcome)
        )
        # Preserve current input. It is taught on the actual main-window selector.
        self.source = QComboBox(self)
        self.source.hide()
        self.source.addItem("麦克风", "microphone")
        self.source.addItem("电脑声音", "system")
        self.source.setCurrentIndex(1 if controls.input.currentData() == "system" else 0)

    def terms_changed(self, checked):
        self.controls.set_rules_accepted(checked)
        if checked:
            self.message.clear()
        self.update_entry_buttons()

    def update_entry_buttons(self):
        enabled = self.controls.has_rules() and self.terms_checkbox.isChecked() and not self.busy
        self.cloud_button.setEnabled(enabled)
        self.local_button.setEnabled(enabled)

    def require_rules(self):
        if self.controls.has_rules() and self.terms_checkbox.isChecked():
            return True
        self.pages.setCurrentWidget(self.welcome)
        self.message.setText("请先阅读并同意《软件使用规则》，再继续。")
        return False

    def set_busy(self, busy):
        self.busy = self.controls.setup_busy = busy
        for widget in (
            self.local_button,
            self.cloud_button,
            self.connect,
            self.key,
            self.back,
            self.finish_button,
            self.backup_button,
            self.dictation_button,
        ):
            widget.setEnabled(not busy)
        self.terms_checkbox.setEnabled(not busy)
        self.update_entry_buttons()
        self.controls.start.setEnabled(not busy)

    def select_source(self):
        return True

    def begin_local(self):
        if self.busy or not self.require_rules():
            return
        if not self.controls.apply_setup_profile("local"):
            return
        self.profile = "local"
        self.preparing_initial = True
        self.set_busy(True)
        self.message.setText("正在自动准备 Apple 本地权限和语言资源；跳过 Groq 后不会生成笔记…")
        self.prepare_permissions()

    def begin_cloud(self):
        if self.busy or not self.require_rules():
            return
        if not self.controls.apply_setup_profile("cloud"):
            return
        self.profile = "cloud"
        self.key.setText(self.controls.key.text())
        if self.apple_prepared:
            self.show_cloud_page()
            return
        self.preparing_initial = True
        self.set_busy(True)
        self.message.setText("先自动准备 Apple 本地备用能力，随后连接 Groq。首次准备可能需要几分钟…")
        self.prepare_permissions()

    def show_cloud_page(self):
        self.pages.setCurrentWidget(self.cloud)
        if not self.controls.key.text().strip():
            self.open_account()

    def open_account(self):
        try:
            if not local_services.open_groq_setup():
                QDesktopServices.openUrl(QUrl(GROQ_KEYS))
        except OSError:
            QDesktopServices.openUrl(QUrl(GROQ_KEYS))

    def submit_key(self):
        if self.busy or not self.require_rules():
            return
        # Read clipboard only on the explicitly labeled Next action with an empty field.
        key = self.key.text().strip()
        if not key:
            key = QApplication.clipboard().text().strip()
            self.key.setText(key)
        if not key or len(key) > 1024 or any(char.isspace() for char in key):
            self.message.setText("请复制 API key（不是网址）后再点此按钮，或直接粘贴到输入框。")
            return
        self.controls.key.setText(key)
        self.set_busy(True)
        self.message.setText("正在验证并保存 key…")
        if self.verified_key == key:
            self.on_step("key", True, "API 已验证。")
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

    def prepare_apple_backup(self):
        if self.busy or not self.require_rules():
            return
        self.set_busy(True)
        self.backup_button.setEnabled(False)
        self.backup_label.setText("正在分别检查英文识别、英中翻译。请完成弹出的语言包下载；首次可能需要几分钟。")

        def run():
            try:
                message = local_services.prepare_local_resources(speech=True, translation=True)
                self.step_done.emit("backup", True, message or "英文识别及英中翻译均已准备完成。")
            except RuntimeError as error:
                self.step_done.emit("backup", False, str(error))

        threading.Thread(target=run, daemon=True).start()

    def prepare_permissions(self):
        if not self.require_rules():
            self.set_busy(False)
            return
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
        speech = self.preparing_initial or self.controls.stt_backend.currentData() == "apple"
        translation = self.preparing_initial or self.controls.translation_backend.currentData() == "apple"

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
        self.set_busy(False)
        if stage == "backup":
            self.apple_prepared = ok
            self.backup_button.setEnabled(True)
            self.backup_label.setText(
                message
                if ok
                else "尚未全部就绪：" + message + " 请重试下载；旧系统也可打开听写设置，添加英语（美国）。"
            )
            return
        if stage == "key" and ok:
            self.verified_key = self.key.text().strip()
            self.controls.key_status.setText(message)
            self.ready_label.setText("Groq 已连接，识别、翻译和自动笔记均已启用。下一步开始窗口教学。")
            self.backup_label.setText(
                "Apple 英文识别与英中翻译均已准备完成，可用作本地备用。"
                if self.apple_prepared
                else "接下来请配置 Apple 本地备用：点击下方检查 / 下载，分别完成英文识别与英中翻译语言包。Groq 已连接也建议完成此步骤。"
            )
            self.controls.save_preferences()
            self.pages.setCurrentWidget(self.ready)
            return
        if stage == "ready" and self.preparing_initial:
            self.preparing_initial = False
            self.apple_prepared = ok
            if self.profile == "cloud":
                if not ok:
                    self.message.setText("Apple 备用能力暂未准备完成：" + message + " 仍可继续配置 Groq。")
                self.show_cloud_page()
            elif ok:
                self.ready_label.setText(
                    "已启用 Apple 本地字幕。你跳过了 Groq，因此无法使用笔记整理。下一步开始窗口教学。"
                )
                self.pages.setCurrentWidget(self.ready)
            return
        if stage == "ready" and ok:
            self.controls.save_preferences()
            self.pages.setCurrentWidget(self.ready)

    def finish(self):
        if not self.require_rules():
            return
        self.controls.onboarding_seen = True
        self.controls.onboarding_flow_version = 3
        self.controls.save_preferences()
        self.accept()
        self.key.clear()
        self.controls.start_tour()

    def done(self, result):
        self.controls.onboarding_seen = True
        self.controls.onboarding_flow_version = 3
        self.controls.save_preferences()
        super().done(result)

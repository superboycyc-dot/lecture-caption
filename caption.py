from pathlib import Path
import os, sys, json, threading, subprocess
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QSlider,
    QCheckBox,
    QMessageBox,
    QTextBrowser,
    QPlainTextEdit,
    QTabWidget,
    QSizeGrip,
    QScrollArea,
    QFrame,
)
from core import ROOT, ASSET_ROOT, DATA_ROOT, Engine, DEFAULTS
import sounddevice as sd
import requests
from credentials import CredentialStore


LIGHT_STYLE = """
QWidget { background:#F3F7FC; color:#233956; font-family:"PingFang SC","Helvetica Neue"; font-size:13px; }
QLabel { background:transparent; padding:3px; }
QLineEdit,QComboBox,QPlainTextEdit,QTextBrowser { background:#FFFFFF; color:#233956; border:1px solid #D9E4F2; border-radius:9px; padding:9px; selection-background-color:#D8E9FF; selection-color:#153E78; }
QLineEdit:focus,QComboBox:focus,QPlainTextEdit:focus { border:1px solid #4288ED; }
QComboBox::drop-down { border:0; width:25px; }
QPushButton { background:#E6F0FF; color:#2264BA; border:1px solid #D3E4FC; border-radius:9px; padding:10px 12px; font-weight:600; }
QPushButton:hover { background:#D7E9FF; border-color:#A4C7F8; }
QPushButton:pressed { background:#C5DDFF; }
QPushButton:checked,QPushButton#primary { background:#2877E1; color:#FFFFFF; border:1px solid #2877E1; }
QPushButton#primary:hover { background:#1766D1; }
QPushButton:disabled { background:#EDF1F6; color:#99A6B8; border-color:#E3E9F1; }
QCheckBox { spacing:8px; background:transparent; }
QSlider { background:transparent; min-height:22px; }
QSlider::groove:horizontal { background:#DAE5F3; height:5px; border-radius:2px; }
QSlider::sub-page:horizontal { background:#5B9AEE; border-radius:2px; }
QSlider::handle:horizontal { background:white; border:2px solid #4389E8; width:13px; margin:-5px 0; border-radius:7px; }
QTabWidget::pane { border:1px solid #D9E4F2; border-radius:10px; background:white; }
QTabBar::tab { background:#E8F0FA; color:#6580A0; padding:9px 18px; border:0; margin-right:4px; border-top-left-radius:8px; border-top-right-radius:8px; }
QTabBar::tab:selected { background:white; color:#1766D1; font-weight:600; }
QScrollBar:vertical { background:transparent; width:8px; }
QScrollBar::handle:vertical { background:#BFCEE3; border-radius:4px; min-height:30px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QToolTip { background:white; color:#233956; border:1px solid #D9E4F2; padding:6px; }
"""


class Signals(QObject):
    status = Signal(str)
    caption = Signal(int, str, str)
    notes = Signal(str, str)
    error = Signal(str)
    capture_failed = Signal(str)
    note_status = Signal(str)
    level = Signal(int)
    tested = Signal(bool, str)
    credential_result = Signal(str, bool, str)


class WindowOptions:
    """Shared presentation controls; changing them never restarts capture."""

    def add_window_options(self, layout, pinned=True, opacity=100):
        self._pinned = pinned
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, pinned)
        row = QHBoxLayout()
        self.pin_button = QPushButton("Pin · 已置顶" if pinned else "Pin · 未置顶")
        self.pin_button.setCheckable(True)
        self.pin_button.setChecked(pinned)
        self.pin_button.setToolTip("保持在其他应用窗口前方；再次点击取消置顶")
        self.pin_button.toggled.connect(self.set_pinned)
        row.addWidget(self.pin_button)
        row.addStretch()
        row.addWidget(QLabel("不透明度"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setValue(opacity)
        self.opacity_slider.setMaximumWidth(140)
        self.opacity_slider.setToolTip("向左更透明；向右更清晰。文字和背景一起变化。")
        self.opacity_label = QLabel(f"{opacity}%")
        self.opacity_label.setMinimumWidth(38)
        self.opacity_slider.valueChanged.connect(self.set_opacity)
        row.addWidget(self.opacity_slider)
        row.addWidget(self.opacity_label)
        layout.addLayout(row)
        self.setWindowOpacity(opacity / 100)

    def set_opacity(self, value):
        self.setWindowOpacity(value / 100)
        self.opacity_label.setText(f"{value}%")

    def set_pinned(self, enabled):
        self._pinned = enabled
        visible = self.isVisible()
        geometry = self.geometry()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, enabled)
        self.pin_button.setText("Pin · 已置顶" if enabled else "Pin · 未置顶")
        if visible:
            self.show()
            self.setGeometry(geometry)
            self.apply_mac_pin()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.apply_mac_pin)

    def apply_mac_pin(self):
        if sys.platform != "darwin" or QApplication.platformName() in ("offscreen", "minimal") or not self.isVisible():
            return
        # Qt's native handle is an NSView. Set its NSWindow level explicitly:
        # Qt.Tool alone can disappear when another app becomes active.
        import ctypes

        objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        address = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        get = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(address)
        set_long = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(address)
        get_bits = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)(address)
        set_bits = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)(address)
        window = get(int(self.winId()), objc.sel_registerName(b"window"))
        if window:
            set_long(window, objc.sel_registerName(b"setLevel:"), 3 if self._pinned else 0)
            selector = objc.sel_registerName(b"collectionBehavior")
            bits = get_bits(window, selector)
            flags = 1 | (1 << 8)  # canJoinAllSpaces, fullScreenAuxiliary
            bits = ((bits & ~(2 | 128 | 512)) | flags) if self._pinned else (bits & ~flags)
            set_bits(window, objc.sel_registerName(b"setCollectionBehavior:"), bits)


class SubtitleWindow(WindowOptions, QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("课堂双语字幕")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(950, 250)
        self.setMinimumSize(560, 180)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        frame = QWidget()
        frame.setObjectName("subtitle")
        layout.addWidget(frame)
        body = QVBoxLayout(frame)
        body.setContentsMargins(24, 16, 24, 16)
        top = QHBoxLayout()
        title = QLabel("LECTURE  /  EN → 中文")
        title.setStyleSheet("color:#4282D6; font-size:11px; font-weight:700; letter-spacing:1px;")
        top.addWidget(title)
        top.addStretch()
        hide = QPushButton("隐藏")
        hide.clicked.connect(self.hide)
        top.addWidget(hide)
        body.addLayout(top)
        self.source = QLabel("原文字幕")
        self.target = QLabel("等待开始收音…")
        for label in (self.source, self.target):
            label.setWordWrap(True)
            label.setTextFormat(Qt.PlainText)
            body.addWidget(label)
        body.addStretch()
        row = QHBoxLayout()
        row.addWidget(QLabel("拖动空白处移动"))
        row.addStretch()
        row.addWidget(QSizeGrip(self))
        body.addLayout(row)
        self.setStyleSheet(
            LIGHT_STYLE
            + "QWidget#subtitle {background:rgba(250,253,255,242); border:1px solid #C9DCF4; border-radius:20px;} QLabel {color:#7791AF; font-size:11px;} QPushButton {padding:6px 10px;}"
        )
        self.add_window_options(body, pinned=True, opacity=100)
        self.set_font(25)
        rect = QApplication.primaryScreen().availableGeometry()
        self.move(rect.center().x() - 475, rect.bottom() - 290)

    def set_font(self, n):
        self.source.setStyleSheet(f"color:#263C59; font-size:{n - 3}px;")
        self.target.setStyleSheet(f"color:#1766D1; font-size:{n}px; font-weight:600;")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.windowHandle().startSystemMove()


class NotesWindow(WindowOptions, QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setWindowTitle("Lecture Caption · 实时 Markdown 笔记")
        self.resize(760, 760)
        body = QVBoxLayout(self)
        self.add_window_options(body, pinned=True, opacity=100)
        self.status = QLabel("收音后，每约45秒整理新增内容；原文即时保存。")
        body.addWidget(self.status)
        tabs = QTabWidget()
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(False)
        self.preview.setStyleSheet("font-size:16px; padding:18px; background:white; color:#233956;")
        self.source = QPlainTextEdit()
        self.source.setReadOnly(True)
        tabs.addTab(self.preview, "阅读")
        tabs.addTab(self.source, "Markdown 源码")
        body.addWidget(tabs)
        row = QHBoxLayout()
        update = QPushButton("立即整理")
        update.clicked.connect(self.engine.force_notes.set)
        row.addWidget(update)
        folder = QPushButton("打开笔记文件夹")
        folder.clicked.connect(self.open_folder)
        row.addWidget(folder)
        body.addLayout(row)
        self.path = QLabel("笔记保存在本机应用数据目录，可点击下方按钮打开")
        self.path.setWordWrap(True)
        body.addWidget(self.path)

    def open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.engine.session_dir or DATA_ROOT / "sessions")))

    def update(self, document, path):
        bar = self.preview.verticalScrollBar()
        follow = bar.maximum() - bar.value() < 50
        old = bar.value()
        self.preview.setMarkdown(document)
        self.source.setPlainText(document)
        self.path.setText(path)
        bar.setValue(bar.maximum() if follow else old)


class Controls(WindowOptions, QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lecture Caption · 云端课堂翻译与笔记")
        self.resize(660, 830)
        config = {}
        if (DATA_ROOT / "config.json").exists():
            try:
                config = json.loads((DATA_ROOT / "config.json").read_text())
            except Exception:
                pass
        self.sig = Signals()
        self.engine = Engine(self.sig, config)
        self.overlay = SubtitleWindow()
        self.notes = NotesWindow(self.engine)
        self.current = -1
        self.sig.status.connect(lambda s: self.status.setText(s))
        self.sig.caption.connect(self.caption)
        self.sig.notes.connect(self.notes.update)
        self.sig.note_status.connect(self.notes.status.setText)
        self.sig.error.connect(self.error)
        self.sig.capture_failed.connect(self.capture_failed)
        self.sig.tested.connect(self.tested)
        self.sig.credential_result.connect(self.credential_result)
        self.credentials = CredentialStore(ROOT, self.engine.config)
        self.credential_busy = False
        self.sig.level.connect(lambda n: self.level.setText("音量  " + "▰" * min(20, n // 5)))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        body = QVBoxLayout(content)
        body.setContentsMargins(24, 20, 24, 22)
        body.setSpacing(12)
        self.add_window_options(body, pinned=False, opacity=100)
        brand = QHBoxLayout()
        brand_icon = QLabel()
        brand_icon.setPixmap(
            QPixmap(str(ASSET_ROOT / "AppIcon.png")).scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        brand.addWidget(brand_icon)
        title = QLabel("Lecture Caption")
        title.setStyleSheet("font-size:27px; font-weight:700; color:#1B579E;")
        brand.addWidget(title)
        brand.addStretch()
        body.addLayout(brand)
        info = QLabel(
            "听懂每一句，记住每个关键点。\n课堂与线上会议 · 双语字幕 · 实时笔记\n音频和文字通过你配置的 API 处理。"
        )
        info.setWordWrap(True)
        body.addWidget(info)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        self.key = QLineEdit(os.environ.get("GROQ_API_KEY", ""))
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("启动时自动从钥匙串读取，或粘贴 gsk_…")
        form.addRow("Groq API key", self.key)
        self.input = QComboBox()
        self.input.addItem("电脑内部音频（会议 / 视频）", "system")
        try:
            default = sd.default.device[0]
            for i, device in enumerate(sd.query_devices()):
                if device["max_input_channels"] > 0:
                    self.input.addItem("麦克风 · " + device["name"], i)
                    if i == default:
                        self.input.setCurrentIndex(self.input.count() - 1)
        except Exception:
            pass
        form.addRow("输入来源", self.input)
        key_options = QHBoxLayout()
        self.remember_key = QCheckBox("验证成功后保存到钥匙串")
        self.remember_key.setChecked(True)
        key_options.addWidget(self.remember_key)
        self.save_key_button = QPushButton("保存 key")
        self.save_key_button.clicked.connect(lambda: self.credential_action("save"))
        key_options.addWidget(self.save_key_button)
        self.delete_key_button = QPushButton("删除已保存 key")
        self.delete_key_button.clicked.connect(lambda: self.credential_action("delete"))
        key_options.addWidget(self.delete_key_button)
        form.addRow(key_options)
        self.key_status = QLabel("正在检查 macOS 钥匙串…")
        self.key_status.setWordWrap(True)
        form.addRow(self.key_status)
        self.translation = QComboBox()
        self.translation.setEditable(True)
        self.translation.addItems(["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"])
        self.translation.setCurrentText(self.engine.config["translation_model"])
        form.addRow("翻译模型", self.translation)
        self.note_model = QComboBox()
        self.note_model.setEditable(True)
        self.note_model.addItems(["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"])
        self.note_model.setCurrentText(self.engine.config["notes_model"])
        form.addRow("笔记模型", self.note_model)
        self.glossary = QLineEdit()
        self.glossary.setPlaceholderText("例如 CS154, Turing machine, polynomial time 或 eigenvalue")
        form.addRow("课程术语（可选）", self.glossary)
        self.interval = QComboBox()
        self.interval.addItem("8 秒：较省额度，默认", 8)
        self.interval.addItem("5 秒：更快，额度消耗更高", 5)
        self.interval.addItem("12 秒：较省额度", 12)
        form.addRow("字幕分段上限", self.interval)
        body.addLayout(form)
        buttons = QHBoxLayout()
        self.test = QPushButton("1 · 测试 API")
        self.test.clicked.connect(self.test_key)
        buttons.addWidget(self.test)
        self.start = QPushButton("2 · 开始收音")
        self.start.setObjectName("primary")
        self.start.clicked.connect(self.toggle)
        buttons.addWidget(self.start)
        body.addLayout(buttons)
        windows = QHBoxLayout()
        subs = QPushButton("显示悬浮字幕")
        subs.clicked.connect(lambda: self.overlay.show())
        windows.addWidget(subs)
        note = QPushButton("显示实时笔记")
        note.clicked.connect(lambda: self.notes.show())
        windows.addWidget(note)
        body.addLayout(windows)
        self.notes_on = QCheckBox("自动整理并保存 Markdown 笔记")
        self.notes_on.setChecked(True)
        body.addWidget(self.notes_on)
        sliders = QFormLayout()
        sliders.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        sensitivity = QSlider(Qt.Horizontal)
        sensitivity.setRange(1, 20)
        sensitivity.setValue(4)
        sensitivity.setToolTip("左侧更灵敏，右侧过滤更多噪声")
        sensitivity.valueChanged.connect(lambda n: setattr(self.engine, "threshold", n / 1000))
        sliders.addRow("噪声门槛", sensitivity)
        size = QSlider(Qt.Horizontal)
        size.setRange(18, 36)
        size.setValue(25)
        size.valueChanged.connect(self.overlay.set_font)
        sliders.addRow("字幕字号", size)
        body.addLayout(sliders)
        self.level = QLabel("音量  ·")
        body.addWidget(self.level)
        self.status = QLabel("就绪。先测试 key，再开始收音。录音不会保存；转写文字会保存在本机。")
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        help_button = QPushButton("申请免费 key / 使用说明")
        help_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT / "docs" / "USER_GUIDE.zh-CN.md")))
        )
        body.addWidget(help_button)
        body.addStretch()
        self.setStyleSheet(LIGHT_STYLE)
        self.notes.setStyleSheet(LIGHT_STYLE)
        self.overlay.show()
        QShortcut(QKeySequence("Ctrl+Space"), self, activated=self.toggle)
        QShortcut(QKeySequence("Meta+Q"), self, activated=self.close)
        QTimer.singleShot(0, lambda: self.credential_action("load"))

    def credential_action(self, operation):
        if self.credential_busy:
            return
        secret = self.key.text().strip() if operation == "save" else None
        if operation == "save" and not secret:
            self.error("先填写 API key，再保存。")
            return
        if operation == "load" and self.key.text().strip():
            self.key_status.setText("已使用环境变量中的 key；点击保存可写入钥匙串。")
            return
        self.credential_busy = True
        self.save_key_button.setEnabled(False)
        self.delete_key_button.setEnabled(False)
        self.key_status.setText("正在访问 macOS 钥匙串…")

        def run():
            try:
                if operation == "load":
                    result = self.credentials.load()
                elif operation == "save":
                    self.credentials.save(secret)
                    result = ""
                else:
                    self.credentials.delete()
                    result = ""
                self.sig.credential_result.emit(operation, True, result)
            except Exception as e:
                self.sig.credential_result.emit(operation, False, str(e))

        threading.Thread(target=run, daemon=True).start()

    def credential_result(self, operation, ok, result):
        self.credential_busy = False
        self.save_key_button.setEnabled(not self.engine.active)
        self.delete_key_button.setEnabled(not self.engine.active)
        if not ok:
            self.key_status.setText(result)
            return
        if operation == "load":
            if result and not self.key.text().strip():
                self.key.setText(result)
                self.key_status.setText("已从 macOS 钥匙串读取 key，可直接测试或开始收音。")
            elif result:
                self.key_status.setText("钥匙串中已有 key；保留你当前输入的内容。")
            else:
                self.key_status.setText("还没有保存 key；填写后测试成功会自动保存。")
        elif operation == "save":
            self.key_status.setText("已安全保存到 macOS 钥匙串，下次打开自动读取。")
        else:
            self.key.clear()
            self.remember_key.setChecked(False)
            self.key_status.setText("已从钥匙串删除；输入框已清空，服务器端 key 仍有效。")

    def config_from_ui(self):
        self.engine.config["translation_model"] = self.translation.currentText().strip()
        self.engine.config["notes_model"] = self.note_model.currentText().strip()
        self.engine.config["chunk_seconds"] = self.interval.currentData()
        self.engine.notes_enabled = self.notes_on.isChecked()
        from core import GLOSSARY

        self.engine.glossary = GLOSSARY + " " + self.glossary.text().strip()[:500]
        self.engine.configure(self.key.text().strip())

    def test_key(self):
        key = self.key.text().strip()
        if not key:
            self.error("请先粘贴 Groq API key。打开使用说明可按步骤免费申请。")
            return
        self.test.setEnabled(False)
        self.status.setText("正在测试 API 连接…")
        models = [self.engine.config["stt_model"], self.translation.currentText(), self.note_model.currentText()]

        def run():
            try:
                base = self.engine.config["stt_base_url"]
                r = requests.get(
                    base.rstrip("/") + "/models", headers={"Authorization": "Bearer " + key}, timeout=(8, 15)
                )
                if not r.ok:
                    self.sig.tested.emit(False, f"连接测试返回 HTTP {r.status_code}，检查 key 和网络。")
                    return
                ids = {m["id"] for m in r.json()["data"]}
                missing = [m for m in models if m not in ids]
                if missing and self.engine.config["stt_base_url"] == self.engine.config["text_base_url"]:
                    self.sig.tested.emit(False, "连接成功，但这些模型不在账号列表中：" + ", ".join(missing))
                    return
                self.sig.tested.emit(True, "API 验证成功。尚未发送音频；可以开始收音。")
            except requests.RequestException:
                self.sig.tested.emit(False, "连接超时或网络不可达，请检查网络后重试。")
            except Exception:
                self.sig.tested.emit(False, "服务响应格式异常，请检查地址。")

        threading.Thread(target=run, daemon=True).start()

    def tested(self, ok, message):
        self.test.setEnabled(True)
        self.status.setText(message)
        if not ok:
            self.error(message)
        elif self.remember_key.isChecked():
            self.credential_action("save")

    def toggle(self):
        if self.engine.active:
            self.engine.stop()
            self.status.setText("已暂停，输入已释放；已识别原文保存，正在整理最后一批笔记。")
        else:
            if not self.key.text().strip():
                self.error("先填写 API key，再开始。")
                return
            self.config_from_ui()
            self.current = -1
            self.engine.start(self.input.currentData())
            if self.engine.active:
                self.overlay.show()
                if self.notes_on.isChecked():
                    self.notes.show()
        active = self.engine.active
        self.start.setText("暂停收音" if active else "开始收音")
        for w in (
            self.input,
            self.key,
            self.translation,
            self.note_model,
            self.glossary,
            self.interval,
            self.notes_on,
            self.test,
            self.save_key_button,
            self.delete_key_button,
            self.remember_key,
        ):
            w.setEnabled(not active)

    def caption(self, ident, text, translation):
        if not self.engine.active or ident < self.current:
            return
        self.current = ident
        self.overlay.source.setText(text)
        self.overlay.target.setText(translation)

    def error(self, message):
        QMessageBox.warning(self, "Lecture Caption", message)

    def capture_failed(self, message):
        if self.engine.active:
            self.toggle()
        self.status.setText(message)
        self.error(message)

    def closeEvent(self, event):
        self.engine.stop()
        self.engine.shutdown = True
        self.engine.force_notes.set()
        self.engine.save_notes()
        self.overlay.close()
        self.notes.close()
        event.accept()
        QApplication.quit()


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        log_path = DATA_ROOT / "logs/app.log"
        log_path.touch(mode=0o600, exist_ok=True)
        sys.stdout = open(log_path, "a", buffering=1, encoding="utf-8")
        sys.stderr = sys.stdout
    app = QApplication(sys.argv)
    app.setApplicationName("Lecture Caption")
    app.setOrganizationName("Lecture Caption")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(str(ASSET_ROOT / "AppIcon.png")))
    main = Controls()
    main.show()
    if "--preview" in sys.argv:

        def capture_preview():
            main.overlay.source.setText("A binary search tree maintains the ordering invariant at every node.")
            main.overlay.target.setText("二叉搜索树在每个节点都保持有序性不变量（ordering invariant）。")
            main.notes.update(
                "# 二叉搜索树\n\n## 核心定义\n\n- 左子树的键小于当前节点，右子树的键大于当前节点。\n- 具体是否允许重复键：【待核对】。\n\n## 时间复杂度\n\n- 查找代价取决于树高 $h$。\n\n> 界面示例，非真实课堂转写。",
                "界面示例",
            )
            main.notes.show()
            main.grab().save(str(DATA_ROOT / "logs" / "controls-preview.png"))
            main.overlay.grab().save(str(DATA_ROOT / "logs" / "subtitle-preview.png"))
            main.notes.grab().save(str(DATA_ROOT / "logs" / "notes-preview.png"))

        QTimer.singleShot(1000, capture_preview)
        QTimer.singleShot(2200, app.quit)
    sys.exit(app.exec())

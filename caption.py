from pathlib import Path
import os, sys, json, threading, subprocess
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QUrl, QPropertyAnimation, QEasingCurve
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
    QDialog,
    QSplitter,
    QProgressBar,
    QToolButton,
    QStackedWidget,
    QSizePolicy,
    QMenu,
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
    quota = Signal(str)
    speech_ready = Signal(bool, str)
    tested = Signal(bool, str)
    credential_result = Signal(str, bool, str)


class CaptionHistory(QWidget):
    """Upsert by segment id; follow only while the reader is near the bottom."""

    def __init__(self):
        super().__init__()
        self.entries = {}
        self.current = -1
        self.font_size = 18
        self.display_mode = "bilingual"
        self.follow = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        self.rows = QVBoxLayout(content)
        self.rows.setContentsMargins(10, 10, 10, 10)
        self.rows.setSpacing(12)
        self.rows.addStretch()
        self.scroll.setWidget(content)
        self.scroll.setStyleSheet("QScrollArea {background:#FFFFFF;border:1px solid #D9E4F2;border-radius:12px;}")
        layout.addWidget(self.scroll)
        self.latest = QPushButton("↓ 回到最新")
        self.latest.clicked.connect(self.resume_follow)
        self.latest.hide()
        layout.addWidget(self.latest, alignment=Qt.AlignRight)
        bar = self.scroll.verticalScrollBar()
        self.animation = QPropertyAnimation(bar, b"value", self)
        self.animation.setDuration(280)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        bar.rangeChanged.connect(lambda *_: self.scroll_latest())
        bar.actionTriggered.connect(self.reader_scrolled)
        bar.sliderPressed.connect(self.reader_scrolled)
        self.scroll.viewport().installEventFilter(self)

    def eventFilter(self, watched, event):
        from PySide6.QtCore import QEvent

        if event.type() == QEvent.Wheel:
            self.reader_scrolled()
        return super().eventFilter(watched, event)

    def reader_scrolled(self, *_):
        self.animation.stop()
        self.follow = False
        self.latest.show()

    def resume_follow(self):
        self.follow = True
        self.latest.hide()
        self.scroll_latest()

    def scroll_latest(self):
        if not self.follow:
            return
        bar = self.scroll.verticalScrollBar()
        self.animation.stop()
        self.animation.setStartValue(bar.value())
        self.animation.setEndValue(bar.maximum())
        self.animation.start()

    def style_entry(self, ident):
        frame, source, target = self.entries[ident]
        active = ident == self.current
        frame.setStyleSheet(
            "QFrame#captionCard {background:"
            + ("#E8F2FF" if active else "#FFFFFF")
            + ";border:1px solid "
            + ("#78ADF3" if active else "#E0E9F4")
            + ";border-radius:14px;}"
        )
        source.setVisible(self.display_mode != "chinese")
        target.setVisible(self.display_mode != "english")
        source.setStyleSheet(f"font-size:{self.font_size - 2}px;color:#60738D;background:transparent;border:0;")
        target.setStyleSheet(
            f"font-size:{self.font_size}px;color:{'#165FC0' if active else '#344D6D'};"
            f"font-weight:{600 if active else 400};background:transparent;border:0;"
        )

    def set_display_mode(self, mode):
        self.display_mode = mode
        for ident in self.entries:
            self.style_entry(ident)
        QTimer.singleShot(0, self.scroll_latest)

    def set_font(self, size):
        self.font_size = size
        for ident in self.entries:
            self.style_entry(ident)

    def append(self, ident, original, translated):
        if ident < self.current:
            return
        previous = self.current
        self.current = ident
        if ident not in self.entries:
            frame = QFrame()
            frame.setObjectName("captionCard")
            body = QVBoxLayout(frame)
            body.setContentsMargins(16, 12, 16, 14)
            source, target = QLabel(), QLabel()
            for label in (source, target):
                label.setWordWrap(True)
                label.setTextFormat(Qt.PlainText)
                label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                body.addWidget(label)
            self.entries[ident] = (frame, source, target)
            self.rows.insertWidget(self.rows.count() - 1, frame)
        _, source, target = self.entries[ident]
        source.setText(original)
        target.setText(translated)
        if previous in self.entries:
            self.style_entry(previous)
        self.style_entry(ident)
        # Keep memory/layout bounded for long lectures; the full transcript stays on disk.
        while len(self.entries) > 300:
            oldest = next(iter(self.entries))
            frame, _, _ = self.entries.pop(oldest)
            self.rows.removeWidget(frame)
            frame.deleteLater()
        QTimer.singleShot(0, self.scroll_latest)


def icon_button(name, tooltip, callback):
    button = QToolButton()
    button.setIcon(QIcon(str(ASSET_ROOT / "icons" / (name + ".svg"))))
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setFixedSize(30, 30)
    button.setStyleSheet(
        "QToolButton {background:transparent;border:0;border-radius:7px;padding:5px;} QToolButton:hover {background:#E4EFFF;}"
    )
    button.clicked.connect(callback)
    return button


class NotesPane(QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.has_content = False
        self.setObjectName("notesPane")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#notesPane {background:white;border:1px solid #D9E4F2;border-radius:12px;}")
        body = QVBoxLayout(self)
        body.setContentsMargins(10, 6, 10, 8)
        body.setSpacing(0)
        row = QHBoxLayout()
        row.addStretch()
        self.update_button = icon_button("refresh", "立即整理笔记", self.engine.force_notes.set)
        self.folder_button = icon_button("folder", "打开笔记文件夹", self.open_folder)
        row.addWidget(self.update_button)
        row.addWidget(self.folder_button)
        body.addLayout(row)
        self.stack = QStackedWidget()
        placeholder = QWidget()
        empty = QVBoxLayout(placeholder)
        empty.setContentsMargins(18, 10, 18, 10)
        title = QLabel("笔记整理")
        title.setStyleSheet("font-size:23px;font-weight:600;color:#346DAF;")
        empty.addWidget(title)
        self.status = QLabel("每约45秒提炼定义、逻辑与推导。\n开始收音后，笔记会自动出现在这里；原文即时保存。")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#8194AD;font-size:14px;")
        empty.addWidget(self.status)
        empty.addStretch()
        self.stack.addWidget(placeholder)
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(False)
        self.preview.setStyleSheet("font-size:16px;padding:12px;background:white;border:0;")
        self.stack.addWidget(self.preview)
        self.source = QPlainTextEdit()
        self.source.setReadOnly(True)
        self.source.setStyleSheet("background:white;border:0;")
        self.stack.addWidget(self.source)
        self.preview.setContextMenuPolicy(Qt.CustomContextMenu)
        self.source.setContextMenuPolicy(Qt.CustomContextMenu)
        self.preview.customContextMenuRequested.connect(lambda pos: self.show_menu(self.preview, pos))
        self.source.customContextMenuRequested.connect(lambda pos: self.show_menu(self.source, pos))
        body.addWidget(self.stack, 1)

    def show_menu(self, editor, pos):
        menu = editor.createStandardContextMenu()
        menu.addSeparator()
        action = menu.addAction("切换 Markdown 源码 / 阅读")
        action.triggered.connect(
            lambda: self.stack.setCurrentWidget(
                self.source if self.stack.currentWidget() is self.preview else self.preview
            )
        )
        menu.exec(editor.mapToGlobal(pos))

    def note_status(self, message):
        self.update_button.setToolTip("立即整理笔记 · " + message)
        if not self.has_content:
            self.status.setText(message)

    def open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.engine.session_dir or DATA_ROOT / "sessions")))

    def update(self, document, path):
        # Ignore the empty session header; the in-frame hint disappears with first content.
        nonempty = bool(self.engine.sections or self.engine.pending or self.engine.inflight) or "界面示例" in path
        bar = self.preview.verticalScrollBar()
        follow = bar.maximum() - bar.value() < 50
        old = bar.value()
        self.preview.setMarkdown(document)
        self.source.setPlainText(document)
        self.folder_button.setToolTip("打开笔记文件夹 · " + path)
        if nonempty and not self.has_content:
            self.has_content = True
            self.stack.setCurrentWidget(self.preview)
        bar.setValue(bar.maximum() if follow else old)


class Controls(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lecture Caption")
        self.resize(1220, 800)
        self.setMinimumSize(860, 560)
        config = {}
        if (DATA_ROOT / "config.json").exists():
            try:
                config = json.loads((DATA_ROOT / "config.json").read_text())
            except Exception:
                pass
        self.sig = Signals()
        self.engine = Engine(self.sig, config)
        self.notes = NotesPane(self.engine)
        self.history = CaptionHistory()
        self.current = -1
        self.credentials = CredentialStore(ROOT, self.engine.config)
        self.credential_busy = False
        self.setStyleSheet(LIGHT_STYLE)
        body = QVBoxLayout(self)
        body.setContentsMargins(12, 10, 12, 8)
        body.setSpacing(8)
        self.paused = False
        header = QHBoxLayout()
        header.setSpacing(7)
        icon = QLabel()
        icon.setToolTip("Lecture Caption")
        icon.setPixmap(
            QPixmap(str(ASSET_ROOT / "AppIcon.png")).scaled(34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        header.addWidget(icon)
        self.input = QComboBox()
        self.input.setToolTip("音源：选择麦克风或电脑内部音频")
        self.input.setMinimumWidth(160)
        self.input.setMaximumWidth(260)
        self.input.addItem("电脑音频", "system")
        try:
            default = sd.default.device[0]
            for i, device in enumerate(sd.query_devices()):
                if device["max_input_channels"] > 0:
                    self.input.addItem("麦克风 · " + device["name"], i)
                    if i == default:
                        self.input.setCurrentIndex(self.input.count() - 1)
        except Exception:
            pass
        header.addWidget(self.input, 2)
        self.stt_backend = QComboBox()
        self.stt_backend.addItem("识别 · Groq", "cloud")
        self.stt_backend.addItem("识别 · 本地", "apple")
        self.stt_backend.setToolTip("语音识别：Groq Whisper / Apple 本地英文识别（实验）")
        self.stt_backend.setCurrentIndex(max(0, self.stt_backend.findData(config.get("stt_backend", "cloud"))))
        header.addWidget(self.stt_backend, 1)
        self.translation_backend = QComboBox()
        self.translation_backend.addItem("翻译 · Groq", "cloud")
        self.translation_backend.addItem("翻译 · 本地", "apple")
        self.translation_backend.setToolTip("翻译：Groq / Apple 本地英中翻译（macOS 15+）")
        self.translation_backend.setCurrentIndex(
            max(0, self.translation_backend.findData(config.get("translation_backend", "cloud")))
        )
        header.addWidget(self.translation_backend, 1)
        self.display = QComboBox()
        self.display.addItem("双语对照", "bilingual")
        self.display.addItem("纯英文", "english")
        self.display.addItem("纯中文", "chinese")
        self.display.setToolTip("字幕显示方式；历史记录也会同步切换")
        self.display.setCurrentIndex(max(0, self.display.findData(config.get("display_mode", "bilingual"))))
        self.history.set_display_mode(self.display.currentData())
        self.display.currentIndexChanged.connect(lambda _: self.history.set_display_mode(self.display.currentData()))
        header.addWidget(self.display, 1)
        self.start = QPushButton("▶ 开始")
        self.start.setObjectName("primary")
        self.start.setMinimumWidth(76)
        self.start.clicked.connect(self.toggle)
        self.stop_button = QPushButton("■ 停止")
        self.stop_button.setMinimumWidth(76)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_capture)
        header.addWidget(self.start)
        header.addWidget(self.stop_button)
        self.settings_button = icon_button("settings", "设置", self.show_settings)
        header.addWidget(self.settings_button)
        body.addLayout(header)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(8)
        splitter.addWidget(self.notes)
        splitter.addWidget(self.history)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([540, 620])
        body.addWidget(splitter, 1)
        self.status = QLabel("就绪 · 选择音源并开始")
        self.status.setWordWrap(False)
        self.status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.status.setStyleSheet("font-size:11px;color:#8295AD;")
        self.notes.layout().addWidget(self.status)
        footer = QHBoxLayout()
        self.quota = QLabel()
        self.quota.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.quota.setStyleSheet("color:#6C829D;font-size:11px;")
        footer.addWidget(self.quota, 1)
        footer.addWidget(QLabel("音量"))
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        self.level.setFixedSize(90, 9)
        self.level.setStyleSheet(
            "QProgressBar {background:#DFE8F4;border:0;border-radius:4px;} QProgressBar::chunk {background:#4C96EF;border-radius:4px;}"
        )
        footer.addWidget(self.level)
        body.addLayout(footer)
        self.server_quota = QLabel("Groq 额度：等待服务端响应")
        self.server_quota.setTextFormat(Qt.PlainText)
        self.server_quota.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.server_quota.setStyleSheet("color:#6C829D;font-size:10px;")
        self.server_quota.setToolTip("最近一次 Groq 限额快照，不是费用余额或所有模型的实时总额度。")
        footer.insertWidget(1, self.server_quota, 2)
        self.build_settings(config)
        self.sig.status.connect(self.status.setText)
        self.sig.caption.connect(self.caption)
        self.sig.notes.connect(self.notes.update)
        self.sig.note_status.connect(self.notes.note_status)
        self.sig.error.connect(self.error)
        self.sig.capture_failed.connect(self.capture_failed)
        self.sig.tested.connect(self.tested)
        self.sig.credential_result.connect(self.credential_result)
        self.sig.level.connect(self.level.setValue)
        self.sig.quota.connect(self.set_server_quota)
        self.sig.speech_ready.connect(self.speech_prepared)
        self.quota_timer = QTimer(self)
        self.quota_timer.timeout.connect(self.refresh_quota)
        self.quota_timer.start(3000)
        self.notes_on.toggled.connect(self.refresh_quota)
        self.refresh_quota()
        QShortcut(QKeySequence("Ctrl+Space"), self, activated=self.toggle)
        QShortcut(QKeySequence("Meta+,"), self, activated=self.show_settings)
        QShortcut(QKeySequence("Meta+Q"), self, activated=self.close)
        QTimer.singleShot(0, lambda: self.credential_action("load"))

    def build_settings(self, config):
        self.settings = QDialog(self)
        self.settings.setWindowTitle("Lecture Caption · 设置")
        self.settings.resize(620, 680)
        outer = QVBoxLayout(self.settings)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        body = QVBoxLayout(content)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(14)
        self.speech_prepare = QPushButton("准备 Apple 英文语音资源（macOS 26+）…")
        self.speech_prepare.clicked.connect(self.prepare_speech)
        form.addRow(self.speech_prepare)
        prepare = QPushButton("准备 Apple 英中翻译语言包…")
        prepare.clicked.connect(self.prepare_translation)
        form.addRow(prepare)
        hint = QLabel(
            "Apple 模式不上传音频/翻译原文；自动笔记仍会发送原文到 Groq。\n语言资源须先下载；本地资源不可用时会提示，不会自动切到云端。"
        )
        hint.setWordWrap(True)
        form.addRow(hint)
        self.key = QLineEdit(os.environ.get("GROQ_API_KEY", ""))
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("从钥匙串自动读取，或粘贴 gsk_…")
        form.addRow("Groq API key", self.key)
        self.remember_key = QCheckBox("验证成功后保存到钥匙串")
        self.remember_key.setChecked(True)
        form.addRow(self.remember_key)
        row = QHBoxLayout()
        self.save_key_button = QPushButton("保存 key")
        self.save_key_button.clicked.connect(lambda: self.credential_action("save"))
        self.delete_key_button = QPushButton("删除已保存 key")
        self.delete_key_button.clicked.connect(lambda: self.credential_action("delete"))
        row.addWidget(self.save_key_button)
        row.addWidget(self.delete_key_button)
        form.addRow(row)
        self.key_status = QLabel("正在检查 macOS 钥匙串…")
        self.key_status.setWordWrap(True)
        form.addRow(self.key_status)
        self.test = QPushButton("测试 API")
        self.test.clicked.connect(self.test_key)
        form.addRow(self.test)
        self.translation = QComboBox()
        self.translation.setEditable(True)
        self.translation.addItems(["openai/gpt-oss-20b", "openai/gpt-oss-120b"])
        self.translation.setCurrentText(self.engine.config["translation_model"])
        form.addRow("Groq 翻译模型", self.translation)
        self.note_model = QComboBox()
        self.note_model.setEditable(True)
        self.note_model.addItems(["openai/gpt-oss-120b", "openai/gpt-oss-20b"])
        self.note_model.setCurrentText(self.engine.config["notes_model"])
        form.addRow("笔记模型", self.note_model)
        self.glossary = QLineEdit(config.get("glossary", ""))
        self.glossary.setPlaceholderText("课程名 / eigenvalue / Turing machine…")
        form.addRow("课程术语", self.glossary)
        self.interval = QComboBox()
        for label, value in (("5 秒 · 更快", 5), ("8 秒 · 默认", 8), ("12 秒 · 更省额度", 12)):
            self.interval.addItem(label, value)
        self.interval.setCurrentIndex(max(0, self.interval.findData(self.engine.config["chunk_seconds"])))
        form.addRow("云端语音分段", self.interval)
        self.notes_on = QCheckBox("自动整理并保存 Markdown 笔记（Groq）")
        self.notes_on.setChecked(config.get("notes_enabled", True))
        form.addRow(self.notes_on)
        sensitivity = QSlider(Qt.Horizontal)
        sensitivity.setRange(1, 20)
        sensitivity.setValue(int(config.get("threshold", 4)))
        self.engine.threshold = sensitivity.value() / 1000
        sensitivity.valueChanged.connect(lambda n: setattr(self.engine, "threshold", n / 1000))
        form.addRow("噪声门槛", sensitivity)
        self.size = QSlider(Qt.Horizontal)
        self.size.setRange(14, 30)
        self.size.setValue(int(config.get("font_size", 18)))
        self.history.set_font(self.size.value())
        self.size.valueChanged.connect(self.history.set_font)
        form.addRow("翻译字号", self.size)
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setValue(int(config.get("opacity", 100)))
        self.opacity_slider.valueChanged.connect(lambda n: self.setWindowOpacity(n / 100))
        self.setWindowOpacity(self.opacity_slider.value() / 100)
        form.addRow("窗口不透明度", self.opacity_slider)
        body.addLayout(form)
        help_button = QPushButton("免费 key / 使用说明")
        help_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT / "docs/USER_GUIDE.zh-CN.md")))
        )
        body.addWidget(help_button)
        close = QPushButton("完成")
        close.setObjectName("primary")
        close.clicked.connect(self.settings.accept)
        outer.addWidget(close)
        self.settings.finished.connect(lambda _: self.save_preferences())
        for combo in (self.stt_backend, self.translation_backend):
            combo.currentIndexChanged.connect(self.refresh_quota)

    def show_settings(self):
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def save_preferences(self):
        self.engine.config.update(
            {
                "stt_backend": self.stt_backend.currentData(),
                "translation_backend": self.translation_backend.currentData(),
                "translation_model": self.translation.currentText().strip(),
                "notes_model": self.note_model.currentText().strip(),
                "chunk_seconds": self.interval.currentData(),
                "notes_enabled": self.notes_on.isChecked(),
                "glossary": self.glossary.text().strip()[:500],
                "threshold": round(self.engine.threshold * 1000),
                "font_size": self.size.value(),
                "display_mode": self.display.currentData(),
                "opacity": self.opacity_slider.value(),
            }
        )
        # Whitelist preferences: credentials are exclusively managed by Keychain.
        data = {k: self.engine.config[k] for k in DEFAULTS}
        for k in ("notes_enabled", "glossary", "threshold", "font_size", "display_mode", "opacity"):
            data[k] = self.engine.config[k]
        temp = DATA_ROOT / "config.tmp"
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.chmod(0o600)
        temp.replace(DATA_ROOT / "config.json")
        self.refresh_quota()

    def refresh_quota(self):
        if not hasattr(self, "stt_backend"):
            return
        local_stt = self.stt_backend.currentData() == "apple"
        local_tr = self.translation_backend.currentData() == "apple"
        st = self.engine.usage.stats()
        self.quota.setText(
            f"24h语音 API：{st['req_day']} 次 · {st['sec_day'] / 60:.1f} 分钟" + (" · 本地识别" if local_stt else "")
        )
        self.quota.setToolTip(
            "仅本机滚动24小时语音 API 统计，不含其他设备和文字模型；不是账号剩余额度。"
            + (" 当前翻译使用 Apple 本地。" if local_tr else "")
        )

    def set_server_quota(self, message):
        self.server_quota.setText(message)
        self.server_quota.setToolTip(message + "\n最近响应快照，不是费用余额或所有模型的实时总额度。")

    def prepare_speech(self):
        from local_services import prepare_speech

        self.speech_prepare.setEnabled(False)
        self.status.setText("正在检查/准备 Apple 英文语音资源，首次下载可能需要几分钟…")

        def run():
            try:
                self.sig.speech_ready.emit(True, prepare_speech())
            except RuntimeError as error:
                self.sig.speech_ready.emit(False, str(error))

        threading.Thread(target=run, daemon=True).start()

    def speech_prepared(self, ok, message):
        self.speech_prepare.setEnabled(not self.engine.active)
        self.status.setText(message)
        if not ok:
            self.error(message)

    def prepare_translation(self):
        from local_services import prepare_translation

        try:
            prepare_translation()
            self.status.setText("已打开 Apple 语言包准备窗口，完成后可关闭该窗口。")
        except RuntimeError as e:
            self.error(str(e))

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
        self.save_preferences()
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
        models = []
        if self.stt_backend.currentData() == "cloud":
            models.append(self.engine.config["stt_model"])
        if self.translation_backend.currentData() == "cloud":
            models.append(self.translation.currentText())
        if self.notes_on.isChecked():
            models.append(self.note_model.currentText())

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
            self.paused = True
            self.status.setText("已暂停，输入已释放；已识别原文保存，正在整理最后一批笔记。")
        else:
            if (
                self.stt_backend.currentData() == "cloud"
                or self.translation_backend.currentData() == "cloud"
                or self.notes_on.isChecked()
            ) and not self.key.text().strip():
                self.show_settings()
                self.error("当前模式需要 Groq API key。纯本地字幕请选择两项 Apple 并关闭自动笔记。")
                return
            self.config_from_ui()
            self.engine.start(self.input.currentData())
            if self.engine.active:
                self.paused = False
        active = self.engine.active
        self.start.setText("Ⅱ 暂停" if active else "▶ 继续" if self.paused else "▶ 开始")
        self.stop_button.setEnabled(active or self.paused)
        if not active:
            self.level.setValue(0)
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
            self.stt_backend,
            self.translation_backend,
            self.speech_prepare,
        ):
            w.setEnabled(not active)

    def stop_capture(self):
        if self.engine.active:
            self.toggle()
        self.paused = False
        self.start.setText("▶ 开始")
        self.stop_button.setEnabled(False)
        self.level.setValue(0)
        self.status.setText("已停止 · 原文与笔记已保存；未完成的笔记整理可能继续。")

    def caption(self, ident, text, translation):
        if not self.engine.active or ident < self.current:
            return
        self.current = ident
        self.history.append(ident, text, translation)

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
        self.save_preferences()
        self.settings.close()
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
            main.history.append(
                1,
                "A binary search tree maintains an ordering invariant.",
                "二叉搜索树保持有序性不变量（ordering invariant）。",
            )
            main.history.append(
                2,
                "The running time depends on the height of the tree.",
                "运行时间取决于树高。",
            )
            main.notes.update(
                "# 二叉搜索树\n\n## 核心定义\n\n- 左子树的键小于当前节点，右子树的键大于当前节点。\n\n## 时间复杂度\n\n- 查找代价取决于树高 $h$。\n\n> 界面示例，非真实课堂转写。",
                "界面示例",
            )
            QTimer.singleShot(350, lambda: main.grab().save(str(DATA_ROOT / "logs/workspace-preview.png")))

        QTimer.singleShot(1000, capture_preview)
        QTimer.singleShot(2200, app.quit)
    sys.exit(app.exec())

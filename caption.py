from pathlib import Path
from software_rules import RULES_VERSION, make_rules_dialog
import os, sys, json, threading, subprocess, time, re
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
    QFileDialog,
    QGroupBox,
)
from core import ROOT, ASSET_ROOT, DATA_ROOT, Engine, DEFAULTS
import sounddevice as sd
import requests
from credentials import CredentialStore
import updater
from onboarding import SetupWizard
from notes_editor import NotesPane, choose_export_format, export_pdf


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
QPushButton:disabled,QPushButton#primary:disabled { background:#EDF1F6; color:#99A6B8; border-color:#E3E9F1; }
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
QMenu {background:white;border:1px solid #D9E4F2;border-radius:8px;padding:6px;}
QMenu::item {padding:8px 16px;border-radius:5px;}
QMenu::item:selected {background:#E6F0FF;}
QToolTip { background:white; color:#233956; border:1px solid #D9E4F2; padding:6px; }
"""


class Signals(QObject):
    status = Signal(str)
    caption = Signal(int, str, str, float, float)
    notes = Signal(str, str)
    finished = Signal(bool, str)
    update_result = Signal(object, str)
    error = Signal(str)
    capture_failed = Signal(str)
    input_failed = Signal(int, str)
    capture_state = Signal(int, str, str)
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
        self.timestamps = {}
        self.current = -1
        self.font_size = 18
        self.display_mode = "bilingual"
        self.follow = True
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setSingleShot(True)
        self.scroll_timer.timeout.connect(self.scroll_latest)
        self.position_timer = QTimer(self)
        self.position_timer.setSingleShot(True)
        self.position_timer.timeout.connect(self.on_scroll_position)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content.setStyleSheet("background:#F3F7FC;")
        self.rows = QVBoxLayout(content)
        self.rows.setContentsMargins(22, 18, 22, 22)
        self.rows.setSpacing(24)
        self.rows.addStretch()
        self.scroll.setWidget(content)
        self.scroll.setStyleSheet(
            "QScrollArea {background:#F3F7FC;border:0;} QScrollBar:vertical {background:transparent;} QScrollBar::handle:vertical {background:#BFCEE3;}"
        )
        layout.addWidget(self.scroll)
        self.latest = QToolButton(self.scroll.viewport())
        self.latest.setText("↓")
        self.latest.setToolTip("回到最新")
        self.latest.setAccessibleName("回到最新")
        self.latest.setFixedSize(32, 32)
        self.latest.setStyleSheet(
            "QToolButton {background:#FFFFFF;color:#2877E1;border:1px solid #C5DDF9;border-radius:7px;font-size:20px;} QToolButton:hover {background:#E8F2FF;}"
        )
        self.latest.clicked.connect(self.resume_follow)
        self.latest.hide()
        bar = self.scroll.verticalScrollBar()
        self.animation = QPropertyAnimation(bar, b"value", self)
        self.animation.setDuration(280)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        bar.rangeChanged.connect(self.on_range_changed)
        bar.valueChanged.connect(self.on_scroll_position)
        bar.actionTriggered.connect(self.reader_scrolled)
        bar.sliderPressed.connect(self.reader_scrolled)
        self.scroll.viewport().installEventFilter(self)

    def eventFilter(self, watched, event):
        from PySide6.QtCore import QEvent

        if event.type() == QEvent.Wheel:
            self.reader_scrolled()
        elif event.type() == QEvent.Resize:
            self.position_latest()
        return super().eventFilter(watched, event)

    def reader_scrolled(self, *_):
        self.animation.stop()
        self.follow = False
        self.position_timer.start(0)

    def on_range_changed(self, *_):
        if self.follow:
            self.scroll_latest()
        else:
            self.on_scroll_position()

    def position_latest(self):
        viewport = self.scroll.viewport()
        self.latest.move(
            max(8, viewport.width() - self.latest.width() - 14), max(8, viewport.height() - self.latest.height() - 14)
        )

    def on_scroll_position(self, *_):
        bar = self.scroll.verticalScrollBar()
        if bar.maximum() - bar.value() <= 4:
            self.follow = True
            self.latest.hide()
        elif not self.follow:
            self.position_latest()
            self.latest.show()
            self.latest.raise_()

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
        frame.setStyleSheet("QFrame {background:transparent;border:0;}")
        source.setVisible(self.display_mode != "chinese")
        target.setVisible(self.display_mode != "english")
        source.setStyleSheet(
            f"font-size:{self.font_size}px;color:{'#1C1C1E' if active else '#3A3A3C'};"
            f"font-weight:{600 if active else 400};background:transparent;border:0;"
        )
        target.setStyleSheet(
            f"font-size:{self.font_size}px;color:{'#1766D1' if active else '#397DC6'};"
            f"font-weight:{600 if active else 400};background:transparent;border:0;"
        )

    def set_display_mode(self, mode):
        self.display_mode = mode
        for ident in self.entries:
            self.style_entry(ident)
        self.scroll_timer.start(0)

    def set_font(self, size):
        self.font_size = size
        for ident in self.entries:
            self.style_entry(ident)

    def append(self, ident, original, translated, started=None, ended=None):
        if ident < self.current and (ident not in self.entries or original != self.entries[ident][1].text()):
            return
        previous = self.current
        self.current = max(self.current, ident)
        if ident not in self.entries:
            frame = QFrame()
            frame.setObjectName("captionParagraph")
            body = QVBoxLayout(frame)
            body.setContentsMargins(0, 0, 0, 0)
            body.setSpacing(7)
            timestamp = QLabel()
            timestamp.setStyleSheet("font-size:11px;color:#8795A8;background:transparent;border:0;")
            self.timestamps[ident] = timestamp
            body.addWidget(timestamp)
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
        if translated:
            target.setText(translated)
        elif not target.text():
            target.setText("正在翻译…")
        started = time.time() if started is None else started
        ended = started if ended is None else ended
        self.timestamps[ident].setText(
            time.strftime("%H:%M:%S", time.localtime(started))
            + " – "
            + time.strftime("%H:%M:%S", time.localtime(ended))
        )
        if previous in self.entries:
            self.style_entry(previous)
        self.style_entry(ident)
        # Keep memory/layout bounded for long lectures; the full transcript stays on disk.
        while len(self.entries) > 300:
            oldest = next(iter(self.entries))
            frame, _, _ = self.entries.pop(oldest)
            self.timestamps.pop(oldest, None)
            self.rows.removeWidget(frame)
            frame.deleteLater()
        self.scroll_timer.start(0)


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


class Controls(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lecture Caption")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.resize(1220, 800)
        self.setMinimumSize(860, 560)
        config = {}
        if (DATA_ROOT / "config.json").exists():
            try:
                config = json.loads((DATA_ROOT / "config.json").read_text())
            except Exception:
                pass
        if config.get("notes_cadence_version") != 2:
            config.update(notes_interval=60, revise_interval=600, notes_cadence_version=2)
        self.rules_accepted_version = config.get("rules_accepted_version", "")
        self.rules_dialog = None
        self.sig = Signals()
        self.engine = Engine(self.sig, config)
        self.notes = NotesPane(self.engine, ASSET_ROOT, DATA_ROOT)
        self.history = CaptionHistory()
        self.current = -1
        self.credentials = CredentialStore(ROOT, self.engine.config)
        self.credential_busy = False
        self.setStyleSheet(LIGHT_STYLE)
        body = QVBoxLayout(self)
        body.setContentsMargins(12, 10, 12, 8)
        body.setSpacing(8)
        self.paused = False
        self.finishing = False
        self.lecture_ended = False
        self.default_pdf_dir = config.get("default_pdf_dir", str(Path.home() / "Desktop"))
        self.last_export_dir = config.get("last_export_dir", str(Path.home() / "Documents"))
        self.staged_update = None
        self.update_busy = False
        self.about = None
        self.setup_busy = False
        self.onboarding = None
        self.onboarding_seen = (
            config.get("onboarding_seen", False) and config.get("onboarding_flow_version", 0) >= 3 and self.has_rules()
        )
        self.onboarding_flow_version = config.get("onboarding_flow_version", 0)
        self.tour = None
        header = QHBoxLayout()
        header.setSpacing(7)
        icon = QToolButton()
        icon.setToolTip("关于 Lecture Caption 与软件更新")
        icon.setIcon(QIcon(str(ASSET_ROOT / "AppIcon.png")))
        from PySide6.QtCore import QSize

        icon.setIconSize(QSize(34, 34))
        icon.setStyleSheet("QToolButton {background:transparent;border:0;}")
        icon.clicked.connect(self.show_about)
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
        self.stt_backend.setToolTip(
            "语音识别：Groq Whisper / Apple 本地英文识别。连贯模式会持续重识别当前段落；Groq 模式的语音额度消耗相应增加。"
        )
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
        self.stop_button = QPushButton("■ 结束")
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
        self.status.setWordWrap(True)
        self.status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.status.setStyleSheet("font-size:11px;color:#8295AD;")
        self.notes.layout().addWidget(self.status)
        self.note_failure = QLabel("Groq模型整理失败，请稍后重试或重新配置模型")
        self.note_failure.setWordWrap(True)
        self.note_failure.setStyleSheet("color:#C94739;font-size:11px;")
        self.note_failure.hide()
        self.notes.layout().addWidget(self.note_failure)
        footer = QHBoxLayout()
        self.quota = QLabel()
        self.quota.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.quota.setStyleSheet("color:#6C829D;font-size:11px;")
        footer.addWidget(self.quota, 1)
        self.save_transcript_button = QPushButton("另存转录")
        self.save_transcript_button.clicked.connect(self.save_transcript)
        footer.addWidget(self.save_transcript_button)
        self.capture_indicator = QLabel("●")
        self.capture_indicator.setFixedWidth(18)
        self.capture_indicator.setAlignment(Qt.AlignCenter)
        self.set_capture_indicator("idle")
        footer.addWidget(self.capture_indicator)
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
        self.server_quota_text = ""
        self.build_settings(config)
        self.sig.status.connect(self.on_status)
        self.sig.caption.connect(self.caption)
        self.sig.notes.connect(self.notes.update)
        self.sig.finished.connect(self.finish_ready)
        self.sig.update_result.connect(self.update_received)
        self.notes.summary_requested.connect(self.summarise_now)
        self.notes.import_requested.connect(self.import_notes)
        self.notes.recent_requested.connect(self.open_recent_note)
        self.notes.save_failed.connect(self.error)
        self.notes.content_changed.connect(self.refresh_end_button)
        self.sig.notes.connect(lambda *_: self.refresh_end_button())
        self.sig.note_status.connect(self.notes.note_status)
        self.sig.note_status.connect(self.on_note_status)
        self.sig.error.connect(self.error)
        self.sig.capture_failed.connect(self.capture_failed)
        self.sig.input_failed.connect(self.on_input_failed)
        self.sig.capture_state.connect(self.on_capture_state)
        self.sig.tested.connect(self.tested)
        self.sig.credential_result.connect(self.credential_result)
        self.sig.level.connect(lambda value: self.level.setValue(value if self.engine.active else 0))
        self.sig.quota.connect(self.set_server_quota)
        self.sig.speech_ready.connect(self.speech_prepared)
        self.switch_timer = QTimer(self)
        self.switch_timer.setSingleShot(True)
        self.switch_timer.setInterval(200)
        self.switch_timer.timeout.connect(self.apply_live_selection)
        for combo in (self.input, self.stt_backend, self.translation_backend, self.translation):
            combo.currentIndexChanged.connect(self.schedule_live_selection)
        self.translation.lineEdit().editingFinished.connect(self.schedule_live_selection)
        self.note_model.currentIndexChanged.connect(self.apply_note_model)
        self.note_model.lineEdit().editingFinished.connect(self.apply_note_model)
        self.quota_timer = QTimer(self)
        self.quota_timer.timeout.connect(self.refresh_quota)
        self.quota_timer.start(3000)
        self.notes_on.toggled.connect(self.refresh_quota)
        self.notes_on.toggled.connect(self.show_notes_mode)
        self.show_notes_mode()
        self.refresh_quota()
        self.usage_network_info = None
        try:
            from PySide6.QtNetwork import QNetworkInformation

            QNetworkInformation.loadDefaultBackend()
            self.usage_network_info = QNetworkInformation.instance()
            if self.usage_network_info:
                self.usage_network_info.reachabilityChanged.connect(
                    lambda reach: (
                        self.engine.usage_reporter.network_available()
                        if reach == QNetworkInformation.Reachability.Online
                        else None
                    )
                )
        except (ImportError, RuntimeError):
            pass  # Timer retries remain available when no OS backend exists.
        QShortcut(QKeySequence("Ctrl+Space"), self, activated=self.toggle)
        QShortcut(QKeySequence("Meta+,"), self, activated=self.show_settings)
        QShortcut(QKeySequence("Meta+Q"), self, activated=self.close)
        self.credential_timer = QTimer(self)
        self.credential_timer.setSingleShot(True)
        self.credential_timer.timeout.connect(lambda: self.credential_action("load"))
        self.credential_timer.start(0)
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(6 * 60 * 60 * 1000)
        self.update_timer.timeout.connect(self.automatic_update)
        self.update_timer.start()
        if not os.environ.get("LECTURE_CAPTION_NO_UPDATE") and "--preview" not in sys.argv:
            QTimer.singleShot(2000, self.automatic_update)
        if (
            not self.onboarding_seen
            and not os.environ.get("LECTURE_CAPTION_NO_ONBOARDING")
            and "--preview" not in sys.argv
        ):
            QTimer.singleShot(350, self.show_setup)

    def build_settings(self, config):
        self.settings = QDialog(self)
        self.settings.setWindowTitle("Lecture Caption · 设置")
        self.settings.resize(620, 560)
        outer = QVBoxLayout(self.settings)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        body = QVBoxLayout(content)
        quick = QHBoxLayout()
        for title, profile in (("一键本地", "local"), ("配置 Groq", "cloud"), ("使用指南", "tour")):
            button = QPushButton(title)
            button.clicked.connect(lambda _, p=profile: self.show_setup(p))
            quick.addWidget(button)
        body.addLayout(quick)
        self.speech_prepare = QPushButton("一键准备当前模式所需权限与语言资源")
        self.speech_prepare.clicked.connect(lambda: self.show_setup("permissions"))
        body.addWidget(self.speech_prepare)
        apple_row = QHBoxLayout()
        for title, action in (
            ("下载英文识别资源", self.prepare_speech),
            ("下载英中翻译语言包", self.prepare_translation),
            (
                "打开系统听写设置",
                lambda: QDesktopServices.openUrl(
                    QUrl("x-apple.systempreferences:com.apple.Keyboard-Settings.extension")
                ),
            ),
        ):
            button = QPushButton(title)
            button.clicked.connect(action)
            apple_row.addWidget(button)
        body.addLayout(apple_row)
        hint = QLabel(
            "推荐先一键准备。英文识别与英中翻译是两套资源；出现下载窗口时请完成下载。旧系统请在听写设置添加英语（美国）。"
        )
        hint.setWordWrap(True)
        body.addWidget(hint)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.key = QLineEdit(os.environ.get("GROQ_API_KEY", ""))
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("自动读取已保存 key，或粘贴新 key")
        pdf_row = QHBoxLayout()
        self.pdf_directory = QLineEdit(self.default_pdf_dir)
        self.pdf_directory.setReadOnly(True)
        pdf_row.addWidget(self.pdf_directory, 1)
        pdf_choose = QPushButton("更改…")
        pdf_choose.clicked.connect(self.choose_pdf_directory)
        pdf_row.addWidget(pdf_choose)
        form.addRow("PDF 自动保存位置", pdf_row)
        form.addRow("Groq API key", self.key)
        self.test = QPushButton("验证并保存 key")
        self.test.clicked.connect(self.test_key)
        form.addRow(self.test)
        self.key_status = QLabel("正在检查 macOS 钥匙串…")
        self.key_status.setWordWrap(True)
        form.addRow(self.key_status)
        self.notes_on = QCheckBox("自动整理并保存 Markdown 笔记（Groq）")
        self.notes_on.setChecked(config.get("notes_enabled", True))
        self.notes_on.setToolTip("启用后，将当前课堂原文与已有笔记（包括导入文件）发送给 Groq；原文同时在本机保留。")
        form.addRow(self.notes_on)
        from usage_sync import USAGE_NOTICE, USAGE_DETAIL

        self.usage_sharing = QCheckBox(USAGE_NOTICE)
        self.usage_sharing.setChecked(bool(config.get("usage_sharing", False)))
        self.usage_sharing.setToolTip(USAGE_DETAIL)
        check_icon = str(ASSET_ROOT / "icons/check-white.svg")
        self.usage_sharing.setStyleSheet(
            "QCheckBox::indicator {width:17px;height:17px;border:1px solid #B5CAE4;border-radius:4px;background:white;}"
            'QCheckBox::indicator:checked {background:#2877E1;border-color:#2877E1;image:url("' + check_icon + '");}'
        )
        self.usage_sharing.toggled.connect(self.set_usage_sharing)
        form.addRow(self.usage_sharing)
        self.usage_privacy = QLabel(USAGE_DETAIL + " 网络服务可能处理或保留 IP 连接诊断。")
        self.usage_privacy.setWordWrap(True)
        self.usage_privacy.setStyleSheet("color:#72849B;font-size:12px;")
        form.addRow(self.usage_privacy)
        self.usage_sync_status = QLabel()
        self.usage_sync_status.setWordWrap(True)
        form.addRow(self.usage_sync_status)
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
        self.settings_custom = QToolButton()
        self.settings_custom.setText("高级设置")
        self.settings_custom.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.settings_custom.setCheckable(True)
        self.settings_custom.setArrowType(Qt.RightArrow)
        self.settings_custom.setStyleSheet(
            "QToolButton {text-align:left;background:transparent;border:0;padding:10px 0;color:#233956;font-weight:600;}"
        )
        advanced = QWidget()
        advanced.setStyleSheet("background:transparent;")
        advanced.setVisible(False)
        self.settings_custom.toggled.connect(advanced.setVisible)
        self.settings_custom.toggled.connect(
            lambda value: self.settings_custom.setArrowType(Qt.DownArrow if value else Qt.RightArrow)
        )
        more = QFormLayout(advanced)
        more.setContentsMargins(0, 8, 0, 8)
        more.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        more.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        more.setVerticalSpacing(12)
        self.translation = QComboBox()
        self.translation.setEditable(True)
        self.translation.addItems(["openai/gpt-oss-20b", "openai/gpt-oss-120b"])
        self.translation.setCurrentText(self.engine.config["translation_model"])
        more.addRow("Groq 翻译模型", self.translation)
        self.note_model = QComboBox()
        self.note_model.setEditable(True)
        self.note_model.addItems(["openai/gpt-oss-120b", "openai/gpt-oss-20b"])
        self.note_model.setCurrentText(self.engine.config["notes_model"])
        more.addRow("Groq 笔记模型", self.note_model)
        self.glossary = QLineEdit(config.get("glossary", ""))
        more.addRow("课程术语", self.glossary)
        self.interval = QComboBox()
        for title, value in (("5 秒 · 更快", 5), ("8 秒 · 默认", 8), ("12 秒 · 更省额度", 12)):
            self.interval.addItem(title, value)
        self.interval.setCurrentIndex(max(0, self.interval.findData(self.engine.config["chunk_seconds"])))
        more.addRow("Groq 识别更新间隔", self.interval)
        self.revise_interval = QComboBox()
        for minutes in (5, 10, 15, 20, 30, 60):
            self.revise_interval.addItem(f"每 {minutes} 分钟", minutes * 60)
        self.revise_interval.setCurrentIndex(max(0, self.revise_interval.findData(config.get("revise_interval", 600))))
        self.revise_interval.currentIndexChanged.connect(
            lambda: self.engine.config.update(revise_interval=self.revise_interval.currentData())
        )
        more.addRow("自动二次整理与命名", self.revise_interval)
        sensitivity = QSlider(Qt.Horizontal)
        sensitivity.setRange(1, 20)
        sensitivity.setValue(int(config.get("threshold", 4)))
        self.engine.threshold = sensitivity.value() / 1000
        sensitivity.valueChanged.connect(lambda n: setattr(self.engine, "threshold", n / 1000))
        more.addRow("噪声门槛", sensitivity)
        self.remember_key = QCheckBox("验证成功后保存到钥匙串")
        self.remember_key.setChecked(True)
        more.addRow(self.remember_key)
        row = QHBoxLayout()
        self.save_key_button = QPushButton("保存 key")
        self.save_key_button.clicked.connect(lambda: self.credential_action("save"))
        self.delete_key_button = QPushButton("删除已保存 key")
        self.delete_key_button.clicked.connect(lambda: self.credential_action("delete"))
        row.addWidget(self.save_key_button)
        row.addWidget(self.delete_key_button)
        more.addRow(row)
        self.auto_update = QCheckBox("自动更新（自动检查和下载，空闲时安装）")
        self.auto_update.setChecked(config.get("auto_update", True) if config.get("auto_update_schema") == 1 else True)
        self.auto_update.setToolTip("启动及每6小时检查官方 GitHub；有课堂内容或正在配置时不会自动重启。")
        body.addWidget(self.auto_update)
        body.addWidget(self.settings_custom)
        body.addWidget(advanced)
        body.addStretch()
        close = QPushButton("完成")
        close.setObjectName("primary")
        close.clicked.connect(self.settings.accept)
        outer.addWidget(close)
        self.settings.finished.connect(lambda _: self.save_preferences())
        for combo in (self.stt_backend, self.translation_backend):
            combo.currentIndexChanged.connect(self.refresh_quota)

    def show_setup(self, profile=None):
        if self.engine.active or self.paused or self.finishing:
            self.error("请先结束当前课程，再使用一键配置。录音中的切换可直接使用顶部选择器。")
            return
        self.settings.hide()
        if self.about:
            self.about.hide()
        if self.onboarding is None:
            self.onboarding = SetupWizard(self)
        self.onboarding.show()
        self.onboarding.raise_()
        if self.setup_busy:
            return
        if profile in ("local", "cloud", "permissions") and not self.onboarding.require_rules():
            return
        if profile == "local":
            self.onboarding.begin_local()
        elif profile == "cloud":
            self.onboarding.begin_cloud()
        elif profile == "tour":
            self.onboarding.hide()
            self.start_tour()
        elif profile == "permissions":
            self.onboarding.profile = "permissions"
            self.onboarding.set_busy(True)
            self.onboarding.message.setText("自动准备当前模式所需权限与资源；不会开始录音。")
            self.onboarding.prepare_permissions()
        else:
            self.onboarding.pages.setCurrentWidget(self.onboarding.welcome)

    def start_tour(self):
        from tutorial import TutorialOverlay

        if self.tour:
            self.tour.close()
            self.tour.deleteLater()
        self.tour = TutorialOverlay(self)
        self.tour.finished.connect(lambda: self.status.setText("准备就绪 · 点击顶部「开始」收音"))
        self.tour.show()
        self.tour.raise_()
        self.tour.setFocus()

    def apply_setup_profile(self, profile):
        if self.engine.active or self.finishing:
            return False
        self.switch_timer.stop()
        if profile == "cloud":
            changed = any(self.engine.config[name] != DEFAULTS[name] for name in ("stt_base_url", "text_base_url"))
            if changed and self.credential_busy:
                self.onboarding.message.setText("正在读取原有钥匙串，请稍后重试一键配置。")
                return False
            for name in (
                "stt_base_url",
                "text_base_url",
                "stt_model",
                "translation_model",
                "notes_model",
                "chunk_seconds",
                "notes_interval",
                "revise_interval",
            ):
                self.engine.config[name] = DEFAULTS[name]
            if changed:
                self.key.clear()
                self.credentials = CredentialStore(ROOT, self.engine.config)
            self.translation.setCurrentText(DEFAULTS["translation_model"])
            self.note_model.setCurrentText(DEFAULTS["notes_model"])
        backend = "apple" if profile == "local" else "cloud"
        self.stt_backend.setCurrentIndex(self.stt_backend.findData(backend))
        self.translation_backend.setCurrentIndex(self.translation_backend.findData(backend))
        self.interval.setCurrentIndex(self.interval.findData(8))
        self.revise_interval.setCurrentIndex(self.revise_interval.findData(600))
        self.notes_on.setChecked(profile == "cloud")
        self.engine.notes_enabled = self.notes_on.isChecked()
        self.remember_key.setChecked(True)
        self.save_preferences()
        return True

    def summarise_now(self):
        if not self.has_rules():
            self.show_setup()
            return
        if self.finishing or not self.notes.end_editing():
            return
        if not self.key.text().strip():
            if self.engine.active:
                self.status.setText("立即整理需要 Groq key；先暂停/结束，再在设置中配置 Groq。")
            else:
                self.show_setup("cloud")
            return
        self.engine.notes_enabled = self.notes_on.isChecked()
        self.engine.config["notes_model"] = self.note_model.currentText().strip()
        self.engine.configure(self.key.text().strip())
        with self.engine.notes_lock:
            if not self.engine.pending and not self.engine.inflight:
                self.engine.pending = [
                    item
                    for ident, item in self.engine.source_paragraphs.items()
                    if ident not in self.engine.live_utterances
                ]
                if not self.engine.pending and self.engine.sections:
                    self.engine.pending = [("已有笔记", "\n\n".join(self.engine.sections))]
            if not self.engine.pending and not self.engine.inflight:
                self.status.setText("先收音、导入或输入一些内容，再立刻整理。")
                return
        self.engine.manual_summary.set()
        self.engine.force_notes.set()
        self.status.setText("已请求立即整理；现有原文和笔记将发送给已配置的笔记服务。")

    def show_settings(self):
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def has_rules(self):
        return self.rules_accepted_version == RULES_VERSION

    def show_rules(self, parent=None):
        if self.rules_dialog:
            self.rules_dialog.close()
            self.rules_dialog.deleteLater()
        self.rules_dialog = make_rules_dialog(self, parent)
        self.rules_dialog.show()
        self.rules_dialog.raise_()

    def set_rules_accepted(self, accepted):
        self.rules_accepted_version = RULES_VERSION if accepted else ""
        self.engine.config["rules_accepted_version"] = self.rules_accepted_version
        if not accepted:
            self.engine.usage_reporter.suspend()
        else:
            self.usage_sharing.setChecked(True)
            self.set_usage_sharing(True)
        self.save_preferences()

    def set_usage_sharing(self, enabled):
        self.engine.config["usage_sharing"] = bool(enabled)
        with self.engine.pipeline_lock:
            if not enabled:
                self.engine.usage_reporter.configure(False)
            elif self.has_rules():
                self.engine.usage_reporter.configure(True)
                self.engine.usage_min_paragraph = self.engine.next_id
                if self.engine.usage_capture_ready:
                    self.engine.usage_reporter.capture_started(self.engine.usage_session_key)
        self.save_preferences()

    def save_preferences(self):
        desired = {
            "stt_backend": self.stt_backend.currentData(),
            "translation_backend": self.translation_backend.currentData(),
            "translation_model": self.translation.currentText().strip(),
            "notes_model": self.note_model.currentText().strip(),
            "chunk_seconds": self.interval.currentData(),
            "notes_enabled": self.notes_on.isChecked(),
            "usage_sharing": self.usage_sharing.isChecked(),
            "rules_accepted_version": self.rules_accepted_version,
            "glossary": self.glossary.text().strip()[:500],
            "threshold": round(self.engine.threshold * 1000),
            "font_size": self.size.value(),
            "display_mode": self.display.currentData(),
            "opacity": self.opacity_slider.value(),
            "revise_interval": self.revise_interval.currentData(),
            "notes_interval": 60,
            "notes_cadence_version": 2,
            "last_export_dir": self.last_export_dir,
            "default_pdf_dir": self.default_pdf_dir,
            "auto_update": self.auto_update.isChecked(),
            "onboarding_seen": self.onboarding_seen,
            "onboarding_flow_version": self.onboarding_flow_version,
            "auto_update_schema": 1,
        }
        # Only apply pipeline preferences while capture is stopped. Active changes
        # are coalesced into a generation-safe handoff by apply_live_selection.
        if not self.engine.active:
            self.engine.config.update(desired)
        combined = {**self.engine.config, **desired}
        data = {k: combined[k] for k in DEFAULTS}
        for k in (
            "notes_enabled",
            "usage_sharing",
            "rules_accepted_version",
            "glossary",
            "threshold",
            "font_size",
            "display_mode",
            "opacity",
            "last_export_dir",
            "default_pdf_dir",
            "auto_update",
            "onboarding_seen",
            "onboarding_flow_version",
            "auto_update_schema",
        ):
            data[k] = combined[k]
        temp = DATA_ROOT / "config.tmp"
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.chmod(0o600)
        temp.replace(DATA_ROOT / "config.json")
        self.refresh_quota()

    def refresh_quota(self):
        if hasattr(self, "usage_sync_status"):
            self.usage_sync_status.setText(self.engine.usage_reporter.state)
        if not hasattr(self, "stt_backend"):
            return
        st = self.engine.usage.stats()
        remaining = re.search(r"当日请求剩余 (\d+(?: / \d+)?)", self.server_quota_text)
        tokens = re.search(r"本分钟 token 剩余 (\d+(?: / \d+)?)", self.server_quota_text)
        day = remaining.group(1) if remaining else "未取得"
        self.quota.setText(
            f"Groq 当日余量：{day}  ·  本机24h语音请求：{st['req_day']} 次"
            + (f"  ·  Token 余量：{tokens.group(1)}" if tokens else "")
        )
        self.quota.setToolTip(
            (self.server_quota_text + "\n" if self.server_quota_text else "")
            + "服务端限额为最近一次响应的模型快照；本机计数仅含语音 API，不含其他设备或文字模型。"
        )

    def set_server_quota(self, message):
        self.server_quota_text = message
        self.refresh_quota()

    def set_capture_indicator(self, state, message=""):
        self._capture_state = state
        self.capture_indicator.setText("!" if state == "error" else "●")
        color = {"recording": "#28A66B", "error": "#DF4545", "idle": "#A0A9B6"}[state]
        self.capture_indicator.setStyleSheet(f"font-size:14px;font-weight:700;color:{color};background:transparent;")
        self.capture_indicator.setToolTip(
            message or {"recording": "正在收音", "error": "音频输入错误", "idle": "未收音"}[state]
        )
        self.capture_indicator.setAccessibleName(self.capture_indicator.toolTip())

    def show_notes_mode(self, *_):
        enabled = self.notes_on.isChecked()
        self.notes.summary_action.setText("立即整理" if enabled else "立即整理（自动笔记已关闭）")
        self.notes.preview.setPlaceholderText(
            "笔记整理\n\n开始收音后自动生成笔记，也可以直接输入。"
            if enabled
            else "自动笔记已关闭\n\n在设置中勾选‘自动整理并保存 Markdown 笔记（Groq）’启用。\n本次已识别内容可通过右上角 ⋯ → 立即整理补充。"
        )
        if not enabled:
            self.status.setText("自动笔记已关闭；设置中开启，或点 ⋯ → 立即整理。")
        elif not self.engine.active:
            self.status.setText("自动笔记已开启 · 收音后约每 1 分钟追加笔记，每 10 分钟整合一次。")

    def on_note_status(self, message):
        self.note_failure.setText(message)
        self.note_failure.setVisible(self.engine.notes_failed)
        self.status.setVisible(not self.engine.notes_failed)
        self.status.setText(message)

    def on_status(self, message):
        if self.engine.notes_failed:
            self.status.setText("Groq模型整理失败，请稍后重试或重新配置模型")
            return
        if message.startswith("●"):
            if self.notes_on.isChecked():
                self.status.clear()
            else:
                self.status.setText("正在收音；自动笔记已关闭，可在设置中开启。")
        else:
            self.status.setText(message)

    def on_capture_state(self, generation, state, message):
        if generation == self.engine.gen and self.engine.active:
            self.set_capture_indicator(state, message)

    def on_input_failed(self, generation, message):
        if generation == self.engine.gen:
            self.audio_input_failed(message)

    def audio_input_failed(self, message):
        self.capture_failed(message)
        self.set_capture_indicator("error", message)

    def apply_note_model(self, *_):
        if self.engine.active:
            self.engine.config["notes_model"] = self.note_model.currentText().strip()
        self.save_preferences()

    def schedule_live_selection(self, *_):
        if self.engine.active:
            self.switch_timer.start()

    def apply_live_selection(self):
        if not self.engine.active:
            return
        if (
            self.stt_backend.currentData() == "cloud"
            or self.translation_backend.currentData() == "cloud"
            or self.notes_on.isChecked()
        ) and not self.key.text().strip():
            self.toggle()
            self.show_settings()
            self.error("已暂停。切换到 Groq 需要先填写 API key，然后点击继续。")
            return
        if (
            self.engine.device == self.input.currentData()
            and self.engine.config["stt_backend"] == self.stt_backend.currentData()
        ):
            self.engine.change_translation(
                self.translation_backend.currentData(), self.translation.currentText().strip(), self.key.text().strip()
            )
            self.save_preferences()
            return
        previous = self.engine.latest_caption
        self.engine.stop()
        self.set_capture_indicator("idle")
        self.config_from_ui()
        self.engine.start(self.input.currentData())
        if previous and self.engine.active:
            from core import bounded_offer

            bounded_offer(self.engine.translation_refresh, (self.engine.gen, previous[1], previous[2]))
        self.paused = False
        self.sync_capture_controls()

    def prepare_speech(self):
        from local_services import prepare_local_resources

        self.speech_prepare.setEnabled(False)
        self.status.setText("正在检查/准备 Apple 英文语音资源，首次下载可能需要几分钟…")

        def run():
            try:
                self.sig.speech_ready.emit(True, prepare_local_resources(speech=True, translation=False))
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

    def focusNextPrevChild(self, forward):
        if self.tour and self.tour.isVisible():
            target = self.tour.next_button if not self.tour.next_button.hasFocus() else self.tour.skip
            target.setFocus()
            return True
        return super().focusNextPrevChild(forward)

    def toggle(self):
        if self.tour and self.tour.isVisible():
            return
        if not self.has_rules():
            self.show_setup()
            return
        if self.setup_busy:
            self.status.setText("正在准备权限和资源，准备完成后即可开始。")
            return
        if self.finishing:
            return
        self.switch_timer.stop()
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
                self.show_setup("cloud")
                return
            if self.lecture_ended:
                if self.engine.notes_busy:
                    self.status.setText("上一课备份仍在整理，请稍后开始新一课。")
                    return
                with self.engine.save_lock, self.engine.notes_lock:
                    self.engine.session_dir = None
                    self.engine.source_paragraphs.clear()
                    self.engine.last_revise = time.monotonic()
                    self.lecture_ended = False
            self.config_from_ui()
            self.engine.start(self.input.currentData())
            if self.engine.active:
                self.paused = False
        self.sync_capture_controls()

    def refresh_end_button(self):
        self.stop_button.setEnabled(
            not self.finishing and (self.engine.active or self.paused or self.notes.has_content)
        )

    def sync_capture_controls(self):
        self.notes.refresh_recent_button()
        active = self.engine.active
        self.start.setText("Ⅱ 暂停" if active else "▶ 继续" if self.paused else "▶ 开始")
        self.refresh_end_button()
        if not active:
            self.level.setValue(0)
            if self._capture_state != "error":
                self.set_capture_indicator("idle")
        for w in (
            self.key,
            self.glossary,
            self.interval,
            self.notes_on,
            self.test,
            self.save_key_button,
            self.delete_key_button,
            self.remember_key,
            self.speech_prepare,
        ):
            w.setEnabled(not active)

    def stop_capture(self):
        if not self.notes.end_editing():
            return
        if self.finishing:
            return
        self.switch_timer.stop()
        self.finishing = True
        self.paused = False
        self.start.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.config_from_ui()
        self.engine.finish()
        self.set_capture_indicator("idle")
        self.sync_capture_controls()
        self.stop_button.setEnabled(False)
        self.status.setText("正在完成最后整理并保留备份，随后选择另存位置…")

    def choose_pdf_directory(self):
        directory = QFileDialog.getExistingDirectory(self.settings, "选择 PDF 自动保存位置", self.default_pdf_dir)
        if directory:
            self.default_pdf_dir = directory
            self.pdf_directory.setText(directory)
            self.save_preferences()

    def save_transcript(self):
        self.engine.save_notes()
        if not self.engine.session_dir:
            self.status.setText("还没有可保存的转录原文。")
            return
        source = self.engine.session_dir / "transcript.md"
        destination, _ = QFileDialog.getSaveFileName(
            self, "另存转录", str(Path(self.default_pdf_dir) / "课堂转录.md"), "Markdown (*.md)"
        )
        if destination:
            target = Path(destination)
            if target.suffix.lower() != ".md":
                target = target.with_name(target.name + ".md")
                if (
                    target.exists()
                    and QMessageBox.question(self, "替换文件", "此文件已存在，是否替换？") != QMessageBox.Yes
                ):
                    return
            try:
                self.write_transcript(source, target)
                self.status.setText("转录原文已另存为 Markdown。")
            except OSError:
                self.error("转录保存失败，请检查目录权限。")

    @staticmethod
    def write_transcript(source, target):
        import tempfile

        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".transcript-", delete=False) as stream:
            temporary = Path(stream.name)
        try:
            temporary.write_bytes(source.read_bytes())
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def autosave_pdf(self, source, title):
        import tempfile
        import datetime

        directory = Path(self.default_pdf_dir).expanduser()
        # Never overwrite an earlier lecture, even when titles repeat.
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target = directory / (title + "-" + stamp + ".pdf")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, prefix=".lecture-", suffix=".pdf", delete=False) as stream:
                temporary = Path(stream.name)
            export_pdf(source, temporary)
            temporary.replace(target)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        return target

    def finish_ready(self, ok, path):
        self.finishing = False
        self.lecture_ended = True
        self.start.setEnabled(True)
        self.sync_capture_controls()
        if not ok:
            self.status.setText("部分内容未整理成功，原文和已有笔记仍在备份中。")
        else:
            self.status.setText("整理完成，备份已保存。")
        if not path:
            return
        title = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", self.engine.note_title).strip(" .")[:60] or "课程笔记"
        transcript = Path(path).with_name("transcript.md")
        import datetime

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        try:
            target = Path(self.default_pdf_dir).expanduser() / (title + "-" + stamp + "-转录.md")
            self.write_transcript(transcript, target)
            transcript_notice = "\n转录原文已自动保存：" + str(target)
        except OSError:
            transcript_notice = "\n转录原文自动保存失败，请使用“另存转录”；应用内原文备份仍保留。"
        try:
            automatic = self.autosave_pdf(Path(path).read_text(encoding="utf-8"), title)
            notice = "PDF 已自动保存至默认位置\n" + str(automatic)
            self.status.setText("PDF 已自动保存；应用内 Markdown 备份仍保留。")
        except (OSError, RuntimeError):
            notice = "PDF 自动保存失败，请检查默认目录权限，或选择另存为 PDF。\n应用内 Markdown 备份仍保留。"
            self.status.setText("PDF 自动保存失败；Markdown 备份已保留。")
        kind = choose_export_format(self, notice + transcript_notice)
        if kind is None:
            return
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "另存本次课程笔记（应用内备份仍保留）",
            str(Path(self.last_export_dir) / (title + "." + kind)),
            "Markdown (*.md)" if kind == "md" else "PDF (*.pdf)",
        )
        if destination:
            try:
                target = Path(destination)
                if target.suffix.lower() != "." + kind:
                    target = target.with_name(target.name + "." + kind)
                    if (
                        target.exists()
                        and QMessageBox.question(self, "替换文件", "此文件已存在，是否替换？") != QMessageBox.Yes
                    ):
                        return
                import tempfile

                with tempfile.NamedTemporaryFile(
                    dir=target.parent, prefix=".lecture-", suffix="." + kind, delete=False
                ) as stream:
                    temporary = Path(stream.name)
                    if kind == "md":
                        stream.write(Path(path).read_bytes())
                try:
                    if kind == "pdf":
                        export_pdf(Path(path).read_text(encoding="utf-8"), temporary)
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
                self.last_export_dir = str(target.parent)
                self.save_preferences()
                self.status.setText("笔记已另存；应用内备份仍保留。")
            except OSError:
                self.error("另存失败，请检查目录权限。应用内备份仍安全保留。")

    def open_recent_note(self, path):
        from recent_notes import read_note

        if self.finishing or self.paused or self.engine.active or self.engine.notes_busy:
            self.error("请先结束当前收音并等待笔记整理完成，再打开历史笔记。")
            return
        if not self.notes.end_editing():
            return
        try:
            document = read_note(DATA_ROOT, path)
            self.engine.open_saved_document(document)
            self.notes.set_document(document)
            self.lecture_ended = False
            self.refresh_end_button()
            self.status.setText("已打开历史笔记；修改或继续记录时会保存续写副本，原文件保留。")
        except (OSError, ValueError):
            self.error("无法打开笔记：文件已不可用，或当前笔记仍在整理中。")

    def import_notes(self):
        if self.finishing or not self.notes.end_editing():
            return
        path, _ = QFileDialog.getOpenFileName(self, "导入 Markdown 作为续课基础", "", "Markdown (*.md *.markdown)")
        if not path:
            return
        try:
            source = Path(path)
            if source.stat().st_size > 2_000_000:
                raise ValueError("文件超过 2 MB，请拆分后导入")
            document = source.read_text(encoding="utf-8-sig")
            self.engine.replace_document(document)
            self.notes.set_document(document)
            self.notes.has_content = bool(document.strip())
            self.refresh_end_button()
            self.status.setText("已导入续课笔记；原文件未修改。自动笔记开启后会发送此基础笔记用于整理。")
        except (OSError, ValueError):
            self.error("导入失败：请选择 UTF-8 Markdown，大小不超过 2 MB。")

    def show_about(self):
        if self.about is None:
            self.about = QDialog(self)
            self.about.setWindowTitle("关于 Lecture Caption")
            self.about.resize(460, 300)
            layout = QVBoxLayout(self.about)
            label = QLabel(
                f"<b>Lecture Caption {updater.current_version()}</b><br>开发者：Yichen Chen<br>"
                '<a href="mailto:superboycyc@gmail.com">superboycyc@gmail.com</a><br><br>'
                f'<a href="{updater.REPOSITORY}">GitHub / 源代码与问题反馈</a><br>'
                f'<a href="{updater.REPOSITORY}/releases/latest">软件下载与更新</a>'
                "<br><br>MIT 开源许可 · 第三方许可随应用提供"
            )
            label.setOpenExternalLinks(True)
            layout.addWidget(label)
            self.update_status = QLabel("尚未检查更新")
            self.update_status.setWordWrap(True)
            layout.addWidget(self.update_status)
            auto = QCheckBox("自动更新")
            auto.setChecked(self.auto_update.isChecked())
            auto.toggled.connect(self.auto_update.setChecked)
            self.auto_update.toggled.connect(auto.setChecked)
            auto.toggled.connect(lambda _: self.save_preferences())
            layout.addWidget(auto)
            self.update_button = QPushButton("检查更新 / 一键更新")
            self.update_button.clicked.connect(self.update_action)
            layout.addWidget(self.update_button)
            guide = QPushButton("重新打开首次使用指南")
            guide.clicked.connect(self.show_setup)
            layout.addWidget(guide)
            rules = QPushButton("软件使用规则")
            rules.clicked.connect(lambda: self.show_rules(self.about))
            layout.addWidget(rules)
        self.about.show()
        self.about.raise_()

    def automatic_update(self):
        if self.auto_update.isChecked() and not os.environ.get("LECTURE_CAPTION_NO_UPDATE"):
            self.check_update(True)

    def update_action(self):
        if self.staged_update:
            self.install_update()
        else:
            self.check_update(False)

    def check_update(self, automatic=False):
        if automatic and self.staged_update:
            return
        if self.update_busy:
            return
        self.update_busy = True
        if self.about:
            self.update_status.setText("正在检查并下载官方最新版本…")

        def run():
            try:
                release = updater.latest_release()
                if updater.version_tuple(release["tag_name"]) <= updater.version_tuple(updater.current_version()):
                    self.sig.update_result.emit({"automatic": automatic}, "当前版本已是最新，或为较新的本地预览版。")
                    return
                app = updater.stage_release(release, DATA_ROOT / "updates")
                self.sig.update_result.emit(
                    {"app": app, "automatic": automatic}, "新版已下载并校验，点击即可安装并重新打开。"
                )
            except Exception:
                self.sig.update_result.emit({}, "更新检查或下载失败，当前应用不受影响。请稍后重试或从 GitHub 下载。")

        threading.Thread(target=run, daemon=True).start()

    def update_received(self, result, message):
        self.update_busy = False
        if result.get("app"):
            self.staged_update = result["app"]
        if self.about:
            self.update_status.setText(message)
            if self.staged_update:
                self.update_button.setText("安装更新并重新打开")
        if self.staged_update:
            self.status.setText(message)
            if (
                result.get("automatic")
                and self.auto_update.isChecked()
                and not self.engine.session_dir
                and not self.notes.dirty
            ):
                self.install_update()
            elif not result.get("automatic"):
                self.install_update()

    def install_update(self):
        if (
            self.setup_busy
            or (self.onboarding and self.onboarding.isVisible())
            or (self.tour and self.tour.isVisible())
        ):
            self.status.setText("新版已就绪；首次配置结束后可从关于窗口安装。")
            return
        if self.engine.active or self.finishing or self.paused or self.engine.notes_busy or self.notes.dirty:
            self.error("请先结束收音、完成另存并关闭笔记编辑窗口，再安装更新。")
            return
        if self.engine.pending and not self.lecture_ended:
            self.error("还有尚未整理内容，请先结束并另存笔记后重试更新。")
            return
        try:
            self.engine.save_notes()
            self.save_preferences()
            updater.launch_installer(self.staged_update)
            self.close()
        except Exception:
            self.error("无法启动安装。请将应用移入“应用程序”，或从 GitHub 下载新版；原应用仍保留。")

    def caption(self, ident, text, translation, started=None, ended=None):
        if not self.engine.active:
            return
        self.current = max(self.current, ident)
        self.history.append(ident, text, translation, started, ended)

    def error(self, message):
        QMessageBox.warning(self, "Lecture Caption", message)

    def capture_failed(self, message):
        if self.engine.active:
            self.toggle()
        self.status.setText(message)
        self.error(message)

    def closeEvent(self, event):
        if self.finishing:
            event.ignore()
            self.status.setText("正在完成最后整理，请先完成另存后关闭。")
            return
        if not self.notes.end_editing():
            event.ignore()
            return
        self.engine.stop()
        self.engine.close()
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
    from app_install import ensure_installed

    if not ensure_installed():
        sys.exit(0)
    main = Controls()
    main.show()
    if "--preview" in sys.argv:

        def capture_preview():
            main.history.append(
                1,
                "A binary search tree maintains an ordering invariant. Its left subtree contains smaller keys and its right subtree contains larger keys.",
                "二叉搜索树保持有序性不变量（ordering invariant）：左子树包含较小的键，右子树包含较大的键。",
                time.time() - 18,
                time.time() - 7,
            )
            main.history.append(
                2,
                "The running time depends on the height of the tree, so balancing the tree helps us keep searches efficient.",
                "运行时间取决于树高，因此保持树的平衡有助于提高查找效率。",
                time.time() - 6,
                time.time(),
            )
            main.notes.update(
                "# 二叉搜索树\n\n## 核心定义\n\n- 左子树的键小于当前节点，右子树的键大于当前节点。\n\n## 时间复杂度\n\n- 查找代价取决于树高 $h$。\n\n> 界面示例，非真实课堂转写。",
                "界面示例",
            )

            def save_preview():
                main.grab().save(str(DATA_ROOT / "logs/workspace-preview.png"))
                main.close()

            QTimer.singleShot(350, save_preview)

        QTimer.singleShot(1000, capture_preview)
    result = app.exec()
    from PySide6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    sys.exit(result)

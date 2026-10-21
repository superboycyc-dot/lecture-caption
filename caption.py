from pathlib import Path
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
)
from core import ROOT, ASSET_ROOT, DATA_ROOT, Engine, DEFAULTS
import sounddevice as sd
import requests
from credentials import CredentialStore
import updater


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
        QTimer.singleShot(0, self.on_scroll_position)

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
        QTimer.singleShot(0, self.scroll_latest)

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
        self.import_button = icon_button("import", "导入 Markdown 续课笔记", lambda: None)
        self.edit_button = icon_button("edit", "编辑当前笔记", lambda: None)
        row.addWidget(self.import_button)
        row.addWidget(self.edit_button)
        row.addStretch()
        self.update_button = icon_button("refresh", "立即整理笔记", self.engine.force_notes.set)
        self.folder_button = icon_button("folder", "打开笔记文件夹", self.open_folder)
        row.addWidget(self.update_button)
        row.addWidget(self.folder_button)
        body.addLayout(row)
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget {background:white;border:0;}")
        placeholder = QWidget()
        placeholder.setObjectName("notesPlaceholder")
        placeholder.setAttribute(Qt.WA_StyledBackground, True)
        placeholder.setStyleSheet("QWidget#notesPlaceholder {background:white;border:0;}")
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
        self.finishing = False
        self.lecture_ended = False
        self.last_export_dir = config.get("last_export_dir", str(Path.home() / "Documents"))
        self.staged_update = None
        self.update_busy = False
        self.about = None
        self.editor = None
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
        self.status.setWordWrap(False)
        self.status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.status.setStyleSheet("font-size:11px;color:#8295AD;")
        self.notes.layout().addWidget(self.status)
        footer = QHBoxLayout()
        self.quota = QLabel()
        self.quota.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.quota.setStyleSheet("color:#6C829D;font-size:11px;")
        footer.addWidget(self.quota, 1)
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
        self.notes.import_button.clicked.connect(self.import_notes)
        self.notes.edit_button.clicked.connect(self.edit_notes)
        self.sig.note_status.connect(self.notes.note_status)
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
        self.refresh_quota()
        QShortcut(QKeySequence("Ctrl+Space"), self, activated=self.toggle)
        QShortcut(QKeySequence("Meta+,"), self, activated=self.show_settings)
        QShortcut(QKeySequence("Meta+Q"), self, activated=self.close)
        QTimer.singleShot(0, lambda: self.credential_action("load"))
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(6 * 60 * 60 * 1000)
        self.update_timer.timeout.connect(self.automatic_update)
        self.update_timer.start()
        if not os.environ.get("LECTURE_CAPTION_NO_UPDATE") and "--preview" not in sys.argv:
            QTimer.singleShot(2000, self.automatic_update)

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
        self.notes_on.setToolTip(
            "启用后，以当前课堂累计原文、连续上下文和已有笔记发送给 Groq 整体整理。完整原文同时保存在本机 transcript.md。"
        )
        form.addRow(self.notes_on)
        self.revise_interval = QComboBox()
        for minutes in range(1, 6):
            self.revise_interval.addItem(f"每 {minutes} 分钟", minutes * 60)
        self.revise_interval.setCurrentIndex(max(0, self.revise_interval.findData(config.get("revise_interval", 180))))
        self.revise_interval.currentIndexChanged.connect(
            lambda: self.engine.config.update(revise_interval=self.revise_interval.currentData())
        )
        form.addRow("自动二次整理与命名", self.revise_interval)
        self.auto_update = QCheckBox("自动更新（自动检查和下载，空闲时安装）")
        self.auto_update.setChecked(config.get("auto_update", True))
        self.auto_update.setToolTip("启动及每6小时检查官方 GitHub；有课堂笔记或录音时不会自动重启。")
        form.addRow(self.auto_update)
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
        desired = {
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
            "revise_interval": self.revise_interval.currentData(),
            "last_export_dir": self.last_export_dir,
            "auto_update": self.auto_update.isChecked(),
        }
        # Only apply pipeline preferences while capture is stopped. Active changes
        # are coalesced into a generation-safe handoff by apply_live_selection.
        if not self.engine.active:
            self.engine.config.update(desired)
        combined = {**self.engine.config, **desired}
        data = {k: combined[k] for k in DEFAULTS}
        for k in (
            "notes_enabled",
            "glossary",
            "threshold",
            "font_size",
            "display_mode",
            "opacity",
            "last_export_dir",
            "auto_update",
        ):
            data[k] = combined[k]
        temp = DATA_ROOT / "config.tmp"
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.chmod(0o600)
        temp.replace(DATA_ROOT / "config.json")
        self.refresh_quota()

    def refresh_quota(self):
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

    def on_status(self, message):
        if message.startswith("●"):
            self.status.clear()
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
                self.show_settings()
                self.error("当前模式需要 Groq API key。纯本地字幕请选择两项 Apple 并关闭自动笔记。")
                return
            if self.lecture_ended:
                self.engine.session_dir = None
                self.engine.source_paragraphs.clear()
                self.engine.last_revise = time.monotonic()
                self.lecture_ended = False
            self.config_from_ui()
            self.engine.start(self.input.currentData())
            if self.engine.active:
                self.paused = False
        self.sync_capture_controls()

    def sync_capture_controls(self):
        active = self.engine.active
        self.start.setText("Ⅱ 暂停" if active else "▶ 继续" if self.paused else "▶ 开始")
        self.stop_button.setEnabled(active or self.paused)
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
        if self.editor:
            self.error("请先保存修改并关闭笔记编辑窗口，再结束课程。")
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
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "另存本次课程笔记（应用内备份仍保留）",
            str(Path(self.last_export_dir) / (title + ".md")),
            "Markdown (*.md)",
        )
        if destination:
            try:
                target = Path(destination)
                if target.suffix.lower() != ".md":
                    target = target.with_name(target.name + ".md")
                import tempfile

                with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".lecture-", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(Path(path).read_bytes())
                try:
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
                self.last_export_dir = str(target.parent)
                self.save_preferences()
                self.status.setText("笔记已另存；应用内备份仍保留。")
            except OSError:
                self.error("另存失败，请检查目录权限。应用内备份仍安全保留。")

    def import_notes(self):
        if self.finishing or self.editor:
            self.error("请先完成整理或关闭笔记编辑窗口。")
            return
        path, _ = QFileDialog.getOpenFileName(self, "导入 Markdown 作为续课基础", "", "Markdown (*.md *.markdown)")
        if not path:
            return
        try:
            source = Path(path)
            if source.stat().st_size > 2_000_000:
                raise ValueError("文件超过 2 MB，请拆分后导入")
            self.engine.replace_document(source.read_text(encoding="utf-8-sig"))
            self.status.setText("已导入续课笔记；原文件未修改。自动笔记开启后会发送此基础笔记用于整理。")
        except (OSError, ValueError):
            self.error("导入失败：请选择 UTF-8 Markdown，大小不超过 2 MB。")

    def edit_notes(self):
        if self.finishing:
            return
        if self.editor:
            self.editor.raise_()
            return
        dialog = self.editor = QDialog(self)
        dialog.setWindowTitle("编辑 Markdown 笔记")
        dialog.resize(760, 640)
        layout = QVBoxLayout(dialog)
        edit = QPlainTextEdit()
        with self.engine.notes_lock:
            edit.setPlainText("\n\n".join(self.engine.sections))
        layout.addWidget(edit)
        save = QPushButton("保存修改")
        layout.addWidget(save)

        def commit():
            try:
                self.engine.replace_document(edit.toPlainText())
                dialog.accept()
            except (OSError, ValueError):
                self.error("保存失败，请检查笔记大小和目录权限。")

        save.clicked.connect(commit)
        dialog.finished.connect(lambda _: setattr(self, "editor", None))
        dialog.show()

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
                and not self.editor
            ):
                self.install_update()
            elif not result.get("automatic"):
                self.install_update()

    def install_update(self):
        if self.engine.active or self.finishing or self.paused or self.engine.notes_busy or self.editor:
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
        if self.editor:
            event.ignore()
            self.editor.raise_()
            return
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
            QTimer.singleShot(350, lambda: main.grab().save(str(DATA_ROOT / "logs/workspace-preview.png")))

        QTimer.singleShot(1000, capture_preview)
        QTimer.singleShot(2200, app.quit)
    sys.exit(app.exec())

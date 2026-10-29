"""Offline Vditor editor. Only bundled assets may be requested by its web view."""

import json
import re
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot, QUrl, QEventLoop, QTimer, Qt, QEvent
from PySide6.QtGui import QPageLayout, QPageSize, QKeySequence, QShortcut
from PySide6.QtCore import QMarginsF
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from math_render import TOKENS


def editor_markdown(source):
    """Adapt legacy TeX delimiters for CommonMark, without touching code examples."""

    def replace(match):
        if match.group("code"):
            return match.group()
        value = match.group()
        if value.startswith(r"\("):
            return "$" + value[2:-2].strip() + "$"
        if value.startswith(r"\["):
            return "$$\n" + value[2:-2].strip() + "\n$$"
        return value

    return TOKENS.sub(replace, source)


class AssetRequests(QWebEngineUrlRequestInterceptor):
    def __init__(self, root, parent):
        super().__init__(parent)
        self.root = root.resolve()
        self.blocked = []

    def interceptRequest(self, info):
        url = info.requestUrl()
        allowed = url.scheme() in ("qrc", "data")
        if url.isLocalFile():
            allowed = Path(url.toLocalFile()).resolve().is_relative_to(self.root)
        if not allowed:
            # Record scheme only, never arbitrary note URLs or content.
            self.blocked.append(url.scheme())
            info.block(True)


class LocalPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, kind, main):
        return url.isLocalFile() and Path(url.toLocalFile()).resolve() == self.entry

    def javaScriptConsoleMessage(self, level, message, line, source):
        # Console errors may quote private note content. Do not log them.
        pass


class NoteBridge(QObject):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    @Slot()
    def started(self):
        self.editor.ready = True
        self.editor.push_document()
        self.editor.loaded.emit()

    @Slot(int)
    def touched(self, epoch):
        if epoch == self.editor.epoch:
            self.editor.textChanged.emit()

    @Slot(int, str)
    def edited(self, epoch, value):
        self.editor.receive(epoch, value)


def javascript(page, script, timeout=5000):
    """A short barrier before save/end; never silently save a stale mirror."""
    loop = QEventLoop()
    result = []
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)

    def done(value):
        result.append(value)
        loop.quit()

    page.runJavaScript("JSON.stringify((" + script + "))", lambda value: done(json.loads(value) if value else None))
    timer.start(timeout)
    loop.exec()
    timer.stop()
    if not result:
        raise ValueError("笔记编辑器响应超时，编辑内容仍保留在窗口中")
    return result[0]


class WebMarkdownEdit(QWebEngineView):
    textChanged = Signal()
    command = Signal(str)
    loaded = Signal()
    load_failed = Signal()

    def __init__(self, assets):
        super().__init__()
        self.ready = False
        self.value = ""
        self.epoch = 0
        root = Path(assets) / "notes"
        self.profile = QWebEngineProfile()
        self.profile.setHttpCacheType(QWebEngineProfile.NoCache)
        self.interceptor = AssetRequests(root, self.profile)
        self.profile.setUrlRequestInterceptor(self.interceptor)
        page = LocalPage(self.profile, self)
        page.entry = (root / "editor.html").resolve()
        self.setPage(page)
        page.destroyed.connect(self.profile.deleteLater)
        settings = page.settings()
        for attribute in (
            QWebEngineSettings.LocalContentCanAccessRemoteUrls,
            QWebEngineSettings.JavascriptCanOpenWindows,
            QWebEngineSettings.JavascriptCanAccessClipboard,
            QWebEngineSettings.HyperlinkAuditingEnabled,
        ):
            settings.setAttribute(attribute, False)
        self.channel = QWebChannel(page)
        self.bridge = NoteBridge(self)
        self.channel.registerObject("notes", self.bridge)
        page.setWebChannel(self.channel)
        self.shortcuts = []
        for sequence, name in (
            ("Ctrl+B", "bold"),
            ("Ctrl+I", "italic"),
            ("Ctrl+H", "highlight"),
            ("Ctrl+Shift+X", "strike"),
            ("Ctrl+Alt+1", "h1"),
            ("Ctrl+Alt+2", "h2"),
            ("Ctrl+Alt+3", "h3"),
            ("Ctrl+Shift+7", "number"),
            ("Ctrl+Shift+8", "bullet"),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda cmd=name: self.command.emit(cmd))
            self.shortcuts.append(shortcut)
        self.load_timer = QTimer(self)
        self.load_timer.setSingleShot(True)
        self.load_timer.timeout.connect(lambda: self.load_failed.emit() if not self.ready else None)
        self.load_timer.start(15000)
        self.loaded.connect(self.load_timer.stop)
        self.loadFinished.connect(self.watch_input)
        self.setUrl(QUrl.fromLocalFile(str(page.entry)))

    def watch_input(self, *_):
        proxy = self.focusProxy()
        if proxy:
            proxy.installEventFilter(self)

    def eventFilter(self, watched, event):
        # Mark a native edit before the renderer's asynchronous input message,
        # so an arriving AI response cannot replace a just-typed character.
        if self.ready:
            modifying = event.type() == QEvent.InputMethod
            if event.type() == QEvent.KeyPress:
                modifying = bool(event.text() and event.text().isprintable()) or event.key() in (
                    Qt.Key_Backspace,
                    Qt.Key_Delete,
                    Qt.Key_Return,
                    Qt.Key_Enter,
                )
                if event.modifiers() & Qt.ControlModifier:
                    modifying = event.key() in (Qt.Key_V, Qt.Key_X, Qt.Key_Z)
            if modifying:
                self.textChanged.emit()
        return super().eventFilter(watched, event)

    def receive(self, epoch, value):
        if epoch != self.epoch or value == self.value:
            return
        self.value = value
        self.textChanged.emit()

    def set_markdown(self, value):
        self.epoch += 1
        self.value = editor_markdown(value)
        if self.ready:
            self.push_document()

    def push_document(self):
        self.page().runJavaScript(f"window.setDocument({json.dumps(self.value)}, {self.epoch})")

    def markdown(self):
        if self.ready:
            state = javascript(self.page(), "window.snapshot()")
            if not isinstance(state, dict) or state.get("epoch") != self.epoch or state.get("composing"):
                raise ValueError("笔记编辑器正在更新，请稍后重试")
            if state.get("modified"):
                self.receive(self.epoch, state["value"])
            else:
                self.value = state["value"]
        return self.value

    def toPlainText(self):
        return self.value

    def setPlaceholderText(self, text):
        self.setToolTip(text)

    def format(self, name):
        if self.ready:
            self.textChanged.emit()
            self.page().runJavaScript(f"window.command({json.dumps(name)})")


def export_web_pdf(source, destination, assets):
    editor = WebMarkdownEdit(assets)
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    editor.loaded.connect(loop.quit)
    timer.start(15000)
    if not editor.ready:
        loop.exec()
    timer.stop()
    try:
        if not editor.ready:
            raise ValueError("PDF 编辑器加载超时")
        editor.set_markdown(source)
        javascript(
            editor.page(),
            "(()=>{window.printReady=false;window.preparePrint("
            + json.dumps(editor_markdown(source))
            + ");return true;})()",
        )
        poll = QTimer()
        poll.setInterval(50)
        ready = [False]

        def check():
            editor.page().runJavaScript(
                "window.printReady===true", lambda value: (ready.__setitem__(0, value), loop.quit()) if value else None
            )

        poll.timeout.connect(check)
        poll.start()
        timer.start(15000)
        loop.exec()
        poll.stop()
        timer.stop()
        if not ready[0]:
            raise ValueError("PDF 公式排版超时")
        output = []

        def printed(data):
            output.append(bytes(data))
            loop.quit()

        layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(16, 16, 16, 16))
        editor.page().printToPdf(printed, layout)
        timer.start(15000)
        loop.exec()
        timer.stop()
        if not output or not output[0].startswith(b"%PDF-"):
            raise ValueError("PDF 导出失败")
        Path(destination).write_bytes(output[0])
    finally:
        editor.close()
        editor.deleteLater()

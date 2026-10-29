"""Inline rich Markdown editing, source mode, highlight extension and local PDF export."""

from pathlib import Path
import re
import time
from PySide6.QtCore import Qt, Signal, QTimer, QEvent, QMarginsF
from PySide6.QtGui import (
    QTextDocument,
    QTextDocumentFragment,
    QTextCursor,
    QTextCharFormat,
    QTextBlockFormat,
    QTextListFormat,
    QColor,
    QFont,
    QPdfWriter,
    QPageSize,
    QDesktopServices,
)
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QWidget,
    QTextEdit,
    QPlainTextEdit,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QToolButton,
    QStackedWidget,
    QMenu,
    QDialog,
    QLabel,
    QPushButton,
    QWidgetAction,
)

from web_notes import WebMarkdownEdit, export_web_pdf

from math_render import protect_math, render_math, restore_math, insert_math, MATH_SOURCE

HIGHLIGHT = "#FFF1A6"


def apply_highlights(document):
    ranges = []
    block = document.begin()
    while block.isValid():
        if not block.blockFormat().nonBreakableLines():
            text = block.text()
            for match in re.finditer(r"(?<![=])==([^=\n]+)==(?![=])", text):
                start = block.position() + utf16(text[: match.start()])
                end = block.position() + utf16(text[: match.end()])
                cursor = QTextCursor(document)
                cursor.setPosition(start + 1)
                start_code = cursor.charFormat().fontFixedPitch()
                cursor.setPosition(end - 1)
                if not start_code and not cursor.charFormat().fontFixedPitch():
                    ranges.append((start, end))
        block = block.next()
    for start, end in reversed(ranges):
        cursor = QTextCursor(document)
        cursor.setPosition(end - 2)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.setPosition(start)
        cursor.setPosition(start + 2, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.setPosition(start)
        cursor.setPosition(end - 4, QTextCursor.KeepAnchor)
        form = QTextCharFormat()
        form.setBackground(QColor(HIGHLIGHT))
        cursor.mergeCharFormat(form)


def protect_escaped_highlights(source, sentinel):
    output, fence = [], None
    for line in source.splitlines(keepends=True):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            output.append(line)
            continue
        if fence or line.startswith(("    ", "\t")):
            output.append(line)
            continue
        parts = re.split(r"(`+[^\n]*?`+)", line)
        for index in range(0, len(parts), 2):
            parts[index] = re.sub(r"\\==([^\n]*?)==", lambda match: sentinel + match.group(1) + sentinel, parts[index])
            parts[index] = parts[index].replace(r"\==", sentinel)
        output.append("".join(parts))
    return "".join(output)


def markdown_document(source, document=None):
    if document is None:
        document = QTextDocument()
    document.setDefaultFont(QFont("PingFang SC", 11))
    document.setDefaultStyleSheet(
        "body {color:#1C1C1E;} table {border-collapse:collapse;} td,th {padding:5px;border:1px solid #D9E4F2;}"
    )
    escaped = "\ue0fa\ue0fb"
    protected, expressions = protect_math(source)
    document.setMarkdown(protect_escaped_highlights(protected, escaped))
    render_math(document, expressions)
    apply_highlights(document)
    cursor = document.find(escaped)
    while not cursor.isNull():
        cursor.insertText("==")
        cursor = document.find(escaped)
    return document


def rich_markdown(document):
    """Qt omits background formatting from Markdown; restore == spans in a clone."""
    clone = document.clone()
    formulas = restore_math(clone)
    literal = "\ue110\ue111"
    block = clone.begin()
    escapes = []
    while block.isValid():
        if not block.blockFormat().nonBreakableLines():
            for match in re.finditer("==", block.text()):
                start = block.position() + utf16(block.text()[: match.start()])
                cursor = QTextCursor(clone)
                cursor.setPosition(start + 1)
                if not cursor.charFormat().fontFixedPitch():
                    escapes.append(start)
        block = block.next()
    for start in reversed(escapes):
        cursor = QTextCursor(clone)
        cursor.setPosition(start)
        cursor.setPosition(start + 2, QTextCursor.KeepAnchor)
        cursor.insertText(literal, cursor.charFormat())
    ranges = []
    block = clone.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.charFormat().background().color().name().upper() == HIGHLIGHT:
                start, end = fragment.position(), fragment.position() + fragment.length()
                if ranges and ranges[-1][1] == start:
                    ranges[-1] = (ranges[-1][0], end)
                else:
                    ranges.append((start, end))
            iterator += 1
        block = block.next()
    for start, end in reversed(ranges):
        cursor = QTextCursor(clone)
        cursor.setPosition(end)
        cursor.insertText("==", QTextCharFormat())
        cursor.setPosition(start)
        cursor.insertText("==", QTextCharFormat())
    result = clone.toMarkdown(QTextDocument.MarkdownDialectGitHub).strip().replace(literal, r"\==")
    for token, original in formulas.items():
        result = result.replace(token, original)
    return result


def export_pdf(source, destination):
    from core import ASSET_ROOT

    try:
        export_web_pdf(source, destination, ASSET_ROOT)
    except ValueError as error:
        raise OSError("PDF 排版失败；Markdown 备份仍保留") from error


def choose_export_format(parent, notice="PDF 已自动保存至默认位置"):
    dialog = QDialog(parent)
    dialog.setWindowTitle("保存本次笔记")
    layout = QVBoxLayout(dialog)
    label = QLabel(notice)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    layout.addWidget(label)
    result = [None]
    for title, kind in (("另存为 MD", "md"), ("另存为 PDF", "pdf")):
        button = QPushButton(title)
        button.clicked.connect(lambda _, value=kind: (result.__setitem__(0, value), dialog.accept()))
        layout.addWidget(button)
    cancel = QPushButton("完成")
    cancel.clicked.connect(dialog.reject)
    layout.addWidget(cancel)
    dialog.exec()
    return result[0]


def utf16(text):
    return len(text.encode("utf-16-le")) // 2


def before_cursor(cursor):
    return cursor.block().text().encode("utf-16-le")[: cursor.positionInBlock() * 2].decode("utf-16-le")


class RichMarkdownEdit(QTextEdit):
    command = Signal(str)

    def mouseDoubleClickEvent(self, event):
        cursor = self.cursorForPosition(event.position().toPoint())
        position = cursor.position()
        for start in (position, position - 1):
            if start < 0:
                continue
            cursor.setPosition(start)
            cursor.setPosition(start + 1, QTextCursor.KeepAnchor)
            original = cursor.charFormat().property(MATH_SOURCE)
            if original and cursor.charFormat().isImageFormat():
                from PySide6.QtWidgets import QInputDialog

                edited, ok = QInputDialog.getMultiLineText(
                    self, "编辑公式", "保留公式分隔符，例如 \\[ ... \\]：", original
                )
                if ok and edited.strip():
                    insert_math(cursor, edited.strip())
                return
        super().mouseDoubleClickEvent(event)

    def event(self, event):
        if event.type() == QEvent.ShortcutOverride and self.command_for(event):
            event.accept()
            return True
        return super().event(event)

    @staticmethod
    def command_for(event):
        modifiers = event.modifiers()
        if not modifiers & Qt.ControlModifier:
            return None
        if modifiers & Qt.AltModifier:
            return {Qt.Key_1: "h1", Qt.Key_2: "h2", Qt.Key_3: "h3"}.get(event.key())
        if modifiers & Qt.ShiftModifier:
            return {Qt.Key_X: "strike", Qt.Key_7: "number", Qt.Key_8: "bullet"}.get(event.key())
        return {Qt.Key_B: "bold", Qt.Key_I: "italic", Qt.Key_H: "highlight"}.get(event.key())

    def insertFromMimeData(self, source):
        text = source.text()
        if not source.hasHtml() and re.search(r"(^|\n)(#{1,6} |[-*] |```)|\*\*.+?\*\*|==.+?==|~~.+?~~", text):
            fragment = QTextDocumentFragment(markdown_document(text))
            self.textCursor().insertFragment(fragment)
        else:
            super().insertFromMimeData(source)

    def keyPressEvent(self, event):
        action = self.command_for(event)
        if action:
            self.command.emit(action)
            return
        cursor = self.textCursor()
        prefix = before_cursor(cursor)
        if (
            not cursor.blockFormat().nonBreakableLines()
            and not cursor.charFormat().fontFixedPitch()
            and event.key() == Qt.Key_Space
            and re.fullmatch(r"#{1,3}|[-*+]|\d+\.|>", prefix)
        ):
            cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            self.setTextCursor(cursor)
            if prefix.startswith("#"):
                self.command.emit("h" + str(len(prefix)))
            elif prefix == ">":
                form = QTextBlockFormat()
                form.setLeftMargin(22)
                cursor.mergeBlockFormat(form)
            else:
                self.command.emit("number" if prefix[0].isdigit() else "bullet")
            return
        super().keyPressEvent(event)
        if (
            event.text() not in ("*", "=", "~")
            or self.currentCharFormat().fontFixedPitch()
            or self.textCursor().blockFormat().nonBreakableLines()
        ):
            return
        cursor = self.textCursor()
        before = before_cursor(cursor)
        patterns = (
            (r"(?<![\\*])\*\*([^*\n]+)\*\*$", "bold"),
            (r"(?<![\\=])==([^=\n]+)==$", "highlight"),
            (r"(?<![\\~])~~([^~\n]+)~~$", "strike"),
            (r"(?<![\\*])\*([^*\n]+)\*$", "italic"),
        )
        for pattern, action in patterns:
            match = re.search(pattern, before)
            if not match:
                continue
            cursor.beginEditBlock()
            cursor.setPosition(cursor.block().position() + utf16(before[: match.start()]))
            cursor.setPosition(cursor.block().position() + utf16(before), QTextCursor.KeepAnchor)
            fmt = QTextCharFormat(cursor.charFormat())
            if action == "bold":
                fmt.setFontWeight(QFont.Bold)
            elif action == "italic":
                fmt.setFontItalic(True)
            elif action == "strike":
                fmt.setFontStrikeOut(True)
            else:
                fmt.setBackground(QColor(HIGHLIGHT))
            cursor.insertText(match.group(1), fmt)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
            self.setCurrentCharFormat(QTextCharFormat())
            break


class SourceEdit(QPlainTextEdit):
    command = Signal(str)

    def event(self, event):
        if event.type() == QEvent.ShortcutOverride and RichMarkdownEdit.command_for(event):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        action = RichMarkdownEdit.command_for(event)
        if action:
            self.command.emit(action)
        else:
            super().keyPressEvent(event)


class NotesPane(QWidget):
    recent_requested = Signal(str)
    import_requested = Signal()
    summary_requested = Signal()
    save_failed = Signal(str)
    content_changed = Signal()

    def __init__(self, engine, assets, data_root, *, legacy_editor=False):
        super().__init__()
        self.engine, self.data_root = engine, data_root
        self.has_content = self.loading = self.saving = self.dirty = False
        self.original = ""
        self.last_snapshot = 0
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setObjectName("notesPane")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#notesPane {background:white;border:1px solid #D9E4F2;border-radius:12px;}")
        body = QVBoxLayout(self)
        body.setContentsMargins(8, 5, 8, 8)
        body.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(1)
        from PySide6.QtGui import QIcon

        self.import_button = QToolButton()
        self.import_button.setIcon(QIcon(str(assets / "icons/import.svg")))
        self.import_button.setToolTip("导入 Markdown 续课笔记")
        self.import_button.clicked.connect(self.import_requested.emit)
        row.addWidget(self.import_button)
        self.title = QLineEdit()
        self.title.setPlaceholderText("笔记整理")
        self.title.setMinimumWidth(60)
        self.title.setStyleSheet("font-weight:600;background:transparent;border:0;padding:3px;")
        row.addWidget(self.title, 1)
        commands = (
            ("B", "bold", "加粗 ⌘B"),
            ("I", "italic", "斜体 ⌘I"),
            ("H1", "h1", "一级标题 ⌘⌥1"),
            ("H2", "h2", "二级标题 ⌘⌥2"),
            ("H3", "h3", "三级标题 ⌘⌥3"),
            ("☷", "bullet", "无序列表 ⌘⇧8"),
            ("1≡", "number", "有序列表 ⌘⇧7"),
            ("", "highlight", "高亮 ==文字== · ⌘H"),
            ("S", "strike", "删除线 ⌘⇧X"),
        )
        self.tools = {}
        for text, command, hint in commands:
            button = QToolButton()
            button.setText(text)
            button.setToolTip(hint)
            button.setAccessibleName(hint)
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(lambda _, cmd=command: self.format(cmd))
            if command == "bold":
                font = button.font()
                font.setBold(True)
                button.setFont(font)
            elif command == "italic":
                font = button.font()
                font.setItalic(True)
                button.setFont(font)
            elif command == "strike":
                font = button.font()
                font.setStrikeOut(True)
                button.setFont(font)
            elif command == "highlight":
                button.setIcon(QIcon(str(assets / "icons/highlight.svg")))
                from PySide6.QtCore import QSize

                button.setIconSize(QSize(22, 22))
            self.tools[command] = button
            row.addWidget(button)
        self.more = QToolButton()
        self.more.setText("⋯")
        self.more.setToolTip("更多笔记操作")
        self.more.setPopupMode(QToolButton.InstantPopup)
        self.menu = QMenu(self.more)

        def menu_action(text, callback=None, checkable=False):
            action = QWidgetAction(self.menu)
            action.setText(text)
            action.setCheckable(checkable)
            button = QPushButton(text)
            button.setMinimumWidth(190)
            button.setStyleSheet(
                "QPushButton {text-align:left;padding:9px 12px;background:white;color:#233956;border:0;border-radius:6px;font-weight:400;} QPushButton:hover {background:#E6F0FF;}"
            )
            action.setDefaultWidget(button)
            action.changed.connect(lambda: button.setText(action.text()))

            def activate():
                action.trigger()
                self.menu.close()

            button.clicked.connect(activate)
            if callback:
                action.triggered.connect(callback)
            self.menu.addAction(action)
            return action

        self.source_action = menu_action("查看源代码", checkable=True)
        self.source_action.toggled.connect(self.toggle_source)
        self.summary_action = menu_action("立即整理", self.summary_requested.emit)
        menu_action("最近笔记", lambda: QTimer.singleShot(0, self.show_recent_notes))
        menu_action("打开文件夹", self.open_folder)
        self.more.setMenu(self.menu)
        row.addWidget(self.more)
        self.setStyleSheet(
            self.styleSheet()
            + "QToolButton {background:transparent;border:0;border-radius:5px;padding:2px;color:#53657A;min-width:22px;min-height:26px;} QToolButton:hover {background:#E6F0FF;} QToolButton::menu-indicator {image:none;width:0;} "
        )
        body.addLayout(row)
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget {background:white;border:0;}")
        self.preview = RichMarkdownEdit() if legacy_editor else WebMarkdownEdit(assets)
        self.preview.setPlaceholderText(
            "笔记整理\n\n开始收音后自动生成笔记，也可以直接输入。\n导入上节课的 Markdown，继续记录本节课。"
        )
        if isinstance(self.preview, RichMarkdownEdit):
            self.preview.setAcceptRichText(True)
        self.source = SourceEdit()
        for editor in (self.preview, self.source):
            editor.setStyleSheet("font-size:16px;padding:12px;background:white;color:#1C1C1E;border:0;")
            editor.installEventFilter(self)
            editor.textChanged.connect(self.changed)
            editor.command.connect(self.format)
            self.stack.addWidget(editor)
        self.source.setStyleSheet(self.source.styleSheet() + 'QPlainTextEdit {font-family:"Menlo","PingFang SC";}')
        if isinstance(self.preview, WebMarkdownEdit):
            self.preview.load_failed.connect(self.editor_load_failed)
        self.title.installEventFilter(self)
        self.title.textEdited.connect(self.changed)
        body.addWidget(self.stack, 1)
        from recent_notes import RecentNotesPopup

        self.recent_popup = RecentNotesPopup(self)
        self.recent_popup.list.setProperty("historyIcon", QIcon(str(assets / "icons/history.svg")))
        self.recent_popup.note_selected.connect(self.recent_requested.emit)
        self.recent_button = QPushButton(self.stack)
        self.recent_button.setAccessibleName("打开历史")
        self.recent_button.setCursor(Qt.PointingHandCursor)
        self.recent_button.setFixedSize(300, 96)
        self.recent_button.setStyleSheet(
            "QPushButton {background:#FAFCFF;border:1px solid #E1EAF5;border-radius:16px;}"
            "QPushButton:hover {background:#F1F7FF;border-color:#BDD4F0;}"
            "QPushButton:pressed {background:#E8F2FF;border-color:#A9C8ED;}"
            "QPushButton:focus {border-color:#70A5E5;}"
        )
        entry = QHBoxLayout(self.recent_button)
        entry.setContentsMargins(20, 16, 20, 16)
        entry.setSpacing(14)
        icon = QLabel()
        icon.setFixedSize(44, 44)
        icon.setAlignment(Qt.AlignCenter)
        icon.setPixmap(QIcon(str(assets / "icons/history.svg")).pixmap(26, 26))
        icon.setStyleSheet("background:#EAF3FF;border-radius:12px;border:0;")
        entry.addWidget(icon)
        text = QVBoxLayout()
        text.setSpacing(5)
        title = QLabel("打开历史")
        title.setStyleSheet("color:#29496D;font-size:16px;font-weight:600;background:transparent;border:0;")
        subtitle = QLabel("继续整理之前的课堂笔记")
        subtitle.setStyleSheet("color:#8A9AAF;font-size:12px;background:transparent;border:0;")
        text.addWidget(title)
        text.addWidget(subtitle)
        entry.addLayout(text, 1)
        arrow = QLabel("›")
        arrow.setStyleSheet("color:#8DA9C9;font-size:24px;font-weight:300;background:transparent;border:0;")
        entry.addWidget(arrow)
        for label in (icon, title, subtitle, arrow):
            label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.recent_button.clicked.connect(self.show_recent_notes)
        self.stack.installEventFilter(self)
        self.refresh_recent_button()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self.flush_edits)
        self.focus_timer = QTimer(self)
        self.focus_timer.setSingleShot(True)
        self.focus_timer.timeout.connect(self.leave_editor)
        self.edit_idle_timer = QTimer(self)
        self.edit_idle_timer.setSingleShot(True)
        self.edit_idle_timer.setInterval(2500)
        self.edit_idle_timer.timeout.connect(self.resume_after_edit)

    def editor_load_failed(self):
        self.source_action.setChecked(True)
        self.save_failed.emit("即时编辑器加载失败，已切换到 Markdown 源码；笔记内容已保留。")

    def refresh_recent_button(self):
        self.recent_button.move(
            max(0, (self.stack.width() - self.recent_button.width()) // 2),
            max(0, (self.stack.height() - self.recent_button.height()) // 2),
        )
        self.recent_button.setVisible(not self.has_content and not self.engine.active)
        self.recent_button.raise_()

    def show_recent_notes(self):
        from recent_notes import recent_notes
        from PySide6.QtCore import QPoint

        entries = recent_notes(self.data_root)
        self.recent_popup.populate(entries)
        screen = self.screen().availableGeometry()
        self.recent_popup.resize(
            min(480, screen.width()), min(140 + max(1, min(4, len(entries))) * 84, screen.height())
        )
        center = self.mapToGlobal(self.rect().center())
        x = max(
            screen.left(),
            min(center.x() - self.recent_popup.width() // 2, screen.right() - self.recent_popup.width() + 1),
        )
        y = max(
            screen.top(),
            min(center.y() - self.recent_popup.height() // 2, screen.bottom() - self.recent_popup.height() + 1),
        )
        self.recent_popup.move(QPoint(x, y))
        self.recent_popup.show()
        self.recent_popup.list.setFocus()

    def eventFilter(self, watched, event):
        if watched is self.stack and event.type() == QEvent.Resize:
            self.refresh_recent_button()
        if event.type() == QEvent.FocusOut:
            self.focus_timer.start(0)
        return super().eventFilter(watched, event)

    def resume_after_edit(self):
        if not self.flush_edits():
            return
        with self.engine.notes_lock:
            self.engine.notes_editing = False

    def leave_editor(self):
        from PySide6.QtWidgets import QApplication

        focus = QApplication.focusWidget()
        if self.window().isActiveWindow() and focus in (self.preview, self.source, self.title):
            return
        if self.flush_edits():
            self.engine.notes_editing = False

    def end_editing(self):
        self.edit_idle_timer.stop()
        if not self.flush_edits():
            return False
        self.preview.clearFocus()
        self.source.clearFocus()
        self.title.clearFocus()
        self.engine.notes_editing = False
        return True

    def changed(self):
        if self.loading:
            return
        self.dirty = True
        with self.engine.notes_lock:
            self.engine.document_revision += 1
            self.engine.notes_editing = True
        self.has_content = True
        self.refresh_recent_button()
        self.content_changed.emit()
        self.timer.start()
        self.edit_idle_timer.start()

    def markdown(self):
        if not self.dirty:
            return self.original
        if self.stack.currentWidget() is self.source:
            return self.source.toPlainText()
        title = self.title.text().strip().replace("\n", " ") or "课堂笔记"
        body = (
            self.preview.markdown()
            if isinstance(self.preview, WebMarkdownEdit)
            else rich_markdown(self.preview.document())
        )
        return "# " + title + "\n\n" + body + "\n"

    def flush_edits(self):
        self.timer.stop()
        try:
            if isinstance(self.preview, WebMarkdownEdit) and self.stack.currentWidget() is self.preview:
                self.preview.markdown()
        except ValueError:
            self.save_failed.emit("编辑器尚未完成保存，请稍后重试；编辑内容仍在窗口中。")
            return False
        if not self.dirty:
            return True
        self.saving = True
        try:
            document = self.markdown()
            snapshot = time.monotonic() - self.last_snapshot > 60
            self.engine.replace_document(document, snapshot=snapshot)
            if snapshot:
                self.last_snapshot = time.monotonic()
            self.original = document
            self.dirty = False
            return True
        except (OSError, ValueError):
            self.save_failed.emit("笔记自动保存失败；编辑内容仍在窗口中，请检查磁盘空间或文档大小。")
            return False
        finally:
            self.saving = False

    def set_document(self, document):
        self.loading = True
        self.original = document
        match = re.match(r"^# ([^\n]*)\n*", document)
        title, body = (match.group(1), document[match.end() :]) if match else ("", document)
        self.title.setText(title)
        self.title.setToolTip(title)
        if isinstance(self.preview, WebMarkdownEdit):
            self.preview.set_markdown(body)
        else:
            markdown_document(body, self.preview.document())
        self.source.setPlainText(document)
        self.loading = False
        self.dirty = False
        self.has_content = bool(document.strip())
        self.refresh_recent_button()

    def toggle_source(self, show):
        if not self.flush_edits():
            self.source_action.blockSignals(True)
            self.source_action.setChecked(not show)
            self.source_action.blockSignals(False)
            return
        self.set_document(self.original)
        self.stack.setCurrentWidget(self.source if show else self.preview)
        self.source_action.setText("返回阅读编辑" if show else "查看源代码")
        (self.source if show else self.preview).setFocus()

    def update(self, document, path):
        if self.saving or self.dirty or self.engine.notes_editing:
            return
        with self.engine.notes_lock:
            content = "\n\n".join(self.engine.sections)
        if "界面示例" in path:
            content = document
        self.has_content = bool(content)
        self.content_changed.emit()
        if content != self.original:
            if isinstance(self.preview, WebMarkdownEdit):
                self.set_document(content)
            else:
                bar = self.preview.verticalScrollBar()
                old = bar.value()
                self.set_document(content)
                bar.setValue(old)

    def note_status(self, message):
        self.summary_action.setToolTip(message)

    def open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.engine.session_dir or self.data_root / "sessions")))

    def format(self, command):
        if self.stack.currentWidget() is self.source:
            cursor = self.source.textCursor()
            selected = cursor.selectedText().replace("\u2029", "\n")
            markers = {"bold": "**", "italic": "*", "highlight": "==", "strike": "~~"}
            if command in markers:
                marker = markers[command]
                cursor.insertText(marker + selected + marker)
                if not selected:
                    cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(marker))
            else:
                cursor.movePosition(QTextCursor.StartOfBlock)
                cursor.insertText({"h1": "# ", "h2": "## ", "h3": "### ", "bullet": "- ", "number": "1. "}[command])
            self.source.setTextCursor(cursor)
            return
        if isinstance(self.preview, WebMarkdownEdit):
            self.preview.format(command)
            return
        cursor = self.preview.textCursor()
        if command in ("h1", "h2", "h3"):
            form = QTextBlockFormat()
            form.setHeadingLevel(int(command[-1]))
            cursor.mergeBlockFormat(form)
            fmt = QTextCharFormat()
            fmt.setFontWeight(QFont.Bold)
            fmt.setFontPointSize({"h1": 22, "h2": 18, "h3": 16}[command])
            cursor.mergeCharFormat(fmt)
        elif command in ("bullet", "number"):
            form = QTextListFormat()
            form.setStyle(QTextListFormat.ListDisc if command == "bullet" else QTextListFormat.ListDecimal)
            cursor.createList(form)
        else:
            form = QTextCharFormat()
            current = self.preview.currentCharFormat()
            if command == "bold":
                form.setFontWeight(QFont.Normal if current.fontWeight() >= QFont.Bold else QFont.Bold)
            elif command == "italic":
                form.setFontItalic(not current.fontItalic())
            elif command == "strike":
                form.setFontStrikeOut(not current.fontStrikeOut())
            else:
                if cursor.blockFormat().nonBreakableLines() or current.fontFixedPitch():
                    return
                form.setBackground(
                    Qt.transparent if current.background().color().name().upper() == HIGHLIGHT else QColor(HIGHLIGHT)
                )
            self.preview.mergeCurrentCharFormat(form)
        self.preview.setFocus()

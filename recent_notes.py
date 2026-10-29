"""Local recent-note discovery and an application-native chooser."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

from PySide6.QtCore import Qt, Signal, QEvent, QSize, QRectF
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QApplication,
    QStyledItemDelegate,
    QStyle,
)
from PySide6.QtGui import QPainter, QColor, QFont, QIcon


@dataclass(frozen=True)
class RecentNote:
    path: Path
    title: str
    modified: float
    preview: str


def read_note(root, path):
    root, path = Path(root) / "sessions", Path(path)
    if path.name != "notes.md" or path.parent.parent != root or path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Invalid history path")
    with path.open("rb") as stream:
        raw = stream.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("Note exceeds 2 MB")
    return raw.decode("utf-8-sig")


def recent_notes(root, limit=50):
    notes = []
    for path in (Path(root) / "sessions").glob("*/notes.md"):
        try:
            document = read_note(root, path).strip()
            match = re.match(r"^# ([^\n]+)\n*", document)
            title, body = (match[1].strip(), document[match.end() :]) if match else ("课堂笔记", document)
            body = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", body)
            body = re.sub(r"(?m)^\s*(?:#{1,6}\s+|[-*>]\s+|\d+[.)]\s+)", "", body)
            body = re.sub(r"[*_`~=]", "", body)
            body = re.sub(r"\s+", "", body)
            if body:
                notes.append(RecentNote(path, title[:100], path.stat().st_mtime, body[:15]))
        except (OSError, ValueError):
            continue
    return sorted(notes, key=lambda note: note.modified, reverse=True)[:limit]


class RecentNoteDelegate(QStyledItemDelegate):
    """One calm, readable row, sharing the main editor's blue palette."""

    def sizeHint(self, option, index):
        return QSize(420, 84)

    def paint(self, painter, option, index):
        note = index.data(Qt.UserRole + 1)
        if note is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        row = QRectF(option.rect).adjusted(0, 2, 0, -2)
        selected = bool(option.state & QStyle.State_Selected)
        hover = bool(option.state & QStyle.State_MouseOver)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#EDF4FE" if selected else "#F6F9FD" if hover else "#FFFFFF"))
        painter.drawRoundedRect(row, 12, 12)
        x, y = int(row.x()), int(row.y())
        painter.setBrush(QColor("#E2EDFD" if selected else "#F0F5FC"))
        painter.drawRoundedRect(QRectF(x + 12, y + 20, 38, 40), 10, 10)
        icon = self.parent().property("historyIcon") or QIcon(str(Path(__file__).parent / "assets/icons/history.svg"))
        icon.paint(painter, x + 20, y + 28, 22, 24)
        font = QFont(option.font)
        font.setPixelSize(14)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor("#29496D"))
        width = max(20, int(row.width()) - 178)
        title = painter.fontMetrics().elidedText(note.title, Qt.ElideRight, width)
        painter.drawText(x + 64, y + 32, title)
        font.setPixelSize(12)
        font.setWeight(QFont.Normal)
        painter.setFont(font)
        painter.setPen(QColor("#8293A9"))
        preview = painter.fontMetrics().elidedText(note.preview, Qt.ElideRight, max(20, int(row.width()) - 90))
        painter.drawText(x + 64, y + 55, preview)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QColor("#93A2B5"))
        stamp = datetime.fromtimestamp(note.modified)
        painter.drawText(option.rect.adjusted(0, 20, -14, 0), Qt.AlignRight | Qt.AlignTop, stamp.strftime("%Y-%m-%d"))
        painter.drawText(option.rect.adjusted(0, 37, -14, 0), Qt.AlignRight | Qt.AlignTop, stamp.strftime("%H:%M"))
        painter.restore()


class RecentNotesPopup(QDialog):
    note_selected = Signal(str)

    def __init__(self, parent):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("recentNotesPopup")
        self.setStyleSheet(
            "QDialog#recentNotesPopup {background:white;border:1px solid #DCE6F3;border-radius:16px;}"
            "QListWidget {background:white;border:0;outline:0;}"
            "QScrollBar:vertical {background:transparent;width:6px;margin:4px 0;}"
            "QScrollBar::handle:vertical {background:#DCE6F3;border-radius:3px;min-height:30px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}"
            "QListWidget::item {border-radius:8px;padding:8px;}"
            "QListWidget::item:selected, QListWidget::item:hover {background:#E6F0FF;color:#233956;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 22, 20, 18)
        layout.setSpacing(10)
        heading = QLabel("历史笔记")
        heading.setStyleSheet("font-size:18px;font-weight:600;color:#29496D;")
        layout.addWidget(heading)
        hint = QLabel("从上次停下的地方继续")
        hint.setStyleSheet("color:#73859B;font-size:12px;")
        layout.addWidget(hint)
        self.list = QListWidget()
        self.list.setItemDelegate(RecentNoteDelegate(self.list))
        self.list.setMouseTracking(True)
        layout.addWidget(self.list, 1)
        footer = QLabel("按最近修改排序  ·  点击外部或按 Esc 关闭")
        footer.setStyleSheet("color:#9AA8BA;font-size:11px;padding-top:4px;")
        layout.addWidget(footer)
        self.empty = QLabel("暂无最近笔记\n完成一次记录后会显示在这里")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("color:#73859B;padding:32px;")
        layout.addWidget(self.empty)
        self.list.installEventFilter(self)
        self.list.itemClicked.connect(self.choose)
        self.list.itemActivated.connect(self.choose)

    def showEvent(self, event):
        # Qt.Popup handles native outside clicks. Watch only the known owner
        # window for synthetic events, not every WebEngine internal QObject.
        self.owner_window = self.parentWidget().window()
        self.owner_window.installEventFilter(self)
        super().showEvent(event)

    def hideEvent(self, event):
        if getattr(self, "owner_window", None):
            self.owner_window.removeEventFilter(self)
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if self.isVisible():
            if event.type() == QEvent.MouseButtonPress and not self.frameGeometry().contains(
                event.globalPosition().toPoint()
            ):
                self.hide()
            elif (
                watched is self.list
                and event.type() == QEvent.KeyPress
                and event.key() in (Qt.Key_Return, Qt.Key_Enter)
            ):
                item = self.list.currentItem()
                if item:
                    self.choose(item)
                return True
        return super().eventFilter(watched, event)

    def populate(self, notes):
        self.list.clear()
        self.empty.setVisible(not notes)
        self.list.setVisible(bool(notes))
        for note in notes:
            item = QListWidgetItem(
                f"{note.title}\n{datetime.fromtimestamp(note.modified):%Y-%m-%d %H:%M}\n{note.preview}"
            )
            item.setData(Qt.UserRole, str(note.path))
            item.setData(Qt.UserRole + 1, note)
            self.list.addItem(item)
        if notes:
            self.list.setCurrentRow(0)

    def choose(self, item):
        if self.isVisible():
            self.hide()
            self.note_selected.emit(item.data(Qt.UserRole))

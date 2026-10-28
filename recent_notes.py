"""Local recent-note discovery and an application-native chooser."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QApplication


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


class RecentNotesPopup(QDialog):
    note_selected = Signal(str)

    def __init__(self, parent):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("recentNotesPopup")
        self.setStyleSheet(
            "QDialog#recentNotesPopup {background:white;border:1px solid #CADCF2;border-radius:12px;}"
            "QListWidget {background:white;border:0;outline:0;}"
            "QListWidget::item {border-radius:8px;padding:8px;}"
            "QListWidget::item:selected, QListWidget::item:hover {background:#E6F0FF;color:#233956;}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        heading = QLabel("最近笔记")
        heading.setStyleSheet("font-size:18px;font-weight:600;color:#233956;")
        layout.addWidget(heading)
        hint = QLabel("按最近修改时间排序 · 点击窗口外关闭")
        hint.setStyleSheet("color:#73859B;font-size:12px;")
        layout.addWidget(hint)
        self.list = QListWidget()
        layout.addWidget(self.list)
        self.empty = QLabel("暂无最近笔记\n完成一次记录后会显示在这里")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("color:#73859B;padding:32px;")
        layout.addWidget(self.empty)
        self.list.installEventFilter(self)
        QApplication.instance().installEventFilter(self)
        self.list.itemClicked.connect(self.choose)
        self.list.itemActivated.connect(self.choose)

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
            self.list.addItem(item)
        if notes:
            self.list.setCurrentRow(0)

    def choose(self, item):
        if self.isVisible():
            self.hide()
            self.note_selected.emit(item.data(Qt.UserRole))

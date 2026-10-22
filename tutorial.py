"""Window-local, input-blocking spotlight tour; never activates capture controls."""

import math
from PySide6.QtCore import Qt, Signal, QRectF, QPoint, QEvent
from PySide6.QtGui import QPainter, QPainterPath, QColor, QPen, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout


class TutorialOverlay(QWidget):
    finished = Signal()

    def __init__(self, controls):
        super().__init__(controls)
        self.controls = controls
        self.index = 0
        self.steps = [
            (controls.start, "开始收音", "点击这里开始录音；再次点击可暂停。教程中不会替你打开麦克风。"),
            (controls.input, "选择音源", "教室选麦克风，会议或视频选电脑音频。录音中也能切换。"),
            (controls.stt_backend, "语音识别", "默认使用 Groq。服务不可用时，可手动切换已准备的 Apple 本地识别。"),
            (controls.translation_backend, "翻译方式", "这里切换 Groq / Apple 翻译；旁边可选择英文、中文或双语显示。"),
            (controls.notes.import_button, "接着上一课记录", "导入已有 Markdown 笔记，作为本节课的基础。"),
            (
                controls.notes.preview,
                "直接编辑笔记",
                "在白色区域直接输入、增删改；内容会自动备份。AI 会等待你结束编辑。",
            ),
            (controls.notes.tools["highlight"], "标记重点", "选中文字后点击 H 高亮，也可以按 ⌘H；⌘B 加粗、⌘I 斜体。"),
            (
                controls.notes.more,
                "更多笔记操作",
                "点三个点可查看源代码、立即整理或打开笔记文件夹。整理笔记需要 Groq。",
            ),
            (
                controls.stop_button,
                "结束并保存",
                "结束后自动完成整理，再选择保存 Markdown 或导出 PDF。应用内备份仍保留。",
            ),
            (controls.settings_button, "需要时再调设置", "大部分参数已有默认值；点设置，再展开「高级设置」即可调整。"),
        ]
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.card = QFrame(self)
        self.card.setObjectName("tourCard")
        self.card.setStyleSheet(
            "QFrame#tourCard {background:white;border:1px solid #E3EAF3;border-radius:14px;} QLabel {background:transparent;border:0;}"
        )
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        self.counter = QLabel()
        self.counter.setStyleSheet("font-size:12px;color:#7A8A9E;")
        self.heading = QLabel()
        self.heading.setStyleSheet("font-size:20px;font-weight:700;color:#233956;")
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setStyleSheet("font-size:14px;color:#53657B;")
        for label in (self.counter, self.heading, self.text):
            layout.addWidget(label)
        buttons = QHBoxLayout()
        self.skip = QPushButton("跳过教程")
        self.skip.clicked.connect(self.finish)
        self.next_button = QPushButton("下一步")
        self.next_button.setObjectName("primary")
        self.next_button.clicked.connect(self.advance)
        buttons.addWidget(self.skip)
        buttons.addStretch()
        buttons.addWidget(self.next_button)
        layout.addLayout(buttons)
        controls.installEventFilter(self)
        self.setGeometry(controls.rect())
        self.refresh()

    def eventFilter(self, watched, event):
        if watched is self.controls and event.type() in (QEvent.Resize, QEvent.LayoutRequest):
            self.setGeometry(self.controls.rect())
            self.position_card()
            self.update()
        return super().eventFilter(watched, event)

    def target_rect(self):
        target = self.steps[self.index][0]
        return (
            QRectF(
                self.mapFromGlobal(target.mapToGlobal(QPoint(0, 0))).x(),
                self.mapFromGlobal(target.mapToGlobal(QPoint(0, 0))).y(),
                target.width(),
                target.height(),
            )
            .adjusted(-6, -6, 6, 6)
            .intersected(QRectF(self.rect()).adjusted(4, 4, -4, -4))
        )

    def position_card(self):
        width = min(390, self.width() - 32)
        self.card.setFixedWidth(width)
        self.card.adjustSize()
        rect = self.target_rect()
        y = rect.bottom() + 42
        if y + self.card.height() > self.height() - 16:
            y = max(16, rect.top() - self.card.height() - 42)
        x = max(16, min(rect.center().x() - width / 2, self.width() - width - 16))
        if rect.height() > self.height() / 2:
            x = max(16, self.width() - width - 28)
            y = max(90, (self.height() - self.card.height()) / 2)
        self.card.move(int(x), int(y))

    def refresh(self):
        self.counter.setText(f"Step {self.index + 1} / {len(self.steps)}")
        self.heading.setText(self.steps[self.index][1])
        self.text.setText(self.steps[self.index][2])
        self.next_button.setText("开始使用" if self.index == len(self.steps) - 1 else "下一步")
        self.position_card()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        target = self.target_rect()
        mask = QPainterPath()
        mask.addRect(QRectF(self.rect()))
        hole = QPainterPath()
        hole.addRoundedRect(target, 9, 9)
        painter.fillPath(mask.subtracted(hole), QColor(25, 34, 46, 170))
        painter.setPen(QPen(QColor("white"), 2))
        painter.drawRoundedRect(target, 9, 9)
        card = QRectF(self.card.geometry())
        end = target.center()
        start = QPointF(card.center().x(), card.top() if end.y() < card.center().y() else card.bottom())
        # Point to the closest edge rather than covering a large editor with the arrow.
        if target.contains(end) and target.height() > 200:
            end = QPointF(target.right() - 25, target.top() + 55)
        painter.setPen(QPen(QColor("white"), 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(start, end)
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        left = QPointF(end.x() - 13 * math.cos(angle - 0.4), end.y() - 13 * math.sin(angle - 0.4))
        right = QPointF(end.x() - 13 * math.cos(angle + 0.4), end.y() - 13 * math.sin(angle + 0.4))
        painter.setBrush(QColor("white"))
        painter.drawPolygon(QPolygonF([end, left, right]))

    def advance(self):
        if self.index == len(self.steps) - 1:
            self.finish()
        else:
            self.index += 1
            self.refresh()

    def finish(self):
        self.controls.removeEventFilter(self)
        self.hide()
        self.finished.emit()
        self.controls.start.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.finish()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Right, Qt.Key_Space):
            self.advance()
        else:
            event.accept()

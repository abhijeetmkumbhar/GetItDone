# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version. See the LICENSE file for details.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Reusable widgets: clickable surfaces, status dots, task rows, story cards."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..models import (
    STATUS_CLOSE,
    STATUS_COLORS,
    STATUS_INPROGRESS,
    STATUS_LABELS,
    STATUS_TODO,
    Story,
    Task,
)

__all__ = [
    "ClickableWidget",
    "StatusDot",
    "StoryWidget",
    "TaskRow",
    "repolish",
]


def repolish(widget: QWidget) -> None:
    """Re-apply the stylesheet after a dynamic property/objectName change."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


class ClickableWidget(QWidget):
    """A widget that reports left-clicks and paints QSS backgrounds."""

    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class StatusDot(QWidget):
    """Painted status indicator.

    Hollow ring (todo), ring + core (in progress), check mark (closed).
    """

    SIZE = 12

    def __init__(self, status: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = status
        self.setFixedSize(self.SIZE, self.SIZE)
        # Let clicks fall through to the parent row.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_status(self, status: str) -> None:
        if status != self._status:
            self._status = status
            self.update()

    @property
    def status(self) -> str:
        return self._status

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(STATUS_COLORS.get(self._status, STATUS_COLORS[STATUS_TODO]))
        ring = QRectF(1.5, 1.5, 9.0, 9.0)

        if self._status == STATUS_CLOSE:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(ring)
            tick = QPen(QColor(255, 255, 255, 235), 1.4)
            tick.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(tick)
            painter.drawLine(QPointF(3.9, 6.2), QPointF(5.5, 7.8))
            painter.drawLine(QPointF(5.5, 7.8), QPointF(8.1, 4.3))
        elif self._status == STATUS_INPROGRESS:
            painter.setPen(QPen(color, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(ring)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QRectF(4.2, 4.2, 3.6, 3.6))
        else:
            painter.setPen(QPen(color, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(ring)


class TaskRow(ClickableWidget):
    """One task line: status dot + title. Click cycles the status."""

    def __init__(self, task: Task, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task = task
        self.setObjectName("TaskRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._dot = StatusDot(task.status)
        self._label = QLabel(task.title)
        self._label.setObjectName("TaskTitle")
        self._label.setWordWrap(True)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._label, 1)

        self.refresh()

    def refresh(self) -> None:
        """Re-read the model and update this row in place (no widget churn)."""
        status = self.task.status
        self._dot.set_status(status)

        object_name = "TaskTitleDone" if status == STATUS_CLOSE else "TaskTitle"
        if self._label.objectName() != object_name:
            self._label.setObjectName(object_name)
            repolish(self._label)

        font = QFont(self._label.font())
        font.setStrikeOut(status == STATUS_CLOSE)
        self._label.setFont(font)

        self.setToolTip(f"{STATUS_LABELS[status]} — click to advance")

    @property
    def status_dot(self) -> StatusDot:
        return self._dot

    @property
    def title_label(self) -> QLabel:
        return self._label


class StoryWidget(QWidget):
    """Story card: header (arrow + title + progress) with a collapsible task list."""

    toggled = pyqtSignal(str)  # story id
    status_cycled = pyqtSignal(str, str)  # story id, task id

    def __init__(
        self, story: Story, expanded: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.story = story
        self._expanded = bool(expanded)
        self._rows: dict[str, TaskRow] = {}
        self.setObjectName("StoryCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        # -- header --------------------------------------------------------- #
        self._header = ClickableWidget(self)
        self._header.setObjectName("StoryHeader")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(6, 5, 6, 5)
        header_layout.setSpacing(8)

        self._arrow = QLabel()
        self._arrow.setObjectName("StoryArrow")
        self._arrow.setFixedWidth(10)
        self._title = QLabel(story.title)
        self._title.setObjectName("StoryTitle")
        self._title.setWordWrap(True)
        self._progress = QLabel()
        self._progress.setObjectName("StoryProgress")

        for child in (self._arrow, self._title, self._progress):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        header_layout.addWidget(self._arrow, 0, Qt.AlignmentFlag.AlignTop)
        header_layout.addWidget(self._title, 1)
        header_layout.addWidget(self._progress, 0, Qt.AlignmentFlag.AlignTop)
        self._header.clicked.connect(lambda: self.toggled.emit(self.story.id))

        # -- body ----------------------------------------------------------- #
        self._body = QWidget(self)
        self._body.setObjectName("StoryBody")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(2, 2, 0, 0)
        self._body_layout.setSpacing(1)

        layout.addWidget(self._header)
        layout.addWidget(self._body)

        self.refresh()
        self.set_expanded(self._expanded)

    # -- state -------------------------------------------------------------- #
    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self._arrow.setText("▼" if self._expanded else "▶")
        self._body.setVisible(self._expanded)

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    @property
    def header(self) -> ClickableWidget:
        return self._header

    @property
    def progress_text(self) -> str:
        return self._progress.text()

    def task_row(self, task_id: str) -> TaskRow | None:
        return self._rows.get(task_id)

    # -- rendering ---------------------------------------------------------- #
    def refresh(self) -> None:
        """Rebuild task rows and the progress badge from the model."""
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._rows.clear()

        if not self.story.tasks:
            hint = QLabel("No tasks yet")
            hint.setObjectName("EmptyHint")
            self._body_layout.addWidget(hint)
        else:
            for task in self.story.tasks:
                row = TaskRow(task, self._body)
                row.clicked.connect(
                    lambda _=False, tid=task.id: self.status_cycled.emit(
                        self.story.id, tid
                    )
                )
                self._rows[task.id] = row
                self._body_layout.addWidget(row)

        self._update_progress()
        self._title.setText(self.story.title)

    def refresh_task(self, task_id: str) -> None:
        """Update a single row in place after a status change."""
        row = self._rows.get(task_id)
        if row is not None:
            row.refresh()
        self._update_progress()

    def _update_progress(self) -> None:
        closed, total = self.story.progress()
        self._progress.setText(f"{closed}/{total}" if total else "")

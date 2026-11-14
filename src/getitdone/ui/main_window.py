# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version. See the LICENSE file for details.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The desktop widget window.

Layering: two strategies, chosen by platform.

* **X11 / XWayland** - the window is tagged ``_NET_WM_WINDOW_TYPE_DESKTOP``
  (see :mod:`getitdone.ui.x11`), which puts it in the *desktop layer*: above the
  wallpaper, below every normal window, and still visible after "Show Desktop".
  This is the Linux counterpart of the Win32 ``WorkerW`` approach.
* **Everything else** - ``WindowStaysOnBottomHint`` keeps the widget under
  normal windows. It is only a hint: it does not survive Win+D, and the window
  manager is free to ignore it.

Both are bottom-of-the-stack by design, so the widget only receives clicks in
screen areas no other window covers. ``--top`` swaps in an ordinary window for
inspection and interaction.
Layout: the widget covers the whole desktop area as a translucent dashboard.
Stories are cards laid out in as many columns as the screen width allows, each
story expandable inline.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..models import Workspace
from ..service import WorkspaceService
from .theme import (
    CARD_SPACING,
    COLUMN_SPACING,
    CONTENT_MARGIN,
    STYLESHEET,
    columns_for_width,
)
from .widgets import StoryWidget

__all__ = ["MainWindow"]


class MainWindow(QWidget):
    """Frameless, always-on-bottom dashboard covering the whole desktop."""

    add_story_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    save_failed = pyqtSignal(str)

    def __init__(
        self,
        workspace: Workspace,
        data_path: str | None = None,
        parent: QWidget | None = None,
        desktop_layer: bool = True,
    ) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self._service = WorkspaceService(workspace, data_path)
        self._expanded_story_id: str | None = None
        self._auto_expand_pending = True
        self._story_widgets: dict[str, StoryWidget] = {}
        self._columns = 0
        self._desktop_layer_applied = False

        # On X11/XWayland the desktop layer is requested through an EWMH window
        # type rather than a Qt flag. ``WindowStaysOnBottomHint`` is deliberately
        # dropped there: it only sets _NET_WM_STATE_BELOW, which fights the
        # window manager for stacking and does not survive "Show Desktop".
        self._desktop_layer = desktop_layer and QGuiApplication.platformName() == "xcb"

        self.setWindowTitle("GetItDone")

        if self._desktop_layer:
            # Preferred: let Qt write the property at the correct moment.
            self.setAttribute(Qt.WidgetAttribute.WA_X11NetWmWindowTypeDesktop)
            self.setWindowFlags(
                Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
            )
        else:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnBottomHint
                | Qt.WindowType.Tool
            )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        # Prevent the common translucent + frameless side-effect of becoming
        # transparent-for-input.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self._build_ui()
        self._apply_geometry()
        self._watch_screen()
        self.refresh()

        if self._desktop_layer:
            # Extra: force sticky + type while the window is still unmapped.
            self._apply_desktop_layer()

    def _apply_desktop_layer(self) -> None:
        """Ask the window manager to place the widget in the desktop layer.

        ``winId()`` forces the native window to exist. The property has to be
        written *before* the window is mapped, otherwise the window manager has
        already decided which layer the window belongs to.
        """
        from .x11 import set_desktop_type

        self._desktop_layer_applied = set_desktop_type(int(self.winId()))

    def _force_input_region(self) -> None:
        """Force a full ShapeInput region so the translucent desktop window
        actually receives mouse events."""
        if not self._desktop_layer:
            return
        from .x11 import force_full_input_region

        geo = self.geometry()
        force_full_input_region(int(self.winId()), geo.width(), geo.height())

    # -- construction ------------------------------------------------------- #
    def _build_ui(self) -> None:
        self.setStyleSheet(STYLESHEET)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._panel = QFrame(self)
        self._panel.setObjectName("Panel")
        outer.addWidget(self._panel)

        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(CONTENT_MARGIN, 12, CONTENT_MARGIN, 12)
        panel_layout.setSpacing(10)

        # header
        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("GetItDone")
        title.setObjectName("HeaderTitle")
        self._summary = QLabel()
        self._summary.setObjectName("HeaderSummary")
        self._summary.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._summary)
        panel_layout.addLayout(header)

        # story columns
        self._scroll = QScrollArea(self._panel)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.viewport().setAutoFillBackground(False)

        self._grid_host = QWidget()
        self._grid_host.setObjectName("GridHost")
        self._columns_layout = QHBoxLayout(self._grid_host)
        self._columns_layout.setContentsMargins(0, 2, 0, 2)
        self._columns_layout.setSpacing(COLUMN_SPACING)
        self._scroll.setWidget(self._grid_host)
        # QScrollArea.setWidget() force-enables autoFillBackground on the content
        # widget, which would paint the opaque palette colour over the panel.
        self._grid_host.setAutoFillBackground(False)
        panel_layout.addWidget(self._scroll, 1)

        # footer
        footer = QHBoxLayout()
        footer.setSpacing(8)
        self._add_button = QPushButton("+ Add Story")
        self._add_button.setObjectName("FooterButton")
        self._add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_button.clicked.connect(self.add_story_requested.emit)

        self._settings_button = QPushButton("Settings")
        self._settings_button.setObjectName("FooterButton")
        self._settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_button.clicked.connect(self.settings_requested.emit)

        footer.addWidget(self._add_button, 1)
        footer.addWidget(self._settings_button, 0)
        panel_layout.addLayout(footer)

    def _watch_screen(self) -> None:
        """Re-fit when the screen changes (resolution, DPI, taskbar show/hide)."""
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            screen.availableGeometryChanged.connect(self._on_screen_geometry_changed)

    def _on_screen_geometry_changed(self, _geometry) -> None:
        self._apply_geometry()
        self.refresh()

    def _apply_geometry(self) -> None:
        """Cover the whole desktop area (taskbar excluded)."""
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.availableGeometry())
            # Keep the input region correct after size changes
            if self.isVisible():
                self._force_input_region()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        # Width changed enough to fit a different number of columns.
        if columns_for_width(self.width()) != self._columns:
            self.refresh()
        # Also keep input region in sync
        if self._desktop_layer and self.isVisible():
            self._force_input_region()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().showEvent(event)
        if self._desktop_layer:
            # A translucent, frameless X11 window can end up with an empty
            # ShapeInput region and receive no mouse events. Re-assert the
            # full region once the native window exists.
            #
            # Deliberately no setWindowFlags()/show() here: re-creating the
            # native window from inside showEvent re-enters this handler.
            self._force_input_region()

    # -- rendering ---------------------------------------------------------- #
    def refresh(self) -> None:
        """Rebuild the story columns from the workspace model."""
        self._clear_list()
        self._story_widgets.clear()
        self._columns = columns_for_width(self.width())
        stories = self.workspace.stories
        if not stories:
            hint = QLabel("No stories yet.\nClick “+ Add Story” to begin.")
            hint.setObjectName("EmptyHint")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setWordWrap(True)
            self._columns_layout.addWidget(hint, 1)
            self._update_summary()
            return

        if self._auto_expand_pending:
            self._expanded_story_id = stories[0].id
            self._auto_expand_pending = False

        # One stretchable column per slot; cards are distributed round-robin so
        # column heights stay roughly even as stories grow and shrink.
        column_layouts: list[QVBoxLayout] = []
        for _ in range(self._columns):
            column = QWidget(self._grid_host)
            column.setObjectName("Column")
            column_layout = QVBoxLayout(column)
            column_layout.setContentsMargins(0, 0, 0, 0)
            column_layout.setSpacing(CARD_SPACING)
            column_layout.addStretch(1)
            self._columns_layout.addWidget(column, 1)
            column_layouts.append(column_layout)

        for index, story in enumerate(stories):
            widget = StoryWidget(
                story,
                expanded=story.id == self._expanded_story_id,
                parent=self._grid_host,
            )
            widget.toggled.connect(self._on_story_toggled)
            widget.status_cycled.connect(self._on_status_cycled)
            self._story_widgets[story.id] = widget

            target = column_layouts[index % self._columns]
            target.insertWidget(target.count() - 1, widget)  # before the stretch
        self._update_summary()

    def _clear_list(self) -> None:
        while self._columns_layout.count():
            item = self._columns_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _update_summary(self) -> None:
        stories = self.workspace.stories
        if not stories:
            self._summary.setText("")
            return
        closed = sum(s.progress()[0] for s in stories)
        total = sum(len(s.tasks) for s in stories)
        label = "story" if len(stories) == 1 else "stories"
        self._summary.setText(f"{len(stories)} {label} · {closed}/{total} done")

    # -- interaction -------------------------------------------------------- #
    def _on_story_toggled(self, story_id: str) -> None:
        """Single-expand accordion: expanding one story collapses the rest."""
        self._expanded_story_id = (
            None if self._expanded_story_id == story_id else story_id
        )
        for sid, widget in self._story_widgets.items():
            widget.set_expanded(sid == self._expanded_story_id)

    def _on_status_cycled(self, story_id: str, task_id: str) -> None:
        story = self.workspace.story_by_id(story_id)
        task = story.task_by_id(task_id) if story else None
        if task is None:
            return

        task.cycle_status()
        widget = self._story_widgets.get(story_id)
        if widget is not None:
            widget.refresh_task(task_id)
        self._update_summary()
        self._save()

    def _save(self) -> None:
        if not self._service.save():
            self.save_failed.emit("Could not save tasks.json")

    # -- read-only accessors ------------------------------------------------ #
    # Public surface for tests and for the Settings dialog. Nothing outside
    # this module should reach into the private widget maps.
    @property
    def columns(self) -> int:
        return self._columns

    @property
    def desktop_layer(self) -> bool:
        """True when the X11 desktop-layer window type is in use."""
        return self._desktop_layer

    @property
    def desktop_layer_applied(self) -> bool:
        """True when the EWMH window type was actually written to X11."""
        return self._desktop_layer_applied

    @property
    def expanded_story_id(self) -> str | None:
        return self._expanded_story_id

    @property
    def summary_text(self) -> str:
        return self._summary.text()

    @property
    def story_widgets(self) -> dict[str, StoryWidget]:
        return dict(self._story_widgets)

    def story_widget(self, story_id: str) -> StoryWidget | None:
        return self._story_widgets.get(story_id)

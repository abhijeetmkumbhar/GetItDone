# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for the desktop widget UI. Runs headless via the offscreen platform."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtTest import QTest

from getitdone import storage
from getitdone.models import (
    STATUS_CLOSE,
    STATUS_INPROGRESS,
    STATUS_TODO,
    Workspace,
)
from getitdone.ui.theme import columns_for_width

pytestmark = pytest.mark.usefixtures("qapp")


def _first_story_id(window):
    return window.workspace.stories[0].id


def _row(window, story_index=0, task_index=0):
    story = window.workspace.stories[story_index]
    return window.story_widget(story.id).task_row(story.tasks[task_index].id)


def _click(widget):
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton)


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
class TestGeometry:
    def test_covers_the_desktop(self, make_window):
        window = make_window()
        assert window.geometry() == QGuiApplication.primaryScreen().availableGeometry()

    def test_column_count_follows_width(self, make_window):
        window = make_window()
        assert window.columns == columns_for_width(window.width())

    def test_columns_for_width_is_clamped(self):
        assert columns_for_width(0) == 1
        assert columns_for_width(719) == 1
        assert columns_for_width(720) == 2
        assert columns_for_width(10_000) == 4

    def test_resizing_reflows_the_columns(self, make_window):
        window = make_window()
        window.setGeometry(0, 0, 1920, 1080)
        assert window.columns == 4


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #
class TestLayout:
    def test_one_widget_per_story(self, make_window, workspace):
        window = make_window(workspace)
        assert len(window.story_widgets) == len(workspace.stories)

    def test_stories_are_spread_across_columns(self, make_window, workspace):
        window = make_window(workspace)
        columns = {id(sw.parent()) for sw in window.story_widgets.values()}
        assert len(columns) == min(window.columns, len(workspace.stories))

    def test_empty_workspace_renders_without_stories(self, make_window):
        window = make_window(Workspace())
        assert window.story_widgets == {}
        assert window.summary_text == ""


# --------------------------------------------------------------------------- #
# Expanding stories
# --------------------------------------------------------------------------- #
class TestAccordion:
    def test_first_story_is_expanded_on_first_render(self, make_window, workspace):
        window = make_window(workspace)
        assert window.story_widget(_first_story_id(window)).is_expanded
        assert not window.story_widget(workspace.stories[1].id).is_expanded

    def test_clicking_a_header_expands_it(self, make_window, workspace):
        window = make_window(workspace)
        second = window.story_widget(workspace.stories[1].id)
        _click(second.header)
        assert second.is_expanded

    def test_expanding_one_collapses_the_other(self, make_window, workspace):
        window = make_window(workspace)
        first = window.story_widget(workspace.stories[0].id)
        second = window.story_widget(workspace.stories[1].id)

        _click(second.header)

        assert second.is_expanded
        assert not first.is_expanded

    def test_clicking_an_expanded_header_collapses_it(self, make_window, workspace):
        window = make_window(workspace)
        first = window.story_widget(workspace.stories[0].id)
        _click(first.header)
        assert not first.is_expanded


# --------------------------------------------------------------------------- #
# Status workflow
# --------------------------------------------------------------------------- #
class TestStatusCycling:
    def test_click_advances_todo_to_inprogress(self, make_window, workspace):
        window = make_window(workspace)
        story = workspace.stories[0]
        story.tasks[0].set_status(STATUS_TODO)

        _click(_row(window))

        assert story.tasks[0].status == STATUS_INPROGRESS

    def test_full_cycle_returns_to_todo(self, make_window, workspace):
        window = make_window(workspace)
        task = workspace.stories[0].tasks[0]
        row = _row(window)

        _click(row)
        assert task.status == STATUS_INPROGRESS
        _click(row)
        assert task.status == STATUS_CLOSE
        _click(row)
        assert task.status == STATUS_TODO

    def test_row_is_updated_in_place(self, make_window, workspace):
        window = make_window(workspace)
        row = _row(window)
        _click(row)
        assert _row(window) is row, "cycling must not rebuild the widget tree"

    def test_dot_and_title_follow_the_status(self, make_window, workspace):
        window = make_window(workspace)
        task = workspace.stories[0].tasks[0]
        task.set_status(STATUS_TODO)
        window.refresh()
        row = _row(window)

        _click(row)
        assert row.status_dot.status == STATUS_INPROGRESS
        assert row.title_label.objectName() == "TaskTitle"
        assert row.title_label.font().strikeOut() is False

        _click(row)
        assert row.status_dot.status == STATUS_CLOSE
        assert row.title_label.objectName() == "TaskTitleDone"
        assert row.title_label.font().strikeOut() is True

    def test_progress_badge_updates(self, make_window, workspace):
        window = make_window(workspace)
        story = workspace.stories[0]
        story_widget = window.story_widget(story.id)
        assert story_widget.progress_text == "1/3"

        _click(_row(window))  # todo -> inprogress, still not closed
        assert story_widget.progress_text == "1/3"

        _click(_row(window))  # inprogress -> close
        assert story_widget.progress_text == "2/3"

    def test_summary_reflects_closed_counts(self, make_window, workspace):
        window = make_window(workspace)
        assert window.summary_text == "2 stories · 1/3 done"

        _click(_row(window))  # todo -> inprogress
        assert window.summary_text == "2 stories · 1/3 done"

        _click(_row(window))  # inprogress -> close
        assert window.summary_text == "2 stories · 2/3 done"

    def test_status_change_is_persisted(self, make_window, workspace, tmp_path):
        window = make_window(workspace)
        task = workspace.stories[0].tasks[0]
        task.set_status(STATUS_TODO)

        _click(_row(window))

        reloaded = storage.load_data(tmp_path / "tasks.json")
        assert reloaded.stories[0].tasks[0].status == STATUS_INPROGRESS


# --------------------------------------------------------------------------- #
# Painting
# --------------------------------------------------------------------------- #
class TestRendering:
    def test_panel_covers_the_canvas_in_dark_fill(self, make_window, workspace):
        window = make_window(workspace)
        image = window.grab().toImage()

        corner = image.pixelColor(1, 1)
        centre = image.pixelColor(image.width() // 2, image.height() // 2)

        for pixel in (corner, centre):
            assert (pixel.red(), pixel.green(), pixel.blue()) == (22, 24, 30)
            assert pixel.alpha() > 200

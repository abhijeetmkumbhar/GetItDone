# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared pytest fixtures.

Qt runs on the ``offscreen`` platform so the UI tests work headless. The
environment variable must be set *before* PyQt6 is imported, hence the
module-level call.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from getitdone.models import STATUS_CLOSE, STATUS_INPROGRESS, Workspace


@pytest.fixture(scope="session")
def qapp():
    """One QApplication for the whole session (Qt allows no more)."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def workspace():
    """A small workspace: one story with three statuses, one task-less story."""
    ws = Workspace()
    story = ws.add_story("Project Proposal", "Initial scope")
    story.add_task("Write project brief")
    story.add_task("Research requirements").set_status(STATUS_INPROGRESS)
    story.add_task("Define milestones").set_status(STATUS_CLOSE)
    ws.add_story("Website Redesign")
    return ws


@pytest.fixture
def make_window(qapp, tmp_path):
    """Factory for MainWindow instances that are torn down afterwards."""
    from getitdone.ui.main_window import MainWindow

    created = []

    def factory(workspace=None, **kwargs):
        kwargs.setdefault("data_path", str(tmp_path / "tasks.json"))
        window = MainWindow(
            workspace if workspace is not None else Workspace(), **kwargs
        )
        window.show()
        created.append(window)
        return window

    yield factory

    for window in created:
        window.close()
        window.deleteLater()

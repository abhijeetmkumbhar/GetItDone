# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for the data model. Pure Python - no Qt involved."""

from __future__ import annotations

import pytest

from getitdone.models import (
    SCHEMA_VERSION,
    STATUS_CLOSE,
    STATUS_INPROGRESS,
    STATUS_TODO,
    STATUSES,
    Story,
    Task,
    Workspace,
    clean_title,
    normalize_status,
)


# --------------------------------------------------------------------------- #
# Status handling
# --------------------------------------------------------------------------- #
class TestNormalizeStatus:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("todo", STATUS_TODO),
            ("TODO", STATUS_TODO),
            ("open", STATUS_TODO),
            ("pending", STATUS_TODO),
            ("inprogress", STATUS_INPROGRESS),
            ("in_progress", STATUS_INPROGRESS),
            ("In-Progress", STATUS_INPROGRESS),
            ("doing", STATUS_INPROGRESS),
            ("wip", STATUS_INPROGRESS),
            ("close", STATUS_CLOSE),
            ("closed", STATUS_CLOSE),
            ("done", STATUS_CLOSE),
            ("  DONE  ", STATUS_CLOSE),
            ("completed", STATUS_CLOSE),
        ],
    )
    def test_aliases_resolve(self, value, expected):
        assert normalize_status(value) == expected

    @pytest.mark.parametrize("value", [None, 42, "", "   ", "banana", [], {}])
    def test_unknown_values_fall_back_to_todo(self, value):
        assert normalize_status(value) == STATUS_TODO


class TestTask:
    def test_new_task_is_todo(self):
        task = Task(title="Write brief")
        assert task.status == STATUS_TODO
        assert task.id.startswith("task-")

    def test_cycle_walks_the_workflow_and_wraps(self):
        task = Task(title="Write brief")
        assert task.cycle_status() == STATUS_INPROGRESS
        assert task.cycle_status() == STATUS_CLOSE
        assert task.cycle_status() == STATUS_TODO

    def test_set_status_reports_whether_it_changed(self):
        task = Task(title="Write brief")
        assert task.set_status(STATUS_CLOSE) is True
        assert task.set_status(STATUS_CLOSE) is False

    def test_set_status_accepts_aliases(self):
        task = Task(title="Write brief")
        task.set_status("done")
        assert task.status == STATUS_CLOSE

    def test_rename_rejects_blank(self):
        task = Task(title="Write brief")
        assert task.rename("   ") is False
        assert task.title == "Write brief"

    def test_roundtrip(self):
        task = Task(title="Write brief", status=STATUS_INPROGRESS)
        restored = Task.from_dict(task.to_dict())
        assert (restored.id, restored.title, restored.status) == (
            task.id,
            task.title,
            task.status,
        )

    @pytest.mark.parametrize("raw", [None, 42, [], {}, {"title": None}])
    def test_from_dict_never_raises(self, raw):
        assert isinstance(Task.from_dict(raw), Task)

    def test_bare_string_is_accepted(self):
        assert Task.from_dict("Just a title").title == "Just a title"


class TestStory:
    def test_add_task_appends(self):
        story = Story(title="Proposal")
        task = story.add_task("Write brief")
        assert story.tasks == [task]
        assert story.task_by_id(task.id) is task

    def test_progress_counts_only_closed(self):
        story = Story(title="Proposal")
        story.add_task("a").set_status(STATUS_CLOSE)
        story.add_task("b").set_status(STATUS_INPROGRESS)
        story.add_task("c")
        assert story.progress() == (1, 3)

    def test_progress_of_empty_story(self):
        assert Story(title="Proposal").progress() == (0, 0)

    def test_status_counts_always_has_all_statuses(self):
        counts = Story(title="Proposal").status_counts()
        assert set(counts) == set(STATUSES)

    def test_remove_task(self):
        story = Story(title="Proposal")
        task = story.add_task("a")
        assert story.remove_task(task.id) is True
        assert story.remove_task(task.id) is False
        assert story.tasks == []

    def test_roundtrip_preserves_tasks(self):
        story = Story(title="Proposal", description="Scope")
        story.add_task("a").set_status(STATUS_CLOSE)
        restored = Story.from_dict(story.to_dict())
        assert restored.title == story.title
        assert restored.description == "Scope"
        assert [t.status for t in restored.tasks] == [STATUS_CLOSE]

    def test_from_dict_drops_non_task_entries(self):
        story = Story.from_dict(
            {"title": "Proposal", "tasks": [{"title": "ok"}, 7, None]}
        )
        assert len(story.tasks) == 1


class TestWorkspace:
    def test_add_and_lookup_story(self):
        ws = Workspace()
        story = ws.add_story("Proposal", "Scope")
        assert ws.story_by_id(story.id) is story
        assert ws.story_by_id("nope") is None
        assert ws.is_empty() is False

    def test_new_workspace_is_empty(self):
        assert Workspace().is_empty() is True

    def test_roundtrip(self):
        ws = Workspace()
        ws.add_story("Proposal").add_task("a").set_status(STATUS_CLOSE)
        ws.add_story("Redesign")
        restored = Workspace.from_dict(ws.to_dict())
        assert [s.title for s in restored.stories] == ["Proposal", "Redesign"]
        assert restored.stories[0].progress() == (1, 1)
        assert restored.version == SCHEMA_VERSION

    def test_accepts_bare_list_of_stories(self):
        ws = Workspace.from_dict([{"title": "Proposal"}])
        assert [s.title for s in ws.stories] == ["Proposal"]

    @pytest.mark.parametrize("raw", [None, 42, "nonsense", {}])
    def test_from_dict_never_raises(self, raw):
        assert isinstance(Workspace.from_dict(raw), Workspace)

    def test_duplicate_ids_are_not_generated(self):
        ws = Workspace()
        ids = {ws.add_story(f"Story {i}").id for i in range(50)}
        assert len(ids) == 50


class TestCleanTitle:
    def test_collapses_whitespace(self):
        assert clean_title("  Write   the\n brief  ") == "Write the brief"

    @pytest.mark.parametrize("value", ["", "   ", None, 42])
    def test_falls_back(self, value):
        assert clean_title(value, "Untitled task") == "Untitled task"

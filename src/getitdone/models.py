# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version. See the LICENSE file for details.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Data models for GetItDone.

Structure is ``Workspace -> Story -> Task``. Everything here is plain Python
(no Qt) so it can be unit tested and reused headlessly.

Every ``from_dict`` is deliberately tolerant: a corrupted or hand-edited JSON
file degrades to sane defaults instead of raising, because a crash at login is
far worse than a missing task title.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

__all__ = [
    "SCHEMA_VERSION",
    "STATUSES",
    "STATUS_CLOSE",
    "STATUS_COLORS",
    "STATUS_CYCLE",
    "STATUS_INPROGRESS",
    "STATUS_LABELS",
    "STATUS_TODO",
    "Story",
    "Task",
    "Workspace",
    "new_id",
    "normalize_status",
    "now_iso",
]

SCHEMA_VERSION = "1.0"

STATUS_TODO = "todo"
STATUS_INPROGRESS = "inprogress"
STATUS_CLOSE = "close"

#: Canonical status values, in workflow order.
STATUSES: tuple[str, ...] = (STATUS_TODO, STATUS_INPROGRESS, STATUS_CLOSE)

#: Click-to-cycle order: todo -> inprogress -> close -> todo.
STATUS_CYCLE: dict[str, str] = {
    STATUS_TODO: STATUS_INPROGRESS,
    STATUS_INPROGRESS: STATUS_CLOSE,
    STATUS_CLOSE: STATUS_TODO,
}

#: Human-readable labels. Single source of truth for status presentation.
STATUS_LABELS: dict[str, str] = {
    STATUS_TODO: "To Do",
    STATUS_INPROGRESS: "In Progress",
    STATUS_CLOSE: "Closed",
}

#: Indicator colours per docs/specification.md (gray / blue / green).
STATUS_COLORS: dict[str, str] = {
    STATUS_TODO: "#8a8a8a",
    STATUS_INPROGRESS: "#2f7fd1",
    STATUS_CLOSE: "#3f9e52",
}

#: Tolerated spellings when loading hand-edited files.
_STATUS_ALIASES: dict[str, str] = {
    "todo": STATUS_TODO,
    "to": STATUS_TODO,
    "open": STATUS_TODO,
    "pending": STATUS_TODO,
    "new": STATUS_TODO,
    "inprogress": STATUS_INPROGRESS,
    "doing": STATUS_INPROGRESS,
    "active": STATUS_INPROGRESS,
    "wip": STATUS_INPROGRESS,
    "close": STATUS_CLOSE,
    "closed": STATUS_CLOSE,
    "done": STATUS_CLOSE,
    "complete": STATUS_CLOSE,
    "completed": STATUS_CLOSE,
    "finished": STATUS_CLOSE,
}


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def now_iso() -> str:
    """Current local time as an ISO 8601 string, second precision."""
    return datetime.now().replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    """Short unique id, e.g. ``story-3f9a1c2b``."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def normalize_status(value: Any) -> str:
    """Coerce anything into one of :data:`STATUSES`. Unknown -> ``todo``."""
    if isinstance(value, str):
        key = value.strip().lower().replace("_", "").replace("-", "").replace(" ", "")
        if key in _STATUS_ALIASES:
            return _STATUS_ALIASES[key]
    return STATUS_TODO


def clean_title(value: Any, fallback: str = "Untitled") -> str:
    """Collapse whitespace; return ``fallback`` for empty/non-string input."""
    if isinstance(value, str):
        text = " ".join(value.split())
        if text:
            return text
    return fallback


def _as_text(value: Any, default: str = "") -> str:
    if isinstance(value, str):
        return value.strip()
    return default


def _iso_or_now(value: Any) -> str:
    """Keep a valid ISO 8601 string, otherwise stamp the current time."""
    if isinstance(value, str) and value.strip():
        candidate = value.strip()
        try:
            datetime.fromisoformat(candidate)
        except ValueError:
            return now_iso()
        return candidate
    return now_iso()


# --------------------------------------------------------------------------- #
# Task
# --------------------------------------------------------------------------- #
@dataclass
class Task:
    """A single unit of work belonging to a :class:`Story`."""

    title: str
    id: str = field(default_factory=lambda: new_id("task"))
    status: str = STATUS_TODO
    created: str = field(default_factory=now_iso)
    modified: str = field(default_factory=now_iso)

    def __post_init__(self) -> None:
        self.title = clean_title(self.title, "Untitled task")
        self.status = normalize_status(self.status)
        self.created = _iso_or_now(self.created)
        self.modified = _iso_or_now(self.modified)
        if not _as_text(self.id):
            self.id = new_id("task")

    # -- mutation ---------------------------------------------------------- #
    def set_status(self, status: str) -> bool:
        """Set status explicitly. Returns ``True`` if anything changed."""
        new_status = normalize_status(status)
        if new_status == self.status:
            return False
        self.status = new_status
        self.modified = now_iso()
        return True

    def cycle_status(self) -> str:
        """Advance ``todo -> inprogress -> close -> todo``; returns new status."""
        self.set_status(STATUS_CYCLE[self.status])
        return self.status

    def rename(self, title: str) -> bool:
        new_title = clean_title(title, self.title)
        if new_title == self.title:
            return False
        self.title = new_title
        self.modified = now_iso()
        return True

    # -- serialization ----------------------------------------------------- #
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "created": self.created,
            "modified": self.modified,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> Task:
        if isinstance(raw, str):
            return cls(title=raw)
        if not isinstance(raw, dict):
            return cls(title="Untitled task")
        return cls(
            title=raw.get("title", "Untitled task"),
            id=_as_text(raw.get("id")) or new_id("task"),
            status=normalize_status(raw.get("status")),
            created=_iso_or_now(raw.get("created")),
            modified=_iso_or_now(raw.get("modified")),
        )


# --------------------------------------------------------------------------- #
# Story
# --------------------------------------------------------------------------- #
@dataclass
class Story:
    """A named container of tasks."""

    title: str
    id: str = field(default_factory=lambda: new_id("story"))
    description: str = ""
    tasks: list[Task] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.title = clean_title(self.title, "Untitled story")
        self.description = _as_text(self.description)
        if not _as_text(self.id):
            self.id = new_id("story")
        self.tasks = [
            t if isinstance(t, Task) else Task.from_dict(t) for t in self.tasks
        ]

    # -- task management --------------------------------------------------- #
    def add_task(self, title: str, status: str = STATUS_TODO) -> Task:
        task = Task(title=title, status=status)
        self.tasks.append(task)
        return task

    def remove_task(self, task_id: str) -> bool:
        for index, task in enumerate(self.tasks):
            if task.id == task_id:
                del self.tasks[index]
                return True
        return False

    def task_by_id(self, task_id: str) -> Task | None:
        return next((t for t in self.tasks if t.id == task_id), None)

    # -- derived state ----------------------------------------------------- #
    def status_counts(self) -> dict[str, int]:
        counts = dict.fromkeys(STATUSES, 0)
        for task in self.tasks:
            counts[task.status] = counts.get(task.status, 0) + 1
        return counts

    def progress(self) -> tuple[int, int]:
        """``(closed_tasks, total_tasks)``."""
        return self.status_counts()[STATUS_CLOSE], len(self.tasks)

    # -- serialization ----------------------------------------------------- #
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def from_dict(cls, raw: Any) -> Story:
        if isinstance(raw, str):
            return cls(title=raw)
        if not isinstance(raw, dict):
            return cls(title="Untitled story")
        tasks = [
            Task.from_dict(item)
            for item in (raw.get("tasks") or [])
            if isinstance(item, (dict, str))
        ]
        return cls(
            title=raw.get("title", "Untitled story"),
            id=_as_text(raw.get("id")) or new_id("story"),
            description=_as_text(raw.get("description", "")),
            tasks=tasks,
        )


# --------------------------------------------------------------------------- #
# Workspace (the whole tasks.json document)
# --------------------------------------------------------------------------- #
@dataclass
class Workspace:
    """Top-level document: schema version, timestamp, and all stories."""

    stories: list[Story] = field(default_factory=list)
    version: str = SCHEMA_VERSION
    last_modified: str = field(default_factory=now_iso)

    def __post_init__(self) -> None:
        self.version = _as_text(self.version) or SCHEMA_VERSION
        self.last_modified = _iso_or_now(self.last_modified)
        self.stories = [
            s if isinstance(s, Story) else Story.from_dict(s) for s in self.stories
        ]

    # -- story management -------------------------------------------------- #
    def add_story(self, title: str, description: str = "") -> Story:
        story = Story(title=title, description=description)
        self.stories.append(story)
        return story

    def remove_story(self, story_id: str) -> bool:
        for index, story in enumerate(self.stories):
            if story.id == story_id:
                del self.stories[index]
                return True
        return False

    def story_by_id(self, story_id: str) -> Story | None:
        return next((s for s in self.stories if s.id == story_id), None)

    def is_empty(self) -> bool:
        return not self.stories

    # -- serialization ----------------------------------------------------- #
    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "last_modified": self.last_modified,
            "stories": [story.to_dict() for story in self.stories],
        }

    @classmethod
    def from_dict(cls, raw: Any) -> Workspace:
        # Tolerate a bare list of stories from older/hand-written files.
        if isinstance(raw, list):
            raw = {"stories": raw}
        if not isinstance(raw, dict):
            raw = {}
        stories = [
            Story.from_dict(item)
            for item in (raw.get("stories") or [])
            if isinstance(item, (dict, str))
        ]
        return cls(
            stories=stories,
            version=_as_text(raw.get("version")) or SCHEMA_VERSION,
            last_modified=_iso_or_now(raw.get("last_modified")),
        )

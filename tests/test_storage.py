# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for JSON persistence: round-trips, corruption recovery, atomicity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from getitdone import storage
from getitdone.models import STATUS_CLOSE, STATUS_INPROGRESS, Workspace


@pytest.fixture(autouse=True)
def _clear_path_cache():
    """Keep the cached default path from leaking between tests."""
    storage.reset_path_cache()
    yield
    storage.reset_path_cache()


class TestRoundTrip:
    def test_save_then_load(self, tmp_path):
        target = tmp_path / "tasks.json"
        ws = Workspace()
        story = ws.add_story("Proposal", "Scope")
        story.add_task("Write brief").set_status(STATUS_CLOSE)
        story.add_task("Research").set_status(STATUS_INPROGRESS)

        assert storage.save_data(ws, target) is True

        restored = storage.load_data(target)
        assert [s.title for s in restored.stories] == ["Proposal"]
        assert restored.stories[0].description == "Scope"
        assert [t.status for t in restored.stories[0].tasks] == [
            STATUS_CLOSE,
            STATUS_INPROGRESS,
        ]

    def test_save_is_readable_json_with_trailing_newline(self, tmp_path):
        target = tmp_path / "tasks.json"
        storage.save_data(Workspace(), target)

        text = target.read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert json.loads(text)["version"] == "1.0"

    def test_save_creates_missing_parent_directories(self, tmp_path):
        target = tmp_path / "deep" / "nested" / "tasks.json"
        assert storage.save_data(Workspace(), target) is True
        assert target.exists()

    def test_save_stamps_last_modified(self, tmp_path):
        target = tmp_path / "tasks.json"
        ws = Workspace()
        before = ws.last_modified
        storage.save_data(ws, target)
        assert ws.last_modified >= before

    def test_save_accepts_a_plain_dict(self, tmp_path):
        target = tmp_path / "tasks.json"
        assert storage.save_data({"stories": [{"title": "From dict"}]}, target) is True
        assert storage.load_data(target).stories[0].title == "From dict"


class TestRecovery:
    def test_missing_file_yields_empty_workspace(self, tmp_path):
        ws = storage.load_data(tmp_path / "does-not-exist.json")
        assert ws.is_empty() is True

    def test_empty_file_yields_empty_workspace(self, tmp_path):
        target = tmp_path / "tasks.json"
        target.write_text("   \n", encoding="utf-8")
        assert storage.load_data(target).is_empty() is True

    def test_corrupt_json_is_quarantined_not_deleted(self, tmp_path):
        target = tmp_path / "tasks.json"
        target.write_text("{ this is not json", encoding="utf-8")

        ws = storage.load_data(target)

        assert ws.is_empty() is True
        assert not target.exists(), "corrupt file should be moved aside"
        backups = list(tmp_path.glob("tasks.json.corrupt-*"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == "{ this is not json"

    def test_unreadable_payload_type_still_yields_a_workspace(self, tmp_path):
        target = tmp_path / "tasks.json"
        target.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        assert isinstance(storage.load_data(target), Workspace)

    def test_partial_document_is_tolerated(self, tmp_path):
        target = tmp_path / "tasks.json"
        target.write_text(
            json.dumps({"stories": [{"title": "Only a title"}]}), encoding="utf-8"
        )

        ws = storage.load_data(target)
        assert ws.stories[0].title == "Only a title"
        assert ws.stories[0].tasks == []


class TestSaveFailures:
    def test_blocked_directory_returns_false(self, tmp_path):
        blocker = tmp_path / "blocker"
        blocker.write_text("I am a file, not a directory", encoding="utf-8")
        assert storage.save_data(Workspace(), blocker / "tasks.json") is False

    def test_target_being_a_directory_returns_false(self, tmp_path):
        target = tmp_path / "tasks.json"
        target.mkdir()
        assert storage.save_data(Workspace(), target) is False

    def test_failed_save_leaves_no_temp_files_behind(self, tmp_path):
        target = tmp_path / "tasks.json"
        target.mkdir()
        storage.save_data(Workspace(), target)
        assert list(tmp_path.glob(".tasks-*")) == []

    def test_existing_file_survives_a_failed_replace(self, tmp_path, monkeypatch):
        """The atomic-write guarantee: a crash during replace must not truncate."""
        target = tmp_path / "tasks.json"
        ws = Workspace()
        ws.add_story("Keep me")
        storage.save_data(ws, target)
        original = target.read_text(encoding="utf-8")

        def boom(*args, **kwargs):
            raise OSError("simulated failure during replace")

        monkeypatch.setattr(storage.os, "replace", boom)

        assert storage.save_data(Workspace(), target) is False
        assert target.read_text(encoding="utf-8") == original
        assert list(tmp_path.glob(".tasks-*")) == [], "temp file should be cleaned up"


class TestDefaultPath:
    def test_resolves_to_tasks_json(self):
        path = storage.default_data_path()
        assert path.name == storage.DATA_FILENAME

    def test_is_cached(self):
        assert storage.default_data_path() == storage.default_data_path()

    def test_reset_clears_the_cache(self):
        first = storage.default_data_path()
        storage.reset_path_cache()
        assert storage.default_data_path() == first

    def test_prefers_the_home_directory(self):
        assert storage.default_data_path().parent.name == storage.APP_DIR_NAME

    def test_never_resolves_inside_the_package(self):
        """User data must not land in the source tree or in site-packages."""
        package_dir = Path(storage.__file__).resolve().parent
        resolved = storage.default_data_path().resolve()
        assert package_dir not in resolved.parents


class TestFallbackDir:
    def test_uses_localappdata_on_windows(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
        assert storage._fallback_dir() == tmp_path / "local" / storage.APP_NAME

    def test_uses_xdg_data_home_when_localappdata_is_absent(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        assert storage._fallback_dir() == tmp_path / "xdg" / storage.APP_NAME.lower()

    def test_fallback_never_points_at_the_package(self):
        package_dir = Path(storage.__file__).resolve().parent
        assert package_dir not in storage._fallback_dir().resolve().parents

    def test_unwritable_home_still_yields_a_sane_path(self, monkeypatch, tmp_path):
        """The last-resort branch must not fall back into the package dir."""
        monkeypatch.setattr(storage, "_dir_is_writable", lambda directory: False)
        resolved = storage.default_data_path()
        assert resolved.name == storage.DATA_FILENAME
        assert Path(storage.__file__).resolve().parent not in resolved.resolve().parents

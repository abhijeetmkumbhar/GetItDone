# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version. See the LICENSE file for details.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""JSON persistence for GetItDone.

One file, one document:

    ~/.getitdone/tasks.json                 (primary)
    %LOCALAPPDATA%/GetItDone/tasks.json     (fallback, if home is unwritable)

User data is never written inside the installed package: ``site-packages`` is
read-only on many systems and is discarded on reinstall or upgrade.

Guarantees:
  * ``load_data()`` never raises. A missing, unreadable, or corrupt file yields
    an empty :class:`Workspace` (the corrupt file is quarantined, not deleted).
  * ``save_data()`` is atomic (temp file + ``os.replace``) so a crash or power
    loss mid-write cannot truncate the existing file. It returns ``False``
    instead of raising so the UI can warn the user.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Workspace, now_iso

__all__ = [
    "APP_DIR_NAME",
    "APP_NAME",
    "DATA_FILENAME",
    "default_data_path",
    "load_data",
    "reset_path_cache",
    "save_data",
]

APP_NAME = "GetItDone"
APP_DIR_NAME = ".getitdone"
DATA_FILENAME = "tasks.json"

#: Cached result of the writability probe (see :func:`default_data_path`).
_resolved_path: Path | None = None


# --------------------------------------------------------------------------- #
# Path resolution
# --------------------------------------------------------------------------- #
def _dir_is_writable(directory: Path) -> bool:
    """True if ``directory`` exists (or can be created) and accepts a write."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    probe = directory / f".write-probe-{os.getpid()}"
    try:
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _fallback_dir() -> Path:
    """Per-user data directory to use when the home directory is unwritable.

    Deliberately outside the source tree and outside ``site-packages``: the
    package directory may be read-only or replaced on upgrade, which would
    silently lose the user's tasks.
    """
    local_appdata = os.environ.get("LOCALAPPDATA")  # Windows
    if local_appdata:
        return Path(local_appdata) / APP_NAME

    xdg_data_home = os.environ.get("XDG_DATA_HOME")  # Linux / BSD
    if xdg_data_home:
        return Path(xdg_data_home) / APP_NAME.lower()

    return Path.home() / ".local" / "share" / APP_NAME.lower()


def default_data_path() -> Path:
    """Resolve the active ``tasks.json`` path, probing writability once."""
    global _resolved_path
    if _resolved_path is not None:
        return _resolved_path

    for candidate in (Path.home() / APP_DIR_NAME, _fallback_dir()):
        if _dir_is_writable(candidate):
            _resolved_path = candidate / DATA_FILENAME
            return _resolved_path

    # Last resort: still return a path; saving will report failure.
    _resolved_path = _fallback_dir() / DATA_FILENAME
    return _resolved_path


def reset_path_cache() -> None:
    """Clear the cached path (used by tests and by the Settings dialog)."""
    global _resolved_path
    _resolved_path = None


def _resolve(path: str | Path | None) -> Path:
    return Path(path) if path else default_data_path()


# --------------------------------------------------------------------------- #
# Load
# --------------------------------------------------------------------------- #
def _quarantine(target: Path) -> Path | None:
    """Rename a corrupt file aside so the user can inspect it later."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = target.with_name(f"{target.name}.corrupt-{stamp}")
    try:
        os.replace(target, backup)
        return backup
    except OSError:
        return None


def load_data(path: str | Path | None = None) -> Workspace:
    """Load the workspace, recovering to an empty one on any failure."""
    target = _resolve(path)

    try:
        raw_text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        # First run: start empty; the file is created on the first save.
        return Workspace()
    except OSError:
        # Unreadable (permissions, locking, device error).
        return Workspace()

    if not raw_text.strip():
        return Workspace()

    try:
        payload: Any = json.loads(raw_text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        _quarantine(target)
        return Workspace()

    try:
        return Workspace.from_dict(payload)
    except Exception:  # noqa: BLE001 - never crash at startup
        _quarantine(target)
        return Workspace()


# --------------------------------------------------------------------------- #
# Save
# --------------------------------------------------------------------------- #
def save_data(
    data: Workspace | dict | None,
    path: str | Path | None = None,
) -> bool:
    """Atomically write ``data`` to disk. Returns ``False`` on failure."""
    workspace = data if isinstance(data, Workspace) else Workspace.from_dict(data)

    workspace.last_modified = now_iso()
    target = _resolve(path)

    tmp_name: str | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(target.parent), prefix=".tasks-", suffix=".tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(workspace.to_dict(), handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
        tmp_name = None
        return True
    except (OSError, TypeError, ValueError):
        return False
    finally:
        if tmp_name and os.path.exists(tmp_name):
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)

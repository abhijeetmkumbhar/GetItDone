# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version. See the LICENSE file for details.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Application service layer: owns the workspace and its persistence.

The UI never imports :mod:getitdone.storage; it asks this service to save.
That keeps file-format and error-handling policy in one place and lets the
widgets be exercised without touching a filesystem.
"""

from __future__ import annotations

import logging
from pathlib import Path

from . import storage
from .models import Workspace

__all__ = ["WorkspaceService"]

logger = logging.getLogger(__name__)


class WorkspaceService:
    """Holds a :class:Workspace and knows where to persist it."""

    def __init__(
        self,
        workspace: Workspace,
        data_path: str | Path | None = None,
    ) -> None:
        self.workspace = workspace
        self.data_path: str | Path | None = data_path

    @classmethod
    def open(cls, data_path: str | Path | None = None) -> WorkspaceService:
        """Load a workspace from `data_path` (or the default location)."""
        return cls(storage.load_data(data_path), data_path)

    def save(self) -> bool:
        """Persist the workspace; returns `False` instead of raising."""
        if storage.save_data(self.workspace, self.data_path):
            return True
        logger.warning("could not save %s", self.data_path or storage.DATA_FILENAME)
        return False

# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Demo data for exercising the widget.

Ships with the package because it backs the `--dev` CLI flag, but it is
never imported on the normal startup path.  Reachable via ``python -m getitdone --dev``.
"""

from __future__ import annotations

from pathlib import Path

from . import storage
from .models import STATUS_CLOSE, STATUS_INPROGRESS, Workspace

__all__ = ["DEMO_DATA_DIR", "DEMO_FILENAME", "default_demo_path", "seed_demo_data"]

#: Scratch directory for generated demo data, relative to the current directory.
DEMO_DATA_DIR = ".dev"
DEMO_FILENAME = "dev_tasks.json"


def default_demo_path() -> Path:
    """``./.dev/dev_tasks.json``, resolved at call time rather than import time."""
    return Path.cwd() / DEMO_DATA_DIR / DEMO_FILENAME


def seed_demo_data(path: Path | None = None, force: bool = False) -> Path:
    """Write a demo workspace to ``path`` unless it already exists."""
    target = Path(path) if path is not None else default_demo_path()
    if target.exists() and not force:
        return target

    workspace = Workspace()

    proposal = workspace.add_story(
        "Project Proposal", "Initial project planning and scope definition"
    )
    proposal.add_task("Write project brief").set_status(STATUS_CLOSE)
    proposal.add_task("Research requirements").set_status(STATUS_INPROGRESS)
    proposal.add_task("Define milestones")
    proposal.add_task(
        "Get sign-off from stakeholders on the revised timeline and budget"
    )

    redesign = workspace.add_story(
        "Website Redesign", "Q2 refresh of the marketing site"
    )
    redesign.add_task("Audit current site").set_status(STATUS_CLOSE)
    redesign.add_task("Collect reference sites")
    redesign.add_task("Wireframe the landing page").set_status(STATUS_INPROGRESS)

    office = workspace.add_story("Home Office Setup")
    office.add_task("Measure the desk alcove")
    office.add_task("Order monitor arm").set_status(STATUS_CLOSE)

    workspace.add_story("Q3 Roadmap")
    workspace.add_story("Team Offsite", "Two days, somewhere with decent wifi")
    workspace.add_story("Docs Refresh")

    storage.save_data(workspace, target)
    return target

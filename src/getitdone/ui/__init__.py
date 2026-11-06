# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Qt widgets making up the desktop dashboard."""

__all__ = ["MainWindow", "StoryWidget", "columns_for_width"]


def __getattr__(name: str):
    # Imported lazily so `import getitdone.ui` does not require a QApplication
    # or pull in Qt at all for non-UI callers.
    if name == "MainWindow":
        from .main_window import MainWindow

        return MainWindow
    if name == "StoryWidget":
        from .widgets import StoryWidget

        return StoryWidget
    if name == "columns_for_width":
        from .theme import columns_for_width

        return columns_for_width
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

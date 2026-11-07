# GetItDone - desktop-embedded project management widget


# Copyright (C) 2026 GetItDone contributors
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version. See the LICENSE file for details.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Application entry point.

python -m getitdone              # normal run against your saved data
python -m getitdone --dev        # demo data in ./.dev/dev_tasks.json
python -m getitdone --top        # ordinary window on top, for inspection
python -m getitdone --no-desktop # always-on-bottom instead of the X11 desktop layer
"""

from __future__ import annotations

import argparse
import sys

from . import __version__, storage
from .ui.main_window import MainWindow

__all__ = ["main"]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="getitdone",
        description="Desktop-embedded project management widget.",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="use ./.dev/dev_tasks.json (demo data) instead of your real data",
    )
    parser.add_argument(
        "--top",
        action="store_true",
        help="show as an ordinary window on top (for inspecting the UI)",
    )
    parser.add_argument(
        "--no-desktop",
        action="store_true",
        help="keep the widget out of the X11 desktop layer (always-on-bottom)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # Qt is imported here so --help works on machines without PyQt6 installed.
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeySequence, QShortcut
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    app.setApplicationName("GetItDone")
    app.setApplicationVersion(__version__)

    if args.dev:
        from .dev import seed_demo_data

        path = seed_demo_data()
    else:
        path = storage.default_data_path()

    workspace = storage.load_data(path)
    # --top and --no-desktop both opt out of the X11 desktop layer.
    desktop_layer = not (args.top or args.no_desktop)
    window = MainWindow(workspace, data_path=str(path), desktop_layer=desktop_layer)

    if args.top:
        window.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
    window.save_failed.connect(
        lambda msg: print(f"[save failed] {msg}", file=sys.stderr)
    )
    window.add_story_requested.connect(
        lambda: print("[not implemented] add story (phase 3)")
    )
    window.settings_requested.connect(
        lambda: print("[not implemented] settings (phase 3)")
    )

    QShortcut(QKeySequence("Ctrl+Q"), window, window.close)

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

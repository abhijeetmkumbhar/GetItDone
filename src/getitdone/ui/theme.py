# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version. See the LICENSE file for details.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Visual constants and the Qt stylesheet.

Everything cosmetic lives here so the widgets stay free of literal colours and
the whole look can be retuned from one file.
"""

from __future__ import annotations

# -- layout ----------------------------------------------------------------- #
# The widget covers the whole desktop, so sizing is driven by how many story
# columns fit across the screen rather than by a fixed panel size.
COLUMN_TARGET_WIDTH = 360  # each column aims for about this width
MAX_COLUMNS = 4  # keep line lengths readable on ultrawide displays
COLUMN_SPACING = 12
CARD_SPACING = 10
CONTENT_MARGIN = 16

# -- palette ---------------------------------------------------------------- #
TEXT = "#e8eaed"
TEXT_MUTED = "#9aa0a6"
TEXT_DONE = "#767c82"
PANEL_BG = "rgba(22, 24, 29, 216)"


def columns_for_width(width: int) -> int:
    """How many story columns fit in ``width`` pixels."""
    if width <= 0:
        return 1
    return max(1, min(MAX_COLUMNS, width // COLUMN_TARGET_WIDTH))


STYLESHEET = f"""
#Panel {{
    background-color: {PANEL_BG};
}}
#StoryCard {{
    background-color: rgba(255, 255, 255, 9);
    border: 1px solid rgba(255, 255, 255, 18);
    border-radius: 10px;
}}
QLabel {{ color: {TEXT}; }}
#HeaderTitle {{ font-size: 15px; font-weight: 600; }}
#HeaderSummary {{ color: {TEXT_MUTED}; font-size: 11px; }}
#EmptyHint {{ color: {TEXT_MUTED}; font-size: 12px; }}
#StoryTitle {{ font-size: 13px; font-weight: 600; }}
#StoryProgress {{ color: {TEXT_MUTED}; font-size: 11px; }}
#StoryArrow {{ color: {TEXT_MUTED}; font-size: 10px; }}
#TaskTitle {{ font-size: 12px; color: {TEXT}; }}
#TaskTitleDone {{ font-size: 12px; color: {TEXT_DONE}; }}

#StoryHeader {{ background: transparent; border-radius: 8px; }}
#StoryHeader:hover {{ background: rgba(255, 255, 255, 14); }}
#TaskRow {{ background: transparent; border-radius: 6px; }}
#TaskRow:hover {{ background: rgba(255, 255, 255, 16); }}

#FooterButton {{
    background: rgba(255, 255, 255, 20);
    color: {TEXT};
    border: none;
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 12px;
}}
#FooterButton:hover {{ background: rgba(255, 255, 255, 38); }}
#FooterButton:pressed {{ background: rgba(255, 255, 255, 52); }}

QScrollArea {{ background: transparent; border: none; }}
#GridHost, #Column {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 45);
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{ background: transparent; }}
"""

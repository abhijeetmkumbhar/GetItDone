# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for the X11 desktop-layer helper.

These run anywhere: the module is required to degrade to a no-op when libX11
or a display is missing, which is exactly what is asserted here.
"""

from __future__ import annotations

import pytest

from getitdone.ui import x11


class TestSupportProbe:
    def test_is_supported_returns_a_bool(self):
        assert isinstance(x11.is_supported(), bool)

    def test_is_supported_is_stable(self):
        assert x11.is_supported() == x11.is_supported()


class TestSetDesktopType:
    @pytest.mark.parametrize("window_id", [0, -1])
    def test_rejects_invalid_window_ids(self, window_id):
        """Must not reach the server: a BadWindow would abort the process."""
        assert x11.set_desktop_type(window_id) is False

    def test_survives_a_missing_libx11(self, monkeypatch):
        monkeypatch.setattr(x11, "_libx11", None)
        monkeypatch.setattr(x11, "_load_attempted", True)
        assert x11.is_supported() is False
        assert x11.set_desktop_type(1234) is False

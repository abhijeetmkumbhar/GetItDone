# GetItDone - desktop-embedded project management widget
# Copyright (C) 2026 GetItDone contributors
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version. See the LICENSE file for details.
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""X11 desktop-layer integration.

A window whose ``_NET_WM_WINDOW_TYPE`` is ``_NET_WM_WINDOW_TYPE_DESKTOP`` is
placed by the window manager in the *desktop layer*: above the wallpaper,
below every normal window, and - crucially - still visible after "Show
Desktop" (Super+D). That is the X11 equivalent of the Windows ``WorkerW``
parenting described in the implementation plan (step 4.2).

Qt exposes no window flag for this, so the property is written straight
through libX11 with ``ctypes``. No new runtime dependency, and everything
here degrades to a no-op on Windows, macOS, or native Wayland.
"""

from __future__ import annotations

import ctypes
import ctypes.util

__all__ = ["is_supported", "set_desktop_type"]

#: X11 atom type for ``ATOM`` (see X11/Xatom.h).
_XA_ATOM = 4
#: ``PropModeReplace`` from X11/X.h.
_PROP_MODE_REPLACE = 0

_libx11: ctypes.CDLL | None = None
_load_attempted = False


def _load() -> ctypes.CDLL | None:
    """Load and prototype libX11 once. ``None`` when unavailable."""
    global _libx11, _load_attempted
    if _load_attempted:
        return _libx11
    _load_attempted = True

    name = ctypes.util.find_library("X11")
    if not name:
        return None
    try:
        lib = ctypes.CDLL(name)
    except OSError:
        return None

    lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    lib.XOpenDisplay.restype = ctypes.c_void_p
    lib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    lib.XInternAtom.restype = ctypes.c_ulong
    lib.XChangeProperty.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.c_int,
    ]
    lib.XChangeProperty.restype = ctypes.c_int
    lib.XFlush.argtypes = [ctypes.c_void_p]
    lib.XFlush.restype = ctypes.c_int
    lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
    lib.XCloseDisplay.restype = ctypes.c_int

    _libx11 = lib
    return lib


def is_supported() -> bool:
    """True when libX11 is available on this machine."""
    return _load() is not None


def set_desktop_type(window_id: int) -> bool:
    """Tag ``window_id`` as ``_NET_WM_WINDOW_TYPE_DESKTOP``.

    Must be called *after* the native window exists but *before* it is mapped,
    otherwise the window manager has already decided where the window belongs.

    Returns ``True`` when the property was written, ``False`` on any failure
    (no libX11, no display, bad window id) so callers can fall back silently.
    """
    lib = _load()
    # A non-positive id would raise a BadWindow X error, which Xlib's default
    # handler turns into process exit. Reject it before touching the server.
    if lib is None or window_id <= 0:
        return False

    display = lib.XOpenDisplay(None)
    if not display:
        return False

    try:
        prop = lib.XInternAtom(display, b"_NET_WM_WINDOW_TYPE", 0)
        desktop = lib.XInternAtom(display, b"_NET_WM_WINDOW_TYPE_DESKTOP", 0)
        if not prop or not desktop:
            return False

        value = (ctypes.c_ulong * 1)(desktop)
        status = lib.XChangeProperty(
            display,
            window_id,
            prop,
            _XA_ATOM,
            32,
            _PROP_MODE_REPLACE,
            value,
            1,
        )
        lib.XFlush(display)
        return bool(status)
    finally:
        lib.XCloseDisplay(display)

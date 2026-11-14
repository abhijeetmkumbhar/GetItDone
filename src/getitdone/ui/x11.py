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

__all__ = ["force_full_input_region", "is_supported", "set_desktop_type"]

#: X11 atom type for ``ATOM`` (see X11/Xatom.h).
_XA_ATOM = 4
#: X11 atom type for ``CARDINAL``.
_XA_CARDINAL = 6
#: ``PropModeReplace`` from X11/X.h.
_PROP_MODE_REPLACE = 0

#: XShape extension constants (see ``X11/extensions/shape.h``).
_SHAPE_INPUT = 2  # ShapeInput
_SHAPE_SET = 0  # ShapeSet
_UNSORTED = 0  # Unsorted

#: ``_NET_WM_DESKTOP`` value that pins a window to every desktop.
_ALL_DESKTOPS = 0xFFFFFFFF

_libx11: ctypes.CDLL | None = None
_libxext: ctypes.CDLL | None = None
_load_attempted = False
_shape_load_attempted = False


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
        lib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.XSync.restype = ctypes.c_int
        lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
        lib.XCloseDisplay.restype = ctypes.c_int
        lib.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        lib.XSetErrorHandler.restype = ctypes.c_void_p
    except (OSError, AttributeError):
        # A libX11 missing these symbols is unusable. Degrade to a no-op
        # instead of raising into a Qt virtual method (which calls qFatal).
        return None

    _libx11 = lib
    return lib


class _XRectangle(ctypes.Structure):
    """X11 ``XRectangle`` (see ``X11/Xlib.h``)."""

    _fields_ = [
        ("x", ctypes.c_short),
        ("y", ctypes.c_short),
        ("width", ctypes.c_ushort),
        ("height", ctypes.c_ushort),
    ]


#: Signature of ``XErrorHandler``: ``int (*)(Display *, XErrorEvent *)``.
_XErrorHandler = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)

_x_error_seen = False


@_XErrorHandler
def _record_x_error(_display, _event) -> int:
    """Swallow one X protocol error for the duration of a guarded call.

    Xlib's *default* handler calls ``exit(1)``, so a stale or foreign window
    id would otherwise take the whole application down.
    """
    global _x_error_seen
    _x_error_seen = True
    return 0


def _load_shape() -> ctypes.CDLL | None:
    """Load and prototype the XShape extension, or ``None`` when unavailable.

    ``XShape*`` lives in **libXext**, *not* libX11. Asking libX11 for those
    symbols raises ``AttributeError``; because this is reached from a Qt
    virtual method (``showEvent``), such an exception turns into ``qFatal``
    and aborts the process. Hence the separate handle and tolerant lookup.
    """
    global _libxext, _shape_load_attempted
    if _shape_load_attempted:
        return _libxext
    _shape_load_attempted = True

    name = ctypes.util.find_library("Xext")
    if not name:
        return None
    try:
        lib = ctypes.CDLL(name)

        lib.XShapeQueryExtension.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.XShapeQueryExtension.restype = ctypes.c_int
        lib.XShapeCombineRectangles.argtypes = [
            ctypes.c_void_p,  # display
            ctypes.c_ulong,  # window
            ctypes.c_int,  # dest_kind (ShapeInput)
            ctypes.c_int,  # x_off
            ctypes.c_int,  # y_off
            ctypes.POINTER(_XRectangle),  # rectangles
            ctypes.c_int,  # n_rects
            ctypes.c_int,  # op (ShapeSet)
            ctypes.c_int,  # ordering
        ]
        lib.XShapeCombineRectangles.restype = None
    except (OSError, AttributeError):
        return None

    _libxext = lib
    return lib


def is_supported() -> bool:
    """True when libX11 is available on this machine."""
    return _load() is not None


def _guarded(lib: ctypes.CDLL, display: int, call) -> bool:
    """Run ``call`` with X errors trapped, then round-trip to collect them.

    X requests are asynchronous, so the ``BadWindow``/``BadValue`` error is
    only delivered by ``XSync``. Without this, Xlib's default error handler
    would ``exit(1)`` the process on a stale window id.
    """
    global _x_error_seen
    previous = lib.XSetErrorHandler(ctypes.cast(_record_x_error, ctypes.c_void_p))
    _x_error_seen = False
    try:
        call()
        lib.XSync(display, 0)
        return not _x_error_seen
    finally:
        lib.XSetErrorHandler(previous)


def set_desktop_type(window_id: int) -> bool:
    """Tag ``window_id`` as a sticky desktop-layer window.

    Sets both:
    - ``_NET_WM_WINDOW_TYPE = _NET_WM_WINDOW_TYPE_DESKTOP``
    - ``_NET_WM_DESKTOP = 0xffffffff`` (all desktops / sticky)

    Must be called *after* the native window exists but *before* it is mapped,
    otherwise the window manager has already decided where the window belongs.

    Returns ``True`` when the properties were written, ``False`` on any failure
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
        type_prop = lib.XInternAtom(display, b"_NET_WM_WINDOW_TYPE", 0)
        desktop_type = lib.XInternAtom(display, b"_NET_WM_WINDOW_TYPE_DESKTOP", 0)
        desktop_prop = lib.XInternAtom(display, b"_NET_WM_DESKTOP", 0)
        if not type_prop or not desktop_type or not desktop_prop:
            return False

        type_value = (ctypes.c_ulong * 1)(desktop_type)
        sticky_value = (ctypes.c_ulong * 1)(_ALL_DESKTOPS)

        def write() -> None:
            lib.XChangeProperty(
                display,
                window_id,
                type_prop,
                _XA_ATOM,
                32,
                _PROP_MODE_REPLACE,
                type_value,
                1,
            )
            lib.XChangeProperty(
                display,
                window_id,
                desktop_prop,
                _XA_CARDINAL,
                32,
                _PROP_MODE_REPLACE,
                sticky_value,
                1,
            )

        return _guarded(lib, display, write)
    finally:
        lib.XCloseDisplay(display)


def force_full_input_region(window_id: int, width: int, height: int) -> bool:
    """Force the window's ShapeInput region to cover the entire window.

    A translucent, frameless X11 window can end up with an empty or partial
    input shape and therefore receive no mouse events at all. Replacing the
    ``ShapeInput`` region with a single window-sized rectangle restores
    hit-testing without affecting what is painted.

    Returns ``True`` when the region was written, ``False`` on any failure.
    """
    lib = _load()
    shape = _load_shape()
    if lib is None or shape is None or window_id <= 0:
        return False
    if width <= 0 or height <= 0:
        return False

    display = lib.XOpenDisplay(None)
    if not display:
        return False

    try:
        event_base = ctypes.c_int()
        error_base = ctypes.c_int()
        if not shape.XShapeQueryExtension(
            display, ctypes.byref(event_base), ctypes.byref(error_base)
        ):
            return False

        rect = _XRectangle(0, 0, width, height)

        def combine() -> None:
            shape.XShapeCombineRectangles(
                display,
                window_id,
                _SHAPE_INPUT,
                0,
                0,
                ctypes.pointer(rect),
                1,
                _SHAPE_SET,
                _UNSORTED,
            )

        return _guarded(lib, display, combine)
    finally:
        lib.XCloseDisplay(display)

"""Detect the true OpenGL drawable size (physical pixels) on Hi-DPI / Retina.

pygame's get_size() reports the window size in *points* (logical units).  On a
Retina display a fullscreen window gets a 2x backing store, so the real GL
drawable is twice as large in each axis.  If we set the viewport to the point
size, we only render into one quarter of the screen.  This module asks the SDL2
that pygame already loaded for the real drawable size (SDL_GL_GetDrawableSize).

Everything is best-effort: on any failure we return the supplied fallback, so
non-Retina setups and odd environments behave exactly as before.
"""

import ctypes
import glob
import os

import pygame

_sdl = None  # cached CDLL handle, or False if unavailable


def _load():
    global _sdl
    if _sdl is not None:
        return _sdl
    base = os.path.dirname(pygame.__file__)
    candidates = (glob.glob(os.path.join(base, '.dylibs', 'libSDL2*.dylib')) +
                  glob.glob(os.path.join(base, '**', 'libSDL2*'), recursive=True))
    for path in candidates:
        try:
            # Re-opening an already-loaded dylib returns the SAME instance, so
            # SDL_GL_GetCurrentWindow() refers to pygame's actual window.
            lib = ctypes.CDLL(path)
            lib.SDL_GL_GetCurrentWindow.restype = ctypes.c_void_p
            lib.SDL_GL_GetDrawableSize.argtypes = [
                ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int)]
            _sdl = lib
            return _sdl
        except Exception:
            continue
    _sdl = False
    return _sdl


def drawable_size(fallback):
    """Return the real (physical-pixel) drawable size, or `fallback` on failure."""
    lib = _load()
    if not lib:
        return fallback
    try:
        win = lib.SDL_GL_GetCurrentWindow()
        if not win:
            return fallback
        w = ctypes.c_int(0)
        h = ctypes.c_int(0)
        lib.SDL_GL_GetDrawableSize(win, ctypes.byref(w), ctypes.byref(h))
        if w.value > 1 and h.value > 1:
            return (w.value, h.value)
    except Exception:
        pass
    return fallback

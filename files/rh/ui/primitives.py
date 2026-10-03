# -*- coding: utf-8 -*-
"""Nguyen thuy SDL2 cho rh/ engine.

Pure ctypes wrapper giong PySDL2 nhung nhe hon, day du cho muc tieu cua
trimui-chiaki-ng (window, renderer, text, texture, event, joystick).
"""

import ctypes
import os
import sys

try:
    if sys.platform.startswith("linux"):
        ctypes.CDLL("libSDL2-2.0.so.0", mode=ctypes.RTLD_GLOBAL)
        ctypes.CDLL("libSDL2_ttf-2.0.so.0", mode=ctypes.RTLD_GLOBAL)
except OSError:
    pass

try:
    _sdl = (ctypes.CDLL("SDL2", mode=ctypes.RTLD_GLOBAL)
            if sys.platform == "win32" else ctypes.CDLL(None))
except OSError:
    # Test tren Windows va moi truong khong co SDL: phan theme/helper duoi
    # day khong can SDL nen van phai import duoc.
    _sdl = None

# SDL.h
SDL_INIT_VIDEO = 0x20
SDL_INIT_JOYSTICK = 0x400
SDL_INIT_GAMECONTROLLER = 0x4000
SDL_INIT_AUDIO = 0x10
SDL_WINDOW_SHOWN = 0x4
SDL_WINDOW_FULLSCREEN = 0x1
SDL_WINDOW_BORDERLESS = 0x10
SDL_RENDERER_ACCELERATED = 0x2
SDL_RENDERER_PRESENTVSYNC = 0x4

SDL_QUIT = 0x100
SDL_KEYDOWN = 0x300
SDL_KEYUP = 0x301
SDL_JOYAXISMOTION = 0x600
SDL_JOYBUTTONDOWN = 0x603
SDL_JOYBUTTONUP = 0x604
SDL_CONTROLLERBUTTONDOWN = 0x650
SDL_CONTROLLERBUTTONUP = 0x651
SDL_CONTROLLERAXISMOTION = 0x654

SDL_GAMECONTROLLER_BUTTON_A = 0
SDL_GAMECONTROLLER_BUTTON_B = 1
SDL_GAMECONTROLLER_BUTTON_X = 2
SDL_GAMECONTROLLER_BUTTON_Y = 3
SDL_GAMECONTROLLER_BUTTON_BACK = 4
SDL_GAMECONTROLLER_BUTTON_GUIDE = 5
SDL_GAMECONTROLLER_BUTTON_START = 6
SDL_GAMECONTROLLER_BUTTON_LEFTSTICK = 7
SDL_GAMECONTROLLER_BUTTON_RIGHTSTICK = 8
SDL_GAMECONTROLLER_BUTTON_LEFTSHOULDER = 9
SDL_GAMECONTROLLER_BUTTON_RIGHTSHOULDER = 10
SDL_GAMECONTROLLER_BUTTON_DPAD_UP = 11
SDL_GAMECONTROLLER_BUTTON_DPAD_DOWN = 12
SDL_GAMECONTROLLER_BUTTON_DPAD_LEFT = 13
SDL_GAMECONTROLLER_BUTTON_DPAD_RIGHT = 14

SDL_HAT_UP = 0x01
SDL_HAT_DOWN = 0x04
SDL_HAT_LEFT = 0x08
SDL_HAT_RIGHT = 0x02


def bind():
    """Bind SDL prototypes va tra ve (lib, fn_dict). Pure stub cho ban 0.1.0.

    Phien ban 0.1.0 chi can class Texture2D va Rect de ve UI don gian. Viec
    bind toan bo SDL se hoan thien trong 0.2.0 cung luc them codec video
    (libplacebo / ffpyplayer).
    """
    return {}


class Rect:
    __slots__ = ("x", "y", "w", "h")
    def __init__(self, x=0, y=0, w=0, h=0):
        self.x = int(x); self.y = int(y); self.w = int(w); self.h = int(h)
    def __iter__(self):
        yield self.x; yield self.y; yield self.w; yield self.h


class Color:
    __slots__ = ("r", "g", "b", "a")
    def __init__(self, r=0, g=0, b=0, a=255):
        self.r = int(r); self.g = int(g); self.b = int(b); self.a = int(a)


# Bo theme dung chung cho toan app. Moi man hinh chi lay mau qua theme(),
# khong hardcode RGB roi rac nua. "dark" giu nhan dien cu, "light" them theo
# yeu cau. Hai theme co cung tap khoa de doi la an toan.
MARGIN = 40
HEADER_H = 64
FOOTER_H = 56

THEMES = {
    "dark": {
        "bg": (13, 17, 28),
        "header": (20, 28, 46),
        "header_line": (0, 230, 150),
        "footer": (10, 14, 24),
        "footer_line": (35, 45, 75),
        "row": (40, 60, 90),
        "card": (30, 43, 66),
        "accent": (0, 230, 150),
        "text": (255, 255, 255),
        "sub": (220, 225, 235),
        "muted": (150, 165, 185),
        "faint": (120, 132, 150),
        "warn": (255, 190, 80),
        "err": (255, 120, 120),
        "gold": (240, 220, 120),
        "chip_text": (10, 14, 24),
        "track": (10, 14, 24),
        "dim": (0, 0, 0),
    },
    "light": {
        "bg": (232, 238, 244),
        "header": (255, 255, 255),
        "header_line": (0, 170, 115),
        "footer": (255, 255, 255),
        "footer_line": (200, 210, 220),
        "row": (255, 255, 255),
        "card": (255, 255, 255),
        "accent": (0, 170, 115),
        "text": (18, 26, 38),
        "sub": (55, 70, 90),
        "muted": (105, 120, 140),
        "faint": (150, 163, 178),
        "warn": (185, 115, 0),
        "err": (200, 45, 45),
        "gold": (150, 110, 0),
        "chip_text": (255, 255, 255),
        "track": (210, 218, 226),
        "dim": (0, 0, 0),
    },
}


def theme(name):
    """Bang mau cua theme; ten la thi roi ve dark."""
    return THEMES.get(name) or THEMES["dark"]


def safe_measure(engine, text, font, fallback_px_per_char=13):
    """Do rong chu, khong bao gio nem exception.

    Mock engine trong test khong co measure_text that (tra ve Mock), nen
    phai try/except va roi ve uoc luong theo ky tu.
    """
    try:
        return int(engine.measure_text(text, font))
    except Exception:
        pass
    try:
        return int(fallback_px_per_char * len(str(text or "")))
    except Exception:
        return 0


def ellipsis_text(engine, text, font, max_width):
    """Cat chu con "..." cho vua max_width. Chu ngan giu nguyen."""
    text = str(text or "")
    if max_width <= 0:
        return ""
    if safe_measure(engine, text, font) <= max_width:
        return text
    trimmed = text
    while trimmed and safe_measure(engine, trimmed + "...", font) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + "...") if trimmed else ""


def wrap_lines(engine, text, font, max_width, max_lines=None):
    """Xuong dong theo tu, giong ban cu cua guide. Qua max_lines thi
    ellipsis dong cuoi."""
    lines = []
    current = ""
    for word in str(text or "").split():
        candidate = word if not current else "%s %s" % (current, word)
        if current and safe_measure(engine, candidate, font) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = ellipsis_text(engine, lines[-1], font, max_width)
    return lines


def footer_layout(engine, actions, start_x=30, max_x=None, gap=36):
    """Vi tri chip footer do theo chu: chip vua key, label noi tiep.

    Tra ve [(key, label, chip_x, chip_w, label_x)]. Khong ve gi ca nen
    test duoc ma khong can SDL.
    """
    items = []
    fx = start_x
    limit = max_x if max_x is not None else 10 ** 9
    for key, label in actions:
        key_w = max(36, safe_measure(engine, key, getattr(engine, "font_sub", None)) + 20)
        label_x = fx + key_w + 12
        label_w = safe_measure(engine, label, getattr(engine, "font_sub", None))
        if fx + key_w + 12 + label_w > limit and items:
            break
        items.append((key, label, fx, key_w, label_x))
        fx = label_x + label_w + gap
    return items
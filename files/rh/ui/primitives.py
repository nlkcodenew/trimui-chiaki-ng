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

_sdl = ctypes.CDLL("SDL2", mode=ctypes.RTLD_GLOBAL) if sys.platform == "win32" else ctypes.CDLL(None)

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
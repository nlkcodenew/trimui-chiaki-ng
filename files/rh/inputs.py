# -*- coding: utf-8 -*-
"""Bien doi su kien SDL thanh virtual action (btn_a, btn_b, btn_up, ...).

Ban 0.2.0 da bind day du qua pysdl2:
    - SDL_CONTROLLERBUTTONDOWN/UP: A/B/X/Y/START/SELECT/L1/R1/L3/R3 + D-Pad
    - SDL_CONTROLLERAXISMOTION: left_x/left_y/right_x/right_y + L2/R2 analog
    - SDL_KEYDOWN/UP: fallback khi khong co gamepad (test tren PC)
    - SDL_QUIT: thoat app

Profile mapping theo trimui: A=Btn 1, B=Btn 0, X=Btn 3, Y=Btn 2,
                            L1=Btn 4/6, R1=Btn 5/7, START=Btn 9,
                            Up=Hat 0/13, Down=Hat 1/14.

SDL_JOYSTICK/HAT duoc su dung khi khong co SDL_GameController (firmware cu).
"""

import os
import sys
import time

try:
    import sdl2
    SDL2_OK = True
except Exception:
    SDL2_OK = False

from .logger import get_logger

log = get_logger()


# Default profile cho Smart Pro S (1 controller, 2 axis, 11 button + 1 hat)
DEFAULT_JOY_PROFILE = {
    "name": "trimui",
    "btn_a": [1],
    "btn_b": [0],
    "btn_x": [3],
    "btn_y": [2],
    "btn_l1": [4, 6],
    "btn_r1": [5, 7],
    "btn_start": [9],
    "btn_select": [8],
    "hat_up": [11, 13],
    "hat_down": [12, 14],
    "hat_left": [13],
    "hat_right": [14],
}


class InputManager:
    """Bien doi SDL_Event thanh virtual action dict."""

    STATE_KEYS = (
        "btn_a", "btn_b", "btn_x", "btn_y",
        "btn_up", "btn_down", "btn_left", "btn_right",
        "btn_start", "btn_select",
        "btn_l1", "btn_r1", "btn_l2", "btn_r2",
        "btn_l3", "btn_r3",
        "axis_left_x", "axis_left_y",
        "axis_right_x", "axis_right_y",
        "quit", "any",
    )

    def __init__(self):
        self._state = {k: False for k in self.STATE_KEYS}
        self._edges = []
        self.controller = None
        self.controller_ax = {"left_x": 0, "left_y": 0, "right_x": 0, "right_y": 0}
        self.profile = dict(DEFAULT_JOY_PROFILE)

    def attach_controller(self, ctl):
        """Set GameController handle khi mo app."""
        self.controller = ctl
        log.info("input controller attached: %s", ctl)

    def set_state(self, key, value):
        if key not in self._state:
            return
        prev = self._state[key]
        self._state[key] = value
        if value and not prev:
            self._edges.append(key)

    def feed_event(self, event):
        """Nhan mot SDL_Event (ctypes struct) va cap nhat state."""
        if not SDL2_OK:
            return
        t = event.type
        if t == sdl2.SDL_QUIT:
            self.set_state("quit", True)
            return
        if t in (sdl2.SDL_CONTROLLERBUTTONDOWN, sdl2.SDL_CONTROLLERBUTTONUP):
            down = (t == sdl2.SDL_CONTROLLERBUTTONDOWN)
            cbtn = event.cbutton.button
            self._map_controller_button(cbtn, down)
            return
        if t == sdl2.SDL_CONTROLLERAXISMOTION:
            axis = event.caxis.axis
            val = event.caxis.value
            self._map_controller_axis(axis, val)
            return
        if t in (sdl2.SDL_KEYDOWN, sdl2.SDL_KEYUP):
            down = (t == sdl2.SDL_KEYDOWN)
            self._map_keyboard(event.key.keysym.scancode, down)
            return
        # Khi da mo GameController, SDL2 van phat SONG SONG su kien JOY* cho
        # cung mot lan bam nut. Neu xu ly ca hai luong, mot nut vat ly se sinh
        # 2 edge nguoc nhau; man Cai dat khi do doi gia tri thay vi thoat khi
        # bam B. Vi vay chi dung JOY* lam fallback khi khong co GameController
        # (firmware cu khong ho tro SDL_GameController).
        if self.controller is not None:
            return
        if t in (sdl2.SDL_JOYBUTTONDOWN, sdl2.SDL_JOYBUTTONUP):
            down = (t == sdl2.SDL_JOYBUTTONDOWN)
            self._map_joy_button(event.jbutton.button, down)
            return
        if t == sdl2.SDL_JOYHATMOTION:
            self._map_hat(event.jhat.value)
            return
        if t == sdl2.SDL_JOYAXISMOTION:
            axis = event.jaxis.axis
            val = event.jaxis.value
            if axis == 0:
                self._set_axis("left_x", val)
            elif axis == 1:
                self._set_axis("left_y", val)

    def _map_controller_button(self, cbtn, down):
        # SDL_GameControllerButton dung ten SDL_CONTROLLER_BUTTON_*. Ban
        # v0.2.3 nham thanh SDL_GAMECONTROLLER_BUTTON_* nen crash ngay lan
        # dau nguoi dung bam nut. Dung gia tri enum on dinh cua SDL2 de van
        # tuong thich voi cac ban PySDL2 khong export enum o package root.
        #
        # SDL2 dat ten nut theo layout Xbox (A=o Nam/south, B=o Dong/east,
        # X=o Tay/west, Y=o Bac/north). TrimUI Smart Pro S dung layout kieu
        # Nintendo: nut A vat ly o o Dong, nut B vat ly o o Nam. Nen phai dao
        # A<->B va X<->Y de virtual action trung voi nut in tren vo may, giong
        # RetroHub. Truoc v0.2.10 map de 0:btn_a/1:btn_b nen nut B vat ly bi
        # hieu thanh btn_a -> Cai dat doi gia tri thay vi thoat (P0).
        m = {
            0: "btn_b",
            1: "btn_a",
            2: "btn_y",
            3: "btn_x",
            4: "btn_select",
            6: "btn_start",
            7: "btn_l3",
            8: "btn_r3",
            9: "btn_l1",
            10: "btn_r1",
            11: "btn_up",
            12: "btn_down",
            13: "btn_left",
            14: "btn_right",
        }
        key = m.get(cbtn)
        if key:
            self.set_state(key, down)

    def _map_controller_axis(self, axis, value):
        # SDL_GameControllerAxis: LEFTX=0, LEFTY=1, RIGHTX=2, RIGHTY=3,
        # TRIGGERLEFT=4, TRIGGERRIGHT=5.
        if axis == 0:
            self._set_axis("left_x", value)
        elif axis == 1:
            self._set_axis("left_y", value)
        elif axis == 2:
            self._set_axis("right_x", value)
        elif axis == 3:
            self._set_axis("right_y", value)
        elif axis == 4:
            self.set_state("btn_l2", value > 8000)
        elif axis == 5:
            self.set_state("btn_r2", value > 8000)

    def _map_keyboard(self, scancode, down):
        m = {
            13: "btn_a",  # Enter
            40: "btn_a",  # KP Enter
            41: "btn_b",  # Escape
            44: "btn_start",  # Space
            42: "btn_select",  # Backspace
            82: "btn_up",
            81: "btn_down",
            80: "btn_left",
            79: "btn_right",
            30: "quit",  # Q
        }
        key = m.get(scancode)
        if key:
            self.set_state(key, down)

    def _map_joy_button(self, btn, down):
        prof = self.profile
        for action, ids in prof.items():
            if isinstance(ids, list) and btn in ids:
                self.set_state(action, down)
                return
        # Direct mapping
        if btn in (0,):
            self.set_state("btn_b", down)
        elif btn in (1,):
            self.set_state("btn_a", down)
        elif btn in (2,):
            self.set_state("btn_y", down)
        elif btn in (3,):
            self.set_state("btn_x", down)
        elif btn in (4, 6):
            self.set_state("btn_l1", down)
        elif btn in (5, 7):
            self.set_state("btn_r1", down)
        elif btn == 9:
            self.set_state("btn_start", down)
        elif btn == 8:
            self.set_state("btn_select", down)

    def _map_hat(self, val):
        self.set_state("btn_up", bool(val & 0x01))
        self.set_state("btn_right", bool(val & 0x02))
        self.set_state("btn_down", bool(val & 0x04))
        self.set_state("btn_left", bool(val & 0x08))

    def _set_axis(self, key, value):
        prev = self.controller_ax.get(key, 0)
        self.controller_ax[key] = value
        thresh = 8000
        if key == "left_x":
            self._state["axis_left_x"] = value
        elif key == "left_y":
            self._state["axis_left_y"] = value
        elif key == "right_x":
            self._state["axis_right_x"] = value
        elif key == "right_y":
            self._state["axis_right_y"] = value

    def poll(self):
        """Tra ve dict: edge-key=True (vua nhan), state-key=True (dang giu)."""
        out = {k: self._state[k] for k in self.STATE_KEYS}
        out["edges"] = list(self._edges)
        self._edges.clear()
        any_btn = any(out[k] for k in self.STATE_KEYS if k.startswith("btn_"))
        out["any"] = any_btn
        return out

    def reset(self):
        for k in self.STATE_KEYS:
            self._state[k] = False
        self._edges.clear()

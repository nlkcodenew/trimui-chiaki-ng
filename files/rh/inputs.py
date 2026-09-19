# -*- coding: utf-8 -*-
"""Bien doi su kien SDL thanh virtual action (btn_a, btn_b, btn_up, ...).

Ban 0.1.0 dung keyboard (ENTER, ESC, arrow) de test tren may tinh. Tren
Smart Pro S that se chuyen sang SDL GameController qua SDL_HINT_JOYSTICK.
"""

import os
import sys

if sys.platform == "linux":
    try:
        import sdl2  # noqa: F401  - pysdl2 vendored neu co
    except Exception:
        pass


class InputManager:
    def __init__(self):
        self._state = {
            "btn_a": False, "btn_b": False, "btn_x": False, "btn_y": False,
            "btn_up": False, "btn_down": False, "btn_left": False, "btn_right": False,
            "btn_start": False, "btn_select": False, "btn_l1": False, "btn_r1": False,
            "btn_l2": False, "btn_r2": False, "quit": False,
        }
        self._kbd_queue = []

    def feed_key(self, scancode):
        """scancode: SDL_Scancode. Mapping don gian cho ban 0.1.0."""
        if scancode in (13, 40):  # Return / KP_Enter -> A
            self._state["btn_a"] = True; self._kbd_queue.append("btn_a")
        elif scancode == 41:  # ESC -> B
            self._state["btn_b"] = True; self._kbd_queue.append("btn_b")
        elif scancode == 82:  # Up
            self._state["btn_up"] = True; self._kbd_queue.append("btn_up")
        elif scancode == 81:  # Down
            self._state["btn_down"] = True; self._kbd_queue.append("btn_down")
        elif scancode == 80:  # Left
            self._state["btn_left"] = True; self._kbd_queue.append("btn_left")
        elif scancode == 79:  # Right
            self._state["btn_right"] = True; self._kbd_queue.append("btn_right")
        elif scancode == 44:  # Space -> Start
            self._state["btn_start"] = True; self._kbd_queue.append("btn_start")
        elif scancode == 42:  # Backspace -> Select
            self._state["btn_select"] = True; self._kbd_queue.append("btn_select")
        elif scancode == 30:  # Q -> Quit
            self._state["quit"] = True; self._kbd_queue.append("quit")

    def feed_keyup(self, scancode):
        if scancode in (13, 40):
            self._state["btn_a"] = False
        elif scancode == 41:
            self._state["btn_b"] = False
        elif scancode == 82:
            self._state["btn_up"] = False
        elif scancode == 81:
            self._state["btn_down"] = False
        elif scancode == 80:
            self._state["btn_left"] = False
        elif scancode == 79:
            self._state["btn_right"] = False
        elif scancode == 44:
            self._state["btn_start"] = False
        elif scancode == 42:
            self._state["btn_select"] = False
        elif scancode == 30:
            self._state["quit"] = False

    def feed_button(self, button):
        if button == "a":
            self._state["btn_a"] = True; self._kbd_queue.append("btn_a")
        elif button == "b":
            self._state["btn_b"] = True; self._kbd_queue.append("btn_b")
        elif button == "up":
            self._state["btn_up"] = True; self._kbd_queue.append("btn_up")
        elif button == "down":
            self._state["btn_down"] = True; self._kbd_queue.append("btn_down")
        elif button == "left":
            self._state["btn_left"] = True; self._kbd_queue.append("btn_left")
        elif button == "right":
            self._state["btn_right"] = True; self._kbd_queue.append("btn_right")
        elif button == "start":
            self._state["btn_start"] = True; self._kbd_queue.append("btn_start")
        elif button == "select":
            self._state["btn_select"] = True; self._kbd_queue.append("btn_select")

    def feed_buttonup(self, button):
        if button == "a":
            self._state["btn_a"] = False
        elif button == "b":
            self._state["btn_b"] = False
        elif button == "up":
            self._state["btn_up"] = False
        elif button == "down":
            self._state["btn_down"] = False
        elif button == "left":
            self._state["btn_left"] = False
        elif button == "right":
            self._state["btn_right"] = False
        elif button == "start":
            self._state["btn_start"] = False
        elif button == "select":
            self._state["btn_select"] = False

    def poll(self):
        """Tra ve mot dict cac virtual action, moi action la True neu vua nhan.
        Caller nen reset _kbd_queue hoac goi poll() nhieu lan neu muon theo doi."""
        out = {k: False for k in self._state}
        out.update({k: True for k in self._kbd_queue})
        out["btn_a"] = self._state["btn_a"] or out["btn_a"]
        out["btn_b"] = self._state["btn_b"] or out["btn_b"]
        out["btn_up"] = self._state["btn_up"] or out["btn_up"]
        out["btn_down"] = self._state["btn_down"] or out["btn_down"]
        out["btn_left"] = self._state["btn_left"] or out["btn_left"]
        out["btn_right"] = self._state["btn_right"] or out["btn_right"]
        out["btn_start"] = self._state["btn_start"] or out["btn_start"]
        out["btn_select"] = self._state["btn_select"] or out["btn_select"]
        out["quit"] = self._state["quit"]
        self._kbd_queue.clear()
        return out

    def reset(self):
        for k in self._state:
            self._state[k] = False
        self._kbd_queue.clear()
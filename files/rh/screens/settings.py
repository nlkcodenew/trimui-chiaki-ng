# -*- coding: utf-8 -*-
"""Man hinh cai dat: video_resolution, fps, bitrate, audio_volume, auto_update."""

import os
import time
from .. import state
from ..i18n import tr
from .base import BaseScreen


class SettingsScreen(BaseScreen):
    ROWS = [
        ("video_resolution", ["360p", "540p", "720p"]),
        ("video_fps", [30, 60]),
        ("video_bitrate", [4000, 6000, 8000, 10000, 12000, 15000]),
        ("audio_volume", [0, 25, 50, 75, 100]),
        ("auto_update", [True, False]),
        ("language", ["VI", "EN"]),
    ]

    def __init__(self, engine=None):
        super().__init__(engine, "settings")
        self.selected = 0

    def get_header_title(self):
        return tr("settings")

    def get_footer_actions(self):
        return [("A", tr("ok")), ("B", tr("back"))]

    def handle_input(self, inputs):
        if inputs.get("btn_up"):
            self.selected = (self.selected - 1) % len(self.ROWS)
            return True
        if inputs.get("btn_down"):
            self.selected = (self.selected + 1) % len(self.ROWS)
            return True
        if inputs.get("btn_left"):
            self._change(-1)
            return True
        if inputs.get("btn_right"):
            self._change(1)
            return True
        if inputs.get("btn_a"):
            self._save()
            self.engine.pop_screen()
            return True
        if inputs.get("btn_b") or inputs.get("quit"):
            self.engine.pop_screen()
            return True
        return False

    def _change(self, delta):
        key, values = self.ROWS[self.selected]
        cur = getattr(state, key)
        if cur in values:
            idx = values.index(cur)
        else:
            idx = 0
        idx = (idx + delta) % len(values)
        setattr(state, key, values[idx])

    def _save(self):
        state.save_settings()

    def render(self, engine):
        engine.fill_rect(0, 64, engine.screen_w, engine.screen_h - 120, 13, 17, 28, 255)
        y = 160
        for i, (key, values) in enumerate(self.ROWS):
            cur = getattr(state, key)
            label = tr(key)
            value = str(cur)
            col = (0, 230, 150) if i == self.selected else (40, 60, 90)
            engine.fill_rect(40, y, engine.screen_w - 80, 70, col[0], col[1], col[2], 240)
            engine.draw_text(label, engine.font_title, 60, y + 8, 255, 255, 255)
            engine.draw_text(value, engine.font_sub, engine.screen_w - 120, y + 22,
                             220, 225, 235)
            y += 80
# -*- coding: utf-8 -*-
"""Man hinh cai dat: video_resolution, fps, bitrate, audio_volume, auto_update.

Luu settings.json atomic qua state.save_settings(). LOG toggle cung duoc cap
nhat level logger ngay lap tuc.
"""

import os
import sys
import time
from .. import state
from ..i18n import tr
from ..logger import get_logger
from .base import BaseScreen

log = get_logger()


class SettingsScreen(BaseScreen):
    def __init__(self, engine=None):
        super().__init__(engine, "settings")
        self.rows = [
            ("video_resolution", ["360p", "540p", "720p"], self._set_resolution),
            ("video_fps", [30, 60], self._set_fps),
            ("video_bitrate", [4000, 6000, 8000, 10000, 12000, 15000], self._set_bitrate),
            ("audio_volume", [0, 25, 50, 75, 100], None),
            ("auto_update", [True, False], None),
            ("enable_logging", [True, False], self._set_logging),
            ("language", ["VI", "EN"], self._set_lang),
        ]
        self.selected = 0

    def get_header_title(self):
        return tr("settings")

    def get_footer_actions(self):
        return [("A", tr("ok")), ("B", tr("back"))]

    def _set_resolution(self, value):
        log.info("setting video_resolution=%s", value)

    def _set_fps(self, value):
        log.info("setting video_fps=%d", value)

    def _set_bitrate(self, value):
        log.info("setting video_bitrate=%d", value)

    def _set_logging(self, value):
        from ..logger import set_debug_level
        set_debug_level(value)
        log.info("logging level toggled: %s", value)

    def _set_lang(self, value):
        log.info("setting language=%s", value)

    def handle_input(self, inputs):
        if inputs.get("edges", []):
            if "btn_up" in inputs["edges"]:
                self.selected = (self.selected - 1) % len(self.rows)
                return True
            if "btn_down" in inputs["edges"]:
                self.selected = (self.selected + 1) % len(self.rows)
                return True
            if "btn_left" in inputs["edges"]:
                self._change(-1)
                return True
            if "btn_right" in inputs["edges"]:
                self._change(1)
                return True
            if "btn_a" in inputs["edges"]:
                self._save()
                self.engine.pop_screen()
                return True
            if "btn_b" in inputs["edges"] or "quit" in inputs["edges"]:
                self.engine.pop_screen()
                return True
        return False

    def _change(self, delta):
        key, values, callback = self.rows[self.selected]
        cur = getattr(state, key)
        try:
            idx = values.index(cur)
        except ValueError:
            idx = 0
        idx = (idx + delta) % len(values)
        setattr(state, key, values[idx])
        if callback:
            try:
                callback(values[idx])
            except Exception as exc:
                log.warning("setting callback %s failed: %s", key, exc)

    def _save(self):
        state.save_settings()
        log.info("settings saved: res=%s fps=%d bitrate=%d vol=%d auto=%s log=%s lang=%s",
                 state.video_resolution, state.video_fps, state.video_bitrate,
                 state.audio_volume, state.auto_update, state.enable_logging,
                 state.current_lang)

    def render(self, engine):
        engine.fill_rect(0, 64, engine.screen_w, engine.screen_h - 120, 13, 17, 28, 255)
        y = 160
        for i, (key, values, _) in enumerate(self.rows):
            cur = getattr(state, key)
            label = tr(key)
            value = str(cur)
            col = (0, 230, 150) if i == self.selected else (40, 60, 90)
            engine.fill_rect(40, y, engine.screen_w - 80, 70, col[0], col[1], col[2], 240)
            engine.draw_text(label, engine.font_title, 60, y + 8, 255, 255, 255)
            engine.draw_text(value, engine.font_sub, engine.screen_w - 120, y + 22,
                             220, 225, 235)
            y += 80
        if engine.font_sub:
            engine.draw_text(tr("profile_summary") % (
                state.video_resolution, state.video_fps, state.video_bitrate),
                engine.font_sub, 40, engine.screen_h - 140, 180, 195, 215)
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
from ..logger import clear_runtime_logs, get_logger, runtime_log_size
from .base import BaseScreen

log = get_logger()


class SettingsScreen(BaseScreen):
    LABEL_KEYS = {
        "current_lang": "language",
    }

    def __init__(self, engine=None):
        super().__init__(engine, "settings")
        self.rows = [
            ("video_resolution", list(state.VIDEO_RESOLUTIONS), self._set_resolution),
            ("video_fps", [30, 60], self._set_fps),
            ("video_bitrate", [3000, 4000, 6000, 8000, 10000, 12000, 15000], self._set_bitrate),
            ("audio_volume", [0, 25, 50, 75, 100], None),
            ("auto_update", [True, False], None),
            ("auto_upload_logs", [True, False], None),
            ("enable_logging", [True, False], self._set_logging),
            ("current_lang", ["VI", "EN"], self._set_lang),
            ("clear_logs", None, None),
            ("back", None, None),
        ]
        self.selected = 0

    def get_header_title(self):
        return tr("settings")

    def get_footer_actions(self):
        key = self.rows[self.selected][0] if 0 <= self.selected < len(self.rows) else ""
        if key == "back":
            return [("A", tr("back")), ("B", tr("back"))]
        if self._is_action_row():
            return [("A", tr("select")), ("B", tr("back"))]
        return [("A", tr("change")), ("B", tr("back"))]

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

    def _is_back_row(self):
        return 0 <= self.selected < len(self.rows) and self.rows[self.selected][0] == "back"

    def _is_action_row(self):
        return 0 <= self.selected < len(self.rows) and self.rows[self.selected][1] is None

    def _clear_logs(self):
        ok, reason, removed_bytes = clear_runtime_logs(protect_pending=True)
        if ok:
            message = tr("clear_logs_done") % max(1, int(removed_bytes / 1024))
        elif reason == "pending":
            message = tr("clear_logs_pending")
        else:
            message = tr("clear_logs_failed")
        self.engine.open_modal("info", {
            "title": tr("clear_logs"),
            "message": message,
        })

    def _confirm_clear_logs(self):
        if runtime_log_size() <= 0:
            self.engine.open_modal("info", {
                "title": tr("clear_logs"),
                "message": tr("clear_logs_empty"),
            })
            return
        self.engine.open_modal("confirm", {
            "title": tr("clear_logs"),
            "message": tr("clear_logs_confirm"),
            "on_yes": self._clear_logs,
        })

    def handle_input(self, inputs):
        if inputs.get("edges", []):
            if "btn_up" in inputs["edges"]:
                self.selected = (self.selected - 1) % len(self.rows)
                return True
            if "btn_down" in inputs["edges"]:
                self.selected = (self.selected + 1) % len(self.rows)
                return True
            edges = inputs["edges"]
            # B (hoac quit) luon chi thoat, khong bao gio doi gia tri. Kiem tra
            # truoc A de neu ca hai edge den cung khung hinh (nut bam nhanh,
            # su kien lap) thi thoat van thang.
            if "btn_b" in edges or "quit" in edges:
                self.engine.pop_screen()
                return True
            if self._is_back_row():
                if any(k in edges for k in ("btn_a", "btn_left", "btn_right")):
                    self.engine.pop_screen()
                    return True
                return False
            if self._is_action_row():
                if "btn_a" in edges:
                    self._confirm_clear_logs()
                    return True
                return False
            if "btn_left" in edges:
                self._change(-1)
                self._save()
                return True
            if "btn_right" in edges:
                self._change(1)
                self._save()
                return True
            if "btn_a" in edges:
                self._change(1)
                self._save()
                return True
        return False

    def _change(self, delta):
        if self._is_back_row():
            return
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
                try:
                    from ..log_uploader import queue_diagnostic
                    queue_diagnostic("settings_callback_failed")
                except Exception as report_exc:
                    log.warning("cannot queue settings diagnostic: %s", report_exc)

    def _save(self):
        saved = state.save_settings()
        if not saved:
            log.error("settings save failed")
            try:
                from ..log_uploader import queue_diagnostic
                queue_diagnostic("settings_save_failed")
            except Exception as exc:
                log.warning("cannot queue settings save diagnostic: %s", exc)
        else:
            log.info("settings saved: res=%s fps=%d bitrate=%d vol=%d auto=%s log=%s lang=%s",
                     state.video_resolution, state.video_fps, state.video_bitrate,
                     state.audio_volume, state.auto_update, state.enable_logging,
                     state.current_lang)

    def render(self, engine):
        engine.fill_rect(0, 64, engine.screen_w, engine.screen_h - 120, 13, 17, 28, 255)
        visible = 6
        first = max(0, min(self.selected - (visible - 2), max(0, len(self.rows) - visible)))
        y = 100
        for i in range(first, min(len(self.rows), first + visible)):
            key, values, _ = self.rows[i]
            if values is None:
                label = tr(key)
                value = "→"
            else:
                cur = getattr(state, key)
                label = tr(self.LABEL_KEYS.get(key, key))
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

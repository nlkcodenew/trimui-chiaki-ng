# -*- coding: utf-8 -*-
"""Brick Pro dual-stick Bluetooth gamepad screen for stock OS."""

from ..bluetooth_gamepad import BluetoothGamepadSession, REPORT_FILE
from ..i18n import tr
from ..logger import get_logger
from .. import state
from .base import BaseScreen

log = get_logger()

# Profile bit nut cho backend (co --profile). "ps" theo vi tri, da do tren
# Android; "labels" theo ten in tren vo, cach cu truoc v0.3.33.
PROFILES = ("ps", "labels")


class BluetoothScreen(BaseScreen):
    def __init__(self, engine=None):
        super().__init__(engine, "bluetooth")
        self.session = BluetoothGamepadSession()
        self.previous_status = ""

    def _profile_index(self):
        try:
            return list(PROFILES).index(state.gamepad_profile)
        except ValueError:
            return 0

    def _cycle_profile(self, delta):
        index = (self._profile_index() + delta) % len(PROFILES)
        state.gamepad_profile = PROFILES[index]
        state.save_settings()
        log.info("bluetooth profile -> %s", state.gamepad_profile)

    def _open_button_test(self):
        # Thu nut can doc /dev/input, nen khong dua chung voi phien Bluetooth:
        # backend giu adapter va tay cam, va nguoi dung se khong bi phuc tap.
        if self.session.running():
            log.info("button test: dung phien Bluetooth truoc")
            self.session.stop()
        self.engine.push_screen("button_test")

    def on_enter(self, params=None):
        self.previous_status = ""
        self.session.start_check()

    def on_exit(self):
        self.session.close()

    def get_header_title(self):
        return tr("bluetooth_title")

    def get_footer_actions(self):
        if self.session.running():
            # B la nut can thu tren dien thoai, nen khong duoc dung de dung
            # phien. Giu MENU 2 giay de dung (guard doc truc tiep evdev).
            return [("MENU", tr("bluetooth_stop_hold"))]
        return [("A", tr("bluetooth_start")), ("X", tr("bluetooth_button_test")),
                ("B", tr("back"))]

    def handle_input(self, inputs):
        edges = inputs.get("edges", []) if inputs else []
        if "btn_b" in edges:
            # B chi lui man hinh khi phien chua chay. Dang chay ma bam B thi
            # bo qua: do la nut test tren dien thoai, khong phai lenh dung.
            if self.session.running():
                return False
            self.engine.pop_screen()
            return True
        if "quit" in edges:
            # Quit chi tu phim Q/SDL_QUIT, khong phai nut tay cam: giu lam
            # duong lui khan cap.
            if self.session.running():
                self.session.stop()
            else:
                self.engine.pop_screen()
            return True
        if "btn_x" in edges and not self.session.running():
            self._open_button_test()
            return True
        if "btn_a" in edges and not self.session.running():
            if not self.session.start():
                log.warning("Bluetooth gamepad start refused")
            return True
        # Doi profile bang Trai/Phai khi phien chua chay. Dang chay thi bo
        # qua de khong vo tinh doi layout giua phien.
        if not self.session.running():
            if "btn_right" in edges:
                self._cycle_profile(1)
                return True
            if "btn_left" in edges:
                self._cycle_profile(-1)
                return True
        return False

    def update(self, dt):
        self.session.poll()
        status = self.session.status()
        if status != self.previous_status:
            log.info("Bluetooth UI status=%s", status)
            self.previous_status = status

    def _status_text(self):
        if self.session.checking:
            return tr("bluetooth_checking")
        status = self.session.status()
        if status.startswith("backend_error_"):
            return tr("bluetooth_status_error") % status.rsplit("_", 1)[-1]
        if status == "error":
            return tr("bluetooth_status_error") % (self.session.last_exit_code or "?")
        if status != "idle":
            key = "bluetooth_status_" + status
            translated = tr(key)
            if translated != key:
                return translated
        check = self.session.check_result
        if check:
            check_key = "bluetooth_check_" + check.lower()
            translated = tr(check_key)
            if translated != check_key:
                return translated
        return tr("bluetooth_status_idle")

    def render(self, engine):
        engine.fill_rect(0, 64, engine.screen_w, engine.screen_h - 120,
                         13, 17, 28, 255)
        engine.draw_text(tr("bluetooth_subtitle"), engine.font_title,
                         48, 92, 255, 255, 255)
        engine.draw_text(self._status_text(), engine.font_sub,
                         48, 154, 0, 230, 150)
        lines = [
            tr("bluetooth_step_1"),
            tr("bluetooth_step_2"),
            tr("bluetooth_step_3"),
            tr("bluetooth_controls"),
            tr("bluetooth_exit_help"),
        ]
        y = 210
        for line in lines:
            engine.draw_text(line, engine.font_sub, 54, y, 220, 225, 235)
            y += 48
        profile_name = tr("bluetooth_profile_" + PROFILES[self._profile_index()])
        engine.draw_text(tr("bluetooth_profile") % profile_name,
                         engine.font_sub, 54, 452, 240, 220, 120)
        engine.draw_text(tr("bluetooth_profile_hint"),
                         engine.font_sub, 54, 484, 150, 165, 185)
        engine.draw_text(tr("bluetooth_log") % REPORT_FILE,
                         engine.font_sub, 54, engine.screen_h - 118,
                         150, 165, 185)

# -*- coding: utf-8 -*-
"""Brick Pro dual-stick Bluetooth gamepad screen for stock OS."""

from ..bluetooth_gamepad import BluetoothGamepadSession, REPORT_FILE
from ..i18n import tr
from ..logger import get_logger
from .base import BaseScreen

log = get_logger()


class BluetoothScreen(BaseScreen):
    def __init__(self, engine=None):
        super().__init__(engine, "bluetooth")
        self.session = BluetoothGamepadSession()
        self.previous_status = ""

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
            return [("B", tr("bluetooth_stop"))]
        return [("A", tr("bluetooth_start")), ("X", tr("bluetooth_button_test")),
                ("B", tr("back"))]

    def handle_input(self, inputs):
        edges = inputs.get("edges", []) if inputs else []
        if "btn_b" in edges or "quit" in edges:
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
        engine.draw_text(tr("bluetooth_log") % REPORT_FILE,
                         engine.font_sub, 54, engine.screen_h - 118,
                         150, 165, 185)

# -*- coding: utf-8 -*-
"""Man hinh GHI NUT: ghi lai tu lan bam, khong doan ma phim.

Vay do chinh: firmware Stock OS co the bao mot lan bam ra nhieu ma phim Linux
cung luc. Man hinh cu hon "hop nhan" tung nut da ghi ban do sai va lam vai nut
sang len cung luc tren dien thoai. O day app chi ghi lai:

1. Bam nut theo thu tu tu 1 den het, moi nut mot lan.
2. Man hinh hien so thu tu vua bam va ma phim tu kernel bao ra, moi lan chi
   hien mot dong trong danh sach.
3. Giu MENU 2 giay de luu file BrickButtons.log va thoat, roi bao lai thu tu
   da bam.

Ban do chi duoc sinh tu log do, khong con gi doan trong app.
"""

import time

from ..gamepad_map import BUTTON_LABELS
from ..i18n import tr
from ..logger import get_logger
from ..ui.primitives import ellipsis_text, theme
from .. import state
from ..pad_probe import (PadProbe, RECORD_LIMIT, append_note, clear_log,
                         find_gamepad, format_entry, write_log)
from ..paths import APP_DIR
from .base import BaseScreen

log = get_logger()

COLORS = {
    "a": (0, 220, 140), "b": (220, 70, 90), "x": (70, 140, 240), "y": (240, 210, 70),
    "l1": (180, 120, 240), "r1": (240, 150, 90), "l3": (120, 220, 220),
    "r3": (240, 120, 200), "select": (150, 160, 190), "start": (200, 200, 210),
    "l2": (120, 150, 200), "r2": (200, 150, 120),
}

# Danh sach nut de nguoi dung doi chieu khi bao lai thu tu. Chi ghi nhung nut
# co MA PHIM that: L2/R2 khong co, chung la cam bien analog (axis 2/5), nen
# bam chung se khong bao gi ca. Truoc day chung co trong danh sach va lam
# moi thu tu lech sau R1.
#
# MENU cung vang khong o day: no la cua thoat, khong phai nut can thu.
DEFAULT_ORDER = ["a", "b", "x", "y", "l1", "r1", "l3", "r3",
                 "select", "start"]


class ButtonTestScreen(BaseScreen):
    def __init__(self, engine=None):
        super().__init__(engine, "button_test")
        self.probe = None
        self.device_path = ""
        self.device_name = ""
        self.entries = []
        self.last = None
        self.saved_path = ""
        self.error = ""
        self.clock = time.time

    # ---- vong doi ----

    def on_enter(self, params=None):
        path, name = find_gamepad()
        if not path:
            self.error = tr("button_test_no_device")
            log.warning("button test: khong tim thay gamepad")
            return
        self.device_path = path
        self.device_name = name
        self.probe = PadProbe(path)
        if not self.probe.open():
            self.error = tr("button_test_open_failed") % path
            return
        self.entries = []
        self.last = None
        self.saved_path = ""
        clear_log()
        log.info("button test: ghi nut tren %s (%s)", path, name)

    def on_exit(self):
        if self.probe:
            # Lay lai danh sach tu probe truoc khi ghi, vi ``reported`` moi la
            # noi dung duy nhat va co the da bo phim thoat.
            self.entries = list(self.probe.reported)
            # Ghi lai ca phien du chua bam A, de khong mat du lieu.
            if self.entries and not self.saved_path:
                write_log(self.entries)
                append_note("device=%s path=%s"
                            % (self.device_name, self.device_path))
            self.probe.close()
            self.probe = None

    def get_header_title(self):
        return tr("button_test_title")

    def get_footer_actions(self):
        # A cung la nut can thu, nen khong duoc lam nut luu. MENU giu 2 giay
        # vua luu log vua thoat; START+SELECT la duong du phong.
        return [("MENU", tr("button_test_save_exit"))]

    # ---- input ----

    def handle_input(self, inputs):
        # A va B deu la nut can thu, nen khong dung lam phim dieu huong. Chi can
        # giu MENU (hoac START+SELECT) de thoat, xu ly o update() khi doc evdev.
        # `quit` van duoc giu la duong lui ve an toan.
        if not inputs:
            return False
        return bool(inputs.get("edges") and "quit" in inputs["edges"])

    # ---- ghi ----

    def update(self, dt):
        if not self.probe:
            return
        for entry in self.probe.poll():
            log.info("button test: %s", format_entry(entry))
        # ``reported`` la noi dung duy nhat. No boc phim thoat ra khoi danh
        # sach, nen doc o day moi dam bao dong do khong bao loi vao log.
        self.entries = list(self.probe.reported)
        self.last = self.entries[-1] if self.entries else None
        if len(self.entries) > RECORD_LIMIT:
            self._save(limit_reached=True)
        if self.probe.exit_held():
            log.info("button test: thoat do giu MENU/START+SELECT")
            self._save()
            self.engine.pop_screen()

    def _save(self, limit_reached=False):
        if not self.entries:
            return
        path = write_log(self.entries)
        if not path:
            self.error = tr("button_test_save_failed")
            return
        self.saved_path = path
        note = tr("button_test_note") % (len(self.entries), len(self.entries))
        if limit_reached:
            note += " " + tr("button_test_limit")
        append_note(note)
        append_note("device=%s path=%s" % (self.device_name, self.device_path))
        append_note("held buttons are one press; codes= lists repeats and noise")
        multi = sum(1 for e in self.entries if len(e["keys"]) > 1)
        burst = sum(1 for e in self.entries
                    if [c for c in e.get("codes", []) if c not in e["keys"]])
        if multi or burst:
            append_note("%d press(es) with several keys, %d with extra codes"
                        % (multi, burst))
        log.info("button test: %s", note)

    # ---- render ----

    def render(self, engine):
        c = theme(state.theme)
        engine.fill_rect(0, 64, engine.screen_w, engine.screen_h - 120,
                         *c["bg"], 255)

        if not self.device_path:
            engine.draw_text(tr("button_test_subtitle"), engine.font_title,
                             40, 92, *c["text"])
            engine.draw_text(self.error or tr("button_test_no_device"),
                             engine.font_sub, 40, 170, *c["err"])
            return

        engine.draw_text(
            ellipsis_text(engine, self.device_name or self.device_path,
                          engine.font_sub, engine.screen_w - 80),
            engine.font_sub, 40, 86, *c["muted"])
        engine.draw_text(tr("button_test_count") % len(self.entries),
                         engine.font_big, 40, 120, *c["accent"])
        engine.draw_text(tr("button_test_hint"), engine.font_sub,
                         40, 190, *c["muted"])
        engine.draw_text(tr("button_test_exit_hint"), engine.font_sub,
                         40, 222, *c["warn"])

        if self.last:
            engine.draw_text(tr("button_test_last"), engine.font_sub,
                             40, 272, *c["gold"])
            engine.draw_text(
                ellipsis_text(engine, format_entry(self.last),
                              engine.font_sub, engine.screen_w - 80),
                engine.font_sub, 40, 310, *c["text"])

        self._render_list(engine)
        self._render_order(engine)

        if self.saved_path:
            engine.draw_text(tr("button_test_saved_ok"), engine.font_sub,
                             40, engine.screen_h - 152, *c["accent"])
        if self.error:
            engine.draw_text(self.error, engine.font_sub, 40, 300, *c["err"])
        engine.draw_text(
            ellipsis_text(engine, tr("button_test_device") % self.device_path,
                          engine.font_sub, engine.screen_w - 80),
            engine.font_sub, 40, engine.screen_h - 118, *c["faint"])

    def _render_list(self, engine):
        c = theme(state.theme)
        if not self.entries:
            engine.draw_text(tr("button_test_empty"), engine.font_sub,
                             40, 348, *c["faint"])
            return
        # Lan bam cuoi da in rieng o dong "Vua bam" phia tren. Danh sach chi
        # lay 4 lan truoc do (348..438) de khong de len khoi thu tu (466).
        history = self.entries[-5:-1] if len(self.entries) > 1 else []
        if not history:
            return
        y = 348
        for entry in history:
            burst = [code for code in entry.get("codes", [])
                     if code not in entry["keys"]]
            if burst:
                # Firmware phat them ma trong khoang giu: chinh la nguon gay
                # ban do sai truoc day.
                color = c["warn"]
            elif len(entry["keys"]) > 1:
                color = c["err"]
            else:
                color = c["text"]
            engine.draw_text(
                ellipsis_text(engine, format_entry(entry), engine.font_sub,
                              engine.screen_w - 80),
                engine.font_sub, 40, y, *color)
            y += 30
        hidden = len(self.entries) - len(history) - 1
        if hidden > 0:
            engine.draw_text(tr("button_test_more") % hidden,
                             engine.font_sub, 40, y, *c["faint"])

    def _render_order(self, engine):
        engine.draw_text(tr("button_test_analog_note"), engine.font_sub,
                         40, engine.screen_h - 254, 120, 132, 150)
        engine.draw_text(tr("button_test_order"), engine.font_sub,
                         40, engine.screen_h - 228, 150, 165, 185)
        x = 40
        y = engine.screen_h - 198
        for index, name in enumerate(DEFAULT_ORDER):
            label = BUTTON_LABELS.get(name, name.upper())
            color = COLORS.get(name, (170, 180, 200))
            engine.draw_text("%d.%s" % (index + 1, label), engine.font_sub,
                             x, y, color[0], color[1], color[2])
            x += 110
            if x > engine.screen_w - 130:
                x = 40
                y += 28




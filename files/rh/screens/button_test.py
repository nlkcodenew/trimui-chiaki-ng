# -*- coding: utf-8 -*-
"""Man hinh THU BUT: xac nhan ma phim that cu tung nut tren Brick Pro.

Van de: firmware Stock OS day ma phim Linux cua mot so nut o vung 304..320 nhung
khong dung thu tu chuan, nen L3/R3 va cac nut phia duoi vo may co the khong
bao toi dien thoai. Man hinh nay hien thi ma phim that moi khi ban, nguoi dung
an nut theo thu tu, va luu ket qua vao bluetooth-map.json.

Hai nguyen tac lam man hinh nay dung:

1. Mot lan ban chi gan MOT nut. Sau khi gan xong phai tha het nut truoc khi
   nhan buoc sau, va ma phim da gan cho nut nao thi khong bao gio cho nut khac.
2. A va B cung la nut can thu, nen khong dung chung lam phim dieu huong khi
   dang o giua phien thu. Dieu huong dung D-pad, thu A/B chi dung o man hinh
   tom tat sau khi thu xong.
"""

import time
from ..gamepad_map import (BUTTON_LABELS, DEFAULT_BUTTONS, EV_KEY, PadReader,
                           duplicate_buttons, find_gamepad, is_gamepad_key,
                           load_map, save_map)
from ..i18n import tr
from ..logger import get_logger
from ..paths import APP_DIR
from .base import BaseScreen

log = get_logger()

# Cac nut se hoi lan luot. "mode" khong bat buoc: nhieu dong may khong co.
ASK_ORDER = ["a", "b", "x", "y", "l1", "r1", "l3", "r3", "select", "start"]

COLORS = {
    "a": (0, 220, 140), "b": (220, 70, 90), "x": (70, 140, 240), "y": (240, 210, 70),
    "l1": (180, 120, 240), "r1": (240, 150, 90), "l3": (120, 220, 220),
    "r3": (240, 120, 200), "select": (150, 160, 190), "start": (200, 200, 210),
}

# Giu D-pad trai hoac phai de thoat khong luu.
HOLD_EXIT = 1.5

HAT_X = "abs16"
HAT_Y = "abs17"


class ButtonTestScreen(BaseScreen):
    def __init__(self, engine=None):
        super().__init__(engine, "button_test")
        self.reader = None
        self.device_path = ""
        self.device_name = ""
        self.buttons = dict(DEFAULT_BUTTONS)
        self.axes = {}
        self.step = 0
        self.keys = {}
        self.hat = {HAT_X: 0, HAT_Y: 0}
        self.consumed = set()
        self.wait_release = False
        self.hat_prev = 0
        self.hat_exit_since = 0.0
        self.flash = ""
        self.flash_until = 0.0
        self.finished = False
        self.error = ""
        # Thay cho phep test dieu khong phai vao time.time().
        self.clock = time.time

    # ---- vong doi ----

    def on_enter(self, params=None):
        self.buttons, self.axes, error = load_map(APP_DIR)
        self.error = tr("button_test_map_broken") % error if error else ""
        path, name = find_gamepad()
        if not path:
            self.error = self.error or tr("button_test_no_device")
            log.warning("button test: khong tim thay gamepad")
            return
        self.device_path = path
        self.device_name = name
        self.reader = PadReader(path)
        if not self.reader.open():
            self.error = tr("button_test_open_failed") % path
            return
        self._restart()
        log.info("button test: bat dau tren %s (%s)", path, name)

    def _restart(self):
        self.step = 0
        self.finished = False
        self.keys = {}
        self.hat = {HAT_X: 0, HAT_Y: 0}
        self.consumed = set()
        self.wait_release = False
        self.hat_prev = 0
        self.hat_exit_since = 0.0
        self.flash = ""
        self.flash_until = 0.0

    def on_exit(self):
        if self.reader:
            self.reader.close()
            self.reader = None

    def get_header_title(self):
        return tr("button_test_title")

    def get_footer_actions(self):
        if self.finished:
            return [("A", tr("button_test_save")), ("B", tr("button_test_restart"))]
        return [("D-PAD", tr("button_test_nav"))]

    # ---- input ----

    def handle_input(self, inputs):
        # A va B la nut can thu, nen khi dang thu chi dung D-pad dieu huong.
        # Neu A/B bi dung o day, nguoi dung an nut duoc yeu cau lai bi hieu
        # nham la bo qua hoac lui lai.
        if self.finished and inputs:
            edges = inputs.get("edges", [])
            if "btn_a" in edges:
                self._save()
                return True
            if "btn_b" in edges:
                self._restart()
                return True
        return False

    # ---- doc input that ----

    def update(self, dt):
        if not self.reader:
            return
        for kind, code, value in self.reader.poll():
            if kind == EV_KEY:
                if value == 0:
                    self.keys.pop(code, None)
                else:
                    self.keys[code] = value
            elif kind == 3:
                # ABS: chi giu lai hat switch, phan con lai khong can o day.
                if code in (16, 17):
                    self.hat[HAT_X if code == 16 else HAT_Y] = value

        if not self.keys:
            self.wait_release = False

        if self.finished:
            self._check_hat_exit()
            return

        self._check_hat_exit()
        self._check_hat_nav()
        if self.wait_release:
            return
        self._accept_press()

    def _check_hat_exit(self):
        """Giu D-pad sang ben de thoat khong luu.

        ABS_HAT0X la trai/phai, ABS_HAT0Y la len/xuong, nen phai dung truc X.
        """
        if abs(self.hat.get(HAT_X, 0)) != 1:
            self.hat_exit_since = 0.0
            return
        now = self.clock()
        if not self.hat_exit_since:
            self.hat_exit_since = now
            return
        if now - self.hat_exit_since >= HOLD_EXIT:
            self.hat_exit_since = 0.0
            log.info("button test: thoat khong luu do giu D-pad")
            self.engine.pop_screen()

    def _check_hat_nav(self):
        """D-pad len bo qua buoc, D-pad xuong lui mot buoc.

        Canh le trai nen khong dung A/B: A va B cung la nut dang duoc thu.
        """
        now = self.hat.get(HAT_Y, 0)
        if now != self.hat_prev:
            self.hat_exit_since = 0.0
            previous, self.hat_prev = self.hat_prev, now
            if now < 0 and previous >= 0:
                log.info("button test: bo qua %s", self._current())
                self.step += 1
                self._maybe_finish()
            elif now > 0 and previous <= 0 and self.step > 0:
                self.step -= 1
                self.flash = tr("button_test_back_step")
                self.flash_until = self.clock() + 2
                log.info("button test: lui ve buoc %s", self._current())

    def _accept_press(self):
        for code in sorted(self.keys):
            if not is_gamepad_key(code):
                continue
            if code in self.consumed:
                # Ma nay da thuoc ve nut khac. Gan lai se lam nhieu nut sang
                # len cung luc tren dien thoai, nen bo qua.
                continue
            self._accept(code)
            return

    # ---- logic ----

    def _current(self):
        if self.step >= len(ASK_ORDER):
            return ""
        return ASK_ORDER[self.step]

    def _accept(self, code):
        name = self._current()
        if not name:
            return
        previous = self.buttons.get(name)
        self.buttons[name] = code
        self.consumed.add(code)
        self.wait_release = True
        self.flash = tr("button_test_got") % (BUTTON_LABELS.get(name, name), code)
        self.flash_until = self.clock() + 2.5
        log.info("button test: %s -> %d (truoc %s)", name, code, previous)
        self.step += 1
        self._maybe_finish()

    def _maybe_finish(self):
        if self.step < len(ASK_ORDER):
            return
        self.finished = True
        duplicates = duplicate_buttons(self.buttons, ASK_ORDER)
        if duplicates:
            names = ", ".join("%s=%s=%d" % pair for pair in duplicates)
            log.warning("button test: van con ma trung: %s", names)
        log.info("button test: het cac buoc. A de luu, B de lam lai.")

    def _save(self):
        duplicates = duplicate_buttons(self.buttons, ASK_ORDER)
        if duplicates:
            names = ", ".join("%s=%s=%d" % pair for pair in duplicates)
            self.flash = tr("button_test_duplicate") % names
            self.flash_until = self.clock() + 8
            log.error("button test: khong luu vi co ma trung: %s", names)
            return
        try:
            path = save_map(APP_DIR, self.buttons, self.axes)
        except OSError as exc:
            log.error("button test: khong luu duoc: %s", exc)
            self.error = tr("button_test_save_failed") % exc
            return
        changed = [name for name in ASK_ORDER
                   if self.buttons.get(name) != DEFAULT_BUTTONS.get(name)]
        self.flash = tr("button_test_saved") % (len(changed), path)
        self.flash_until = self.clock() + 6
        log.info("button test: da luu, %d nut khac mac dinh: %s", len(changed), changed)
        self.engine.pop_screen()

    # ---- render ----

    def render(self, engine):
        engine.fill_rect(0, 64, engine.screen_w, engine.screen_h - 120, 13, 17, 28, 255)

        if not self.device_path:
            engine.draw_text(tr("button_test_subtitle"), engine.font_title,
                             40, 92, 255, 255, 255)
            engine.draw_text(self.error or tr("button_test_no_device"),
                             engine.font_sub, 40, 170, 255, 140, 120)
            return

        engine.draw_text(self.device_name or self.device_path, engine.font_sub,
                         40, 86, 150, 165, 190)

        if self.finished:
            self._render_summary(engine)
        else:
            self._render_prompt(engine)
        self._render_live(engine)
        self._render_pad(engine)

        if self.flash and self.clock() < self.flash_until:
            engine.draw_text(self.flash, engine.font_sub, 40,
                             engine.screen_h - 190, 240, 220, 120)
        if self.error:
            engine.draw_text(self.error, engine.font_sub, 40, 300, 255, 140, 120)
        engine.draw_text(tr("button_test_device") % self.device_path,
                         engine.font_sub, 40, engine.screen_h - 118, 120, 135, 155)

    def _render_prompt(self, engine):
        label = BUTTON_LABELS.get(self._current(), self._current())
        engine.draw_text(tr("button_test_press") % label, engine.font_title,
                         40, 130, 0, 230, 150)
        engine.draw_text(tr("button_test_progress") % (self.step + 1, len(ASK_ORDER)),
                         engine.font_sub, 40, 182, 180, 195, 215)
        if self.wait_release:
            engine.draw_text(tr("button_test_release"), engine.font_sub,
                             40, 224, 240, 210, 120)
        else:
            engine.draw_text(tr("button_test_hint"), engine.font_sub,
                             40, 224, 150, 165, 185)

    def _render_summary(self, engine):
        engine.draw_text(tr("button_test_done"), engine.font_title,
                         40, 130, 0, 230, 150)
        half = (len(ASK_ORDER) + 1) // 2
        for index, name in enumerate(ASK_ORDER):
            column = 0 if index < half else 1
            row = index if column == 0 else index - half
            x = 40 + column * 470
            y = 196 + row * 46
            changed = self.buttons.get(name, 0) != DEFAULT_BUTTONS.get(name)
            engine.draw_text(BUTTON_LABELS.get(name, name), engine.font_sub,
                             x, y, 235, 238, 245)
            color = (0, 230, 150) if changed else (150, 160, 180)
            engine.draw_text(str(self.buttons.get(name, 0)), engine.font_sub,
                             x + 150, y, color[0], color[1], color[2])
            if changed:
                engine.draw_text(tr("button_test_new"), engine.font_sub,
                                 x + 215, y, 240, 200, 90)

    def _render_live(self, engine):
        """Ma phim dang giu. Day la thong tin de doc truc tiep tren may."""
        codes = sorted(code for code in self.keys if is_gamepad_key(code))
        text = tr("button_test_live") % (", ".join(str(c) for c in codes) or "-")
        color = (0, 230, 150) if codes else (120, 132, 150)
        engine.draw_text(text, engine.font_sub, 40, 250, color[0], color[1], color[2])
        axis = "hat %d,%d" % (self.hat.get(HAT_X, 0), self.hat.get(HAT_Y, 0))
        engine.draw_text(axis, engine.font_sub, 520, 250, 120, 132, 150)

    def _render_pad(self, engine):
        base_y = engine.screen_h - 128
        columns = ["a", "b", "x", "y", "l1", "r1", "l3", "r3", "select", "start"]
        for index, name in enumerate(columns):
            x = 40 + index * 94
            if x + 84 > engine.screen_w:
                break
            code = self.buttons.get(name, 0)
            active = code in self.keys
            color = COLORS.get(name, (150, 160, 190))
            if active:
                fill, text = color, (20, 24, 32)
            else:
                fill, text = (34, 42, 60), (200, 210, 225)
            engine.fill_rect(x, base_y, 84, 58, fill[0], fill[1], fill[2], 235)
            engine.draw_text(BUTTON_LABELS.get(name, name), engine.font_sub,
                             x + 8, base_y + 4, text[0], text[1], text[2])
            engine.draw_text(str(code), engine.font_sub, x + 8, base_y + 30,
                             text[0], text[1], text[2])
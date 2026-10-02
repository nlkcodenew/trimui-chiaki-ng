# -*- coding: utf-8 -*-
"""Man hinh THU BUT: xac nhan ma phim that cu tung nut tren Brick Pro.

Van de: firmware Stock OS day ma phim Linux cua mot so nut o vung 304..320 nhung
khong dung thu tu chuan, nen L3/R3 va cac nut phia duoi vo may co the khong
bao toi dien thoai. Man hinh nay hien thi ma phim that moi khi ban, nguoi dung
an nut theo thu tu, va luu ket qua vao bluetooth-map.json.
"""

import time

from ..gamepad_map import (BUTTON_LABELS, DEFAULT_BUTTONS, EV_KEY, PadReader,
                           find_gamepad, is_gamepad_key, load_map, save_map)
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

# Mot ma phim chi duoc gan mot lan. Do la ly do bo qua ma da thuoc ve nut khac.
ASSIGNED_ON_START = set(DEFAULT_BUTTONS.values())


class ButtonTestScreen(BaseScreen):
    def __init__(self, engine=None):
        super().__init__(engine, "button_test")
        self.reader = None
        self.device_path = ""
        self.device_name = ""
        self.buttons = dict(DEFAULT_BUTTONS)
        self.axes = {}
        self.step = 0
        self.down = {}
        self.consumed = set()
        self.flash = ""
        self.flash_until = 0.0
        self.finished = False
        self.error = ""
        self.hold_b_since = None

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
        self.step = 0
        self.finished = False
        self.down = {}
        self.consumed = set(ASSIGNED_ON_START)
        log.info("button test: bat dau tren %s (%s)", path, name)

    def on_exit(self):
        if self.reader:
            self.reader.close()
            self.reader = None

    def get_header_title(self):
        return tr("button_test_title")

    def get_footer_actions(self):
        if self.finished:
            return [("A", tr("button_test_save")), ("B", tr("button_test_restart"))]
        return [("A", tr("button_test_skip")), ("B", tr("button_test_back"))]

    # ---- input tu SDL ----

    def handle_input(self, inputs):
        if not inputs:
            return False
        edges = inputs.get("edges", [])
        now = time.time()

        # B vua duoc gan o buoc 2 nen phai phan biet "bam" voi "giu". Giu B
        # huy hanh dong; bam B lui mot buoc.
        if inputs.get("btn_b"):
            if self.hold_b_since is None:
                self.hold_b_since = now
            elif now - self.hold_b_since >= 1.5 and self.hold_b_since is not None:
                started = self.hold_b_since
                self.hold_b_since = None
                if now - started >= 1.5:
                    log.info("button test: huy do giu B")
                    self.engine.pop_screen()
                    return True
        else:
            self.hold_b_since = None

        if "btn_b" in edges:
            if self.finished:
                self.step = 0
                self.finished = False
                self.consumed = set(ASSIGNED_ON_START)
                return True
            self._back()
            return True

        if "btn_a" in edges:
            if self.finished:
                self._save()
            else:
                log.info("button test: bo qua %s", self._current())
                self.step += 1
                self._maybe_finish()
            return True
        return False

    # ---- logic ----

    def _current(self):
        if self.step >= len(ASK_ORDER):
            return ""
        return ASK_ORDER[self.step]

    def _back(self):
        if self.step > 0:
            self.step -= 1
        self._maybe_finish()

    def _accept(self, code):
        name = self._current()
        if not name:
            return
        previous = self.buttons.get(name)
        self.buttons[name] = code
        self.consumed.add(code)
        self.flash = tr("button_test_got") % (BUTTON_LABELS.get(name, name), code)
        self.flash_until = time.time() + 2.5
        log.info("button test: %s -> %d (truoc %s)", name, code, previous)
        self.step += 1
        self._maybe_finish()

    def _maybe_finish(self):
        if self.step < len(ASK_ORDER):
            return
        self.finished = True
        log.info("button test: het cac buoc. A de luu, B de lam lai.")

    def _save(self):
        try:
            path = save_map(APP_DIR, self.buttons, self.axes)
        except OSError as exc:
            log.error("button test: khong luu duoc: %s", exc)
            self.error = tr("button_test_save_failed") % exc
            return
        changed = [name for name in ASK_ORDER
                   if self.buttons.get(name) != DEFAULT_BUTTONS.get(name)]
        self.flash = tr("button_test_saved") % (len(changed), path)
        self.flash_until = time.time() + 6
        log.info("button test: da luu, %d nut khac mac dinh: %s", len(changed), changed)
        self.engine.pop_screen()

    # ---- doc input that ----

    def update(self, dt):
        if not self.reader:
            return
        for kind, code, value in self.reader.poll():
            if kind != EV_KEY:
                continue
            key = "key%d" % code
            if value == 0:
                self.down.pop(key, None)
            else:
                self.down[key] = value

        if self.finished:
            return

        # Gan nut moi nhat. Bo qua ma da gan cho nut khac de khong ghi de.
        for key in sorted(self.down):
            code = int(key[3:])
            if key in self.consumed or not is_gamepad_key(code):
                continue
            self._accept(code)
            break

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
        self._render_pad(engine)

        if self.flash and time.time() < self.flash_until:
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
                         engine.font_sub, 40, 185, 180, 195, 215)
        engine.draw_text(tr("button_test_hint"), engine.font_sub,
                         40, 235, 150, 165, 185)

    def _render_summary(self, engine):
        engine.draw_text(tr("button_test_done"), engine.font_title,
                         40, 130, 0, 230, 150)
        half = (len(ASK_ORDER) + 1) // 2
        for index, name in enumerate(ASK_ORDER):
            column = 0 if index < half else 1
            row = index if column == 0 else index - half
            x = 40 + column * 470
            y = 200 + row * 46
            changed = self.buttons.get(name, 0) != DEFAULT_BUTTONS.get(name)
            engine.draw_text(BUTTON_LABELS.get(name, name), engine.font_sub,
                             x, y, 235, 238, 245)
            color = (0, 230, 150) if changed else (150, 160, 180)
            engine.draw_text(str(self.buttons.get(name, 0)), engine.font_sub,
                             x + 150, y, color[0], color[1], color[2])
            if changed:
                engine.draw_text(tr("button_test_new"), engine.font_sub,
                                 x + 215, y, 240, 200, 90)
        engine.draw_text(tr("button_test_star_note"), engine.font_sub,
                         40, engine.screen_h - 150, 150, 165, 185)

    def _render_pad(self, engine):
        base_y = engine.screen_h - 128
        columns = ["a", "b", "x", "y", "l1", "r1", "l3", "r3", "select", "start"]
        for index, name in enumerate(columns):
            x = 40 + index * 94
            if x + 84 > engine.screen_w:
                break
            active = ("key%d" % self.buttons.get(name, 0)) in self.down
            color = COLORS.get(name, (150, 160, 190))
            if active:
                fill, text = color, (20, 24, 32)
            else:
                fill, text = (34, 42, 60), (200, 210, 225)
            engine.fill_rect(x, base_y, 84, 58, fill[0], fill[1], fill[2], 235)
            engine.draw_text(BUTTON_LABELS.get(name, name), engine.font_sub,
                             x + 8, base_y + 4, text[0], text[1], text[2])

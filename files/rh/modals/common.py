# -*- coding: utf-8 -*-
from .base import BaseModal
from .. import state
from ..i18n import tr
from ..ui.primitives import safe_measure, theme, wrap_lines


def _modal_box(engine, title, message, font, content_h=200):
    """Hop modal can giua, rong theo noi dung nhung kep trong man hinh."""
    c = theme(state.theme)
    engine.fill_rect(0, 0, engine.screen_w, engine.screen_h, *c["dim"], 180)
    inner = engine.screen_w - 240
    title_w = safe_measure(engine, title, engine.font_title)
    lines = wrap_lines(engine, message, font, inner - 80)
    w = min(engine.screen_w - 80, max(480, title_w + 80))
    if lines:
        w = min(engine.screen_w - 80,
                max(w, safe_measure(engine, lines[0], font) + 80))
    h = content_h + max(0, len(lines) - 1) * 34
    x = (engine.screen_w - w) // 2
    y = (engine.screen_h - h) // 2
    engine.fill_rect(x, y, w, h, *c["header"], 240)
    engine.fill_rect(x, y, w, 3, *c["accent"], 255)
    return c, x, y, w, h, lines


class InfoModal(BaseModal):
    def __init__(self, engine=None):
        super().__init__(engine)
        self.title = ""
        self.message = ""

    def open(self, data=None):
        super().open(data or {})
        self.title = (self.data or {}).get("title", "")
        self.message = (self.data or {}).get("message", "")

    def handle_input(self, inputs):
        edges = inputs.get("edges", [])
        if any(key in edges for key in ("btn_a", "btn_b", "quit")):
            self.close()
            return True
        return False

    def render(self, engine):
        c, x, y, w, h, lines = _modal_box(
            engine, self.title, self.message, engine.font_item)
        engine.draw_text(self.title, engine.font_title, x + 40, y + 30, *c["text"])
        for index, line in enumerate(lines[:3]):
            engine.draw_text(line, engine.font_item, x + 40, y + 100 + index * 34,
                             *c["sub"])
        engine.draw_text(tr("ok"), engine.font_sub, x + w // 2, y + h - 50,
                         *c["accent"], center_x=True)


class ConfirmModal(BaseModal):
    def __init__(self, engine=None):
        super().__init__(engine)
        self.title = ""
        self.message = ""
        self.on_yes = None
        self.on_no = None

    def open(self, data=None):
        super().open(data or {})
        self.title = (self.data or {}).get("title", "")
        self.message = (self.data or {}).get("message", "")
        self.on_yes = (self.data or {}).get("on_yes")
        self.on_no = (self.data or {}).get("on_no")

    def handle_input(self, inputs):
        edges = inputs.get("edges", [])
        if "btn_a" in edges:
            callback = self.on_yes
            self.close()
            if callback:
                try:
                    callback()
                except Exception:
                    pass
            return True
        if "btn_b" in edges or "quit" in edges:
            callback = self.on_no
            self.close()
            if callback:
                try:
                    callback()
                except Exception:
                    pass
            return True
        return False

    def render(self, engine):
        c, x, y, w, h, lines = _modal_box(
            engine, self.title, self.message, engine.font_item,
            content_h=240)
        engine.draw_text(self.title, engine.font_title, x + 40, y + 30, *c["text"])
        for index, line in enumerate(lines[:3]):
            engine.draw_text(line, engine.font_item, x + 40, y + 100 + index * 34,
                             *c["sub"])
        engine.draw_text("[A] %s    [B] %s" % (tr("yes"), tr("no")),
                         engine.font_sub, x + 40, y + h - 60, *c["accent"])


class StreamLoadingModal(BaseModal):
    def __init__(self, engine=None):
        super().__init__(engine)
        self.title = ""
        self.message = ""
        self.progress = 0.0

    def open(self, data=None):
        super().open(data or {})
        self.title = (self.data or {}).get("title", "")
        self.message = (self.data or {}).get("message", "")

    def set_progress(self, value, message=""):
        self.progress = max(0.0, min(1.0, float(value)))
        if message:
            self.message = message

    def handle_input(self, inputs):
        edges = inputs.get("edges", [])
        if "btn_b" in edges or "quit" in edges:
            self.close()
            return True
        return False

    def render(self, engine):
        c = theme(state.theme)
        engine.fill_rect(0, 0, engine.screen_w, engine.screen_h, *c["dim"], 180)
        w, h = 800, 200
        x = (engine.screen_w - w) // 2
        y = (engine.screen_h - h) // 2
        engine.fill_rect(x, y, w, h, *c["header"], 240)
        engine.fill_rect(x, y, w, 3, *c["accent"], 255)
        engine.draw_text(self.title, engine.font_title, x + 40, y + 30, *c["text"])
        engine.draw_text(self.message, engine.font_item, x + 40, y + 100, *c["sub"])
        # progress bar
        bar_x = x + 40
        bar_y = y + 160
        bar_w = w - 80
        bar_h = 14
        engine.fill_rect(bar_x, bar_y, bar_w, bar_h, *c["track"], 255)
        if self.progress > 0:
            engine.fill_rect(bar_x, bar_y, int(bar_w * self.progress), bar_h, *c["accent"], 255)

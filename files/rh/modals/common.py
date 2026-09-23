# -*- coding: utf-8 -*-
from .base import BaseModal
from ..i18n import tr


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
        engine.fill_rect(0, 0, engine.screen_w, engine.screen_h, 0, 0, 0, 180)
        w, h = engine.measure_text(self.title, engine.font_title) + 80, 200
        x = (engine.screen_w - w) // 2
        y = (engine.screen_h - h) // 2
        engine.fill_rect(x, y, w, h, 20, 28, 46, 240)
        engine.draw_text(self.title, engine.font_title, x + 40, y + 30, 255, 255, 255)
        engine.draw_text(self.message, engine.font_item, x + 40, y + 100, 220, 225, 235)
        engine.draw_text(tr("ok"), engine.font_sub, x + w // 2, y + h - 50,
                         0, 230, 150, center_x=True)


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
        engine.fill_rect(0, 0, engine.screen_w, engine.screen_h, 0, 0, 0, 180)
        w, h = engine.measure_text(self.title, engine.font_title) + 80, 240
        x = (engine.screen_w - w) // 2
        y = (engine.screen_h - h) // 2
        engine.fill_rect(x, y, w, h, 20, 28, 46, 240)
        engine.draw_text(self.title, engine.font_title, x + 40, y + 30, 255, 255, 255)
        engine.draw_text(self.message, engine.font_item, x + 40, y + 100, 220, 225, 235)
        engine.draw_text("[A] %s    [B] %s" % (tr("yes"), tr("no")),
                         engine.font_sub, x + 40, y + h - 60, 0, 230, 150)


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
        engine.fill_rect(0, 0, engine.screen_w, engine.screen_h, 0, 0, 0, 180)
        w, h = 800, 200
        x = (engine.screen_w - w) // 2
        y = (engine.screen_h - h) // 2
        engine.fill_rect(x, y, w, h, 20, 28, 46, 240)
        engine.draw_text(self.title, engine.font_title, x + 40, y + 30, 255, 255, 255)
        engine.draw_text(self.message, engine.font_item, x + 40, y + 100, 220, 225, 235)
        # progress bar
        bar_x = x + 40
        bar_y = y + 160
        bar_w = w - 80
        bar_h = 14
        engine.fill_rect(bar_x, bar_y, bar_w, bar_h, 10, 14, 24, 255)
        if self.progress > 0:
            engine.fill_rect(bar_x, bar_y, int(bar_w * self.progress), bar_h, 0, 230, 150, 255)

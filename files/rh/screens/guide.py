# -*- coding: utf-8 -*-
"""Huong dan su dung trong app theo tung buoc."""

from ..i18n import tr
from .base import BaseScreen


class GuideScreen(BaseScreen):
    STEPS = tuple(
        ("guide_%d_title" % index, "guide_%d_body" % index)
        for index in range(1, 9)
    )

    def __init__(self, engine=None):
        super().__init__(engine, "guide")
        self.selected = 0

    def on_enter(self, params=None):
        self.selected = 0

    def get_header_title(self):
        return tr("guide")

    def get_footer_actions(self):
        return [("UP/DN", tr("guide_nav")), ("A", tr("next")), ("B", tr("back"))]

    def handle_input(self, inputs):
        edges = inputs.get("edges", []) if inputs else []
        if "btn_b" in edges or "quit" in edges:
            self.engine.pop_screen()
            return True
        if "btn_up" in edges or "btn_left" in edges:
            self.selected = max(0, self.selected - 1)
            return True
        if any(key in edges for key in ("btn_down", "btn_right", "btn_a")):
            self.selected = min(len(self.STEPS) - 1, self.selected + 1)
            return True
        return False

    @staticmethod
    def _wrap_text(engine, text, font, max_width):
        lines = []
        current = ""
        for word in str(text).split():
            candidate = word if not current else "%s %s" % (current, word)
            width = engine.measure_text(candidate, font)
            if current and width > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    def render(self, engine):
        engine.fill_rect(0, 64, engine.screen_w, engine.screen_h - 120,
                         13, 17, 28, 255)
        total = len(self.STEPS)
        title_key, body_key = self.STEPS[self.selected]
        engine.draw_text(
            tr("guide_progress") % (self.selected + 1, total),
            engine.font_sub, 40, 90, 0, 230, 150,
        )
        card_y = 135
        card_h = engine.screen_h - card_y - 80
        engine.fill_rect(40, card_y, engine.screen_w - 80, card_h,
                         30, 43, 66, 245)
        engine.draw_text(tr(title_key), engine.font_title, 70, card_y + 30,
                         255, 255, 255)
        lines = self._wrap_text(
            engine, tr(body_key), engine.font_sub, engine.screen_w - 140)
        y = card_y + 100
        for line in lines:
            engine.draw_text(line, engine.font_sub, 70, y, 220, 225, 235)
            y += 42

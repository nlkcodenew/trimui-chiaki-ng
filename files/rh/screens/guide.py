# -*- coding: utf-8 -*-
"""Huong dan su dung trong app theo tung buoc."""

from .. import state
from ..i18n import tr
from ..ui.primitives import ellipsis_text, theme, wrap_lines
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

    def render(self, engine):
        c = theme(state.theme)
        engine.fill_rect(0, 64, engine.screen_w, engine.screen_h - 120,
                         *c["bg"], 255)
        total = len(self.STEPS)
        title_key, body_key = self.STEPS[self.selected]
        engine.draw_text(
            tr("guide_progress") % (self.selected + 1, total),
            engine.font_sub, 40, 90, *c["accent"],
        )
        card_y = 135
        card_h = engine.screen_h - card_y - 80
        engine.fill_rect(40, card_y, engine.screen_w - 80, card_h,
                         *c["card"], 245)
        engine.fill_rect(40, card_y, engine.screen_w - 80, 3,
                         *c["accent"], 255)
        engine.draw_text(
            ellipsis_text(engine, tr(title_key), engine.font_title,
                          engine.screen_w - 180),
            engine.font_title, 70, card_y + 30, *c["text"])
        lines = wrap_lines(engine, tr(body_key), engine.font_sub,
                           engine.screen_w - 200, max_lines=8)
        y = card_y + 100
        for line in lines:
            engine.draw_text(line, engine.font_sub, 70, y, *c["sub"])
            y += 42
        dot_y = card_y + card_h - 28
        dot_x0 = engine.screen_w // 2 - total * 11
        for index in range(total):
            dot_c = c["accent"] if index == self.selected else c["faint"]
            engine.fill_rect(dot_x0 + index * 22, dot_y, 10, 10, *dot_c, 255)

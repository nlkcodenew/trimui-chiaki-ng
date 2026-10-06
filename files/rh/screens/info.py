# -*- coding: utf-8 -*-
"""Information screen with the author's MoMo donation QR."""

import os

from .. import state
from ..i18n import tr
from ..paths import APP_DIR
from ..ui.primitives import theme, wrap_lines
from .base import BaseScreen


class InfoScreen(BaseScreen):
    QR_PATH = os.path.join(APP_DIR, "assets", "donate-qr.bmp")
    DONATE_KEYS = (
        "info_donate_title",
        "info_donate_scan",
        "info_donate_owner",
        "info_donate_note",
        "info_donate_thanks",
    )

    def __init__(self, engine=None):
        super().__init__(engine, "info")

    def get_header_title(self):
        return tr("info")

    def get_footer_actions(self):
        return [("B", tr("back"))]

    def handle_input(self, inputs):
        edges = inputs.get("edges", []) if inputs else []
        if "btn_b" in edges or "quit" in edges:
            self.engine.pop_screen()
            return True
        return False

    def render(self, engine):
        colors = theme(state.theme)
        engine.fill_rect(0, 64, engine.screen_w, engine.screen_h - 120,
                         *colors["bg"], 255)
        card_x = 40
        card_y = 92
        card_w = engine.screen_w - 80
        card_h = engine.screen_h - card_y - 80
        engine.fill_rect(card_x, card_y, card_w, card_h,
                         *colors["card"], 245)
        engine.fill_rect(card_x, card_y, card_w, 3,
                         *colors["accent"], 255)

        qr_h = min(390, card_h - 80)
        qr_w = int(qr_h * 237 / 243)
        qr_x = card_x + 65
        qr_y = card_y + (card_h - qr_h) // 2
        draw_bmp = getattr(engine, "draw_bmp", None)
        qr_drawn = bool(draw_bmp and draw_bmp(
            self.QR_PATH, qr_x, qr_y, qr_w, qr_h))
        if not qr_drawn:
            engine.draw_text(tr("info_qr_missing"), engine.font_sub,
                             qr_x, card_y + card_h // 2, *colors["muted"])

        text_x = card_x + 520
        text_w = max(260, card_x + card_w - text_x - 55)
        y = card_y + 95
        for index, key in enumerate(self.DONATE_KEYS):
            font = engine.font_title if index == 0 else engine.font_sub
            color = colors["text"] if index == 0 else colors["sub"]
            lines = wrap_lines(engine, tr(key), font, text_w, max_lines=3)
            for line in lines:
                engine.draw_text(line, font, text_x, y, *color)
                y += 48 if index == 0 else 38
            y += 12 if index in (0, 2) else 4

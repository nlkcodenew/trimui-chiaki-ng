# -*- coding: utf-8 -*-
"""Chon font co the ve tieng Viet (Latin Extended Additional + o-horn, u-horn).

Trich y rh/fonts.py cua RetroHub - khi chua co font chuan, ta fallback ve
DejaVuVu (san trong firmware TrimUI Linux) hoac fallback.ttf neu co.
"""

import glob
import os

from .paths import APP_DIR, SDCARD_PATH

FALLBACK_FONT = os.path.join(APP_DIR, "assets", "fallback.ttf")

VIET_PROBE = (0x01A1, 0x01B0, 0x1EC7, 0x1ED9, 0x1EF9)


def font_candidates():
    return ([FALLBACK_FONT] if os.path.isfile(FALLBACK_FONT) else [])


def pick_font(candidates):
    """Ban 0.1.0 chi tra file ton tai. Viec probe glyph se hoan thien o 0.2.0
    cung SDL2_ttf binding that su."""
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None
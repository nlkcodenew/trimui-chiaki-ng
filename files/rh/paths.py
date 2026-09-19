# -*- coding: utf-8 -*-
"""Vi tri he thong cho trimui-chiaki-ng.

Nhan app luon nam trong $SDCARD_PATH/Apps/Chiaki hoac tuong duong. Khi OS TrimUI
goi launch.sh, no export SDCARD_PATH, va $0%/* cung cho APP_DIR chinh xac.
"""

import os

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _detect_sdcard_path():
    env_sd = os.environ.get("SDCARD_PATH")
    if env_sd and os.path.isdir(env_sd):
        return os.path.abspath(env_sd)
    parent = os.path.dirname(APP_DIR)
    if os.path.basename(parent).lower() == "apps":
        candidate = os.path.dirname(parent)
        if os.path.isdir(candidate):
            return os.path.abspath(candidate)
    for candidate in ("/mnt/SDCARD", "/mnt/mmc", "/userdata", "/roms", "/mnt/sdcard"):
        if os.path.isdir(candidate):
            return candidate
    return env_sd or "/mnt/SDCARD"


SDCARD_PATH = _detect_sdcard_path()
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
BIN_DIR = os.path.join(APP_DIR, "bin")
LOG_DIR = APP_DIR
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trimui-chiaki-ng - PS4/PS5 Remote Play cho TrimUI Smart Pro S.

Phien ban 0.2.0:
    - Logger rolling 2 file (Chiaki-loi.txt / Chiaki-debug.log) co level + thread
    - Wire protocol discovery + wakeup (port 987 PS4 / 9302 PS5)
    - Chiaki.conf parse theo mau Switch
    - SDL GameController bind day du (axis + button)
    - Auto-update OTA qua GitHub Raw + ghproxy + jsDelivr
    - Video stream that se them o 0.3.0 (FFmpeg subprocess / libplacebo)

Thu vien Python can thiet (co san trong firmware TrimUI Linux 1.1.1):
    - python3 (>=3.10)
    - pysdl2 (dat san trong $APP/libs hoac /usr/lib64)
    - sdl2, sdl2_ttf
    - curl/wget de auto-update

Copy vao $SDCARD_PATH/Apps/Chiaki/ roi mo tu menu TrimUI.
"""

import os
import sys
import traceback


def _vendor_path():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    paths = [
        os.path.join(app_dir, "libs"),
        os.path.join(app_dir, "vendor"),
        "/usr/trimui/lib",
        "/usr/lib64",
        "/usr/lib",
    ]
    for p in paths:
        if os.path.isdir(p):
            sys.path.insert(0, p)


_vendor_path()

os.environ["PYSDL2_DLL_PATH"] = ":".join([
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "libs"),
    "/usr/trimui/lib",
    "/usr/lib64",
    "/usr/lib",
])

from rh import state, paths
from rh.logger import init_logger, get_logger, set_debug_level
from rh.engine import ChiakiEngine
from rh.screens.home import HomeScreen
from rh.screens.settings import SettingsScreen
from rh.modals.update import UpdateModal
from rh.modals.common import InfoModal, ConfirmModal


def main():
    # Logger khoi dong SOM nhat de bat moi loi import / sys.argv
    init_logger()
    log = get_logger()
    log.info("== trimui-chiaki-ng v%s khoi dong ==", "0.2.0")
    log.info("SDCARD_PATH=%s", paths.SDCARD_PATH)
    log.info("APP_DIR=%s", paths.APP_DIR)
    log.info("PYTHON=%s", sys.version.replace("\n", " "))
    log.info("enable_logging=%s", state.enable_logging)
    if state.enable_logging:
        set_debug_level(True)

    engine = ChiakiEngine()
    if not engine.init_sdl():
        log.error("init_sdl that bai")
        sys.stderr.write("Khong khoi dong duoc SDL2.\n")
        return 1
    if not engine.init_fonts():
        log.error("init_fonts that bai")
        sys.stderr.write("Khong tai duoc font he thong.\n")
        return 1
    log.info("SDL + fonts ok, screen=%dx%d", engine.screen_w, engine.screen_h)

    engine.register_screen("home", HomeScreen(engine))
    engine.register_screen("settings", SettingsScreen(engine))
    engine.register_modal("update", UpdateModal(engine))
    engine.register_modal("info", InfoModal(engine))
    engine.register_modal("confirm", ConfirmModal(engine))

    engine.push_screen("home")

    try:
        engine.run()
    except Exception:
        err = traceback.format_exc()
        log.error("crash: %s", err)
        sys.stderr.write("\ntrimui-chiaki-ng crash:\n%s\n" % err)
        return 1
    finally:
        engine.cleanup()
        log.info("== app thoat ==")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        err = traceback.format_exc()
        log_path = os.path.join(paths.APP_DIR, "Chiaki-loi.txt")
        try:
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(err)
        except Exception:
            pass
        raise
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trimui-chiaki-ng - PS4/PS5 Remote Play cho TrimUI Smart Pro S.

Phien ban 0.1.0: khoi dong SDL2, hien menu, scan host qua UDP, modal cap nhat.
Streaming video that su se them o 0.2.0 cung codec H264/H265.

Thu vien Python can thiet (co san trong firmware TrimUI Linux 1.1.1):
    - python3 (>=3.8)
    - sdl2, pysdl2 (dat san trong $APP/libs hoac /usr/lib64)
    - sdl2_ttf
    - curl/wget de auto-update
"""

import os
import sys
import threading
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

# Ep shell/pysdl2 tim SDL2 o cac duong dan mac dinh cua TrimUI Linux 1.1.1
os.environ["PYSDL2_DLL_PATH"] = ":".join([
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "libs"),
    "/usr/trimui/lib",
    "/usr/lib64",
    "/usr/lib",
])

from rh import state, paths, logger, i18n
from rh.engine import ChiakiEngine
from rh.screens.home import HomeScreen
from rh.screens.settings import SettingsScreen
from rh.modals.update import UpdateModal
from rh.modals.common import InfoModal, ConfirmModal


def main():
    logger.init_logger()

    engine = ChiakiEngine()
    if not engine.init_sdl():
        sys.stderr.write("Khong khoi dong duoc SDL2.\n")
        return 1
    if not engine.init_fonts():
        sys.stderr.write("Khong tai duoc font he thong.\n")
        return 1

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
        logger.log(err)
        sys.stderr.write("\ntrimui-chiaki-ng crash:\n%s\n" % err)
        return 1
    finally:
        engine.cleanup()
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
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trimui-chiaki-ng - PS4/PS5 Remote Play cho TrimUI Smart Pro S.

Phien ban 0.2.10:
    - Sua nut B trong Cai dat bi doi gia tri: dao lai anh xa A/B/X/Y cua
      SDL GameController theo layout trimui (A vat ly = BUTTON_B), bo qua su
      kien JOY* khi da mo GameController de tranh edge trung lap
    - Cai dat: B chi thoat, A/Left/Right doi gia tri + luu ngay; dong
      "Quay lai" moi nut deu thoat
    - Bundled pysdl2 vao vendor/sdl2 - khong can cai pip tren may
    - Giao dien tieng Viet day du dau, OTA va crash log qua GitHub Issues

Luu y khi update tu v0.2.0 hoac v0.2.1: nen xoa App/Chiaki cu va giai nen
Release moi nhat vao goc the de vendor/sdl2 duoc cai day du.

Video stream that se them o 0.3.0 (FFmpeg subprocess / libplacebo).

Thu vien can thiet:
    - python3 (>= 3.10, san trong firmware TrimUI Linux 1.1.1)
    - libSDL2.so, libSDL2_ttf.so (san trong /usr/lib64 firmware)
    - libopus.so, libcurl.so (san trong /usr/lib)
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
from rh.version import APP_VERSION


def main():
    # Logger khoi dong SOM nhat de bat moi loi import / sys.argv
    init_logger()
    log = get_logger()
    log.info("== trimui-chiaki-ng v%s khoi dong ==", APP_VERSION)
    log.info("SDCARD_PATH=%s", paths.SDCARD_PATH)
    log.info("APP_DIR=%s", paths.APP_DIR)
    log.info("PYTHON=%s", sys.version.replace("\n", " "))
    log.info("enable_logging=%s", state.enable_logging)
    if state.enable_logging:
        set_debug_level(True)

    try:
        from rh.log_uploader import start_pending_upload
        start_pending_upload("startup_retry")
    except Exception as exc:
        log.warning("cannot start pending log uploader: %s", exc)

    # Import SDL-dependent modules only after logger is ready. Neu SDL/pysdl2
    # thieu, traceback se duoc launch.sh thu gom va gui len GitHub Issue.
    from rh.engine import ChiakiEngine
    from rh.screens.home import HomeScreen
    from rh.screens.settings import SettingsScreen
    from rh.modals.update import UpdateModal
    from rh.modals.common import InfoModal, ConfirmModal

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
        exit_reason = engine.run()
    except Exception:
        err = traceback.format_exc()
        log.error("crash: %s", err)
        sys.stderr.write("\ntrimui-chiaki-ng crash:\n%s\n" % err)
        return 1
    finally:
        engine.cleanup()
        log.info("== app thoat ==")
    if exit_reason not in ("user_exit", "update_restart"):
        log.error("unexpected app exit: %s", exit_reason)
        return 2
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

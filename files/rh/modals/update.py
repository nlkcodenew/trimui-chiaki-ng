# -*- coding: utf-8 -*-
"""Modal popup OTA update - copy y RetroHub.

Cho phep nguoi dung chon CAI NGAY / DE SAU / BO QUA khi co phien ban moi.
"""

import os
import threading
from .. import state
from ..i18n import tr
from ..paths import APP_DIR
from ..version import is_newer, APP_VERSION
from ..logger import get_logger
from ..ui.primitives import ellipsis_text, theme, wrap_lines
from ..updater import (
    apply_update, check_for_update, download_update, release_note,
    request_restart, skip_version,
    SETTINGS_REL,
)
from .base import BaseModal

log = get_logger()


class UpdateModal(BaseModal):
    def __init__(self, engine=None):
        super().__init__(engine)
        self.manifest = None
        self.files = []
        self.selected_opt = 0
        self.busy = False
        self.failed = False
        self.restart = False
        self.status = ""
        self.progress_pct = 0.0
        self.progress_done = 0
        self.progress_total = 0
        self.progress_file = ""
        self.phase = ""

    def open(self, data=None):
        super().open(data or {})
        self.manifest = (self.data or {}).get("manifest")
        raw_files = (self.data or {}).get("files") or []
        # settings.json KHONG bao gio nam trong pending_files (updater da lo).
        # Loc lai o day de phong nguon ngoai (API, test) dua file nay vao.
        self.files = [f for f in raw_files if f.get("path") != SETTINGS_REL]
        self.cat_only = False
        self.rt_only = False
        # Cat-only: version khong moi, khong co file code pending.
        if (self.manifest
                and not is_newer(self.manifest.get("version", ""), APP_VERSION)
                and not self.files):
            self.cat_only = True
        self.selected_opt = 0
        self.busy = False
        self.failed = False
        self.restart = False
        self.status = ""
        self.progress_pct = 0.0
        self.progress_done = 0
        self.progress_total = len(self.files)
        self.progress_file = ""
        self.phase = tr("update_checking")

    def get_labels(self):
        return [tr("update_install"), tr("update_later"), tr("update_skip")]

    def _move(self, delta):
        if self.busy:
            return
        self.selected_opt = (self.selected_opt + delta) % len(self.get_labels())

    def handle_input(self, inputs):
        edges = inputs.get("edges", [])
        if self.busy:
            return False
        if "btn_left" in edges:
            self._move(-1)
            return True
        if "btn_right" in edges:
            self._move(1)
            return True
        if "btn_up" in edges:
            self._move(-1)
            return True
        if "btn_down" in edges:
            self._move(1)
            return True
        if "btn_a" in edges:
            self._activate(self.selected_opt)
            return True
        if "btn_b" in edges or "quit" in edges:
            self._activate(1)
            return True
        return False

    def _activate(self, idx):
        if idx == 0:
            log.info("update modal: install selected for v%s",
                     (self.manifest or {}).get("version", "?"))
            self._start_install()
        elif idx == 1:
            log.info("update modal: later selected")
            self.close()
        else:
            if self.manifest and "version" in self.manifest:
                log.info("update modal: skip v%s", self.manifest["version"])
                skip_version(self.manifest["version"])
            self.close()

    def _start_install(self):
        if not self.manifest or self.busy:
            return
        self.busy = True
        self.phase = tr("update_downloading")
        self.status = tr("update_network_check")
        threading.Thread(target=self._run_install, daemon=True).start()

    def _run_install(self):
        m = self.manifest
        files = self.files
        def prog(done, total, path):
            self.progress_done = done
            self.progress_total = total
            self.progress_file = os.path.basename(path) if path else ""
            if total > 0:
                self.progress_pct = min(0.9, done / total)
            self.status = "%s %d/%d: %s" % (
                tr("update_download_progress"), done, total, self.progress_file)
        try:
            ok = download_update(m, files, progress=prog) if files else True
            if ok:
                self.phase = tr("update_installing")
                self.progress_pct = 0.95
                ok = apply_update(m, files) if files else True
            if ok:
                self.phase = tr("update_done")
                self.progress_pct = 1.0
                self.restart = request_restart()
                if self.restart and self.engine:
                    self.engine.quit("update_restart")
                elif not self.restart:
                    self.phase = tr("update_failed")
                    self.status = tr("update_failed_hint")
                    self.failed = True
            else:
                self.phase = tr("update_failed")
                self.status = tr("update_failed_hint")
                self.failed = True
        except Exception as exc:
            log.exception("update modal install failed: %s", exc)
            try:
                from ..log_uploader import queue_diagnostic
                queue_diagnostic("ota_install_exception")
            except Exception as report_exc:
                log.warning("cannot queue OTA install diagnostic: %s", report_exc)
            self.phase = tr("update_failed")
            self.status = tr("update_failed_hint")
            self.failed = True
        finally:
            self.busy = False

    def render(self, engine):
        c = theme(state.theme)
        engine.fill_rect(0, 0, engine.screen_w, engine.screen_h, *c["dim"], 180)
        w, h = 920, 380
        x = (engine.screen_w - w) // 2
        y = (engine.screen_h - h) // 2
        engine.fill_rect(x, y, w, h, *c["header"], 240)
        engine.fill_rect(x, y, w, 3, *c["accent"], 255)
        engine.draw_text(tr("update"), engine.font_title, x + 40, y + 30, *c["text"])
        if self.manifest:
            note = release_note(self.manifest, state.current_lang)
            engine.draw_text("v%s" % self.manifest.get("version", "?"),
                             engine.font_item, x + 40, y + 90, *c["accent"])
            for index, line in enumerate(wrap_lines(engine, note or "",
                                                    engine.font_sub, w - 80,
                                                    max_lines=2)):
                engine.draw_text(line, engine.font_sub, x + 40, y + 130 + index * 30,
                                 *c["sub"])
            engine.draw_text("%d file(s)" % len(self.files),
                             engine.font_sub, x + 40, y + 196, *c["muted"])
        if self.busy:
            engine.draw_text(self.phase, engine.font_sub, x + 40, y + 236, *c["text"])
            status = ellipsis_text(engine, self.status, engine.font_sub, w - 80)
            engine.draw_text(status, engine.font_sub, x + 40, y + 266, *c["muted"])
            bar_x, bar_y, bar_w, bar_h = x + 40, y + 300, w - 80, 14
            engine.fill_rect(bar_x, bar_y, bar_w, bar_h, *c["track"], 255)
            if self.progress_pct > 0:
                engine.fill_rect(bar_x, bar_y, int(bar_w * self.progress_pct), bar_h,
                                 *c["accent"], 255)
        else:
            labels = self.get_labels()
            base_x = x + 40
            base_y = y + h - 90
            for i, lbl in enumerate(labels):
                bx = base_x + i * 280
                selected = (i == self.selected_opt)
                engine.fill_rect(bx, base_y, 240, 60, *(c["accent"] if selected else c["row"]), 240)
                if selected:
                    engine.fill_rect(bx, base_y, 6, 60, *c["accent"], 255)
                engine.draw_text(lbl, engine.font_sub, bx + 120, base_y + 30,
                                 *(c["chip_text"] if selected else c["text"]),
                                 center_x=True, center_y=True)

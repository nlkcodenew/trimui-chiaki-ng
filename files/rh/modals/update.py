# -*- coding: utf-8 -*-
"""Modal popup OTA update - copy y RetroHub.

Cho phep nguoi dung chon CAI NGAY / DE SAU / BO QUA khi co phien ban moi.
"""

import os
import threading
from .. import state
from ..i18n import tr
from ..paths import APP_DIR
from ..updater import (
    apply_update, check_for_update, download_update, release_note,
    request_restart, skip_version,
)
from .base import BaseModal


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
        self.files = (self.data or {}).get("files") or []
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
        if self.busy:
            if inputs.get("btn_b") or inputs.get("quit"):
                self.close()
                return True
            return False
        if inputs.get("btn_left"):
            self._move(-1)
            return True
        if inputs.get("btn_right"):
            self._move(1)
            return True
        if inputs.get("btn_up"):
            self._move(-1)
            return True
        if inputs.get("btn_down"):
            self._move(1)
            return True
        if inputs.get("btn_a"):
            self._activate(self.selected_opt)
            return True
        if inputs.get("btn_b") or inputs.get("quit"):
            self._activate(1)
            return True
        return False

    def _activate(self, idx):
        if idx == 0:
            self._start_install()
        elif idx == 1:
            self.close()
        else:
            if self.manifest and "version" in self.manifest:
                skip_version(self.manifest["version"])
            self.close()

    def _start_install(self):
        if not self.manifest or self.busy:
            return
        self.busy = True
        self.phase = tr("update_downloading")
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
            self.status = "Download %d/%d: %s" % (done, total, self.progress_file)
        try:
            ok = download_update(m, files, progress=prog) if files else True
            if ok:
                self.phase = tr("update_installing")
                self.progress_pct = 0.95
                ok = apply_update(m, files) if files else True
            if ok:
                self.phase = tr("update_done")
                self.progress_pct = 1.0
                self.restart = True
                request_restart()
            else:
                self.phase = tr("update_failed")
                self.failed = True
        except Exception as exc:
            print("Update error: %s" % exc)
            self.phase = tr("update_failed")
            self.failed = True
        finally:
            self.busy = False

    def render(self, engine):
        engine.fill_rect(0, 0, engine.screen_w, engine.screen_h, 0, 0, 0, 180)
        w, h = 920, 380
        x = (engine.screen_w - w) // 2
        y = (engine.screen_h - h) // 2
        engine.fill_rect(x, y, w, h, 20, 28, 46, 240)
        engine.draw_text(tr("update"), engine.font_title, x + 40, y + 30, 255, 255, 255)
        if self.manifest:
            note = release_note(self.manifest, state.current_lang)
            engine.draw_text("v%s" % self.manifest.get("version", "?"),
                             engine.font_item, x + 40, y + 90, 0, 230, 150)
            engine.draw_text(note or "", engine.font_sub, x + 40, y + 130,
                             220, 225, 235)
            engine.draw_text("%d file(s)" % len(self.files),
                             engine.font_sub, x + 40, y + 160, 180, 195, 215)
        if self.busy:
            engine.draw_text(self.phase, engine.font_sub, x + 40, y + 200, 255, 255, 255)
            engine.draw_text(self.status, engine.font_sub, x + 40, y + 230, 200, 210, 220)
            bar_x, bar_y, bar_w, bar_h = x + 40, y + 270, w - 80, 14
            engine.fill_rect(bar_x, bar_y, bar_w, bar_h, 10, 14, 24, 255)
            if self.progress_pct > 0:
                engine.fill_rect(bar_x, bar_y, int(bar_w * self.progress_pct), bar_h,
                                 0, 230, 150, 255)
        else:
            labels = self.get_labels()
            base_x = x + 40
            base_y = y + h - 90
            for i, lbl in enumerate(labels):
                bx = base_x + i * 280
                col = (0, 230, 150) if i == self.selected_opt else (40, 60, 90)
                engine.fill_rect(bx, base_y, 240, 60, col[0], col[1], col[2], 240)
                engine.draw_text(lbl, engine.font_sub, bx + 120, base_y + 30,
                                 255, 255, 255, center_x=True)
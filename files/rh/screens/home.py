# -*- coding: utf-8 -*-
"""Man hinh chinh: quet may PS4/PS5, BAT DAU CHOI, cai dat, cap nhat."""

import os
import threading
import time
from .. import state, chiaki
from ..i18n import tr
from ..logger import get_logger
from .base import BaseScreen

log = get_logger()


class HomeScreen(BaseScreen):
    """Man hinh chinh cua app. Cac muc menu:

        1. QUET MAY PS4/PS5  (scan)
        2. CAI DAT          (settings)
        3. CAP NHAT         (update)
        4. THOAT            (exit)
    """

    ITEMS = [
        ("scan", "discover"),
        ("settings", "settings"),
        ("update", "update"),
        ("exit", "exit"),
    ]

    def __init__(self, engine=None):
        super().__init__(engine, "home")
        self.selected = 0
        self.hosts = []
        self.scanning = False
        self.host_selected = 0
        self.toast = ""
        self.toast_until = 0

    def on_enter(self, params=None):
        log.info("home: on_enter, auto_update=%s", state.auto_update)
        if state.auto_update:
            self._check_pending_update()

    def _check_pending_update(self):
        if not self.engine:
            return
        def worker():
            try:
                from ..updater import check_for_update
                res = check_for_update(force=False)
            except Exception as exc:
                log.warning("auto-update check failed: %s", exc)
                return
            if res and self.engine:
                manifest, files = res
                log.info("auto-update popup: %s (%d files)", manifest.get("version"), len(files))
                self.engine.open_modal("update", {"manifest": manifest, "files": files})
        threading.Thread(target=worker, daemon=True).start()

    def get_header_title(self):
        return tr("app_title")

    def get_footer_actions(self):
        if self.hosts:
            return [("A", tr("connect")), ("B", tr("back")), ("START", tr("exit"))]
        return [("A", tr("connect")), ("B", tr("back")), ("START", tr("exit"))]

    def _start_scan(self):
        if self.scanning:
            return
        self.scanning = True
        self.toast = tr("scan_running")
        self.toast_until = time.time() + 6
        log.info("home: bat dau scan...")
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        try:
            hosts = chiaki.discovery_broadcast(timeout=3.0)
        except Exception as exc:
            log.error("scan exception: %s", exc)
            hosts = []
        self.hosts = hosts
        self.scanning = False
        if hosts:
            self.toast = tr("scan_done") % len(hosts)
            log.info("scan: %d host(s) %s",
                     len(hosts), [h.addr for h in hosts])
        else:
            self.toast = tr("scan_none")
            log.info("scan: khong thay host")
        self.toast_until = time.time() + 4

    def _start_stream(self, host):
        if not host:
            return
        log.info("home: yeu cau stream toi %s (%s)", host.name or host.addr, host.addr)
        profile = chiaki.video_profile_summary()
        self.toast = "%s [%s]" % (tr("stream_running") % host.name, profile)
        self.toast_until = time.time() + 3

    def handle_input(self, inputs):
        if not inputs:
            return False
        edges = inputs.get("edges", [])
        if self.hosts:
            if "btn_down" in edges:
                self.host_selected = (self.host_selected + 1) % len(self.hosts)
                return True
            if "btn_up" in edges:
                self.host_selected = (self.host_selected - 1) % len(self.hosts)
                return True
            if "btn_a" in edges:
                self._start_stream(self.hosts[self.host_selected])
                return True
            if "btn_b" in edges:
                self.hosts = []
                self.host_selected = 0
                return True
        if "btn_up" in edges:
            self.selected = (self.selected - 1) % len(self.ITEMS)
            return True
        if "btn_down" in edges:
            self.selected = (self.selected + 1) % len(self.ITEMS)
            return True
        if "btn_a" in edges:
            self._activate()
            return True
        if "btn_start" in edges or "quit" in edges:
            log.info("home: user exit")
            self.engine.quit()
            return True
        return False

    def _activate(self):
        key = self.ITEMS[self.selected][0]
        if key == "scan":
            self._start_scan()
        elif key == "settings":
            self.engine.push_screen("settings")
        elif key == "update":
            from ..updater import check_for_update
            threading.Thread(target=self._force_update_check, daemon=True).start()
        elif key == "exit":
            self.engine.quit()

    def _force_update_check(self):
        from ..updater import check_for_update
        res = check_for_update(force=True)
        if res:
            manifest, files = res
            self.engine.open_modal("update", {"manifest": manifest, "files": files})
        else:
            self.toast = tr("update_no_network")
            self.toast_until = time.time() + 3

    def update(self, dt):
        if self.toast and time.time() > self.toast_until:
            self.toast = ""

    def render(self, engine):
        engine.fill_rect(0, 64, engine.screen_w, engine.screen_h - 120, 13, 17, 28, 255)
        engine.draw_text(tr("app_subtitle"), engine.font_sub, 40, 90, 180, 195, 215)
        if self.hosts:
            self._render_hosts(engine)
        else:
            self._render_menu(engine)
        if self.toast:
            engine.fill_rect(40, engine.screen_h - 110, 720, 50, 20, 28, 46, 220)
            engine.draw_text(self.toast, engine.font_sub, 60, engine.screen_h - 100, 0, 230, 150)
        if self.scanning:
            engine.draw_text(tr("scanning"), engine.font_sub, engine.screen_w - 200,
                             engine.screen_h - 100, 180, 195, 215)

    def _render_menu(self, engine):
        y = 160
        for i, (key, label) in enumerate(self.ITEMS):
            col = (0, 230, 150) if i == self.selected else (40, 60, 90)
            engine.fill_rect(40, y, engine.screen_w - 80, 100, col[0], col[1], col[2], 240)
            engine.draw_text(tr(label), engine.font_title, 70, y + 20, 255, 255, 255)
            sub = tr(label + "_hint")
            if sub != label + "_hint":
                engine.draw_text(sub, engine.font_sub, 70, y + 60, 220, 225, 235)
            y += 110

    def _render_hosts(self, engine):
        engine.draw_text(tr("host"), engine.font_title, 40, 160, 255, 255, 255)
        y = 220
        for i, h in enumerate(self.hosts[:6]):
            col = (0, 230, 150) if i == self.host_selected else (40, 60, 90)
            engine.fill_rect(40, y, engine.screen_w - 80, 90, col[0], col[1], col[2], 240)
            label = "%s [%s]" % (h.name or "(no name)", h.state)
            engine.draw_text(label, engine.font_title, 60, y + 8, 255, 255, 255)
            sub = "%s | v%s | %s" % (h.addr, h.system_version or "?", h.running_app or "-")
            engine.draw_text(sub, engine.font_sub, 60, y + 50, 220, 225, 235)
            y += 100
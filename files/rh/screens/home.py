# -*- coding: utf-8 -*-
"""Man hinh chinh: nut quet may, nhap IP, BAT DAU CHOI, cai dat, cap nhat."""

import os
import threading
import time
from .. import state, chiaki
from ..i18n import tr
from .base import BaseScreen


class HomeScreen(BaseScreen):
    ITEMS = [
        ("scan", "discover"),
        ("settings", "settings"),
        ("update", "update"),
        ("exit", "exit"),
    ]

    def __init__(self, engine=None):
        super().__init__(engine, "home")
        self.selected = 0
        self.last_input = {}
        self.hosts = []
        self.scanning = False
        self.host_selected = 0
        self.overlay = None
        self.toast = ""
        self.toast_until = 0

    def on_enter(self, params=None):
        self._check_pending_update()

    def _check_pending_update(self):
        if not state.auto_update:
            return
        if not self.engine:
            return
        def worker():
            try:
                found = chiaki.check_for_update.__self__ if hasattr(chiaki.check_for_update, "__self__") else None
            except Exception:
                found = None
            from ..updater import check_for_update as _cfu
            res = _cfu(force=False)
            if res and self.engine:
                manifest, files = res
                self.engine.open_modal("update", {"manifest": manifest, "files": files})
        threading.Thread(target=worker, daemon=True).start()

    def get_header_title(self):
        return tr("app_title")

    def get_footer_actions(self):
        return [("A", tr("connect")), ("B", tr("back")), ("START", tr("exit"))]

    def _start_scan(self):
        if self.scanning:
            return
        self.scanning = True
        self.toast = tr("update_checking")
        self.toast_until = time.time() + 6
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        try:
            hosts = chiaki.discovery_broadcast(timeout=3.0)
        except Exception as exc:
            hosts = []
            print("scan failed: %s" % exc)
        self.hosts = hosts
        self.scanning = False
        if hosts:
            self.toast = tr("scan_done") % len(hosts)
        else:
            self.toast = tr("scan_none")
        self.toast_until = time.time() + 4

    def _start_stream(self, host):
        """Stub stream - ban 0.2.0 se goi chiaki.init_session / run_stream."""
        if not host:
            return
        self.toast = tr("stream_running") % host.name
        self.toast_until = time.time() + 3

    def handle_input(self, inputs):
        self.last_input = inputs
        if self.hosts:
            if inputs.get("btn_down"):
                self.host_selected = (self.host_selected + 1) % max(1, len(self.hosts))
                return True
            if inputs.get("btn_up"):
                self.host_selected = (self.host_selected - 1) % max(1, len(self.hosts))
                return True
            if inputs.get("btn_a"):
                self._start_stream(self.hosts[self.host_selected])
                return True
        if inputs.get("btn_up"):
            self.selected = (self.selected - 1) % len(self.ITEMS)
            return True
        if inputs.get("btn_down"):
            self.selected = (self.selected + 1) % len(self.ITEMS)
            return True
        if inputs.get("btn_a"):
            self._activate()
            return True
        if inputs.get("btn_start") or inputs.get("quit"):
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
            res = check_for_update(force=True)
            if res:
                manifest, files = res
                self.engine.open_modal("update", {"manifest": manifest, "files": files})
            else:
                self.toast = tr("update_no_network")
                self.toast_until = time.time() + 3
        elif key == "exit":
            self.engine.quit()

    def update(self, dt):
        if self.toast and time.time() > self.toast_until:
            self.toast = ""

    def render(self, engine):
        engine.fill_rect(0, 64, engine.screen_w, engine.screen_h - 120, 13, 17, 28, 255)
        engine.draw_text(tr("app_subtitle"), engine.font_sub, 40, 90,
                         180, 195, 215)
        if self.hosts:
            self._render_hosts(engine)
        else:
            self._render_menu(engine)
        if self.toast:
            engine.fill_rect(40, engine.screen_h - 110, 600, 50, 20, 28, 46, 220)
            engine.draw_text(self.toast, engine.font_sub, 60, engine.screen_h - 100,
                             0, 230, 150)

    def _render_menu(self, engine):
        y = 160
        for i, (key, label) in enumerate(self.ITEMS):
            x = 60
            col = (0, 230, 150) if i == self.selected else (40, 60, 90)
            engine.fill_rect(x, y, 360, 70, col[0], col[1], col[2], 240)
            engine.draw_text(tr(label), engine.font_title, x + 30, y + 12,
                             255, 255, 255)
            y += 90

    def _render_hosts(self, engine):
        engine.draw_text(tr("host"), engine.font_title, 40, 160, 255, 255, 255)
        y = 220
        for i, h in enumerate(self.hosts[:6]):
            col = (0, 230, 150) if i == self.host_selected else (40, 60, 90)
            engine.fill_rect(40, y, engine.screen_w - 80, 80, col[0], col[1], col[2], 240)
            label = "%s [%s]" % (h.name or h.addr, h.state)
            engine.draw_text(label, engine.font_title, 60, y + 8, 255, 255, 255)
            sub = "%s | v%s | %s" % (h.addr, h.system_version, h.running_app or "-")
            engine.draw_text(sub, engine.font_sub, 60, y + 48, 220, 225, 235)
            y += 90
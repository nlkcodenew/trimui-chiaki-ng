# -*- coding: utf-8 -*-
import time
from .. import state
from .. import chiaki
from ..i18n import tr
from ..logger import get_logger
from .base import BaseScreen
log = get_logger()
class PairScreen(BaseScreen):
    def __init__(self, engine=None):
        super().__init__(engine, "pair")
        self.host = None
        self.pin = ""
        self.status = ""
        self.pairing = False
        self.cursor = 0
    def on_enter(self, params=None):
        self.host = (params or {}).get("host")
        self.pin = ""
        self.status = tr("pair_enter_pin") if self.host else tr("pair_no_host")
        self.pairing = False
        self.cursor = 0
    def get_header_title(self):
        return tr("pair_title")
    def get_footer_actions(self):
        return [("A", tr("pair_start")), ("B", tr("back"))]
    def handle_input(self, inputs):
        edges = inputs.get("edges", []) if inputs else []
        if not edges: return False
        if "btn_b" in edges or "quit" in edges:
            self.engine.pop_screen()
            return True
        if "btn_up" in edges: self._digit_change(1); return True
        if "btn_down" in edges: self._digit_change(-1); return True
        if "btn_left" in edges: self.cursor = max(0, self.cursor-1); return True
        if "btn_right" in edges: self.cursor = min(7, self.cursor+1); return True
        if "btn_a" in edges: self._start_pair(); return True
        return False
    def _digit_change(self, d):
        while len(self.pin) < 8: self.pin += "0"
        lst = list(self.pin[:8])
        v = int(lst[self.cursor]) if lst[self.cursor].isdigit() else 0
        v = (v + d) % 10
        lst[self.cursor] = str(v)
        self.pin = "".join(lst)
    def _start_pair(self):
        if not self.host: self.status = tr("pair_no_host"); return
        pin = "".join(c for c in self.pin if c.isdigit())[:8]
        if len(pin) != 8: self.status = tr("pair_pin_invalid"); return
        if self.pairing: return
        self.pairing = True
        self.status = tr("pair_running") % getattr(self.host, "addr", "")
        import threading
        threading.Thread(target=self._do_pair, args=(pin,), daemon=True).start()
    def _do_pair(self, pin):
        try: ok, info = chiaki.regist_with_pin(self.host, pin)
        except Exception as e:
            log.error("pair exception: %s", e); self.status = tr("pair_failed") % e; self.pairing = False; return
        if ok:
            try:
                state.host_addr = self.host.addr
                state.host_name = getattr(self.host, "name", "") or self.host.addr
                state.regist_key = info.get("regist_key", pin)
                state.psn_account_id = info.get("rp_key", "")
                state.save_settings()
                import json, os
                from ..paths import APP_DIR
                ppath = os.path.join(APP_DIR, "paired_hosts.json")
                paired = []
                if os.path.isfile(ppath):
                    try: paired = json.load(open(ppath, "r", encoding="utf-8")) or []
                    except: paired = []
                paired = [h for h in paired if h.get("addr") != self.host.addr]
                paired.append({"addr": self.host.addr, "name": getattr(self.host, "name", ""), "is_ps5": bool(getattr(self.host, "is_ps5", False)), "regist_key": state.regist_key, "rp_key": state.psn_account_id})
                json.dump(paired, open(ppath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            except Exception as e: log.warning("pair save failed: %s", e)
            self.status = tr("pair_success")
            time.sleep(1)
            try: self.engine.pop_screen()
            except: pass
        else: self.status = tr("pair_failed") % (info.get("error", "unknown") if isinstance(info, dict) else str(info))
        self.pairing = False
    def render(self, engine):
        engine.fill_rect(0, 64, engine.screen_w, engine.screen_h - 120, 13, 17, 28, 255)
        if not self.host:
            engine.draw_text(self.status, engine.font_title, engine.screen_w//2, 200, 255, 100, 100, center_x=True); return
        title = "%s [%s]" % (self.host.name or "PS4", self.host.addr)
        engine.draw_text(title, engine.font_title, engine.screen_w//2, 140, 255, 255, 255, center_x=True)
        engine.draw_text(tr("pair_pin_label"), engine.font_sub, engine.screen_w//2, 210, 180, 195, 215, center_x=True)
        bw, bh, gap = 72, 86, 12
        total = 8*bw + 7*gap
        x0 = (engine.screen_w - total)//2
        y0 = 260
        disp = (self.pin + "00000000")[:8]
        for i, ch in enumerate(disp):
            x = x0 + i*(bw+gap)
            col = (0, 230, 150) if i == self.cursor else (40, 60, 90)
            engine.fill_rect(x, y0, bw, bh, col[0], col[1], col[2], 240)
            engine.draw_text(ch, engine.font_title, x+bw//2, y0+bh//2, 255, 255, 255, center_x=True, center_y=True)
        engine.draw_text(self.status, engine.font_sub, engine.screen_w//2, y0+120, 0, 230, 150, center_x=True)
        engine.draw_text(tr("pair_hint_input"), engine.font_sub, engine.screen_w//2, y0+160, 180, 195, 215, center_x=True)

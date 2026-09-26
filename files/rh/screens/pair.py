# -*- coding: utf-8 -*-
import time
from .. import state
from .. import chiaki
from ..i18n import tr
from ..logger import get_logger
from .base import BaseScreen
log = get_logger()
ACCOUNT_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

class PairScreen(BaseScreen):
    def __init__(self, engine=None):
        super().__init__(engine, "pair")
        self.host = None
        self.pin = ""
        self.status = ""
        self.pairing = False
        self.cursor = 0
        self.mode = "pin"
        self.account_id = ""
        self.diagnostic_code = ""
    def on_enter(self, params=None):
        self.host = (params or {}).get("host")
        self.pin = ""
        if self.host and getattr(self.host, "is_ps5", False):
            self.account_id = self._editable_account_id(
                getattr(state, "psn_account_id", ""))
            if self._valid_account_id(getattr(state, "psn_account_id", "")):
                self.mode = "pin"
                self.status = tr("pair_enter_pin_ps5")
            else:
                self.mode = "account_id"
                self.status = tr("pair_ps5_account_enter")
        else:
            self.mode = "pin"
            self.account_id = ""
            self.status = tr("pair_enter_pin") if self.host else tr("pair_no_host")
        self.pairing = False
        self.cursor = 0
        self.diagnostic_code = ""
    def get_header_title(self):
        return tr("pair_title")
    def get_footer_actions(self):
        if self._is_ps5() and self.mode == "account_id":
            return [("A", tr("pair_ps5_account_save")), ("B", tr("back"))]
        if self._is_ps5():
            return [("A", tr("pair_start")), ("X", tr("pair_ps5_account_edit")),
                    ("B", tr("back"))]
        return [("A", tr("pair_start")), ("B", tr("back"))]
    def handle_input(self, inputs):
        edges = inputs.get("edges", []) if inputs else []
        if not edges: return False
        if "btn_b" in edges or "quit" in edges:
            self.engine.pop_screen()
            return True
        if self._is_ps5() and self.mode == "account_id":
            if "btn_up" in edges: self._account_change(1); return True
            if "btn_down" in edges: self._account_change(-1); return True
            if "btn_left" in edges: self.cursor = max(0, self.cursor-1); return True
            if "btn_right" in edges: self.cursor = min(10, self.cursor+1); return True
            if "btn_a" in edges: self._save_account_id(); return True
            return False
        if self._is_ps5() and self.mode == "account_error":
            if "btn_a" in edges or "btn_x" in edges:
                self.mode = "account_id"
                self.cursor = 0
                self.status = tr("pair_ps5_account_enter")
                return True
            return False
        if self._is_ps5() and "btn_x" in edges:
            self.mode = "account_id"
            self.account_id = self._editable_account_id(state.psn_account_id)
            self.cursor = 0
            self.status = tr("pair_ps5_account_enter")
            self.diagnostic_code = ""
            return True
        if "btn_up" in edges: self._digit_change(1); return True
        if "btn_down" in edges: self._digit_change(-1); return True
        if "btn_left" in edges: self.cursor = max(0, self.cursor-1); return True
        if "btn_right" in edges: self.cursor = min(7, self.cursor+1); return True
        if "btn_a" in edges: self._start_pair(); return True
        return False
    def _is_ps5(self):
        return bool(self.host and getattr(self.host, "is_ps5", False))
    @staticmethod
    def _valid_account_id(value):
        try:
            from ..ps5_regist import normalize_account_id
            normalize_account_id(value)
            return True
        except Exception:
            return False
    @staticmethod
    def _editable_account_id(value):
        try:
            from ..ps5_regist import normalize_account_id
            return normalize_account_id(value)
        except Exception:
            return "?" * 11 + "="
    def _account_change(self, delta):
        chars = list((self.account_id or "A" * 11 + "=")[:12])
        while len(chars) < 12:
            chars.append("=" if len(chars) == 11 else "A")
        current = chars[self.cursor]
        try:
            index = ACCOUNT_ALPHABET.index(current)
        except ValueError:
            index = 0
        chars[self.cursor] = ACCOUNT_ALPHABET[(index + delta) % len(ACCOUNT_ALPHABET)]
        chars[11] = "="
        self.account_id = "".join(chars)
    def _save_account_id(self):
        from ..ps5_regist import PS5RegistError, diagnostic_code, normalize_account_id
        try:
            normalized = normalize_account_id(self.account_id)
        except PS5RegistError as exc:
            self.diagnostic_code = diagnostic_code(exc.stage)
            self.status = tr("pair_ps5_account_invalid")
            self.mode = "account_error"
            log.warning("PS5 Account-ID rejected: stage=%s code=%s length=%d",
                        exc.stage, self.diagnostic_code,
                        len(str(self.account_id or "")))
            self._report_error("pair_ps5_account_id")
            return
        state.psn_account_id = normalized
        if not state.save_settings():
            self.diagnostic_code = "PS5-AID-SAVE-01"
            self.status = tr("pair_ps5_account_save_failed")
            self.mode = "account_error"
            log.error("PS5 Account-ID save failed: code=%s", self.diagnostic_code)
            self._report_error("pair_ps5_account_save_failed")
            return
        log.info("PS5 Account-ID accepted: bytes=8 base64_length=12")
        self.mode = "pin"
        self.pin = ""
        self.cursor = 0
        self.diagnostic_code = ""
        self.status = tr("pair_enter_pin_ps5")
    def _digit_change(self, d):
        while len(self.pin) < 8: self.pin += "0"
        lst = list(self.pin[:8])
        v = int(lst[self.cursor]) if lst[self.cursor].isdigit() else 0
        v = (v + d) % 10
        lst[self.cursor] = str(v)
        self.pin = "".join(lst)
    def _start_pair(self):
        if not self.host: self.status = tr("pair_no_host"); return
        if self._is_ps5() and not self._valid_account_id(state.psn_account_id):
            self.mode = "account_id"
            self.account_id = self._editable_account_id(state.psn_account_id)
            self.cursor = 0
            self.status = tr("pair_ps5_account_invalid")
            self.diagnostic_code = "PS5-AID-01"
            self._report_error("pair_ps5_account_id")
            return
        pin = "".join(c for c in self.pin if c.isdigit())[:8]
        if len(pin) != 8:
            self.status = tr("pair_pin_invalid")
            self._report_error("pair_pin_invalid")
            return
        if self.pairing: return
        self.pairing = True
        self.status = tr("pair_running") % getattr(self.host, "addr", "")
        import threading
        threading.Thread(target=self._do_pair, args=(pin,), daemon=True).start()
    def _do_pair(self, pin):
        try: ok, info = chiaki.regist_with_pin(self.host, pin)
        except Exception as e:
            log.error("pair exception: %s", e)
            self._report_error("pair_screen_exception")
            self.status = tr("pair_failed") % e; self.pairing = False; return
        if ok:
            try:
                state.host_addr = self.host.addr
                state.host_name = info.get("name") or getattr(self.host, "name", "") or self.host.addr
                state.host_target = int(info.get("target", 0) or 0)
                state.regist_key = info["regist_key"]
                state.rp_key = info["rp_key"]
                state.rp_key_type = int(info.get("rp_key_type", 0))
                state.server_mac = info.get("server_mac", "")
                if not state.save_settings():
                    raise OSError("settings save failed")
                import json, os
                from ..paths import APP_DIR
                ppath = os.path.join(APP_DIR, "paired_hosts.json")
                paired = []
                if os.path.isfile(ppath):
                    try: paired = json.load(open(ppath, "r", encoding="utf-8")) or []
                    except: paired = []
                paired = [h for h in paired if h.get("addr") != self.host.addr]
                paired.append({
                    "addr": self.host.addr,
                    "name": state.host_name,
                    "is_ps5": bool(getattr(self.host, "is_ps5", False)),
                    "target": int(info.get("target", state.host_target or 0)),
                    "regist_key": state.regist_key,
                    "rp_key": state.rp_key,
                    "rp_key_type": state.rp_key_type,
                    "server_mac": state.server_mac,
                })
                temp_path = ppath + ".tmp"
                with open(temp_path, "w", encoding="utf-8") as handle:
                    json.dump(paired, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, ppath)
            except Exception as e:
                log.error("pair save failed: %s", e)
                self._report_error("pair_save_failed")
                self.status = tr("pair_failed") % "không lưu được khóa"
                self.pairing = False
                return
            self.status = tr("pair_success")
            time.sleep(1)
            try: self.engine.pop_screen()
            except: pass
        else:
            if isinstance(info, dict):
                self.diagnostic_code = info.get("code", "")
                stage = info.get("stage", "")
                if self._is_ps5() and stage:
                    self.status = tr("pair_ps5_stage_failed") % stage
                else:
                    self.status = tr("pair_failed") % info.get("error", "unknown")
            else:
                self.status = tr("pair_failed") % str(info)
        self.pairing = False
    @staticmethod
    def _report_error(reason):
        try:
            from ..log_uploader import queue_diagnostic
            queue_diagnostic(reason)
        except Exception as exc:
            log.warning("cannot queue diagnostic %s: %s", reason, exc)
    def render(self, engine):
        engine.fill_rect(0, 64, engine.screen_w, engine.screen_h - 120, 13, 17, 28, 255)
        if not self.host:
            engine.draw_text(self.status, engine.font_title, engine.screen_w//2, 200, 255, 100, 100, center_x=True); return
        title = "%s [%s]" % (self.host.name or "PS4", self.host.addr)
        engine.draw_text(title, engine.font_title, engine.screen_w//2, 140, 255, 255, 255, center_x=True)
        if self._is_ps5() and self.mode == "account_id":
            self._render_account_id(engine)
            return
        if self._is_ps5() and self.mode == "account_error":
            self._render_account_error(engine)
            return
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
        engine.draw_text(self.status, engine.font_sub, engine.screen_w//2, y0+115, 0, 230, 150, center_x=True)
        if getattr(self.host, "is_ps5", False):
            engine.draw_text(tr("pair_ps5_account_ready"), engine.font_sub,
                             engine.screen_w//2, y0+150, 220, 225, 235, center_x=True)
            if self.diagnostic_code:
                engine.draw_text(tr("pair_ps5_report_code") % (
                    self.diagnostic_code, getattr(state, "device_id", "CHI-????")),
                    engine.font_sub, engine.screen_w//2, y0+185,
                    255, 190, 80, center_x=True)
        else:
            engine.draw_text(tr("pair_hint_input"), engine.font_sub,
                             engine.screen_w//2, y0+160, 180, 195, 215, center_x=True)
    def _render_account_id(self, engine):
        engine.draw_text(tr("pair_ps5_account_title"), engine.font_title,
                         engine.screen_w//2, 200, 255, 255, 255, center_x=True)
        engine.draw_text(tr("pair_ps5_account_help"), engine.font_sub,
                         engine.screen_w//2, 245, 180, 195, 215, center_x=True)
        box_w, box_h, gap = 68, 72, 8
        total = 12 * box_w + 11 * gap
        x0 = (engine.screen_w - total) // 2
        y0 = 300
        value = (self.account_id or "?" * 11 + "=")[:12]
        for index, char in enumerate(value):
            x = x0 + index * (box_w + gap)
            selected = index == self.cursor and index < 11
            color = (0, 230, 150) if selected else (40, 60, 90)
            engine.fill_rect(x, y0, box_w, box_h, color[0], color[1], color[2], 240)
            engine.draw_text(char, engine.font_title, x + box_w//2, y0 + box_h//2,
                             255, 255, 255, center_x=True, center_y=True)
        engine.draw_text(tr("pair_ps5_account_controls"), engine.font_sub,
                         engine.screen_w//2, y0 + 145, 220, 225, 235, center_x=True)
        engine.draw_text(self.status, engine.font_sub, engine.screen_w//2,
                         y0 + 105, 0, 230, 150, center_x=True)
        engine.draw_text(tr("pair_ps5_account_private"), engine.font_sub,
                         engine.screen_w//2, y0 + 180, 255, 190, 80, center_x=True)
        if self.diagnostic_code:
            engine.draw_text(tr("pair_ps5_report_code") % (
                self.diagnostic_code, getattr(state, "device_id", "CHI-????")),
                engine.font_sub, engine.screen_w//2, y0 + 215,
                255, 120, 120, center_x=True)
    def _render_account_error(self, engine):
        engine.draw_text(tr("pair_ps5_account_error_title"), engine.font_title,
                         engine.screen_w//2, 230, 255, 120, 120, center_x=True)
        engine.draw_text(self.status, engine.font_sub, engine.screen_w//2,
                         300, 220, 225, 235, center_x=True)
        engine.draw_text(tr("pair_ps5_report_code") % (
            self.diagnostic_code, getattr(state, "device_id", "CHI-????")),
            engine.font_title, engine.screen_w//2, 370,
            255, 190, 80, center_x=True)
        engine.draw_text(tr("pair_ps5_account_error_help"), engine.font_sub,
                         engine.screen_w//2, 430, 220, 225, 235, center_x=True)
        engine.draw_text(tr("pair_ps5_account_hidden"), engine.font_sub,
                         engine.screen_w//2, 475, 180, 195, 215, center_x=True)

# -*- coding: utf-8 -*-
"""Logger rolling 2 file cho trimui-chiaki-ng.

Hai file log, moi file < 256 KB, xoay vong khi qua nguong:

    $APP_DIR/Chiaki-loi.txt   - error + warning (giu lau, toi da 3 file backup)
    $APP_DIR/Chiaki-debug.log - info + debug (xoay vong, chi giu 1 file)

Format: YYYY-MM-DD HH:MM:SS.mmm | LEVEL | thread | message
        [2026-09-19 11:30:00.123] [INFO ] [MainThread] chiaki: init ok

Bat ky tu nao goi logger.info() / .warning() / .error() / .debug() deu rot vao
ca 2 file neu level tuong ung. settings.json dieu khien:

    "enable_logging": true   -> .debug() cung duoc ghi
    "enable_logging": false  -> chi ghi info/warning/error

`--log` o launch.sh ep nguon file log khac (dung khi user muon gui log cho dev).
"""

import logging
import logging.handlers
import os
import sys
import threading
import time

from .paths import APP_DIR


_DEFAULT_ERR = os.path.join(APP_DIR, "Chiaki-loi.txt")
_DEFAULT_DBG = os.path.join(APP_DIR, "Chiaki-debug.log")

_init_lock = threading.Lock()
_inited = False
_logger = None



def _env_enable_logging():
    """Tra ve True neu user bat enable_logging trong settings.json."""
    cfg_path = os.path.join(APP_DIR, "settings.json")
    if not os.path.isfile(cfg_path):
        return False
    try:
        import json
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return bool(cfg.get("enable_logging", False))
    except Exception:
        return False


def _detect_log_paths():
    """Neu settings.json co log_path_overrides thi dung, nguoc lai ghi vao
    $APP_DIR. Tra ve (err_path, dbg_path)."""
    cfg_path = os.path.join(APP_DIR, "settings.json")
    err = _DEFAULT_ERR
    dbg = _DEFAULT_DBG
    if not os.path.isfile(cfg_path):
        return err, dbg
    try:
        import json
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        env_err = os.environ.get("CHIAKI_LOG_ERR")
        env_dbg = os.environ.get("CHIAKI_LOG_DBG")
        if env_err:
            err = env_err
        if env_dbg:
            dbg = env_dbg
        if isinstance(cfg, dict):
            if "log_err_path" in cfg and isinstance(cfg["log_err_path"], str):
                err = cfg["log_err_path"]
            if "log_dbg_path" in cfg and isinstance(cfg["log_dbg_path"], str):
                dbg = cfg["log_dbg_path"]
    except Exception:
        pass
    return err, dbg


class _TrimFile:
    """File handler don gian co size cap, khong dung logging.FileHandler de
    giu compat voi cac Python cu (3.8)."""

    def __init__(self, path, max_bytes=256 * 1024, backups=1):
        self.path = path
        self.max_bytes = max_bytes
        self.backups = backups
        self._fh = None
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            self._fh = open(path, "a", encoding="utf-8")
        except OSError:
            self._fh = None

    def write(self, msg):
        if self._fh is None:
            return
        try:
            self._fh.write(msg)
            self._fh.flush()
        except OSError:
            return
        try:
            if self._fh.tell() > self.max_bytes:
                self._rotate()
        except OSError:
            pass

    def _rotate(self):
        try:
            self._fh.close()
        except Exception:
            pass
        for i in range(self.backups, 0, -1):
            src = "%s.%d" % (self.path, i)
            dst = "%s.%d" % (self.path, i + 1)
            if os.path.exists(src):
                try:
                    if i == self.backups:
                        os.remove(src)
                except OSError:
                    pass
                try:
                    os.replace(src, dst)
                except OSError:
                    pass
        try:
            os.replace(self.path, "%s.1" % self.path)
        except OSError:
            pass
        try:
            self._fh = open(self.path, "w", encoding="utf-8")
        except OSError:
            self._fh = None

    def close(self):
        if self._fh:
            try:
                self._fh.close()
            except OSError:
                pass


_lock = threading.Lock()


def init_logger():
    global _inited, _logger
    with _init_lock:
        if _inited:
            return
        _inited = True

        err_path, dbg_path = _detect_log_paths()

        # cho phep settings.enable_logging (load sau trong state), nhung o day
        # ta default = INFO. State.update_log_level() se nang level len DEBUG
        # neu user bat enable_logging.
        root = logging.getLogger("trimui-chiaki-ng")
        root.setLevel(logging.INFO)
        root.propagate = False
        for h in list(root.handlers):
            root.removeHandler(h)

        err_fh = _TrimFile(err_path, max_bytes=256 * 1024, backups=3)
        dbg_fh = _TrimFile(dbg_path, max_bytes=512 * 1024, backups=1)

        class _FanOut:
            def __init__(self, err, dbg):
                self.err = err
                self.dbg = dbg
                self.min_dbg = logging.DEBUG

            def write(self, m):
                self.err.write(m)
            def flush(self):
                pass

        fmt_err = logging.Formatter("[%(asctime)s.%(msecs)03d] [%(levelname)-5s] [%(threadName)-12s] %(message)s",
                                     datefmt="%Y-%m-%d %H:%M:%S")
        fmt_dbg = logging.Formatter("[%(asctime)s.%(msecs)03d] [%(levelname)-5s] [%(threadName)-12s] [%(name)s] %(message)s",
                                    datefmt="%Y-%m-%d %H:%M:%S")
        # Error log chi nhan warning/error. Debug log nhan toan bo level khi
        # enable_logging=True; logger root se chan DEBUG khi tuy chon nay tat.
        eh = logging.StreamHandler(_FanOut(err_fh, dbg_fh))
        eh.setLevel(logging.WARNING)
        eh.setFormatter(fmt_err)
        root.addHandler(eh)

        dh = logging.StreamHandler(_FanOut(dbg_fh, err_fh))
        dh.setLevel(logging.DEBUG)
        dh.setFormatter(fmt_dbg)
        root.addHandler(dh)

        _logger = root

        # stderr handler luon chi warning+
        if sys.stderr and getattr(sys.stderr, "isatty", lambda: False)():
            sh = logging.StreamHandler(sys.stderr)
            sh.setLevel(logging.WARNING)
            sh.setFormatter(fmt_err)
            root.addHandler(sh)

        # Cap nhat level theo settings.enable_logging
        root.setLevel(logging.DEBUG if _env_enable_logging() else logging.INFO)
        root.info("logger inited: err=%s dbg=%s", err_path, dbg_path)


def get_logger():
    if not _inited:
        init_logger()
    return logging.getLogger("trimui-chiaki-ng")


def set_debug_level(enabled):
    log = get_logger()
    log.setLevel(logging.DEBUG if enabled else logging.INFO)
    log.info("log level -> %s", "DEBUG" if enabled else "INFO")


def log(*args, level=logging.INFO):
    """Ham compat nguoc cho code cu. Moi truong hop moi nen dung get_logger()."""
    log_obj = get_logger()
    log_obj.log(level, " ".join(str(a) for a in args))


def shutdown():
    log = get_logger()
    for h in list(log.handlers):
        try:
            h.close()
        except Exception:
            pass
        log.removeHandler(h)

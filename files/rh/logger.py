# -*- coding: utf-8 -*-
"""Logger rolling 2 file cho trimui-chiaki-ng.

Hai file log duoc xoay vong khi qua nguong:

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
_PENDING_LOG_UPLOAD = os.path.join(APP_DIR, ".pending_crash")
_ERR_MAX_BYTES = 256 * 1024
_DBG_MAX_BYTES = 512 * 1024
_ERR_BACKUPS = 3
_DBG_BACKUPS = 1

_init_lock = threading.Lock()
_file_lock = threading.RLock()
_inited = False
_logger = None
_trim_files = []



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
        with _file_lock:
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
        with _file_lock:
            if self._fh:
                try:
                    self._fh.close()
                except OSError:
                    pass
                self._fh = None

    def clear(self):
        with _file_lock:
            self.close()
            for index in range(1, self.backups + 2):
                try:
                    os.remove("%s.%d" % (self.path, index))
                except OSError:
                    pass
            try:
                self._fh = open(self.path, "w", encoding="utf-8")
            except OSError:
                self._fh = None


_lock = threading.Lock()


def init_logger():
    global _inited, _logger, _trim_files
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

        err_fh = _TrimFile(err_path, max_bytes=_ERR_MAX_BYTES, backups=_ERR_BACKUPS)
        dbg_fh = _TrimFile(dbg_path, max_bytes=_DBG_MAX_BYTES, backups=_DBG_BACKUPS)
        _trim_files = [err_fh, dbg_fh]

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


def _file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _log_candidates():
    err_path, dbg_path = _detect_log_paths()
    paths = [(err_path, _ERR_BACKUPS), (dbg_path, _DBG_BACKUPS)]
    stderr_path = os.environ.get("CHIAKI_STDERR_LOG", "")
    known = {os.path.abspath(err_path), os.path.abspath(dbg_path)}
    if stderr_path and os.path.abspath(stderr_path) not in known:
        paths.append((stderr_path, _ERR_BACKUPS))
    return paths


def runtime_log_size():
    total = 0
    for path, backups in _log_candidates():
        total += _file_size(path)
        for index in range(1, backups + 2):
            total += _file_size("%s.%d" % (path, index))
    return total


def _truncate_path(path):
    absolute = os.path.abspath(path)
    try:
        stderr_target = os.path.abspath(os.path.realpath("/proc/self/fd/2"))
    except OSError:
        stderr_target = ""
    if stderr_target == absolute:
        try:
            os.ftruncate(2, 0)
            os.lseek(2, 0, os.SEEK_SET)
            return True
        except OSError:
            pass
    try:
        with open(path, "w", encoding="utf-8"):
            pass
        return True
    except OSError:
        return False


def clear_runtime_logs(protect_pending=True):
    """Xoa log va backup, nhung khong lam mat report dang cho upload."""
    if protect_pending and os.path.exists(_PENDING_LOG_UPLOAD):
        return False, "pending", 0
    removed_bytes = runtime_log_size()
    active_paths = set()
    with _file_lock:
        for trim_file in _trim_files:
            active_paths.add(os.path.abspath(trim_file.path))
            trim_file.clear()
        for path, backups in _log_candidates():
            if os.path.abspath(path) not in active_paths:
                _truncate_path(path)
            for index in range(1, backups + 2):
                try:
                    os.remove("%s.%d" % (path, index))
                except OSError:
                    pass
    get_logger().info("logs cleared by user; removed_bytes=%d", removed_bytes)
    return True, "cleared", removed_bytes


def _keep_tail(path, max_bytes):
    temp = path + ".trim"
    try:
        if os.path.getsize(path) <= max_bytes:
            return False
        with open(path, "rb") as handle:
            handle.seek(-max_bytes, os.SEEK_END)
            data = handle.read()
        newline = data.find(b"\n")
        if newline >= 0:
            data = data[newline + 1:]
        with open(temp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        return True
    except OSError:
        try:
            os.remove(temp)
        except OSError:
            pass
        return False


def cap_runtime_logs():
    """Giu phan cuoi log native sau stream de file khong tang vo han."""
    err_path, dbg_path = _detect_log_paths()
    limits = {
        os.path.abspath(err_path): _ERR_MAX_BYTES,
        os.path.abspath(dbg_path): _DBG_MAX_BYTES,
    }
    changed = False
    for path, _ in _log_candidates():
        max_bytes = limits.get(os.path.abspath(path), _ERR_MAX_BYTES)
        changed = _keep_tail(path, max_bytes) or changed
    return changed


def shutdown():
    global _inited, _logger, _trim_files
    log = get_logger()
    for h in list(log.handlers):
        try:
            h.close()
        except Exception:
            pass
        log.removeHandler(h)
    for trim_file in _trim_files:
        trim_file.close()
    _trim_files = []
    _logger = None
    _inited = False


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if argv == ["--cap-runtime"]:
        cap_runtime_logs()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

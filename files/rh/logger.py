# -*- coding: utf-8 -*-
"""Log ra file Chiaki-loi.txt o goc the, giong RetroHub."""

import os
import sys
import threading
from .paths import APP_DIR, LOG_DIR

_lock = threading.Lock()
_init = False
_f = None


def init_logger():
    global _init, _f
    if _init:
        return
    _init = True
    path = os.path.join(LOG_DIR, "Chiaki-loi.txt")
    try:
        _f = open(path, "a", encoding="utf-8")
    except OSError:
        _f = None


def log(*args):
    if _f is None:
        return
    msg = " ".join(str(a) for a in args)
    with _lock:
        try:
            _f.write("%s %s\n" % (_stamp(), msg))
            _f.flush()
        except OSError:
            pass


def _stamp():
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")
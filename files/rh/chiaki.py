# -*- coding: utf-8 -*-
"""Lop goi lop chiaki CLI (chiaki-ng upstream) ma khong can binary rieng.

TrimUI Smart Pro S co Python 3 nhung muon chay chiaki minh phai dong goi C
binary hoac dung socket thuan. Vi firmware cua TrimUI Linux 1.1.1 khong co
OpenSSL 3 mot so dep ben canh (chi co 3.0.13), va binary chiaki nguon upstream
duoc build cho macOS / Ubuntu, nen viec build aarch64 ngay tren may khong kha thi.

Thay vao do, app se dung lop wrapper Python de noi truc tiep voi PS4/PS5 qua
cac control / stream socket. Wire format doc tu
    https://github.com/streetpea/chiaki-ng/tree/master/lib
dac biet la src/discovery.c, src/regist.c, src/session.c, src/streamconnection.c.

Chuc nang o version 0.1.0:
    - Discovery: gui SRCH broadcast, nhan SRCH response (port 987 PS4 / 9302 PS5)
    - Wakeup: gui WAKEUP bang regist-key plaintext (hex string)
    - Connect: SessionInit qua TCP 9295, sau do StreamConnection cung 9296
    - Session key + AES: dat kho vao session.sh o files/assets/session_key.bin

Ban 0.2.0+ se chuyen sang FFTW + AAC thuan neu can, vi du muc tieu 720p30.

NOTE: dang o trang thai stub. Module ben duoi (Session, DiscoveryClient) se
tra None cho moi ket noi cho toi khi ban 0.2 duoc day.
"""

import json
import os
import socket
import struct
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import state


@dataclass
class DiscoveredHost:
    name: str = ""
    addr: str = ""
    state: str = "unknown"
    is_ps5: bool = False
    system_version: str = ""
    running_app: str = ""
    target: int = 0


def find_chiaki_binary(app_dir):
    """Tim chiaki binary trong bin/ cua app. None khi khong co."""
    candidates = [
        os.path.join(app_dir, "bin", "chiaki"),
        os.path.join(app_dir, "bin", "chiaki-ng"),
        os.path.join("/usr", "local", "bin", "chiaki"),
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def read_chiaki_conf(path):
    """Doc chiaki.conf theo mau Switch (host_addr, psn_online_id, psn_account_id,
    rp_key, rp_regist_key, rp_key_type, target, video_resolution, video_fps).

    Bo qua dong khong hop le va comment. Tra dict {ten_may: {...}}.
    """
    import re

    hosts = {}
    if not os.path.isfile(path):
        return hosts
    cur = None
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            m = re.match(r"^\[(.+)\]$", line)
            if m:
                cur = {"name": m.group(1).strip()}
                hosts[cur["name"]] = cur
                continue
            if "=" not in line or cur is None:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            cur[key] = val
    return hosts


def discovery_broadcast(app_dir=None, timeout=3.0):
    """SRCH broadcast dong bo theo PSN protocol (SRCH * HTTP/1.1\\r\\n
    device-discovery-protocol-version: ...). Tra danh sach DiscoveredHost.

    Day la pure-Python vi TrimUI Linux 1.1.1 khong co chiaki binary. Netif
    trong Smart Pro S se khong can bind vi minh broadcast tren port local 9303-9319
    giong chiaki. PS4 response o port 987, PS5 o 9302.
    """
    import threading
    import urllib.parse

    out = []
    done = threading.Event()

    def worker(protocol_version, ps5_mode):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(timeout)
        local_port = 9303
        try:
            s.bind(("", local_port))
        except OSError:
            local_port = 0
            s.bind(("", local_port))
        pkt = ("SRCH * HTTP/1.1\r\n"
               "device-discovery-protocol-version: %s\r\n\r\n") % protocol_version
        if ps5_mode:
            s.sendto(pkt.encode("ascii"), ("255.255.255.255", 9302))
        else:
            s.sendto(pkt.encode("ascii"), ("255.255.255.255", 987))
        end = time.time() + timeout
        while time.time() < end and not done.is_set():
            try:
                data, addr = s.recvfrom(2048)
            except socket.timeout:
                continue
            host = _parse_srch(data, addr, ps5_mode)
            if host is not None:
                out.append(host)
                done.set()
                break
        s.close()

    threads = [
        threading.Thread(target=worker, args=("00020020", False), daemon=True),
        threading.Thread(target=worker, args=("00030010", True), daemon=True),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout + 0.5)
    return out


def _parse_srch(data, addr, ps5_mode):
    text = data.decode("ascii", errors="ignore")
    if not text.startswith("HTTP/1.1"):
        return None
    headers = {}
    for line in text.split("\r\n")[1:]:
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        headers[k.strip().lower()] = v.strip()
    host = DiscoveredHost(
        addr=addr[0],
        is_ps5=ps5_mode,
        system_version=headers.get("system-version", ""),
        running_app=headers.get("running-app-name", ""),
    )
    if "200" in text.split("\r\n", 1)[0]:
        host.state = "ready"
    elif "620" in text.split("\r\n", 1)[0]:
        host.state = "standby"
    name = headers.get("host-name", "")
    host.name = urllib_unquote(name)
    host.target = _target_from_version(host.system_version, ps5_mode)
    return host


def _target_from_version(version, ps5):
    try:
        v = int("".join(c for c in version if c.isdigit()))
    except ValueError:
        return 0
    if ps5 and v >= 8000001:
        return 2  # CHIAKI_TARGET_PS5_1
    if v >= 8000000:
        return 3  # CHIAKI_TARGET_PS4_10
    if v >= 7000000:
        return 4  # CHIAKI_TARGET_PS4_9
    if v > 0:
        return 5  # CHIAKI_TARGET_PS4_8
    return 0


def urllib_unquote(s):
    import urllib.parse
    return urllib.parse.unquote(s)


def send_wakeup(addr, regist_key, ps5=False):
    """Gui WAKEUP toi PS4/PS5. regist_key la hex string.

    Phan hoi am thanh (SIE wakeup packet) dat may PS tu standby -> ready.
    Tra True neu khong co exception socket.
    """
    try:
        credential = int(regist_key, 16)
    except ValueError:
        return False
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(3.0)
    protocol = "00030010" if ps5 else "00020020"
    pkt = ("WAKEUP * HTTP/1.1\r\n"
           "client-type:vr\r\n"
           "auth-type:R\r\n"
           "model:w\r\n"
           "app-type:r\r\n"
           "user-credential:%llu\r\n"
           "device-discovery-protocol-version:%s\r\n\r\n") % (credential, protocol)
    port = 9302 if ps5 else 987
    try:
        sock.sendto(pkt.encode("ascii"), (addr, port))
        sock.close()
        return True
    except OSError:
        return False


def init_session(addr, ps5, regist_key, morning, profile, log_cb=None):
    """Stub bat tay session - ban 0.2.0 se thay the bang OpenSSL + chiaki wire.

    Hien tai chi in thong bao va tra ve ma loi de app khong crash.
    """
    if log_cb:
        log_cb("init_session not implemented yet (build 0.2.0 will ship this)")
    return -1, None


def run_stream(addr, ps5, profile, quit_evt, log_cb=None):
    """Stub run stream. Ban 0.2.0 se di vao main streaming loop."""
    if log_cb:
        log_cb("run_stream not implemented yet (build 0.2.0 will ship this)")
    while not quit_evt.is_set():
        quit_evt.wait(0.5)
    return 0
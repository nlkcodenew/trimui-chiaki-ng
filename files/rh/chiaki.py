# -*- coding: utf-8 -*-
"""Lop wire protocol cho trimui-chiaki-ng.

Bao gom:
    - Discovery SRCH broadcast, response parse (port 987 PS4 / 9302 PS5)
    - Wakeup WAKEUP voi regist-key plaintext
    - Connect RPCrypt den controller port 9295 (PS4/PS5)
    - Doc chiaki.conf theo mau Switch (host_addr, psn_account_id, rp_key, rp_regist_key,
      rp_key_type, video_resolution, video_fps, target)

Crypto va session init van de~ dang o upstream chiaki-ng. v0.2.0 se build lib
C aarch64 hoac dung OpenSSL 3.0.13 (san trong firmware TrimUI Linux 1.1.1) de
thuc thi cac buoc tiep theo:

    chiaki_session_init
    chiaki_session_start
    chiaki_session_set_controller_state
    chiaki_session_set_video_sample_cb

Hien tai cac ham chi in log va tra ve ma loi de app khong crash.
"""

import json
import os
import socket
import struct
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import state
from .logger import get_logger

log = get_logger()


@dataclass
class DiscoveredHost:
    name: str = ""
    addr: str = ""
    state: str = "unknown"
    is_ps5: bool = False
    system_version: str = ""
    running_app: str = ""
    target: int = 0
    host_request_port: int = 9295


def find_chiaki_binary(app_dir):
    """Tim chiaki binary trong bin/ cua app. None khi khong co."""
    candidates = [
        os.path.join(app_dir, "bin", "chiaki"),
        os.path.join(app_dir, "bin", "chiaki-ng"),
        os.path.join("/usr", "local", "bin", "chiaki"),
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            log.info("chiaki binary found: %s", path)
            return path
    log.debug("chiaki binary not bundled, using pure python shim")
    return None


def read_chiaki_conf(path=None):
    """Doc chiaki.conf theo mau Switch.

    File mau:
        [PS5-xxx]
        host_addr = 192.168.1.10
        psn_online_id = user
        psn_account_id = base64==
        rp_key = base64==
        rp_regist_key = abcdef12
        rp_key_type = 2
        target = 2

        video_resolution = 720p
        video_fps = 30

    Tra dict {ten_may: {key: value}}. Gia tri duoc strip va bo dau ngoac kep.
    """
    import re

    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "chiaki.conf")
        path = os.path.abspath(path)

    hosts = {}
    if not os.path.isfile(path):
        log.debug("chiaki.conf khong ton tai: %s", path)
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
    log.info("chiaki.conf parsed: %d host(s) from %s", len(hosts), path)
    return hosts


def write_chiaki_conf(hosts, path=None):
    """Ghi chiaki.conf (format giong Switch, dung de dump cho debug)."""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "chiaki.conf")
        path = os.path.abspath(path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            for name, h in hosts.items():
                f.write("[%s]\n" % name)
                for k in ("host_addr", "psn_online_id", "psn_account_id",
                         "rp_key", "rp_regist_key", "rp_key_type",
                         "target", "video_resolution", "video_fps"):
                    if k in h and h[k]:
                        f.write("%s = \"%s\"\n" % (k, h[k]))
                f.write("\n")
        log.info("chiaki.conf written: %s", path)
        return True
    except OSError as exc:
        log.warning("chiaki.conf write failed: %s", exc)
        return False


# Cong discovery theo upstream chiaki (lib/include/chiaki/discovery.h).
# DAY LA CONG DICH ma PS4/PS5 lang nghe goi SRCH. Truoc v0.2.11 code gui SRCH
# toi chinh cong nguon 9303-9308 nen khong bao gio toi duoc may PS -> luon 0 host.
PS4_DISCOVERY_PORT = 987
PS5_DISCOVERY_PORT = 9302
PS4_PROTOCOL_VERSION = "00020020"
PS5_PROTOCOL_VERSION = "00030010"
# Khoang cong nguon cuc bo de bind va nhan phan hoi (PS tra loi ve dung cong nguon).
LOCAL_PORT_MIN = 9303
LOCAL_PORT_MAX = 9319


def _build_srch(protocol_version):
    """Goi SRCH, giong het chiaki_discovery_packet_fmt cua upstream.

    Upstream dinh dang: "SRCH * HTTP/1.1\\ndevice-discovery-protocol-version:%s\\n"
    (dung '\\n', khong co dau cach sau ':') va gui kem byte null cuoi (sendto len+1).
    """
    body = "SRCH * HTTP/1.1\ndevice-discovery-protocol-version:%s\n" % protocol_version
    return body.encode("ascii") + b"\x00"


def _parse_srch(data, addr, ps5_mode):
    try:
        text = data.decode("ascii", errors="ignore")
    except Exception:
        return None
    # Parser upstream (chiaki_http_header_parse) chap nhan ca '\r' va '\n'.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith("HTTP/1.1"):
        return None
    lines = text.split("\n")
    status_line = lines[0]
    headers = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        headers[k.strip().lower()] = v.strip()
    # Ma HTTP: 200 = ready, 620 = standby (chiaki_discovery_srch_response_parse).
    host_state = "unknown"
    parts = status_line.split()
    if len(parts) >= 2:
        try:
            code = int(parts[1])
        except ValueError:
            code = 0
        if code == 200:
            host_state = "ready"
        elif code == 620:
            host_state = "standby"
    try:
        req_port = int(headers.get("host-request-port", "9295") or "9295")
    except ValueError:
        req_port = 9295
    host = DiscoveredHost(
        addr=addr[0],
        is_ps5=ps5_mode,
        state=host_state,
        system_version=headers.get("system-version", ""),
        running_app=urllib.parse.unquote(headers.get("running-app-name", "")),
        host_request_port=req_port,
    )
    host.name = urllib.parse.unquote(headers.get("host-name", ""))
    host.target = _target_from_version(host.system_version, ps5_mode)
    return host


def _target_from_version(version, ps5):
    # chiaki_discovery_host_system_version_target: PS5 >= 8050001 -> PS5_1.
    digits = "".join(c for c in version if c.isdigit())
    try:
        v = int(digits) if digits else 0
    except ValueError:
        return 0
    if ps5 and v >= 8050001:
        return 2  # CHIAKI_TARGET_PS5_1
    if v >= 8000000:
        return 3  # CHIAKI_TARGET_PS4_10
    if v >= 7000000:
        return 4  # CHIAKI_TARGET_PS4_9
    if v > 0:
        return 5  # CHIAKI_TARGET_PS4_8
    return 0


def discovery_broadcast(timeout=3.0):
    """SRCH broadcast theo PSN protocol. Tra danh sach DiscoveredHost.

    Dung protocol upstream chiaki:
        - Gui SRCH toi cong dich 987 (PS4) va 9302 (PS5).
        - Socket nguon bind trong khoang 9303-9319; PS4/PS5 tra loi ve dung
          dia chi + cong nguon cua goi SRCH.
    """
    out = []
    seen = set()
    lock = threading.Lock()

    def worker(protocol_version, ps5_mode, dest_port):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.settimeout(timeout)
            bound = False
            for local_port in range(LOCAL_PORT_MIN, LOCAL_PORT_MAX + 1):
                try:
                    s.bind(("", local_port))
                    bound = True
                    break
                except OSError:
                    continue
            if not bound:
                s.bind(("", 0))
            pkt = _build_srch(protocol_version)
            try:
                src_port = s.getsockname()[1]
            except OSError:
                src_port = 0
            # Gui 2 lan cach nhau mot chut: mot so firmware bo qua goi dau tien.
            for attempt in range(2):
                s.sendto(pkt, ("255.255.255.255", dest_port))
                if attempt == 0:
                    time.sleep(0.15)
            log.info("discovery: SRCH -> 255.255.255.255:%d (%s) src_port=%d",
                     dest_port, "PS5" if ps5_mode else "PS4", src_port)
            end = time.time() + timeout
            while time.time() < end:
                try:
                    data, addr = s.recvfrom(2048)
                except socket.timeout:
                    continue
                except OSError as exc:
                    log.warning("discovery recvfrom error: %s", exc)
                    break
                host = _parse_srch(data, addr, ps5_mode)
                if host is None:
                    continue
                with lock:
                    if host.addr in seen:
                        continue
                    seen.add(host.addr)
                    out.append(host)
        except OSError as exc:
            log.warning("discovery worker dest %d error: %s", dest_port, exc)
        finally:
            s.close()

    threads = [
        threading.Thread(target=worker, daemon=True,
                         args=(PS4_PROTOCOL_VERSION, False, PS4_DISCOVERY_PORT)),
        threading.Thread(target=worker, daemon=True,
                         args=(PS5_PROTOCOL_VERSION, True, PS5_DISCOVERY_PORT)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout + 0.5)
    log.info("discovery: %d host(s)", len(out))
    return out


def send_wakeup(addr, regist_key, ps5=False, timeout=3.0):
    """Gui WAKEUP toi PS4/PS5.

    Tra True neu packet gui thanh cong (PS4/PS5 se bat tu standby thanh ready).
    """
    try:
        credential = int(regist_key, 16)
    except ValueError:
        log.error("regist_key khong phai hex: %r", regist_key)
        return False
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        protocol = "00030010" if ps5 else "00020020"
        pkt = ("WAKEUP * HTTP/1.1\r\n"
               "client-type:vr\r\n"
               "auth-type:R\r\n"
               "model:w\r\n"
               "app-type:r\r\n"
               "user-credential:%llu\r\n"
               "device-discovery-protocol-version:%s\r\n\r\n") % (credential, protocol)
        port = 9302 if ps5 else 987
        sock.sendto(pkt.encode("ascii"), (addr, port))
        log.info("wakeup sent: %s ps5=%s port=%d", addr, ps5, port)
        return True
    except OSError as exc:
        log.error("wakeup failed: %s", exc)
        return False
    finally:
        sock.close()


def _video_profile_from_state():
    """Tra ve dict theo cau truc ChiakiConnectVideoProfile (4-tuple):
        (width, height, max_fps, bitrate)."""
    res = getattr(state, "video_resolution", "720p")
    fps = int(getattr(state, "video_fps", 30))
    bitrate = int(getattr(state, "video_bitrate", 8000))
    if res == "360p":
        w, h = 640, 360
    elif res == "540p":
        w, h = 960, 540
    elif res == "1080p":
        w, h = 1920, 1080
    else:
        w, h = 1280, 720
    if fps not in (30, 60):
        fps = 30
    return {"width": w, "height": h, "max_fps": fps, "bitrate": bitrate}


def video_profile_summary():
    p = _video_profile_from_state()
    return "%dx%d@%dfps %dkbps" % (p["width"], p["height"], p["max_fps"], p["bitrate"])


def init_session(addr, ps5, regist_key, morning, profile=None, log_cb=None):
    """Stub - ban 0.2.0 se goi OpenSSL + chiaki wire o day.

    Tra ve (rc, session_handle). Hien tai rc = -1 de app biet chua ho tro.
    """
    if profile is None:
        profile = _video_profile_from_state()
    log.info("init_session stub: addr=%s ps5=%s profile=%s", addr, ps5, profile)
    if log_cb:
        log_cb("init_session not implemented (v0.2.0)")
    return -1, None


def run_stream(addr, ps5, profile, quit_evt, log_cb=None):
    """Stub streaming loop - chi cho quit event."""
    if log_cb:
        log_cb("run_stream stub running")
    log.info("run_stream stub: addr=%s ps5=%s", addr, ps5)
    quit_evt.wait()
    log.info("run_stream stub: quit")
    return 0

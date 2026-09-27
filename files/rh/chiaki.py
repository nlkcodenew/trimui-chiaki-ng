# -*- coding: utf-8 -*-
"""Lop wire protocol cho trimui-chiaki-ng.

Bao gom:
    - Discovery SRCH broadcast va response parse cho PS4 (port 987)
    - Wakeup WAKEUP voi regist-key plaintext
    - Connect RPCrypt den controller port 9295
    - Doc chiaki.conf theo mau Switch (host_addr, psn_account_id, rp_key, rp_regist_key,
      rp_key_type, video_resolution, video_fps, target)

Crypto và session stream chạy trong native helper AArch64 build bằng SDK TG5050:

    chiaki_session_init
    chiaki_session_start
    chiaki_session_set_controller_state
    chiaki_session_set_video_sample_cb

Python chỉ chuẩn bị file phiên tạm quyền 0600 và yêu cầu launch.sh chuyển sang
native helper sau khi SDL menu đã đóng hoàn toàn.
"""

import base64
import json
import os
import shlex
import socket
import struct
import tempfile
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import state
from .logger import get_logger

log = get_logger()


def _report_error(reason):
    try:
        from .log_uploader import queue_diagnostic
        queue_diagnostic(reason)
    except Exception as exc:
        log.warning("cannot queue diagnostic %s: %s", reason, exc)


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
    """Tìm native stream helper trong bin/ của app."""
    candidates = [
        os.path.join(app_dir, "bin", "chiaki-stream"),
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        if not os.access(path, os.X_OK):
            try:
                os.chmod(path, 0o755)
            except OSError:
                continue
        if os.access(path, os.X_OK):
            log.info("chiaki binary found: %s", path)
            return path
    log.error("native stream helper not found in %s", os.path.join(app_dir, "bin"))
    _report_error("stream_native_helper_missing")
    return None


def _native_runtime(app_dir, model=None):
    """Select an isolated native runtime only for Brick Pro Stock OS."""
    if model is None:
        from .device_identity import device_model
        model = device_model()
    runtime_dir = os.path.join(app_dir, "libs", "brick-stock")
    if str(model or "").strip().lower() == "sun50iw10" and os.path.isdir(runtime_dir):
        return "brick-stock", runtime_dir
    return "system", ""


def _native_preload_prefix(runtime_dir):
    if not runtime_dir:
        return ""
    return (
        'LD_PRELOAD="${OPENSSL_PRELOAD:+$OPENSSL_PRELOAD'
        '${LD_PRELOAD:+:$LD_PRELOAD}}" '
    )

def _paired_credentials(addr):
    from .paths import APP_DIR

    entries = []
    paired_path = os.path.join(APP_DIR, "paired_hosts.json")
    try:
        with open(paired_path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        if isinstance(value, list):
            entries.extend(value)
    except (OSError, ValueError, TypeError):
        pass
    if getattr(state, "host_addr", "") == addr:
        entries.append({
            "addr": state.host_addr,
            "name": state.host_name,
            "is_ps5": False,
            "regist_key": state.regist_key,
            "rp_key": state.rp_key,
            "server_mac": getattr(state, "server_mac", ""),
            "target": int(getattr(state, "host_target", 0) or 0),
        })
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("addr") != addr:
            continue
        regist_key = str(entry.get("regist_key") or "")
        rp_key = str(entry.get("rp_key") or "")
        try:
            decoded = base64.b64decode(rp_key, validate=True)
        except Exception:
            decoded = b""
        if (1 <= len(regist_key) <= 8
                and all(char in "0123456789abcdefABCDEF" for char in regist_key)
                and len(decoded) == 16
                and not rp_key.startswith("stub-rp-key-")):
            return {
                "addr": addr,
                "name": entry.get("name") or addr,
                "is_ps5": bool(entry.get("is_ps5", False)),
                "regist_key": regist_key,
                "rp_key": rp_key,
                "server_mac": str(entry.get("server_mac") or ""),
                "target": int(entry.get("target", 0) or 0),
            }
    return None


def paired_hosts_for_discovery(discovered=None):
    """Merge saved paired PS4 hosts without exposing credentials."""
    from .paths import APP_DIR

    hosts = [host for host in (discovered or [])
             if not bool(getattr(host, "is_ps5", False))]
    seen = {getattr(host, "addr", "") for host in hosts}
    entries = []
    paired_path = os.path.join(APP_DIR, "paired_hosts.json")
    try:
        with open(paired_path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        if isinstance(value, list):
            entries.extend(value)
    except (OSError, ValueError, TypeError):
        pass
    if getattr(state, "host_addr", ""):
        entries.append({
            "addr": state.host_addr,
            "name": state.host_name,
            "is_ps5": False,
            "target": int(getattr(state, "host_target", 0) or 0),
        })
    for entry in entries:
        if not isinstance(entry, dict) or bool(entry.get("is_ps5", False)):
            continue
        addr = str(entry.get("addr") or "")
        if not addr or addr in seen or not _paired_credentials(addr):
            continue
        hosts.append(DiscoveredHost(
            name=str(entry.get("name") or addr),
            addr=addr,
            state="offline",
            is_ps5=bool(entry.get("is_ps5", False)),
            target=int(entry.get("target", 0) or 0),
        ))
        seen.add(addr)
    return hosts


def paired_ps4_addresses():
    """Return saved PS4 addresses for manual unicast discovery."""
    return [host.addr for host in paired_hosts_for_discovery([])
            if not host.is_ps5]


def wake_paired_host(host):
    """Wake a saved PS4 using its private registration credential."""
    if bool(getattr(host, "is_ps5", False)):
        log.warning("wakeup rejected: PS5 support is disabled")
        return False
    credentials = _paired_credentials(getattr(host, "addr", ""))
    if not credentials or credentials["is_ps5"]:
        return False
    return send_wakeup(credentials["addr"], credentials["regist_key"])


def wake_paired_ps4_until_ready(host, timeout=120.0):
    """Wake a paired PS4 and wait for READY on the same socket."""
    addr = str(getattr(host, "addr", "") or "")
    if not addr or bool(getattr(host, "is_ps5", False)):
        return None
    credentials = _paired_credentials(addr)
    if not credentials or credentials["is_ps5"]:
        log.error("wakeup transaction missing PS4 credentials: host=%s", addr)
        return None
    return _wake_ps4_until_ready(addr, credentials["regist_key"], timeout)

def _rp_version_string(target):
    t = int(target or 0)
    if t == 800:
        return "8.0"
    if t == 900:
        return "9.0"
    if t >= 1000000:
        return "1.0"
    return "10.0"


def prepare_stream_launch(host):
    """Chuẩn bị native stream rồi trả về (ok, thông báo)."""
    from .paths import APP_DIR

    if bool(getattr(host, "is_ps5", False)):
        log.warning("stream preparation rejected: PS5 support is disabled")
        return False, "Bản này chỉ hỗ trợ PS4"
    binary = find_chiaki_binary(APP_DIR)
    if not binary:
        return False, "Thiếu bin/chiaki-stream"
    credentials = _paired_credentials(getattr(host, "addr", ""))
    if not credentials:
        log.error("stream preparation rejected: paired credentials unavailable")
        _report_error("stream_credentials_missing")
        return False, "Khóa ghép nối không hợp lệ; hãy ghép lại PS4"
    if credentials["is_ps5"]:
        log.warning("stream preparation rejected: saved PS5 credentials")
        return False, "Bản này chỉ hỗ trợ PS4"
    discovered_target = int(getattr(host, "target", 0) or 0)
    stored_target = int(credentials.get("target", 0) or 0)
    if (discovered_target in (800, 900, 1000)
            and stored_target in (800, 900, 1000)
            and discovered_target != stored_target):
        log.warning("pair target mismatch: host=%d stored=%d; re-pair required",
                    discovered_target, stored_target)
        _report_error("stream_pair_target_mismatch")
        return False, "Khóa pair cũ; hãy ghép lại PS4 một lần"
    profile = _video_profile_from_state()
    requested_temp = os.environ.get("CHIAKI_SESSION_DIR", "")
    temp_dir = requested_temp if requested_temp and os.path.isdir(requested_temp) else (
        "/tmp" if os.path.isdir("/tmp") else APP_DIR)
    session_path = ""
    try:
        descriptor, session_path = tempfile.mkstemp(
            prefix="chiaki-session-", suffix=".conf", dir=temp_dir)
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        else:
            os.chmod(session_path, 0o600)
        rp_version = _rp_version_string(credentials.get("target", 0))
        with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as handle:
            handle.write("host=%s\n" % credentials["addr"])
            handle.write("regist_key=%s\n" % credentials["regist_key"])
            handle.write("rp_key=%s\n" % credentials["rp_key"])
            handle.write("ps5=0\n")
            handle.write("target=%d\n" % int(credentials.get("target", 0) or 0))
            handle.write("rp_version=%s\n" % rp_version)
            native_verbose = os.environ.get("CHIAKI_NATIVE_VERBOSE", "").lower() in (
                "1", "true", "yes", "on")
            handle.write("verbose=%d\n" % int(native_verbose))
            handle.write("width=%d\n" % profile["width"])
            handle.write("height=%d\n" % profile["height"])
            handle.write("fps=%d\n" % profile["max_fps"])
            handle.write("bitrate=%d\n" % profile["bitrate"])
            handle.write("volume=%d\n" % int(getattr(state, "audio_volume", 80)))
            handle.flush()
            os.fsync(handle.fileno())

        debug_path = os.path.join(APP_DIR, "Chiaki-debug.log")
        error_path = os.path.join(APP_DIR, "Chiaki-loi.txt")
        runtime_name, runtime_dir = _native_runtime(APP_DIR)
        launcher_path = os.environ.get("CHIAKI_STREAM_LAUNCHER", "/tmp/launch_game.sh")
        launcher_temp = launcher_path + ".tmp"
        dollar = "$"
        quoted = {name: shlex.quote(value) for name, value in {
            "binary": binary,
            "session": session_path,
            "debug": debug_path,
            "error": error_path,
            "runtime": runtime_dir,
        }.items()}
        lines = [
            "#!/bin/sh",
            "BIN=%s" % quoted["binary"],
            "SESSION=%s" % quoted["session"],
            "DEBUG=%s" % quoted["debug"],
            "ERROR_LOG=%s" % quoted["error"],
            "trap 'rm -f \"%sSESSION\"' EXIT INT TERM" % dollar,
            "chmod +x \"%sBIN\" 2>/dev/null || true" % dollar,
            "echo \"[%s(date '+%%Y-%%m-%%d %%H:%%M:%%S')] native stream preflight\" >> \"%sDEBUG\"" % (dollar, dollar),
            "echo \"native runtime: %s\" >> \"%sDEBUG\"" % (runtime_name, dollar),
        ]
        if runtime_dir:
            lines.extend([
                "RUNTIME=%s" % quoted["runtime"],
                "if [ -n \"${LD_LIBRARY_PATH:-}\" ]; then",
                "    LD_LIBRARY_PATH=\"${LD_LIBRARY_PATH%:}:$RUNTIME\"",
                "else",
                "    LD_LIBRARY_PATH=\"$RUNTIME\"",
                "fi",
                "export LD_LIBRARY_PATH",
                "OPENSSL_PRELOAD=\"$RUNTIME/libcrypto.so.1.1:$RUNTIME/libssl.so.1.1\"",
                "echo \"native OpenSSL: bundled 1.1.1\" >> \"$DEBUG\"",
            ])
        preload = _native_preload_prefix(runtime_dir)
        lines.extend([
            "%sLD_TRACE_LOADED_OBJECTS=1 \"%sBIN\" >> \"%sDEBUG\" 2>&1 || true" % (
                preload, dollar, dollar),
            "%s\"%sBIN\" \"%sSESSION\" >> \"%sDEBUG\" 2>> \"%sERROR_LOG\"" % (
                preload, dollar, dollar, dollar, dollar),
            "RC=%s?" % dollar,
            "echo \"[%s(date '+%%Y-%%m-%%d %%H:%%M:%%S')] native stream exit=%sRC\" >> \"%sDEBUG\"" % (dollar, dollar, dollar),
            "exit \"%sRC\"" % dollar,
        ])
        with open(launcher_temp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(launcher_temp, 0o700)
        os.replace(launcher_temp, launcher_path)
        log.info("native stream prepared: host=%s profile=%s",
                 credentials["addr"], video_profile_summary())
        return True, "Đang mở Remote Play..."
    except OSError as exc:
        if session_path:
            try:
                os.remove(session_path)
            except OSError:
                pass
        log.error("cannot prepare native stream: %s", exc)
        _report_error("stream_prepare_failed")
        return False, "Không chuẩn bị được stream: %s" % exc


def read_chiaki_conf(path=None):
    """Doc chiaki.conf theo mau Switch.

    File mau:
        [PS4-xxx]
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
        _report_error("settings_legacy_config_write_failed")
        return False


# Cong discovery theo upstream chiaki (lib/include/chiaki/discovery.h).
# DAY LA CONG DICH ma PS4 lang nghe goi SRCH. Truoc v0.2.11 code gui SRCH
# toi chinh cong nguon 9303-9308 nen khong bao gio toi duoc may PS -> luon 0 host.
PS4_DISCOVERY_PORT = 987
PS4_PROTOCOL_VERSION = "00020020"
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


def _build_wakeup(regist_key):
    key = str(regist_key or "").split("\x00", 1)[0]
    if not key or len(key) > 8:
        raise ValueError("invalid registration key")
    credential = int(key, 16)
    body = ("WAKEUP * HTTP/1.1\n"
            "client-type:vr\n"
            "auth-type:R\n"
            "model:w\n"
            "app-type:r\n"
            "user-credential:%d\n"
            "device-discovery-protocol-version:%s\n") % (
                credential, PS4_PROTOCOL_VERSION,
            )
    return body.encode("ascii") + b"\x00"


def _bind_discovery_socket(sock):
    for local_port in range(LOCAL_PORT_MIN, LOCAL_PORT_MAX + 1):
        try:
            sock.bind(("", local_port))
            return local_port
        except OSError:
            continue
    sock.bind(("", 0))
    return sock.getsockname()[1]


def _parse_srch(data, addr):
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
    protocol = headers.get("device-discovery-protocol-version", "")
    if protocol and protocol != PS4_PROTOCOL_VERSION:
        log.info("discovery: ignored non-PS4 protocol response")
        return None
    host = DiscoveredHost(
        addr=addr[0],
        is_ps5=False,
        state=host_state,
        system_version=headers.get("system-version", ""),
        running_app=urllib.parse.unquote(headers.get("running-app-name", "")),
        host_request_port=req_port,
    )
    host.name = urllib.parse.unquote(headers.get("host-name", ""))
    host.target = _target_from_version(host.system_version)
    return host


def _target_from_version(version):
    digits = "".join(c for c in version if c.isdigit())
    try:
        v = int(digits) if digits else 0
    except ValueError:
        return 0
    if "09." in version or "9." in version or "0900000" in version:
        return 900  # CHIAKI_TARGET_PS4_9
    if v >= 8000000:
        return 1000  # CHIAKI_TARGET_PS4_10
    if v >= 7000000:
        return 900  # CHIAKI_TARGET_PS4_9
    if v > 0:
        return 800  # CHIAKI_TARGET_PS4_8
    return 0


def discovery_broadcast(timeout=3.0, ps4_hosts=None):
    """Send PS4-only SRCH broadcast/unicast and return discovered hosts.

    Dung protocol upstream chiaki:
        - Gui SRCH broadcast toi cong dich 987 (PS4).
        - Gui them SRCH unicast toi cac PS4 da pair, giong manual host upstream.
        - Mot socket nguon bind trong khoang 9303-9319 de nhan phan hoi PS4.
    """
    out = []
    seen = set()

    manual_ps4_hosts = []
    for addr in ps4_hosts or []:
        addr = str(addr or "").strip()
        if addr and addr not in manual_ps4_hosts:
            manual_ps4_hosts.append(addr)

    destinations = ["255.255.255.255"] + manual_ps4_hosts
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        source_port = _bind_discovery_socket(sock)
        packet = _build_srch(PS4_PROTOCOL_VERSION)
        for attempt in range(2):
            for destination in destinations:
                sock.sendto(packet, (destination, PS4_DISCOVERY_PORT))
            if attempt == 0:
                time.sleep(0.15)
        log.info(
            "discovery: PS4-only single socket %s -> port=%d "
            "src_port=%d manual_hosts=%d",
            "broadcast+unicast" if len(destinations) > 1 else "broadcast",
            PS4_DISCOVERY_PORT, source_port, len(manual_ps4_hosts),
        )
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError as exc:
                log.warning("discovery recvfrom error: %s", exc)
                _report_error("discovery_receive_error")
                break
            host = _parse_srch(data, addr)
            if host is None or host.addr in seen:
                continue
            log.info(
                "discovery host: console=PS4 state=%s system_version=%s target=%d",
                host.state, host.system_version or "missing", host.target,
            )
            seen.add(host.addr)
            out.append(host)
    except OSError as exc:
        log.warning("PS4 discovery error: %s", exc)
        _report_error("discovery_worker_error")
    finally:
        sock.close()
    log.info("discovery: %d host(s)", len(out))
    return out


def regist_with_pin(host, pin, timeout=10.0):
    """Đăng ký PS4 qua LAN bằng PIN 8 số, không kết nối dịch vụ PSN."""
    pin = "".join(c for c in str(pin) if c.isdigit())[:8]
    if len(pin) != 8:
        log.warning("registration rejected: PIN must contain 8 digits")
        _report_error("pair_pin_invalid")
        return False, {"error": "PIN phai 8 so"}
    addr = getattr(host, "addr", "") or "unknown"
    is_ps5 = bool(getattr(host, "is_ps5", False))
    target = int(getattr(host, "target", 0) or 0)
    account_id_configured = bool(
        str(getattr(state, "psn_account_id", "") or "").strip()
    )
    log.info(
        "registration start: host=%s ps5=%s target=%d system_version=%s "
        "account_id_configured=%s",
        addr, is_ps5, target, getattr(host, "system_version", "") or "missing",
        account_id_configured,
    )
    if is_ps5:
        message = "PS5 support is disabled; this build is PS4-only"
        log.warning("registration rejected: %s", message)
        return False, {"error": message}
    if target not in (0, 800, 900, 1000):
        message = "this beta supports PS4 firmware 8.0 or newer"
        log.warning("registration rejected: target=%d", target)
        _report_error("pair_ps4_target_unsupported")
        return False, {"error": message}
    try:
        from .ps4_regist import register
        result = register(addr, pin, getattr(state, "psn_account_id", ""), timeout,
                          target=target)
    except Exception as exc:
        log.error("registration failed: host=%s error=%s", addr, exc)
        _report_error("pair_registration_failed")
        return False, {"error": str(exc)}
    result.update({"addr": addr, "is_ps5": False, "target": target})
    log.info(
        "registration success: host=%s key_type=%s mac_available=%s "
        "offline_account=%s",
        addr, result.get("rp_key_type"), bool(result.get("server_mac")),
        result.get("used_offline_account"),
    )
    return True, result


def send_wakeup(addr, regist_key, ps5=False, timeout=3.0):
    """Gui WAKEUP toi PS4; PS5 bi vo hieu hoa trong ung dung."""
    if ps5:
        log.warning("wakeup rejected: PS5 support is disabled")
        return False
    try:
        payload = _build_wakeup(regist_key)
    except (TypeError, ValueError):
        log.error("wakeup credential is invalid")
        return False
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        source_port = _bind_discovery_socket(sock)
        sent = sock.sendto(payload, (addr, PS4_DISCOVERY_PORT))
        log.info(
            "wakeup sent: host=%s console=PS4 source_port=%d dest_port=%d "
            "packets=1 bytes=%d format=lf+nul mode=upstream-unicast",
            addr, source_port, PS4_DISCOVERY_PORT, len(payload),
        )
        return sent == len(payload)
    except OSError as exc:
        log.error("wakeup failed: %s", exc)
        return False
    finally:
        sock.close()


def _wake_ps4_until_ready(addr, regist_key, timeout=120.0):
    """Send one upstream DDP WAKEUP, then wait for the paired PS4."""
    try:
        wake_payload = _build_wakeup(regist_key)
    except (TypeError, ValueError):
        log.error("wakeup credential is invalid")
        return None
    srch_payload = _build_srch(PS4_PROTOCOL_VERSION)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    deadline = time.monotonic() + max(1.0, float(timeout))
    last_state = "unknown"
    probes = 0
    try:
        sock.settimeout(1.0)
        source_port = _bind_discovery_socket(sock)
        log.info(
            "wakeup DDP-only start: host=%s source_port=%d timeout=%.1f "
            "wake_packets=1 wake_destination=unicast wol=False retry=False",
            addr, source_port, timeout,
        )
        sent = sock.sendto(wake_payload, (addr, PS4_DISCOVERY_PORT))
        wake_sent = sent == len(wake_payload)
        log.info(
            "wakeup DDP-only sent: host=%s source_port=%d packets=1 bytes=%d",
            addr, source_port, sent,
        )
        while time.monotonic() < deadline:
            probe_started = time.monotonic()
            sock.sendto(srch_payload, (addr, PS4_DISCOVERY_PORT))
            probes += 1
            probe_deadline = min(deadline, time.monotonic() + 1.0)
            while time.monotonic() < probe_deadline:
                try:
                    data, response_addr = sock.recvfrom(2048)
                except socket.timeout:
                    break
                if response_addr[0] != addr:
                    continue
                discovered = _parse_srch(data, response_addr)
                if not discovered:
                    continue
                last_state = discovered.state
                log.info(
                    "wakeup DDP-only response: host=%s state=%s "
                    "source_port=%d probes=%d",
                    addr, last_state, source_port, probes,
                )
                if last_state == "ready":
                    return discovered
                break
            remaining = deadline - time.monotonic()
            delay = min(1.0 - (time.monotonic() - probe_started), remaining)
            if delay > 0:
                time.sleep(delay)
        log.error(
            "wakeup DDP-only timeout: host=%s state=%s sent=%s probes=%d "
            "wol=False retry=False",
            addr, last_state, wake_sent, probes,
        )
        return None
    except OSError as exc:
        log.error("wakeup transaction failed: host=%s error=%s", addr, exc)
        return None
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
    elif res == "720p":
        w, h = 1280, 720
    else:
        w, h = 1280, 720
    if fps not in (30, 60):
        fps = 30
    return {"width": w, "height": h, "max_fps": fps, "bitrate": bitrate}


def video_profile_summary():
    p = _video_profile_from_state()
    return "%dx%d@%dfps %dkbps" % (p["width"], p["height"], p["max_fps"], p["bitrate"])


def init_session(addr, ps5, regist_key, morning, profile=None, log_cb=None):
    """Stub - bản stream thật sẽ gọi native Chiaki session ở đây.

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

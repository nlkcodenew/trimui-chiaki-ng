# -*- coding: utf-8 -*-
"""PS5 LAN registration through the isolated native chiaki helper."""

import base64
import os
import subprocess
import tempfile

from .logger import get_logger
from .paths import APP_DIR

log = get_logger()

PS5_TARGET = 1000100


class PS5RegistError(Exception):
    def __init__(self, stage, message):
        super().__init__(message)
        self.stage = stage


def _decode_account_id(value):
    try:
        decoded = base64.b64decode(str(value or "").strip(), validate=True)
    except Exception as exc:
        raise PS5RegistError("account_id", "PSN Account-ID Base64 không hợp lệ") from exc
    if len(decoded) != 8:
        raise PS5RegistError("account_id", "PSN Account-ID phải mã hóa đúng 8 byte")
    return base64.b64encode(decoded).decode("ascii")


def _helper_path():
    path = os.path.join(APP_DIR, "bin", "chiaki-regist")
    if not os.path.isfile(path):
        raise PS5RegistError("helper", "thiếu helper PS5 chiaki-regist")
    try:
        os.chmod(path, 0o755)
    except OSError:
        pass
    if not os.access(path, os.X_OK):
        raise PS5RegistError("helper", "helper PS5 không có quyền chạy")
    return path


def _runtime_env():
    env = os.environ.copy()
    try:
        from .chiaki import _native_runtime
        _, runtime_dir = _native_runtime(APP_DIR)
    except Exception:
        runtime_dir = ""
    if not runtime_dir:
        return env
    current = env.get("LD_LIBRARY_PATH", "").rstrip(":")
    env["LD_LIBRARY_PATH"] = "%s%s%s" % (
        current, ":" if current else "", runtime_dir)
    crypto = os.path.join(runtime_dir, "libcrypto.so.1.1")
    ssl = os.path.join(runtime_dir, "libssl.so.1.1")
    preload = ":".join(path for path in (crypto, ssl) if os.path.isfile(path))
    if preload:
        current_preload = env.get("LD_PRELOAD", "").strip(":")
        env["LD_PRELOAD"] = "%s%s%s" % (
            preload, ":" if current_preload else "", current_preload)
    return env


def _write_input(host, pin, account_id):
    temp_dir = os.environ.get("TMPDIR") or "/tmp"
    descriptor, path = tempfile.mkstemp(
        prefix="chiaki-ps5-regist-", suffix=".conf", dir=temp_dir)
    if hasattr(os, "fchmod"):
        os.fchmod(descriptor, 0o600)
    else:
        os.chmod(path, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as handle:
        handle.write("host=%s\n" % host)
        handle.write("pin=%s\n" % pin)
        handle.write("account_id=%s\n" % account_id)
        handle.flush()
        os.fsync(handle.fileno())
    return path


def _result_path():
    temp_dir = os.environ.get("TMPDIR") or "/tmp"
    descriptor, path = tempfile.mkstemp(
        prefix="chiaki-ps5-result-", suffix=".conf", dir=temp_dir)
    os.close(descriptor)
    os.chmod(path, 0o600)
    return path


def _parse_result(path):
    values = {}
    try:
        with open(path, "r", encoding="ascii") as handle:
            for line in handle:
                key, separator, value = line.strip().partition("=")
                if separator:
                    values[key] = value
    except OSError as exc:
        raise PS5RegistError("result", "helper PS5 không tạo kết quả") from exc

    try:
        target = int(values.get("target", "0"))
        rp_key_type = int(values.get("rp_key_type", "0"))
        regist_raw = bytes.fromhex(values.get("regist_key", ""))
        rp_key = bytes.fromhex(values.get("rp_key", ""))
        server_mac = bytes.fromhex(values.get("server_mac", ""))
        regist_raw = regist_raw.rstrip(b"\0")
        if regist_raw and all(byte in b"0123456789abcdefABCDEF" for byte in regist_raw):
            regist_key = regist_raw.decode("ascii")
        else:
            regist_key = regist_raw.hex()
    except (ValueError, UnicodeError) as exc:
        raise PS5RegistError("result", "helper PS5 trả khóa không hợp lệ") from exc
    if (target != PS5_TARGET or not 1 <= len(regist_key) <= 8
            or any(char not in "0123456789abcdefABCDEF" for char in regist_key)
            or len(rp_key) != 16 or len(server_mac) != 6):
        raise PS5RegistError("result", "helper PS5 trả kết quả thiếu hoặc sai định dạng")
    return {
        "name": values.get("name", ""),
        "regist_key": regist_key,
        "rp_key": base64.b64encode(rp_key).decode("ascii"),
        "rp_key_type": rp_key_type,
        "server_mac": server_mac.hex(),
        "target": target,
    }


def register(host, pin, account_id_b64, timeout=15.0):
    account_id = _decode_account_id(account_id_b64)
    helper = _helper_path()
    input_path = _write_input(host, pin, account_id)
    result_path = _result_path()
    log.info("PS5 registration stage=input status=ready target=%d", PS5_TARGET)
    try:
        try:
            completed = subprocess.run(
                [helper, input_path, result_path],
                env=_runtime_env(), capture_output=True, text=True,
                timeout=max(10.0, float(timeout)), check=False)
        except subprocess.TimeoutExpired as exc:
            raise PS5RegistError("network", "PS5 không phản hồi đăng ký trong thời gian chờ") from exc
        output = "\n".join(part.strip() for part in (
            completed.stdout, completed.stderr) if part and part.strip())
        if output:
            for line in output.splitlines():
                log.info("PS5 helper: %s", line[:500])
        if completed.returncode != 0:
            stage = "protocol"
            for candidate in ("input", "start", "network", "protocol", "result"):
                if "stage=%s" % candidate in output:
                    stage = candidate
            log.error("PS5 helper failed: stage=%s exit=%d", stage,
                      completed.returncode)
            raise PS5RegistError(
                stage, "PS5 từ chối hoặc không hoàn tất đăng ký (bước %s, mã %d)" %
                (stage, completed.returncode))
        result = _parse_result(result_path)
        log.info("PS5 registration stage=result status=success target=%d", PS5_TARGET)
        return result
    finally:
        for path in (input_path, result_path):
            try:
                os.remove(path)
            except OSError:
                pass

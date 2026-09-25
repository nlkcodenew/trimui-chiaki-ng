# -*- coding: utf-8 -*-
"""Gui log da loc qua HTTPS relay; app khong chua GitHub credential."""

import argparse
import hashlib
import json
import os
import platform
import re
import threading
import time
import urllib.parse
import urllib.request

from . import state
from .paths import APP_DIR
from .version import APP_VERSION
from .logger import get_logger
from .ssl_context import create_ssl_context
from .device_identity import diagnostic_identity

log = get_logger()

REPORTING_FILE = os.path.join(APP_DIR, "reporting.json")
STATE_FILE = os.path.join(APP_DIR, ".log_upload_state.json")
PENDING_FILE = os.path.join(APP_DIR, ".pending_crash")
MAX_LOG_BYTES = 24000
MAX_BODY_CHARS = 60000
TIMEOUT = 15
MAX_PENDING_REASONS = 8

_SECRET_LINE = re.compile(
    r"(?im)^([^\n]*(?:token|password|passwd|secret|regist_key|rp_key|"
    r"psn_account_id|psn_online_id|host_name|host_addr|serial[-_ ]?(?:number|no)|"
    r"sunxi_chipid|chip[-_ ]?id|machine[-_ ]?id)[^:=\n]*[:=]\s*)"
    r"[^\s,}\]]+"
)
_GITHUB_TOKEN = re.compile(
    r"\b(?:ghp|github_pat|gho|ghu|ghs|ghr)_[^\s,}\]\[\"']+"
)
_PRIVATE_IP = re.compile(
    r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
)
_MAC_ADDRESS = re.compile(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b")
_pending_lock = threading.Lock()
_upload_lock = threading.Lock()


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _clean_reason(reason):
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(reason or "error"))
    return value.strip("_.-")[:80] or "error"


def _pending_reasons():
    value = _read_json(PENDING_FILE)
    reasons = value.get("reasons", []) if isinstance(value, dict) else []
    if not isinstance(reasons, list):
        return []
    return [_clean_reason(reason) for reason in reasons[:MAX_PENDING_REASONS]]


def _remember_pending_reason(reason):
    with _pending_lock:
        reason = _clean_reason(reason)
        reasons = _pending_reasons()
        if reason not in reasons:
            reasons.append(reason)
        temp_path = PENDING_FILE + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump({"reasons": reasons[-MAX_PENDING_REASONS:]}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, PENDING_FILE)
            return True
        except OSError as exc:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            log.warning("cannot remember diagnostic reason %s: %s", reason, exc)
            return False


def _clear_uploaded_reasons(uploaded_reasons):
    with _pending_lock:
        current = _pending_reasons()
        remaining = [reason for reason in current if reason not in uploaded_reasons]
        if remaining:
            temp_path = PENDING_FILE + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump({"reasons": remaining}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, PENDING_FILE)
            return
        try:
            os.remove(PENDING_FILE)
        except OSError:
            pass


def _report_configuration():
    public_cfg = _read_json(REPORTING_FILE)
    relay_url = (os.environ.get("CHIAKI_ISSUE_RELAY_URL") or
                 public_cfg.get("issue_relay_url", ""))
    enabled = bool(getattr(state, "auto_upload_logs", False))
    return relay_url.strip(), enabled


def _tail(path, max_bytes=MAX_LOG_BYTES):
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            data = handle.read(max_bytes)
        return data.decode("utf-8", errors="replace")
    except OSError:
        return ""


def _sanitize(text):
    text = _GITHUB_TOKEN.sub("[REDACTED_TOKEN]", text)
    text = _SECRET_LINE.sub(r"\1[REDACTED]", text)
    text = _PRIVATE_IP.sub("[PRIVATE_IP]", text)
    text = _MAC_ADDRESS.sub("[MAC_ADDRESS]", text)
    return text.replace("\x00", "")


def _log_paths():
    candidates = [
        os.environ.get("CHIAKI_STDERR_LOG", ""),
        os.path.join(APP_DIR, "Chiaki-loi.txt"),
        os.path.join(APP_DIR, "Chiaki-debug.log"),
    ]
    out = []
    seen = set()
    for path in candidates:
        if not path:
            continue
        path = os.path.abspath(path)
        if path not in seen and os.path.isfile(path):
            seen.add(path)
            out.append(path)
    return out


def _collect():
    sections = []
    for path in _log_paths():
        text = _sanitize(_tail(path))
        if text.strip():
            sections.append((os.path.basename(path), text))
    return sections


def _fingerprint(sections, reason=None):
    payload = "%s\n%s" % (
        _clean_reason(reason),
        "\n".join(text[-8000:] for _, text in sections),
    )
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def _content_fingerprint(sections):
    payload = "\n".join(text[-8000:] for _, text in sections)
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def _issue_body(sections, reason, fingerprint):
    reason = _sanitize(str(reason).replace("`", ""))[:80]
    if reason == "native_stream_quality":
        summary = "Báo cáo chất lượng stream được gửi tự động từ thiết bị TrimUI."
    elif reason.startswith("wakeup_"):
        summary = "Báo cáo chẩn đoán đánh thức PlayStation được gửi tự động."
    elif reason.startswith(("ota_", "discovery_", "pair_", "stream_", "settings_")):
        summary = "Báo cáo lỗi vận hành được gửi tự động từ thiết bị TrimUI."
    elif reason.endswith("_retry"):
        summary = "Báo cáo đang chờ được gửi lại khi ứng dụng thoát."
    else:
        summary = "Log được gửi tự động từ thiết bị TrimUI sau khi ứng dụng lỗi."
    identity = diagnostic_identity()
    lines = [
        summary,
        "",
        "| Trường | Giá trị |",
        "|---|---|",
        "| App | trimui-chiaki-ng v%s |" % APP_VERSION,
        "| Lý do | `%s` |" % reason,
        "| Model | `%s` |" % identity["model"],
        "| Mã cài đặt | `%s` |" % identity["install_id"],
        "| Mã phần cứng băm | `%s` |" % identity["hardware_id"],
        "| Python | `%s` |" % platform.python_version(),
        "| Hệ thống | `%s` |" % _sanitize(platform.platform()),
        "| Fingerprint | `%s` |" % fingerprint[:16],
        "",
        "> Token, khóa đăng ký, PSN Account ID, địa chỉ IP, MAC và serial thô đã được lọc.",
    ]
    for name, text in sections:
        safe_text = text[-MAX_LOG_BYTES:].replace("```", "` ` `")
        lines.extend(["", "### %s" % name, "```text", safe_text, "```"])
    return "\n".join(lines)[:MAX_BODY_CHARS]


def _post_relay(relay_url, title, body, fingerprint):
    parsed = urllib.parse.urlsplit(relay_url)
    if (parsed.scheme != "https" or not parsed.netloc or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("issue relay URL must be HTTPS without credentials or query")
    payload = json.dumps({
        "schema": 1,
        "app": "trimui-chiaki-ng",
        "version": APP_VERSION,
        "fingerprint": fingerprint,
        "title": title,
        "body": body,
    }).encode("utf-8")
    request = urllib.request.Request(
        relay_url,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/json",
            "User-Agent": "trimui-chiaki-ng/%s" % APP_VERSION,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT,
                                context=create_ssl_context()) as response:
        result = json.loads(response.read(128 * 1024).decode("utf-8"))
    issue_url = result.get("issue_url", "") or result.get("html_url", "")
    if result.get("accepted") is not True and not issue_url:
        raise ValueError("issue relay did not accept report")
    return issue_url


def _upload_pending(reason="crash", force=False):
    relay_url, enabled = _report_configuration()
    if not enabled and not force:
        log.info("log upload disabled in settings")
        return False
    if not force and not os.path.exists(PENDING_FILE):
        return False
    pending_reasons = _pending_reasons()
    uploaded_reasons = list(pending_reasons)
    caller_reason = _clean_reason(reason)
    if pending_reasons:
        report_reasons = list(pending_reasons)
        if (caller_reason not in ("startup", "startup_retry", "user_exit_retry", "crash")
                and caller_reason not in report_reasons):
            report_reasons.append(caller_reason)
        reason = "+".join(report_reasons)
    else:
        reason = caller_reason
    if not relay_url:
        log.warning("log upload pending: no HTTPS issue relay configured")
        return False

    sections = _collect()
    if not sections:
        log.warning("log upload pending but no readable logs")
        return False
    fingerprint = _fingerprint(sections, reason)
    content_fingerprint = _content_fingerprint(sections)
    history = _read_json(STATE_FILE)
    if not force:
        exact_duplicate = history.get("fingerprint") == fingerprint
        legacy_retry_duplicate = (
            not pending_reasons
            and caller_reason.endswith("_retry")
            and history.get("content_fingerprint") == content_fingerprint
        )
        if exact_duplicate or legacy_retry_duplicate:
            _clear_uploaded_reasons(uploaded_reasons)
            return True

    identity = diagnostic_identity()
    title_reason = reason[:80]
    title = "[device-log][%s][%s][%s] v%s %s %s" % (
        identity["model"][:32], identity["install_id"][:16],
        identity["hardware_id"][:16], APP_VERSION, title_reason,
        fingerprint[:8],
    )
    body = _issue_body(sections, reason, fingerprint)
    try:
        issue_url = _post_relay(relay_url, title, body, fingerprint)
    except Exception as exc:
        log.warning("diagnostic report upload failed: %s", exc)
        return False

    tmp = STATE_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({
                    "fingerprint": fingerprint,
                    "content_fingerprint": content_fingerprint,
                "version": APP_VERSION,
                "issue_url": issue_url,
                "uploaded_at": int(time.time()),
            }, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, STATE_FILE)
        _clear_uploaded_reasons(uploaded_reasons)
    except OSError:
        pass
    log.info("diagnostic report uploaded: %s", issue_url or "ok")
    return True


def upload_pending(reason="crash", force=False):
    with _upload_lock:
        return _upload_pending(reason, force)


def start_pending_upload(reason="startup"):
    if not os.path.exists(PENDING_FILE):
        return None
    thread = threading.Thread(
        target=upload_pending,
        kwargs={"reason": reason},
        name="log-uploader",
        daemon=True,
    )
    thread.start()
    return thread


def queue_diagnostic(reason):
    """Mark a non-crash diagnostic and upload it without blocking the UI."""
    if not bool(getattr(state, "auto_upload_logs", True)):
        log.info("diagnostic upload disabled: reason=%s", _clean_reason(reason))
        return None
    reason = _clean_reason(reason)
    if not _remember_pending_reason(reason):
        return None
    return start_pending_upload(reason)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--reason", default="crash")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    return 0 if upload_pending(args.reason, args.force) else 1


if __name__ == "__main__":
    raise SystemExit(main())

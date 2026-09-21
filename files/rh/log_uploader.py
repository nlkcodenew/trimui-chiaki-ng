# -*- coding: utf-8 -*-
"""Gui crash log len GitHub Issues.

GitHub khong cho tao Issue an danh, vi vay thiet bi can mot fine-grained token
chi co quyen Issues: Read and write cho duy nhat repo nhan log. Token duoc doc
tu secrets.json (khong nam trong manifest/Release) hoac CHIAKI_GITHUB_TOKEN.

Uploader chi chay khi co .pending_crash, loc token/key/password/private IP,
gioi han kich thuoc, va nho fingerprint de khong tao Issue trung lap.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import ssl
import threading
import time
import urllib.request

from . import state
from .paths import APP_DIR
from .version import APP_VERSION
from .logger import get_logger

log = get_logger()

SECRETS_FILE = os.path.join(APP_DIR, "secrets.json")
STATE_FILE = os.path.join(APP_DIR, ".log_upload_state.json")
PENDING_FILE = os.path.join(APP_DIR, ".pending_crash")
MAX_LOG_BYTES = 24000
MAX_BODY_CHARS = 60000
TIMEOUT = 15

_SECRET_LINE = re.compile(
    r"(?im)^([^\n]*(?:token|password|passwd|secret|regist_key|rp_key|"
    r"psn_account_id|psn_online_id|host_name|host_addr)[^:=\n]*[:=]\s*)"
    r"[^\s,}\]]+"
)
_GITHUB_TOKEN = re.compile(r"\b(?:ghp|github_pat|gho|ghu|ghs|ghr)_[A-Za-z0-9_]+\b")
_PRIVATE_IP = re.compile(
    r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
)
_MAC_ADDRESS = re.compile(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b")
_REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _configuration():
    cfg = _read_json(SECRETS_FILE)
    token = os.environ.get("CHIAKI_GITHUB_TOKEN") or cfg.get("github_token", "")
    repo = (cfg.get("github_issue_repo") or
            getattr(state, "github_issue_repo", "") or
            "nlkcodenew/trimui-chiaki-ng")
    enabled = bool(getattr(state, "auto_upload_logs", True))
    return token.strip(), repo.strip(), enabled


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
    # Không đưa reason vào fingerprint: cùng một crash có thể được thử lại với
    # reason startup_retry sau khi lần upload đầu mất mạng.
    payload = "\n".join(text[-8000:] for _, text in sections)
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def _device_hash():
    value = str(getattr(state, "device_id", "unknown"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


def _issue_body(sections, reason, fingerprint):
    reason = _sanitize(str(reason).replace("`", ""))[:80]
    lines = [
        "Log được gửi tự động từ TrimUI Smart Pro S sau khi ứng dụng lỗi.",
        "",
        "| Trường | Giá trị |",
        "|---|---|",
        "| App | trimui-chiaki-ng v%s |" % APP_VERSION,
        "| Lý do | `%s` |" % reason,
        "| Thiết bị | `%s` |" % _device_hash(),
        "| Python | `%s` |" % platform.python_version(),
        "| Hệ thống | `%s` |" % _sanitize(platform.platform()),
        "| Fingerprint | `%s` |" % fingerprint[:16],
        "",
        "> Token, khóa đăng ký, PSN Account ID và địa chỉ IP nội bộ đã được lọc.",
    ]
    for name, text in sections:
        safe_text = text[-MAX_LOG_BYTES:].replace("```", "` ` `")
        lines.extend(["", "### %s" % name, "```text", safe_text, "```"])
    return "\n".join(lines)[:MAX_BODY_CHARS]


def _post_issue(token, repo, title, body):
    url = "https://api.github.com/repos/%s/issues" % repo
    payload = json.dumps({"title": title, "body": body}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer %s" % token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "trimui-chiaki-ng/%s" % APP_VERSION,
            "Content-Type": "application/json",
        },
    )
    # Khong tat verify TLS vi request mang token GitHub. Neu firmware thieu CA,
    # uploader se ghi loi va thu lai o lan khoi dong sau.
    with urllib.request.urlopen(request, timeout=TIMEOUT,
                                context=ssl.create_default_context()) as response:
        result = json.loads(response.read(128 * 1024).decode("utf-8"))
    return result.get("html_url", "")


def upload_pending(reason="crash", force=False):
    token, repo, enabled = _configuration()
    if not enabled and not force:
        log.info("log upload disabled in settings")
        return False
    if not force and not os.path.exists(PENDING_FILE):
        return False
    if not token:
        log.warning("log upload pending: missing secrets.json github_token")
        return False
    if not _REPO_NAME.fullmatch(repo):
        log.error("invalid github_issue_repo: %s", repo)
        return False

    sections = _collect()
    if not sections:
        log.warning("log upload pending but no readable logs")
        return False
    fingerprint = _fingerprint(sections, reason)
    history = _read_json(STATE_FILE)
    if not force and history.get("fingerprint") == fingerprint:
        try:
            os.remove(PENDING_FILE)
        except OSError:
            pass
        return True

    title = "[device-log] v%s %s %s" % (APP_VERSION, reason, fingerprint[:8])
    body = _issue_body(sections, reason, fingerprint)
    try:
        issue_url = _post_issue(token, repo, title, body)
    except Exception as exc:
        log.warning("GitHub log upload failed: %s", exc)
        return False

    tmp = STATE_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({
                "fingerprint": fingerprint,
                "version": APP_VERSION,
                "issue_url": issue_url,
                "uploaded_at": int(time.time()),
            }, handle, indent=2)
        os.replace(tmp, STATE_FILE)
        os.remove(PENDING_FILE)
    except OSError:
        pass
    log.info("GitHub log uploaded: %s", issue_url or "ok")
    return True


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


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--reason", default="crash")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    return 0 if upload_pending(args.reason, args.force) else 1


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Auto-update theo manifest.json, copy nguyen kieu RetroHub.

Khi ban moi duoc day len GitHub:
    - tools/make_release.py quet files/ va ghi manifest.json voi sha256 moi
    - app se goi check_for_update() o moi lan khoi dong (auto_update=True)
    - neu co phien ban moi (manifest["version"] > APP_VERSION), app hien popup
      cho phep nguoi dung chon CAI / DE SAU / BO QUA
    - neu nguoi dung chon CAI, moi file se duoc tai vao .update_staging, kiem
      tra sha256, roi doi sang cho that qua os.replace (tranh crash khi user
      rut the)
    - settings.json khong bi ghi de neu da ton tai (giu cau hinh nguoi dung)
    - cuoi cung goi request_restart() de launch.sh khoi dong lai app
"""

import gzip
import hashlib
import json
import os
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from . import state
from .paths import APP_DIR
from .version import APP_VERSION, is_newer
from .logger import get_logger

log = get_logger()

# Repo public mac dinh. Co the doi qua settings.json > update_url.
DEFAULT_REPO = "nlkcodenew/trimui-chiaki-ng"
DEFAULT_BRANCH = "main"

UPDATE_BASE_URL = "https://raw.githubusercontent.com/%s/%s" % (DEFAULT_REPO, DEFAULT_BRANCH)
LATEST_RELEASE_URL = "https://github.com/%s/releases/latest/download" % DEFAULT_REPO
GHPROXY_BASE_URL = "https://ghproxy.net/" + UPDATE_BASE_URL
CDN_BASE_URL = "https://cdn.jsdelivr.net/gh/%s@%s" % (DEFAULT_REPO, DEFAULT_BRANCH)

UA = "trimui-chiaki-ng/%s" % APP_VERSION
TIMEOUT = 15
MAX_MANIFEST_BYTES = 512 * 1024

# settings.json la file cua nguoi dung, bao gio cung khong nam trong OTA.
# Neu de no trong manifest, khi state.py random device_id roi ghi lai,
# hash se lech hang chu, lam pending_files() khong bao gio rong, gay vong
# lap update vong v. Exclude o ca make_release.py va pending_files() de
# phong 2 lop.
SETTINGS_REL = "settings.json"

MAX_FILE_BYTES = 16 * 1024 * 1024

STAGING_DIR = os.path.join(APP_DIR, ".update_staging")


def base_url():
    return (getattr(state, "update_url", "") or UPDATE_BASE_URL).rstrip("/")


def candidate_base_urls(rel_path=""):
    """Tra ve danh sach URL de thu theo thu tu uu tien (GitHub Raw -> ghproxy ->
    jsDelivr CDN). Voi manifest.json luon uu tien GitHub Raw de tranh CDN cache.
    """
    custom = base_url()
    candidates = [custom]
    if "raw.githubusercontent.com" in custom:
        candidates.append("https://ghproxy.net/" + custom)
        if rel_path.lower().endswith(".json"):
            return [custom, "https://ghproxy.net/" + custom]
        parts = custom.replace("https://raw.githubusercontent.com/", "").strip("/").split("/", 2)
        if len(parts) == 3:
            candidates.append("https://cdn.jsdelivr.net/gh/%s/%s@%s" % (parts[0], parts[1], parts[2]))
    return candidates


def candidate_manifest_urls():
    """Ưu tiên manifest đính kèm Release; main là cầu nối/fallback."""
    custom = getattr(state, "update_url", "") or ""
    if custom.strip():
        return ["%s/manifest.json" % base.rstrip("/")
                for base in candidate_base_urls("manifest.json")]
    urls = ["%s/manifest.json" % LATEST_RELEASE_URL]
    urls.extend("%s/manifest.json" % base.rstrip("/")
                for base in candidate_base_urls("manifest.json"))
    return urls


def payload_base_urls(manifest, rel_path=""):
    """URL payload nằm trong thư mục files/ của source repository."""
    out = []
    release_tag = (manifest or {}).get("release_tag")
    if isinstance(release_tag, str) and release_tag:
        release_path = release_tag.rstrip("/")
        if not release_path.endswith("/files"):
            release_path += "/files"
        out.append("https://raw.githubusercontent.com/%s/%s" %
                   (DEFAULT_REPO, release_path))
    manifest_base = (manifest or {}).get("base_url")
    if isinstance(manifest_base, str) and manifest_base.strip():
        out.append(manifest_base.rstrip("/"))
    custom = getattr(state, "update_url", "") or ""
    if custom.strip():
        out.extend(candidate_base_urls(rel_path))
    else:
        out.extend([
            UPDATE_BASE_URL + "/files",
            "https://ghproxy.net/" + UPDATE_BASE_URL + "/files",
            CDN_BASE_URL + "/files",
        ])
    seen = set()
    return [url for url in out if not (url in seen or seen.add(url))]


def _get(url, max_bytes, timeout=TIMEOUT):
    headers = {
        "User-Agent": UA,
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
    }
    req = urllib.request.Request(url, headers=headers)
    kwargs = {"timeout": timeout}
    if url.startswith("https://"):
        kwargs["context"] = ssl.create_default_context()
    started = time.time()
    log.info("network GET start: %s timeout=%ss", url, timeout)
    with urllib.request.urlopen(req, **kwargs) as resp:
        buf = bytearray()
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            buf.extend(chunk)
            if len(buf) > max_bytes:
                raise ValueError("response larger than %d bytes" % max_bytes)
    elapsed = time.time() - started
    log.info("network GET ok: status=%s bytes=%d elapsed=%.2fs url=%s",
             getattr(resp, "status", "?"), len(buf), elapsed, url)
    return bytes(buf)


def _fetch_blob(rel_path, max_bytes, expected_sha=None, manifest=None):
    last = None
    quoted = urllib.parse.quote(rel_path, safe="/")
    for base in payload_base_urls(manifest, rel_path):
        url = "%s/%s?_t=%d" % (base, quoted, int(time.time()))
        for attempt in range(2):
            try:
                log.info("OTA download: file=%s attempt=%d url=%s",
                         rel_path, attempt + 1, url)
                data = _get(url, max_bytes)
                if expected_sha:
                    if hashlib.sha256(data).hexdigest() == expected_sha:
                        log.info("OTA verified: file=%s bytes=%d", rel_path, len(data))
                        return data
                    last = ValueError("hash mismatch for %s" % rel_path)
                    log.warning("OTA hash mismatch: file=%s url=%s", rel_path, url)
                else:
                    return data
            except Exception as exc:
                last = exc
                log.warning("OTA download attempt failed: file=%s url=%s error=%s",
                            rel_path, url, exc)
            time.sleep(0.3)
    raise last or RuntimeError("fetch failed for %s" % rel_path)


def _safe_rel(rel):
    if not rel or rel.startswith("/") or "\\" in rel:
        return False
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return False
    return True


def sha256_of(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 18), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def fetch_manifest():
    for manifest_url in candidate_manifest_urls():
        try:
            separator = "&" if "?" in manifest_url else "?"
            url = "%s%s_t=%d" % (manifest_url, separator, int(time.time()))
            log.info("OTA manifest check: %s", url)
            raw = _get(url, MAX_MANIFEST_BYTES)
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict) or not parsed.get("version"):
                continue
            files = parsed.get("files", [])
            if not isinstance(files, list):
                continue
            ok = True
            for f in files:
                if not isinstance(f, dict):
                    ok = False
                    break
                if not _safe_rel(f.get("path", "")) or len(f.get("sha256", "")) != 64:
                    ok = False
                    break
            if ok:
                log.info("OTA manifest ready: version=%s files=%d source=%s",
                         parsed.get("version"), len(files), manifest_url)
                return parsed
        except (urllib.error.URLError, OSError, ValueError, UnicodeDecodeError) as exc:
            log.warning("OTA manifest failed: source=%s error=%s", manifest_url, exc)
            continue
    return None


def pending_files(manifest):
    out = []
    for f in manifest.get("files", []):
        # settings.json luon duoc loai: state.py tu sinh device_id ngau nhien
        # o lan chay dau va luu xuong, hash se khac manifest vinh vien. De no
        # trong pending thi app se bat popup update mai mai.
        if f.get("path") == SETTINGS_REL:
            continue
        local = os.path.join(APP_DIR, f["path"])
        if sha256_of(local) != f["sha256"]:
            out.append(f)
    return out


def check_for_update(force=False):
    """Tra ve (manifest, files) neu co ban moi, None neu khong.

    Quy tac:
        - Neu remote version moi hon APP_VERSION (is_newer=True) va user BO QUA
          -> return None, khong hoi lai.
        - Neu chi con file pending (catalog-only/runtime-only chua dong bo),
          KHONG ap dung skipped_versions, de user van duoc nhan nhac fix catalog
          sau khi skip.
        - Neu khong co gi moi -> return None.
    """
    try:
        m = fetch_manifest()
    except Exception as exc:
        log.exception("OTA update check failed: %s", exc)
        return None
    if not m:
        return None
    files = pending_files(m)
    is_new_version = is_newer(m["version"], APP_VERSION)
    if not is_new_version and not files:
        return None
    # Skipped_versions chi chan popup version-moi that su, khong chan catalog-only.
    if (not force
            and is_new_version
            and m["version"] in (state.skipped_versions or [])):
        return None
    return m, files


def download_update(manifest, files, progress=None):
    ok = _stage_files(manifest, files, progress)
    if not ok:
        shutil.rmtree(STAGING_DIR, ignore_errors=True)
    return ok


def _stage_files(manifest, files, progress=None):
    shutil.rmtree(STAGING_DIR, ignore_errors=True)
    try:
        os.makedirs(STAGING_DIR, exist_ok=True)
    except OSError as exc:
        log.error("OTA staging setup failed: %s", exc)
        return False
    total = len(files)
    log.info("OTA staging start: version=%s files=%d network=required",
             manifest.get("version"), total)
    for i, f in enumerate(files):
        if progress:
            progress(i, total, f["path"])
        try:
            data = _fetch_blob(f["path"], MAX_FILE_BYTES,
                               expected_sha=f["sha256"], manifest=manifest)
        except ValueError:
            log.error("OTA hash mismatch for %s", f["path"])
            return False
        except Exception as exc:
            log.error("OTA download failed for %s: %s", f["path"], exc)
            return False
        dst = os.path.join(STAGING_DIR, f["path"])
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as fh:
                fh.write(data)
        except OSError as exc:
            log.error("OTA staging write failed for %s: %s", f["path"], exc)
            return False
    if progress:
        progress(total, total, "")
    log.info("OTA staging complete: version=%s files=%d", manifest.get("version"), total)
    return True


def apply_update(manifest, files):
    """Move staged files vao APP_DIR. version.py duoc doi cuoi cung.

    os.replace dam bao shell dang chay launch.sh khong bi mat inode giua chung.
    settings.json luon duoc bo qua, de bao toan cau hinh nguoi dung. Neu loi
    manifest tinh ghi no len, cung khong thanh cong (defense in depth).
    """
    # Loai settings.json o 2 lop: khoi staged (neu co) va khoi ordered list.
    cleaned = [f for f in files if f.get("path") != SETTINGS_REL]
    ordered = sorted(cleaned, key=lambda f: f["path"] == "rh/version.py")
    moved = 0
    for f in ordered:
        src = os.path.join(STAGING_DIR, f["path"])
        dst = os.path.join(APP_DIR, f["path"])
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.replace(src, dst)
            if f["path"].endswith(".sh") or f["path"].startswith("bin/"):
                try:
                    os.chmod(dst, 0o755)
                except OSError:
                    pass
            moved += 1
        except OSError as exc:
            log.error("OTA install failed for %s: %s", f["path"], exc)
            return False
    for rel in manifest.get("remove", []):
        if not _safe_rel(rel):
            continue
        try:
            os.remove(os.path.join(APP_DIR, rel))
        except OSError:
            pass
    _purge_pycache()
    shutil.rmtree(STAGING_DIR, ignore_errors=True)
    log.info("OTA installed: %d file(s) -> %s", moved, manifest["version"])
    return True


def _purge_pycache():
    for root, dirs, _ in os.walk(APP_DIR):
        for d in list(dirs):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                dirs.remove(d)


def skip_version(version):
    if version not in (state.skipped_versions or []):
        state.skipped_versions.append(version)
        state.save_settings()


def request_restart():
    """Yeu cau launch.sh chay lai app. Ghi file /tmp/launch_game.sh de launcher
    nhan vao vong lap while true va khoi dong app.py moi."""
    try:
        with open("/tmp/launch_game.sh", "w") as f:
            f.write("#!/bin/sh\n:\n")
        os.chmod("/tmp/launch_game.sh", 0o755)
        return True
    except OSError as exc:
        log.error("OTA restart request failed: %s", exc)
        return False


def release_note(manifest, lang="VI"):
    note = (manifest or {}).get("note") if isinstance(manifest, dict) else None
    if isinstance(note, str):
        note = {"vi": note, "en": note}
    if not isinstance(note, dict):
        return ""
    key = "vi" if (lang or "VI").upper() == "VI" else "en"
    other = "en" if key == "vi" else "vi"
    for k in (key, other):
        text = note.get(k)
        if isinstance(text, str) and text.strip():
            return " ".join(text.split())
    return ""

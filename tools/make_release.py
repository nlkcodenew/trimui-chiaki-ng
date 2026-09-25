#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tạo manifest OTA và gói ZIP cài đặt cho GitHub Releases.

Quét toàn bộ files/, tính sha256 cho mỗi file OTA và tạo ZIP có cấu trúc
App/Chiaki/ để người dùng giải nén trực tiếp vào gốc thẻ nhớ.
"""

import hashlib
import json
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_DIR = os.path.join(ROOT, "files")
MANIFEST_PATH = os.path.join(ROOT, "manifest.json")
DIST_DIR = os.path.join(ROOT, "dist")
TZ = timezone(timedelta(hours=7))
REPO = "nlkcodenew/trimui-chiaki-ng"
BRANCH = "main"

EXCLUDE_NAMES = {"__pycache__", ".update_staging", ".update_runtime"}
EXCLUDE_FILES = {"desktop.ini", ".DS_Store"}
# settings.json la file cau hinh nguoi dung (device_id random + tuy chinh).
# Dua no vao manifest se lam pending_files luon co no vi hash luon lech sau
# lan chay dau, gay vong lap popup. Exclude ngay tu be build.
EXCLUDE_USER_FILES = {
    "settings.json",
    "secrets.json",
    "secrets..json",
    ".log_upload_state.json",
    ".pending_crash",
}
ARCHIVE_EXCLUDE_FILES = {
    "secrets.json",
    "secrets..json",
    "settings.json.tmp",
}
ARCHIVE_EXCLUDE_PREFIXES = (
    "Chiaki-loi.txt",
    "Chiaki-debug.log",
)
LF_NORMALIZED_EXTENSIONS = {
    ".json", ".md", ".py", ".sh", ".txt", ".yaml", ".yml",
}


def _runtime_file(name):
    return name.startswith(ARCHIVE_EXCLUDE_PREFIXES)


def app_version():
    with open(os.path.join(FILES_DIR, "rh", "version.py"), encoding="utf-8") as f:
        m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', f.read())
    if not m:
        raise SystemExit("khong thay APP_VERSION trong files/rh/version.py")
    return m.group(1).strip().lstrip("v")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def release_bytes(path):
    with open(path, "rb") as handle:
        data = handle.read()
    if os.path.splitext(path)[1].lower() in LF_NORMALIZED_EXTENSIONS:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data


def _archive_file(archive, source, target, executable=False):
    """Ghi file với mode Unix ổn định, kể cả khi build trên Windows."""
    data = release_bytes(source)
    info = zipfile.ZipInfo(target, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    mode = 0o100755 if executable else 0o100644
    info.external_attr = mode << 16
    archive.writestr(info, data)


def _archive_excluded(name):
    return (
        name in EXCLUDE_FILES
        or name in ARCHIVE_EXCLUDE_FILES
        or name.startswith(".")
        or name.endswith(".pyc")
        or _runtime_file(name)
    )


def build_release_zip(version):
    """Tạo ZIP có cấu trúc App/Chiaki để giải nén vào gốc thẻ nhớ."""
    shutil.rmtree(DIST_DIR, ignore_errors=True)
    os.makedirs(DIST_DIR, exist_ok=True)
    archive_name = "trimui-chiaki-ng-v%s.zip" % version
    archive_path = os.path.join(DIST_DIR, archive_name)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        _archive_file(archive, os.path.join(ROOT, "INSTALL.md"), "CAI_DAT.md")
        _archive_file(archive, os.path.join(ROOT, "LICENSE"), "LICENSE.txt")
        for root, dirs, names in os.walk(FILES_DIR):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_NAMES)
            for name in sorted(names):
                if _archive_excluded(name):
                    continue
                src = os.path.join(root, name)
                rel = os.path.relpath(src, FILES_DIR).replace(os.sep, "/")
                executable = rel.endswith(".sh") or rel.startswith("bin/")
                _archive_file(archive, src, "App/Chiaki/%s" % rel, executable)
    with open(archive_path, "rb") as handle:
        checksum = sha256(handle.read())
    checksum_path = archive_path + ".sha256"
    with open(checksum_path, "w", encoding="ascii", newline="\n") as handle:
        handle.write("%s  %s\n" % (checksum, archive_name))
    return archive_name, checksum, os.path.getsize(archive_path)


def main():
    version = app_version()
    print("APP_VERSION = %s" % version)
    files = []
    total = 0
    for root, dirs, names in os.walk(FILES_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_NAMES]
        for fn in sorted(names):
            if (fn in EXCLUDE_FILES or fn in EXCLUDE_USER_FILES
                    or fn.startswith(".") or fn.endswith(".pyc")
                    or _runtime_file(fn)):
                continue
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, FILES_DIR).replace(os.sep, "/")
            data = release_bytes(fp)
            files.append({
                "path": rel,
                "sha256": sha256(data),
                "size": len(data),
            })
            total += len(data)
            print("  %s (%d bytes)" % (rel, len(data)))
    print("total: %d file(s), %d bytes" % (len(files), total))

    manifest = {
        "version": version,
        "app": "trimui-chiaki-ng",
        "python": "3.10+",
        "built": datetime.now(TZ).replace(microsecond=0).isoformat(),
        "base_url": "https://raw.githubusercontent.com/%s/v%s/files" % (REPO, version),
        # Hau to /files giu tuong thich voi updater v0.2.4/v0.2.5, noi ghep
        # release_tag truc tiep voi path app.py thay vi biet source nam trong
        # thu muc files/. Updater moi cung chap nhan dinh dang nay.
        "release_tag": "v%s/files" % version,
        "note": {
            "vi": "v%s: thêm hướng dẫn trong app và hiện mã máy cạnh version." % version,
            "en": "v%s: add an in-app guide and show the device ID beside the version." % version,
        },
        "files": files,
        "remove": [],
    }
    archive_name, archive_sha, archive_size = build_release_zip(version)
    manifest["release_asset"] = {
        "name": archive_name,
        "sha256": archive_sha,
        "size": archive_size,
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("wrote %s" % MANIFEST_PATH)


if __name__ == "__main__":
    main()

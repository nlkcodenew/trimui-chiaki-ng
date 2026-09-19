#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tao manifest.json cho OTA updater.

Quet toan bo files/, tinh sha256 + size cho moi file, ghi ra manifest.json.
File nay duoc GitHub Action goi khi push tag v* hoac chay thu cong.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_DIR = os.path.join(ROOT, "files")
MANIFEST_PATH = os.path.join(ROOT, "manifest.json")
TZ = timezone(timedelta(hours=7))
REPO = "nlkcodenew/trimui-chiaki-ng"
BRANCH = "main"

EXCLUDE_NAMES = {"__pycache__", ".update_staging", ".update_runtime"}
EXCLUDE_FILES = {"desktop.ini", ".DS_Store"}


def app_version():
    with open(os.path.join(FILES_DIR, "rh", "version.py"), encoding="utf-8") as f:
        m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', f.read())
    if not m:
        raise SystemExit("khong thay APP_VERSION trong files/rh/version.py")
    return m.group(1).strip().lstrip("v")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    version = app_version()
    print("APP_VERSION = %s" % version)
    files = []
    total = 0
    for root, dirs, names in os.walk(FILES_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_NAMES]
        for fn in sorted(names):
            if fn in EXCLUDE_FILES or fn.startswith(".") or fn.endswith(".pyc"):
                continue
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, FILES_DIR).replace(os.sep, "/")
            with open(fp, "rb") as f:
                data = f.read()
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
        "base_url": "https://raw.githubusercontent.com/%s/%s" % (REPO, BRANCH),
        "note": {
            "vi": "Phien ban %s - cap nhat tu dong." % version,
            "en": "Version %s - auto-update." % version,
        },
        "files": files,
        "remove": [],
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("wrote %s" % MANIFEST_PATH)


if __name__ == "__main__":
    main()
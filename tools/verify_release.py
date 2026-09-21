#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm tra manifest và ZIP trước khi đưa lên GitHub Releases."""

import glob
import hashlib
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_DIR = os.path.join(ROOT, "files")

FORBIDDEN_MANIFEST = {
    "settings.json",
    "secrets.json",
    ".log_upload_state.json",
    ".pending_crash",
}
REQUIRED_ARCHIVE = {
    "CAI_DAT.md",
    "LICENSE.txt",
    "App/Chiaki/app.py",
    "App/Chiaki/config.json",
    "App/Chiaki/icon.png",
    "App/Chiaki/launch.sh",
    "App/Chiaki/settings.json",
    "App/Chiaki/secrets.example.json",
    "App/Chiaki/assets/fallback.ttf",
    "App/Chiaki/vendor/sdl2/__init__.py",
}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(256 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message):
    raise SystemExit("release verification failed: %s" % message)


def app_version():
    path = os.path.join(FILES_DIR, "rh", "version.py")
    with open(path, encoding="utf-8") as handle:
        match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)', handle.read())
    return match.group(1) if match else ""


def main():
    manifest_path = os.path.join(ROOT, "manifest.json")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)

    version = app_version()
    if manifest.get("version") != version:
        fail("manifest version does not match APP_VERSION")
    if manifest.get("release_tag") != "v%s" % version:
        fail("release_tag does not match APP_VERSION")

    listed = set()
    for item in manifest.get("files", []):
        rel = item.get("path", "")
        if rel in FORBIDDEN_MANIFEST:
            fail("private/user file appears in manifest: %s" % rel)
        source = os.path.join(FILES_DIR, *rel.split("/"))
        if not os.path.isfile(source):
            fail("manifest source is missing: %s" % rel)
        if sha256_file(source) != item.get("sha256"):
            fail("manifest hash mismatch: %s" % rel)
        listed.add(rel)

    archives = glob.glob(os.path.join(ROOT, "dist", "trimui-chiaki-ng-v*.zip"))
    if len(archives) != 1:
        fail("expected exactly one release ZIP")
    archive_path = archives[0]
    expected_name = "trimui-chiaki-ng-v%s.zip" % version
    if os.path.basename(archive_path) != expected_name:
        fail("ZIP name does not match APP_VERSION")

    release_asset = manifest.get("release_asset", {})
    if release_asset.get("name") != expected_name:
        fail("release asset name mismatch")
    if release_asset.get("sha256") != sha256_file(archive_path):
        fail("release asset hash mismatch")
    if release_asset.get("size") != os.path.getsize(archive_path):
        fail("release asset size mismatch")

    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    missing = REQUIRED_ARCHIVE - names
    if missing:
        fail("ZIP is missing: %s" % ", ".join(sorted(missing)))
    for name in names:
        base = os.path.basename(name)
        if base == "secrets.json" or base.startswith(".log_upload_state"):
            fail("secret/runtime file appears in ZIP: %s" % name)
        if base.startswith(".pending_crash") or base.startswith("Chiaki-loi.txt"):
            fail("log/runtime file appears in ZIP: %s" % name)
        if base.startswith("Chiaki-debug.log"):
            fail("log/runtime file appears in ZIP: %s" % name)

    checksum_path = archive_path + ".sha256"
    with open(checksum_path, encoding="ascii") as handle:
        checksum_line = handle.read().strip()
    if checksum_line != "%s  %s" % (sha256_file(archive_path), expected_name):
        fail("sha256 sidecar is invalid")

    print("release verified: v%s, %d OTA files, %d ZIP entries" %
          (version, len(listed), len(names)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

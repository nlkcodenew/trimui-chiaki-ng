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

from make_release import release_bytes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_DIR = os.path.join(ROOT, "files")
CA_BUNDLE_SHA256 = "f66dff1bdf8f96060b8177976f8b7d9254bc89bc4db933d769f7384d28480bc9"
BRICK_RUNTIME = {
    "libSDL2-2.0.so.0": "0fc2e4d6bfdf3a84eb9334dd7a39096c1f9555c3101140883497ecee73c36d01",
    "libatomic.so.1": "fead8ddf3612a4867881747c947a68f38c1d50f6a677eb8a38acdf9cea12bb4f",
    "libavcodec.so.60": "cc629446328d77ccea432e89c5cdf94dc234e4ebfb33210a2cef08808f1c9bde",
    "libavutil.so.58": "017691c97d410c546fb3806af316be06c4be518b0349ca5f026d8b8aff78e284",
    "libcrypto.so.1.1": "e40f8d5a4c1ca2c2fdfe0fe4c98f9d7f45cf200b3355a93b78b71f19a4cd25b1",
    "libevent-2.1.so.7": "ff25e48ec5e768768f67f1ff7c96176631ba0298625a54c51705fd52654af725",
    "libjson-c.so.5": "02312a94c5be7b846a0152a6e8a3c1536d3dfa84389f601f01ee926596b1314d",
    "liblzma.so.5": "47978ea76e3d91a6d9d8f6f6202fa877be8be7a89d54ed670a1eb1c0098988a6",
    "libnghttp2.so.14": "a66731cd3df3d495bf74e6309b39d0d4b09b59d7b3dc8d5d3cf5ff073f292540",
    "libopus.so.0": "763c521af740736a3fa13a81382b609e1ef83bc4bc7a6bab60d0b1eae24b0123",
    "libssl.so.1.1": "a8e40386762686f58a9dfb5115b8924050eff51fcb3393629d4f04ea50ec60c2",
    "libswresample.so.4": "01cf2e3d7c74c31bfaa8467a323d30a7cb5840ff68167d669f7d59ede337ffb4",
    "libswscale.so.7": "77b9ba3c7c68a78f17972decef03a43a38ac8aa2877e7ef3b679035f16f25c7d",
    "libz.so.1": "93094436a4ecb7d8a42f2b4c5c32347a8b8081afae68e7afaaf833ec87aa7f34",
}

FORBIDDEN_MANIFEST = {
    "settings.json",
    "secrets.json",
    "secrets..json",
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
    "App/Chiaki/bin/chiaki-stream",
    "App/Chiaki/certs/README.txt",
    "App/Chiaki/certs/cacert.pem",
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


def verify_aarch64_elf(path, label):
    with open(path, "rb") as handle:
        elf_header = handle.read(20)
    if elf_header[:4] != b"\x7fELF" or elf_header[4] != 2 or elf_header[5] != 1:
        fail("%s is not a little-endian ELF64 binary" % label)
    if int.from_bytes(elf_header[18:20], "little") != 183:
        fail("%s is not an AArch64 binary" % label)


def verify_symbol_version(path, version, label):
    with open(path, "rb") as handle:
        if version.encode("ascii") not in handle.read():
            fail("%s does not contain symbol version %s" % (label, version))


def main():
    manifest_path = os.path.join(ROOT, "manifest.json")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)

    version = app_version()
    if manifest.get("version") != version:
        fail("manifest version does not match APP_VERSION")
    if manifest.get("release_tag") not in ("v%s" % version, "v%s/files" % version):
        fail("release_tag does not match APP_VERSION")
    expected_base = "https://raw.githubusercontent.com/nlkcodenew/trimui-chiaki-ng/v%s/files" % version
    if manifest.get("base_url") != expected_base:
        fail("base_url does not point to immutable tag files directory")

    with open(os.path.join(FILES_DIR, "settings.json"), encoding="utf-8") as handle:
        default_settings = json.load(handle)
    if default_settings.get("device_id"):
        fail("default settings.json must not contain a generated device_id")

    ca_bundle_path = os.path.join(FILES_DIR, "certs", "cacert.pem")
    if sha256_file(ca_bundle_path) != CA_BUNDLE_SHA256:
        fail("bundled CA checksum does not match the reviewed Mozilla bundle")

    native_path = os.path.join(FILES_DIR, "bin", "chiaki-stream")
    verify_aarch64_elf(native_path, "chiaki-stream")
    verify_symbol_version(native_path, "OPENSSL_1_1_1", "chiaki-stream")

    runtime_dir = os.path.join(FILES_DIR, "libs", "brick-stock")
    for name, expected_hash in sorted(BRICK_RUNTIME.items()):
        runtime_path = os.path.join(runtime_dir, name)
        verify_aarch64_elf(runtime_path, "Brick runtime %s" % name)
        if sha256_file(runtime_path) != expected_hash:
            fail("Brick runtime checksum mismatch: %s" % name)
    for name in ("libcrypto.so.1.1", "libssl.so.1.1"):
        verify_symbol_version(
            os.path.join(runtime_dir, name), "OPENSSL_1_1_1", "Brick runtime %s" % name)

    listed = set()
    for item in manifest.get("files", []):
        rel = item.get("path", "")
        if rel in FORBIDDEN_MANIFEST:
            fail("private/user file appears in manifest: %s" % rel)
        base = os.path.basename(rel)
        if base.startswith("Chiaki-loi.txt") or base.startswith("Chiaki-debug.log"):
            fail("log file appears in manifest: %s" % rel)
        source = os.path.join(FILES_DIR, *rel.split("/"))
        if not os.path.isfile(source):
            fail("manifest source is missing: %s" % rel)
        if hashlib.sha256(release_bytes(source)).hexdigest() != item.get("sha256"):
            fail("manifest hash mismatch: %s" % rel)
        listed.add(rel)

    if "certs/cacert.pem" not in listed:
        fail("bundled CA is missing from OTA manifest")
    expected_runtime = {"libs/brick-stock/%s" % name for name in BRICK_RUNTIME}
    missing_runtime = expected_runtime - listed
    if missing_runtime:
        fail("Brick runtime is missing from manifest: %s" % ", ".join(sorted(missing_runtime)))
    if "libs/brick-stock/THIRD_PARTY_NOTICES.txt" not in listed:
        fail("Brick runtime notices are missing from manifest")

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
        for item in manifest.get("files", []):
            archived = archive.read("App/Chiaki/%s" % item["path"])
            if hashlib.sha256(archived).hexdigest() != item.get("sha256"):
                fail("ZIP payload hash mismatch: %s" % item["path"])
    missing = REQUIRED_ARCHIVE - names
    if missing:
        fail("ZIP is missing: %s" % ", ".join(sorted(missing)))
    for name in names:
        base = os.path.basename(name)
        if base in ("secrets.json", "secrets..json") or base.startswith(".log_upload_state"):
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

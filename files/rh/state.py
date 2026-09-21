# -*- coding: utf-8 -*-
"""Bien runtime, chia se giua cac module.

Luon dung `state.<ten>` thay vi `from .state import ...` de cap nhat thay doi
giua cac vong lap (ngon ngu, profile video,...) duoc nhin thay ngay.
"""

import json
import os
import threading
from .paths import APP_DIR, SETTINGS_FILE

current_lang = "VI"
video_resolution = "720p"
video_fps = 30
video_bitrate = 8000
audio_volume = 80
wifi_awake = True
auto_update = True
enable_logging = False
device_id = ""
skipped_versions = []
update_url = ""
pending_update = ""
pending_catalog_notice = ""
host_name = ""
host_addr = ""
psn_account_id = ""
psn_online_id = ""
regist_key = ""
auto_upload_logs = True
github_issue_repo = "nlkcodenew/trimui-chiaki-ng"

_save_lock = threading.Lock()


def _load():
    global current_lang, video_resolution, video_fps, video_bitrate, audio_volume
    global wifi_awake, auto_update, enable_logging, device_id, skipped_versions
    global update_url, pending_update, pending_catalog_notice, host_name, host_addr
    global psn_account_id, psn_online_id, regist_key
    global auto_upload_logs, github_issue_repo
    if not os.path.exists(SETTINGS_FILE):
        return
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError, json.JSONDecodeError):
        return
    current_lang = cfg.get("language", current_lang)
    video_resolution = cfg.get("video_resolution", video_resolution)
    video_fps = int(cfg.get("video_fps", video_fps))
    video_bitrate = int(cfg.get("video_bitrate", video_bitrate))
    audio_volume = int(cfg.get("audio_volume", audio_volume))
    wifi_awake = bool(cfg.get("wifi_awake", wifi_awake))
    auto_update = bool(cfg.get("auto_update", auto_update))
    enable_logging = bool(cfg.get("enable_logging", enable_logging))
    device_id = cfg.get("device_id", device_id)
    skipped_versions = cfg.get("skipped_versions", []) or []
    update_url = cfg.get("update_url", update_url)
    pending_update = cfg.get("pending_update", pending_update)
    pending_catalog_notice = cfg.get("pending_catalog_notice", pending_catalog_notice)
    host_name = cfg.get("host_name", host_name)
    host_addr = cfg.get("host_addr", host_addr)
    psn_account_id = cfg.get("psn_account_id", psn_account_id)
    psn_online_id = cfg.get("psn_online_id", psn_online_id)
    regist_key = cfg.get("regist_key", regist_key)
    auto_upload_logs = bool(cfg.get("auto_upload_logs", auto_upload_logs))
    github_issue_repo = cfg.get("github_issue_repo", github_issue_repo)


def save_settings():
    """Ghi settings.json theo kieu atomic: ghi file tam roi rename, tranh bi trung
    luc may tat dot ngot giua chung (deep suspend hay user rut the)."""
    with _save_lock:
        try:
            tmp = SETTINGS_FILE + ".tmp"
            data = {
                "language": current_lang,
                "video_resolution": video_resolution,
                "video_fps": video_fps,
                "video_bitrate": video_bitrate,
                "audio_volume": audio_volume,
                "wifi_awake": wifi_awake,
                "auto_update": auto_update,
                "enable_logging": enable_logging,
                "device_id": device_id,
                "skipped_versions": skipped_versions,
                "update_url": update_url,
                "pending_update": pending_update,
                "pending_catalog_notice": pending_catalog_notice,
                "host_name": host_name,
                "host_addr": host_addr,
                "psn_account_id": psn_account_id,
                "psn_online_id": psn_online_id,
                "regist_key": regist_key,
                "auto_upload_logs": auto_upload_logs,
                "github_issue_repo": github_issue_repo,
            }
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, SETTINGS_FILE)
        except OSError as exc:
            print("save_settings failed: %s" % exc)


_load()
if not device_id:
    import random
    device_id = "CHI-%s" % "".join(random.choices("0123456789ABCDEF", k=4))
    save_settings()

SCREEN_W = 1280
SCREEN_H = 720

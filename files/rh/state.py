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
host_target = 0
psn_account_id = ""
psn_online_id = ""
regist_key = ""
rp_key = ""
rp_key_type = 0
server_mac = ""
auto_upload_logs = True
github_issue_repo = "nlkcodenew/trimui-chiaki-ng"
settings_load_error = ""
settings_save_error = ""

_save_lock = threading.Lock()


def _load():
    global settings_load_error
    global current_lang, video_resolution, video_fps, video_bitrate, audio_volume
    global wifi_awake, auto_update, enable_logging, device_id, skipped_versions
    global update_url, pending_update, pending_catalog_notice, host_name, host_addr
    global psn_account_id, psn_online_id, regist_key, rp_key, rp_key_type, server_mac
    global host_target
    global auto_upload_logs, github_issue_repo
    if not os.path.exists(SETTINGS_FILE):
        return
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        settings_load_error = exc.__class__.__name__
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
    host_target = int(cfg.get("host_target", host_target) or 0)
    psn_account_id = cfg.get("psn_account_id", psn_account_id)
    psn_online_id = cfg.get("psn_online_id", psn_online_id)
    regist_key = cfg.get("regist_key", regist_key)
    rp_key = cfg.get("rp_key", rp_key)
    rp_key_type = int(cfg.get("rp_key_type", rp_key_type) or 0)
    server_mac = cfg.get("server_mac", server_mac)
    if str(psn_account_id).startswith("stub-rp-key-"):
        psn_account_id = ""
        regist_key = ""
    auto_upload_logs = bool(cfg.get("auto_upload_logs", auto_upload_logs))
    github_issue_repo = cfg.get("github_issue_repo", github_issue_repo)


def save_settings():
    """Ghi settings.json theo kieu atomic: ghi file tam roi rename, tranh bi trung
    luc may tat dot ngot giua chung (deep suspend hay user rut the)."""
    global settings_save_error
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
                "host_target": host_target,
                "psn_account_id": psn_account_id,
                "psn_online_id": psn_online_id,
                "regist_key": regist_key,
                "rp_key": rp_key,
                "rp_key_type": rp_key_type,
                "server_mac": server_mac,
                "auto_upload_logs": auto_upload_logs,
                "github_issue_repo": github_issue_repo,
            }
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, SETTINGS_FILE)
            settings_save_error = ""
            return True
        except OSError as exc:
            settings_save_error = exc.__class__.__name__
            print("save_settings failed: %s" % exc)
            return False


_load()
# v0.2.3 vo tinh dong goi device_id nay trong settings.json. OTA khong ghi de
# cau hinh nguoi dung, nen doi no mot lan tren cac may da cai ban bi loi.
if not device_id or device_id == "CHI-A6A9":
    import random
    device_id = "CHI-%s" % "".join(random.choices("0123456789ABCDEF", k=4))
    if not settings_load_error:
        save_settings()

SCREEN_W = 1280
SCREEN_H = 720

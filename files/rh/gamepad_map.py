# -*- coding: utf-8 -*-
"""Doc va ghi ban do nut cua Brick Pro.

Backend Go doc mot tai day ``bluetooth-map.json``. File nay cho phep nguoi
dung doi ma phim Linux cua tung nut ma khong can cai lai app.

Thong tin phim lay truc tiep tu ``/proc/bus/input/devices`` va ``/dev/input/``
nhu backend, nen man hinh THU BUT va phien Bluetooth luon thong nhat.
"""

import errno
import json
import os
import struct

from .logger import get_logger

log = get_logger()

MAP_NAME = "bluetooth-map.json"
DEVICES_FILE = "/proc/bus/input/devices"

# struct input_event tren ARM64: struct timeval gom hai long 64-bit, roi u16
# type, u16 code va s32 value, khong co padding. "q" la long long 8 byte;
# "l" trong struct cua Python chi la 4 byte nen khong dung.
EVENT_FORMAT = "@qqHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
if EVENT_SIZE != 24:
    raise RuntimeError("input_event ABI khong dung: %d byte" % EVENT_SIZE)

EV_KEY = 1

# HID report descriptor quang bao nut o vung BTN_GAMEPAD (0x130..0x140).
BTN_GAMEPAD_MIN = 0x130
BTN_GAMEPAD_MAX = 0x140

# Mac dinh phai khop voi defaultMapping() trong bluetooth-native/mapping.go.
DEFAULT_BUTTONS = {
    "a": 304, "b": 305, "x": 307, "y": 308,
    "l1": 310, "r1": 311, "l2": 312, "r2": 313,
    "select": 314, "start": 315, "mode": 316,
    "l3": 317, "r3": 318,
    "dpad_up": 103, "dpad_down": 108, "dpad_left": 105, "dpad_right": 106,
}

DEFAULT_AXES = {
    "left_x": 0, "left_y": 1, "l2": 2,
    "right_x": 3, "right_y": 4, "r2": 5,
    "hat_x": 16, "hat_y": 17,
}

# Nut tren vo may theo layout in, de hien thi cho dung.
BUTTON_LABELS = {
    "a": "A", "b": "B", "x": "X", "y": "Y",
    "l1": "L1", "r1": "R1", "l2": "L2", "r2": "R2",
    "select": "SELECT", "start": "START",
    "l3": "L3", "r3": "R3", "mode": "MODE",
}

def is_gamepad_key(code):
    """Ma phim trong vung BTN_GAMEPAD, tuc la nut gamepad chu khong phai phim."""
    return BTN_GAMEPAD_MIN <= code <= BTN_GAMEPAD_MAX


def map_path(app_dir):
    return os.path.join(app_dir, MAP_NAME)


def load_map(app_dir):
    """Tra ve (buttons, axes, error). Khong co file thi dung mac dinh."""
    path = map_path(app_dir)
    buttons = dict(DEFAULT_BUTTONS)
    axes = dict(DEFAULT_AXES)
    if not os.path.isfile(path):
        return buttons, axes, ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle) or {}
    except (OSError, ValueError) as exc:
        return buttons, axes, str(exc)
    if not isinstance(data, dict):
        return buttons, axes, "not an object"
    raw_buttons = data.get("buttons")
    if isinstance(raw_buttons, dict):
        for name, code in raw_buttons.items():
            if name in buttons and isinstance(code, int) and 0 < code < 768:
                buttons[name] = code
    raw_axes = data.get("axes")
    if isinstance(raw_axes, dict):
        for name, code in raw_axes.items():
            if name in axes and isinstance(code, int) and 0 <= code < 64:
                axes[name] = code
    return buttons, axes, ""


def save_map(app_dir, buttons, axes):
    path = map_path(app_dir)
    payload = {
        "version": 1,
        "note": "Do app viet khi ban thu nut. Xoa file de dung mac dinh.",
        "buttons": {name: int(code) for name, code in sorted(buttons.items()) if code},
        "axes": {name: int(code) for name, code in sorted(axes.items()) if code is not None},
    }
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)
    log.info("da luu ban do nut: %s", path)
    return path


def read_devices():
    """Parse /proc/bus/input/devices thanh danh sach (ten, handlers)."""
    out = []
    try:
        with open(DEVICES_FILE, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError as exc:
        log.warning("khong doc duoc %s: %s", DEVICES_FILE, exc)
        return out
    block = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if block.get("N:") or block.get("handlers"):
                out.append(block)
            block = {}
            continue
        if line.startswith("N:"):
            block["N:"] = line[2:].strip().strip('"')
        elif line.startswith("H:"):
            block["handlers"] = line[2:].split()
        elif line.startswith("I:"):
            block["I:"] = line[2:].strip()
        elif line.startswith("S:"):
            block["S:"] = line[2:].strip()
        elif line.startswith("U:"):
            block["uniq"] = line[2:].strip()
    if block.get("N:") or block.get("handlers"):
        out.append(block)
    return out


def _device_score(block):
    name = (block.get("N:") or "").lower()
    score = 0
    if "trimui" in name:
        score += 100
    if "player1" in name or "gamepad" in name or "player" in name:
        score += 30
    if "keyboard" in name or "pek" in name or "jack" in name:
        score -= 100
    if not block.get("handlers"):
        score -= 100
    return score


def find_gamepad():
    """Tra ve (duong_dan_event, ten) cua thiet bi gamepad tot nhat."""
    best = None
    best_score = -1000
    for block in read_devices():
        score = _device_score(block)
        if score <= best_score:
            continue
        for handler in block.get("handlers", []):
            if not handler.startswith("event"):
                continue
            path = "/dev/input/%s" % handler
            if os.path.exists(path):
                best = (path, block.get("N:") or handler)
                best_score = score
                break
    if best is None:
        return None, ""
    return best


class PadReader:
    """Doc truc tiep /dev/input de hien thi nut dang bam.

    Khong dung EVIOCGRAB: app va backend phai doc cung mot thiet bi.
    """

    def __init__(self, path):
        self.path = path
        self.fd = None
        self.buffer = b""

    def open(self):
        try:
            self.fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as exc:
            log.warning("khong mo %s: %s", self.path, exc)
            self.fd = None
            return False
        self.buffer = b""
        return True

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    def poll(self):
        """Tra ve danh sach (kind, code, value) doc duoc, khong chan."""
        if self.fd is None:
            return []
        events = []
        for _ in range(8):
            try:
                chunk = os.read(self.fd, EVENT_SIZE * 64)
            except OSError as exc:
                if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    break
                log.warning("doc %s that bai: %s", self.path, exc)
                self.close()
                break
            if not chunk:
                break
            self.buffer += chunk
            usable = len(self.buffer) - (len(self.buffer) % EVENT_SIZE)
            for offset in range(0, usable, EVENT_SIZE):
                _, _, kind, code, value = struct.unpack(
                    EVENT_FORMAT, self.buffer[offset:offset + EVENT_SIZE])
                events.append((kind, code, value))
            self.buffer = self.buffer[usable:]
            if len(chunk) < EVENT_SIZE * 64:
                break
        return events

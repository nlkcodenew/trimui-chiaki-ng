# -*- coding: utf-8 -*-
"""Ghi lai thoi diem bam nut, khong doan.

Vay do: firmware Stock OS co the bao mot lan bam ra nhieu ma phim Linux
cung luc, nen app khong the tu quyet dinh ma nao la dung. Man hinh nay chi
ghi nguyen trang thai vao file, nguoi dung bao lai thu tu da bam, va ban do
duoc sinh ra tu log do.

Dinh dang moi dong ghi:

    001 +1.20s   keys=305
    002 +3.45s   keys=304 codes=305 held=120ms
    003 +6.10s   hat=1,0 keys=

Y nghia cac truong:

- ``keys``  ma phim nut bao len truoc.
- ``codes`` ma phim phat them trong cung khoang thoi gian, gom ca ma lap lai
  do firmware gui khi nut dang giu. Neu ``codes`` dai hon ``keys`` thi do la
  nhieu hoac do phim gui lai, khong phai nhieu nut.
- ``held``  thoi gian nut duoc giu. Mot nut giu bao lau van chi la MOT dong.

Giu nut MENU (bat ky phim nao ngoai vung BTN_GAMEPAD) hoac giu START+SELECT de
thoat man hinh. Cac phim thoat do khong bao ghi lai, vi khong phai nut can thu.
"""

import json
import os
import struct
import time

from .logger import get_logger
from .paths import APP_DIR

log = get_logger()

LOG_NAME = "BrickButtons.log"
MAP_NAME = "bluetooth-map.json"

DEVICES_FILE = "/proc/bus/input/devices"

# So khung im lang coi la phim da nha han. Firmware bao "key xuong, SYN, key
# len" trong cung mot lan bam, nen phai doi mot chút moi chot duoc su kien.
RELEASE_FRAMES = 3
RECORD_LIMIT = 120

# Mot lan bam duoc ghi ngay khi phim xuong, thay vi doi cho den khi nha het.
# Cach doi song song giu so lan bam nhung cheo so luong ma bi firmware bao lai,
# nen van ghi ngay. Phan "codes=" cuoi moi la toan bo ma kernel da phat cho
# su kien do, dung de xac dinh nhieu nut co bi bao trung mot luc hay khong.
COOLDOWN_SECONDS = 0.45

# Doi thoat bang nut MENU, khong dung B: B cung la mot nut trong danh sach
# can thu, nen bam B phai duoc ghi chu khong duoc lam phim dieu khong.
#
# Ma MENU la 316 (BTN_MODE), xac nhan bang may that: nguoi dung giu MENU va
# BrickButtons.log ghi ra 316 o cac dong 013, 014, 016, 017. Ban doan "nut
# thoat la phim ngoai vung gamepad" da sai, vi 316 nam trong 0x130..0x140 nen
# bi chinh no chan lai ngay.
KEY_MENU = 316

# Du phong cho truong hop nguoi dung khong tim ra nut nao la MENU.
KEY_SELECT = 314
KEY_START = 315

HOLD_EXIT_SECONDS = 1.5
HOLD_START_SELECT_SECONDS = 2.0

EVENT_FORMAT = "@qqHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
if EVENT_SIZE != 24:
    raise RuntimeError("input_event ABI khong dung: %d byte" % EVENT_SIZE)

EV_SYN = 0
EV_KEY = 1
EV_ABS = 3

SYN_REPORT = 0

HAT_CODES = (16, 17)


def log_path(app_dir=APP_DIR):
    return os.path.join(app_dir, LOG_NAME)


def map_path(app_dir=APP_DIR):
    return os.path.join(app_dir, MAP_NAME)


def is_gamepad_key(code):
    """Ma phim nam trong vung BTN_GAMEPAD, tuc la nut gamepad chu khong phai phim."""
    return 0x130 <= code <= 0x140


def read_devices():
    """Parse /proc/bus/input/devices thanh danh sach ten + handlers."""
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
            if block:
                out.append(block)
            block = {}
            continue
        if line.startswith("N:"):
            # Dang thuc tren may la: N: Name="TRIMUI Player1"
            name = line[2:].strip()
            if "=" in name:
                name = name.split("=", 1)[1].strip()
            if len(name) >= 2 and name[0] == '"' and name[-1] == '"':
                name = name[1:-1]
            block["name"] = name
        elif line.startswith("H:"):
            block["handlers"] = line[2:].split()
        elif line.startswith("I:"):
            block["id"] = line[2:].strip()
        elif line.startswith("B: ABS="):
            block["abs"] = line[len("B: ABS="):].strip()
    if block:
        out.append(block)
    return out


def find_gamepad():
    """Tra ve (duong_dan_event, ten) cua thiet bi gamepad tot nhat.

    Uu tien ten chua TrimUI, sau do so truc ABS. Cach nay dung voi ten
    "TRIMUI Player1" cua Stock OS va khong dua vao ten hang, nen dung khi
    doi phien ban firmware.
    """
    best = None
    best_score = None
    for block in read_devices():
        name = (block.get("name") or "").lower()
        events = [h for h in block.get("handlers", []) if h.startswith("event")]
        if not events:
            continue
        axes = 0
        raw_abs = block.get("abs") or ""
        try:
            axes = int(raw_abs, 16)
        except ValueError:
            axes = 0
        score = (1 if "trimui" in name else 0, bin(axes).count("1"))
        if best_score is None or score > best_score:
            best = ("/dev/input/%s" % events[0], block.get("name") or events[0])
            best_score = score
    if best is None:
        return None, ""
    return best


class PadProbe:
    """Doc evdev va gom cac su kien bam nut thanh tung lan.

    Mot lan bam duoc chot ngay khi co nut moi xuong, roi dung truoc COOLDOWN
    de lan sau khong bi ghep nham. Ma phim cua su kien do duoc giu lai trong
    ``burst`` de biet firmware co phat them ma nao trong khoang thoi gian do.
    """

    def __init__(self, path):
        self.path = path
        self.fd = None
        self.keys = {}
        self.hat = {16: 0, 17: 0}
        self.pending = []
        self.reported = []
        self.quiet = RELEASE_FRAMES
        self.last_press = 0.0
        self.open_entry = None
        self.burst = []
        self.held = []
        # Thoi diem bat dau giu nut thoat (MENU hoac START+SELECT).
        self.hold_started = None
        # Thay cho phep kiem thu dieu khong phai vao dong ho thuc.
        self.clock = time.time
        self.started = self.clock()

    def open(self):
        try:
            self.fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as exc:
            log.warning("khong mo %s: %s", self.path, exc)
            self.fd = None
            return False
        return True

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    def poll(self):
        """Doc het su co san. Tra ve danh sach lan bam moi."""
        if self.fd is None:
            return []
        fresh = []
        for _ in range(16):
            try:
                chunk = os.read(self.fd, EVENT_SIZE * 64)
            except OSError as exc:
                import errno
                if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    break
                log.warning("doc %s that bai: %s", self.path, exc)
                self.close()
                break
            if not chunk:
                break
            usable = len(chunk) - (len(chunk) % EVENT_SIZE)
            for offset in range(0, usable, EVENT_SIZE):
                _sec, _usec, kind, code, value = struct.unpack(
                    EVENT_FORMAT, chunk[offset:offset + EVENT_SIZE])
                if kind == EV_KEY:
                    fresh.extend(self._on_key(code, value))
                elif kind == EV_ABS and code in HAT_CODES:
                    self.hat[code] = value
                    if value:
                        fresh.extend(self._on_hat())
        fresh.extend(self._close_open())
        return fresh

    def exit_held(self):
        """Nut thoat dang duoc giu, neu co.

        Giu MENU (bat ky phim nao ngoai vung gamepad) la thoat. START+SELECT cung
        duoc chap nhan lam duong lui. Phim dang giu la phim thoat thi khong bao
        ghi vao danh sach lan bam, vi do khong phai la nut can thu.
        """
        gesture = self._exit_gesture()
        if not gesture or self.hold_started is None:
            return ""
        limit = (HOLD_START_SELECT_SECONDS if gesture == "start_select"
                 else HOLD_EXIT_SECONDS)
        if self.clock() - self.hold_started < limit:
            return ""
        return gesture

    def _exit_gesture(self):
        """Ten cua cua thoat dang duoc giu, hoac chuong rong.

        MENU chi la cua thoat khi no duoc giu MOT MINH. Neu nut gamepad nao
        khac cung dang xuong thi day khong phai thoat, vi du firmware bao them
        ma 316 cung luc khi bam A. ``START+SELECT`` la ngoai le duy nhat, vi hai
        phim do la mot cua rieng chu khong phai nut can thu.
        """
        if not self.keys:
            return ""
        if set(self.keys) == {KEY_SELECT, KEY_START}:
            return "start_select"
        if set(self.keys) == {KEY_MENU}:
            return "menu"
        return ""

    

    def _on_key(self, code, value):
        """Ghi mot su kien EV_KEY. Nut xuong sau thoi gian ngung la lan bam moi."""
        if value == 0:
            self.keys.pop(code, None)
            self._sync_hold()
            return []
        was_down = code in self.keys
        self.keys[code] = value
        now = self.clock()
        if not was_down:
            self._sync_hold()
        if self.hold_started is not None:
            # Dang giu MENU hoac START+SELECT: day la cua thoat man hinh, khong
            # phai nut can thu, nen khong ghi vao danh sach lan bam.
            return []
        if was_down and self.open_entry is not None:
            # Firmware lap lai ma cua nut dang giu: nay la nhieu, khong phai
            # nut moi. Van ghi vao burst de do lau duoc.
            self._note_burst(code)
            return []
        if now - self.last_press < COOLDOWN_SECONDS:
            self._note_burst(code)
            return []
        fresh = self._close_open()
        self.last_press = now
        self.open_entry = {
            "index": len(self.reported) + 1,
            "elapsed": round(now - self.started, 2),
            "keys": [code],
            "hat": [self.hat.get(16, 0), self.hat.get(17, 0)],
            "held_ms": 0,
        }
        self.burst = [code]
        self.held = [now]
        self.reported.append(self.open_entry)
        return fresh + [self.open_entry]

    def _on_hat(self):
        now = self.clock()
        if now - self.last_press < COOLDOWN_SECONDS:
            return []
        fresh = self._close_open()
        self.last_press = now
        entry = {
            "index": len(self.reported) + 1,
            "elapsed": round(now - self.started, 2),
            "keys": [],
            "hat": [self.hat.get(16, 0), self.hat.get(17, 0)],
            "held_ms": 0,
        }
        self.open_entry = entry
        self.burst = []
        self.held = [now]
        self.reported.append(entry)
        return fresh + [entry]

    def _note_burst(self, code):
        if code not in self.burst:
            self.burst.append(code)
            self.burst.sort()

    def _sync_hold(self):
        """Bat dau dem gio giu cua thoat ngay khi phim thoat xuong.

        START va SELECT duoc giu lai phim thoat khi di cung nhau, nhung van phai
        thu duoc khi bam rieng. Nut vua duoc ghi truoc do se bi bo khi no chi
        chua phim thoat, vi du START an truoc roi SELECT moi an sau.
        """
        if not self._exit_gesture():
            self.hold_started = None
            return
        if self.hold_started is None:
            self.hold_started = self.clock()
        self._drop_exit_only_entry()

    def _drop_exit_only_entry(self):
        """Bo cac dong chi chua phim thoat.

        Do phim thoat co the xuong truoc nut can thu (START an truoc roi
        SELECT), nen dong do da ghi phai bi lay ra khoi danh sach. Danh sach
        ``reported`` la noi dung duy nhat: man hinh doc chinh no, nen dong bi
        bo o day se khong bao gio xuat hien trong log.
        """
        exit_keys = set(self.keys) & {KEY_MENU, KEY_SELECT, KEY_START}
        if not exit_keys:
            return
        if self.open_entry is not None and self.open_entry["keys"] and \
                set(self.open_entry["keys"]) <= exit_keys:
            self._discard(self.open_entry)
        self.reported = [e for e in self.reported
                         if not (e["keys"] and set(e["keys"]) <= exit_keys)]

    def _discard(self, entry):
        if entry in self.reported:
            self.reported.remove(entry)
        if self.open_entry is entry:
            self.open_entry = None

    def _close_open(self):
        """Dong su kien dang mo, ghi them ma phim phat ra trong khoang do."""
        if self.open_entry is None:
            return []
        entry = self.open_entry
        self.open_entry = None
        if self.held:
            entry["held_ms"] = int((self.clock() - self.held[0]) * 1000)
        entry["codes"] = sorted(self.burst)
        return []


def format_entry(entry):
    """Dong log cho nguoi dung doc va cho may sinh ban do.

    ``keys`` la ma cua nut bao len truoc. ``codes`` la tat ca ma firmware
    phat ra trong khoang thoi gian cua lan bam do, nen neu ``codes`` dai hon
    ``keys`` thi do la nhieu do firmware lap ma, khong phai nhieu nut.
    """
    hat_x, hat_y = entry["hat"]
    parts = []
    if hat_x or hat_y:
        parts.append("hat=%d,%d" % (hat_x, hat_y))
    keys = entry.get("keys") or []
    parts.append("keys=" + (",".join(str(c) for c in keys) if keys else "-"))
    burst = [c for c in entry.get("codes", []) if c not in keys]
    if burst:
        parts.append("codes=" + ",".join(str(c) for c in burst))
    if entry.get("held_ms"):
        parts.append("held=%dms" % entry["held_ms"])
    return "%03d +%-7s %s" % (entry["index"], "%.2fs" % entry["elapsed"],
                              " ".join(parts))


def write_log(entries, path=None, app_dir=APP_DIR, header=True):
    """Ghi lai toan bo phien thu vao file, co phan dau giai thich."""
    target = path or log_path(app_dir)
    lines = []
    if header:
        lines.append("## Brick Pro button press log")
        lines.append("## Each numbered line is one physical press.")
        lines.append("## Report the button name for each number to finish the map.")
        lines.append("## keys=  first key code reported")
        lines.append("## codes= extra codes in the same moment (repeats or noise)")
        lines.append("## held=  how long the button was held")
        lines.append("## Generated %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("")
    for entry in entries:
        lines.append(format_entry(entry))
    body = "\n".join(lines) + "\n"
    try:
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        log.error("khong ghi duoc %s: %s", target, exc)
        return ""
    log.info("da ghi %d lan bam vao %s", len(entries), target)
    return target


def append_note(text, path=None, app_dir=APP_DIR):
    target = path or log_path(app_dir)
    try:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write("## %s\n" % text)
    except OSError as exc:
        log.warning("khong them ghi chu vao %s: %s", target, exc)


def clear_log(path=None, app_dir=APP_DIR):
    target = path or log_path(app_dir)
    try:
        if os.path.isfile(target):
            os.remove(target)
    except OSError as exc:
        log.warning("khong xoa duoc %s: %s", target, exc)


def build_map(order, entries, app_dir=APP_DIR):
    """Sinh ban do nut tu thu tu nguoi dung bao.

    ``order`` la danh sach ten nut cung thu tu so lan bam tu 1 den het.
    ``entries`` la cac lan bam da ghi. Moi nut lay ma phim cua lan bam tuong
    ung. Mot lan bam ra nhieu ma thi lay ma nho nhat trong vung BTN_GAMEPAD
    va ghi chu lai tat ca, vi do la thong tin người dung cần xem.
    """
    if len(order) != len(entries):
        raise ValueError("thu tu co %d nut nhung log co %d lan bam"
                         % (len(order), len(entries)))
    defaults = _default_buttons()
    buttons = dict(defaults)
    notes = []
    for name, entry in zip(order, entries):
        candidates = [c for c in entry["keys"] if is_gamepad_key(c)]
        if not candidates:
            notes.append("%s: khong co ma phim nut (chi co hat)" % name)
            continue
        code = min(candidates)
        buttons[name] = code
        if len(candidates) > 1:
            notes.append("%s: mot lan bam ra %s, chon %d"
                         % (name, ",".join(str(c) for c in candidates), code))
    payload = {
        "version": 1,
        "note": "Sinh tu BrickButtons.log. Xoa file de dung mac dinh.",
        "buttons": {k: int(v) for k, v in sorted(buttons.items()) if v},
    }
    target = map_path(app_dir)
    try:
        temporary = target + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, target)
    except OSError as exc:
        raise OSError("khong ghi duoc %s: %s" % (target, exc))
    return target, notes


def _default_buttons():
    """Mac dinh phai khop voi defaultMapping() trong bluetooth-native/mapping.go.

    Gia tri doc tu BrickButtons.log ngay 2026-10-03, xac nhan tren may that.
    Luu y A <-> B va X <-> Y so voi BTN_SOUTH/BTN_EAST va BTN_NORTH/BTN_WEST
    cua Linux: day la hanh vi cua firmware Stock OS, khong phai loi.

    L2/R2 vang khong co ma: chung la cam bien analog (axis 2/5).
    """
    return {
        "a": 305, "b": 304, "x": 308, "y": 307,
        "l1": 310, "r1": 311,
        "select": 314, "start": 315, "mode": 316,
        "l3": 317, "r3": 318,
        "dpad_up": 103, "dpad_down": 108,
        "dpad_left": 105, "dpad_right": 106,
    }


def parse_log(path=None, app_dir=APP_DIR):
    """Doc lai log da ghi, dung khi can sinh ban do ngoai may."""
    target = path or log_path(app_dir)
    entries = []
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("##"):
                    continue
                parts = line.split(None, 2)
                if len(parts) < 3:
                    continue
                try:
                    index = int(parts[0])
                except ValueError:
                    continue
                keys = []
                hat = [0, 0]
                for token in parts[2].split():
                    if token.startswith("keys="):
                        raw_keys = token[5:]
                        if raw_keys and raw_keys != "-":
                            keys = [int(x) for x in raw_keys.split(",")
                                    if x.strip().isdigit()]
                    elif token.startswith("hat="):
                        try:
                            hat = [int(x) for x in token[4:].split(",")]
                        except ValueError:
                            pass
                entries.append({"index": index, "keys": keys, "hat": hat})
    except OSError:
        return []
    return entries

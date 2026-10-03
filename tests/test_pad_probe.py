# -*- coding: utf-8 -*-
"""Kiem thu bo ghi tho cua muc GHI NUT.

Muc dich cua bo ghi la khong doan: no chi ghi lai ma phim kernel phat ra.
Cac truong hop can khoa la:

1. Mot lan bam chi duoc ghi MOT LAN, duyet keo dai.
2. Firmware lap lai ma cua nut dang giu thi vao ``codes``, khong tao lan bam moi.
3. Giu mot nut lau van chi tao mot lan bam, va ``held_ms`` phai lon.
4. Nut moi xuong ngay sau khi nha thi la hai lan bam rieng.
5. Log doc lai ra duoc dung thu tu va khong duoc bo suc.
"""

import importlib
import os
import shutil
import sys
import tempfile
import unittest

ROOT = r"E:\Trimiu Brick Pro\Project APPS\chiaki-ng"
FILES = os.path.join(ROOT, "files")
if FILES not in sys.path:
    sys.path.insert(0, FILES)


class ProbeStub:
    """Thay the PadProbe de tieu khien khong phu thuoc thiet bi that."""

    def __init__(self):
        self.now = 1000.0
        self.events = []
        self.probe = None

    def start(self, path="/dev/input/event3"):
        module = importlib.import_module("rh.pad_probe")
        self.probe = module.PadProbe(path)
        self.probe.started = self.now
        self.probe.clock = lambda: self.now
        return self.probe

    def advance(self, seconds):
        self.now += seconds

    def press(self, code, hold=0.0):
        """Nut xuong, giu ``hold`` giay, roi nha."""
        probe = self.probe
        fresh = probe._on_key(code, 1)
        self.advance(hold)
        probe._on_key(code, 0)
        probe._close_open()
        return fresh


class PadProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="pad-probe-tests-")
        cls.app_dir = os.path.join(cls.temp_dir, "files")
        shutil.copytree(FILES, cls.app_dir)
        sys.path.insert(0, cls.app_dir)
        cls.module = importlib.import_module("rh.pad_probe")

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(cls.app_dir)
        for name in list(sys.modules):
            if name == "rh" or name.startswith("rh."):
                sys.modules.pop(name, None)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.stub = ProbeStub()
        self.probe = self.stub.start()

    def test_one_press_is_one_entry(self):
        self.stub.press(305, hold=0.2)
        self.assertEqual(len(self.probe.reported), 1)
        self.assertEqual(self.probe.reported[0]["keys"], [305])

    def test_held_button_is_not_counted_again(self):
        probe = self.probe
        probe._on_key(305, 1)
        for _ in range(200):
            probe._on_key(305, 2)  # value 2 la auto-repeat
            probe._on_key(305, 1)
        probe._on_key(305, 0)
        probe._close_open()
        self.assertEqual(len(probe.reported), 1)
        self.assertEqual(probe.reported[0]["keys"], [305])

    def test_hold_long_gives_one_entry_with_held_time(self):
        probe = self.probe
        probe._on_key(305, 1)
        self.stub.advance(5.0)
        probe._on_key(305, 0)
        probe._close_open()
        self.assertEqual(len(probe.reported), 1)
        self.assertGreater(probe.reported[0]["held_ms"], 4500)

    def test_extra_codes_land_in_codes_not_keys(self):
        """Mot lan bam ra nhieu ma thi ma phu vao ``codes``.

        Day la truong hop lam ban do sai: ma phu khong phai la nut khac.
        """
        probe = self.probe
        probe._on_key(304, 1)
        self.stub.advance(0.05)
        probe._on_key(305, 1)
        probe._on_key(304, 0)
        probe._on_key(305, 0)
        probe._close_open()
        self.assertEqual(len(probe.reported), 1)
        entry = probe.reported[0]
        self.assertEqual(entry["keys"], [304])
        self.assertIn(305, entry["codes"])

    def test_menu_is_316_because_the_device_log_says_so(self):
        """MENU=316 do nguoi dung bam tren may that, khong phai doan."""
        self.assertEqual(self.module.KEY_MENU, 316)

    def test_menu_is_inside_the_gamepad_range(self):
        """316 nam trong 0x130..0x140, nen phim loai "khong phai gamepad"
        se loai chinh nut thoat. Day la ly do quy tac do loi."""
        self.assertTrue(self.module.is_gamepad_key(self.module.KEY_MENU))

    def test_holding_menu_records_nothing_and_signals_exit(self):
        """MENU la cua thoat, nen khong duoc ghi nhu mot nut can thu."""
        probe = self.probe
        self.assertEqual(probe._on_key(self.module.KEY_MENU, 1), [])
        self.assertEqual(len(probe.reported), 0)
        self.assertEqual(probe.exit_held(), "")
        self.stub.advance(self.module.HOLD_EXIT_SECONDS + 0.1)
        self.assertEqual(probe.exit_held(), "menu")

    def test_menu_press_after_release_is_a_normal_exit_signal(self):
        probe = self.probe
        probe._on_key(self.module.KEY_MENU, 1)
        self.stub.advance(self.module.HOLD_EXIT_SECONDS + 0.2)
        probe._on_key(self.module.KEY_MENU, 0)
        probe._on_key(self.module.KEY_MENU, 1)
        self.stub.advance(0.01)
        self.assertEqual(probe.exit_held(), "")

    def test_keys_outside_the_gamepad_range_are_ordinary_presses(self):
        """60, 63, 114, 115, 172 khong phai MENU, nen phai duoc ghi binh thuong."""
        probe = self.probe
        for code in (60, 63, 114, 115, 172):
            with self.subTest(code=code):
                probe._on_key(code, 1)
                self.stub.advance(self.module.COOLDOWN_SECONDS + 0.1)
                probe._on_key(code, 0)
        seen = set()
        for entry in probe.reported:
            seen.update(entry["keys"])
            self.assertNotIn(self.module.KEY_MENU, entry["keys"])
        self.assertEqual(seen, {60, 63, 114, 115, 172})
        probe._on_key(172, 1)
        self.stub.advance(self.module.HOLD_EXIT_SECONDS + 0.5)
        self.assertEqual(probe.exit_held(), "")
        probe._on_key(172, 0)

    def test_extra_code_beside_a_button_never_signals_exit(self):
        """Firmware bao MENU kem nut that, nen phai giu phim thoat MOT MINH."""
        probe = self.probe
        probe._on_key(305, 1)
        probe._on_key(self.module.KEY_MENU, 1)
        self.stub.advance(self.module.HOLD_EXIT_SECONDS + 0.5)
        self.assertEqual(probe.exit_held(), "")

    def test_menu_released_while_a_stays_down_still_never_exits(self):
        probe = self.probe
        probe._on_key(305, 1)
        probe._on_key(self.module.KEY_MENU, 1)
        probe._on_key(self.module.KEY_MENU, 0)
        self.stub.advance(self.module.HOLD_EXIT_SECONDS + 0.5)
        self.assertEqual(probe.exit_held(), "")
        self.assertIn(305, [e["keys"][0] for e in probe.reported])

    def test_start_plus_select_while_a_is_also_down_is_not_an_exit(self):
        probe = self.probe
        probe._on_key(304, 1)
        probe._on_key(self.module.KEY_START, 1)
        probe._on_key(self.module.KEY_SELECT, 1)
        self.stub.advance(self.module.HOLD_START_SELECT_SECONDS + 0.5)
        self.assertEqual(probe.exit_held(), "")

    def test_start_select_combo_is_the_fallback_exit(self):
        probe = self.probe
        probe._on_key(self.module.KEY_SELECT, 1)
        probe._on_key(self.module.KEY_START, 1)
        self.assertEqual(len(probe.reported), 0)
        self.stub.advance(self.module.HOLD_START_SELECT_SECONDS + 0.1)
        self.assertEqual(probe.exit_held(), "start_select")

    def test_select_alone_is_still_recorded(self):
        """SELECT doi thanh thoat khi co START, nhung van phai thu duoc."""
        probe = self.probe
        probe._on_key(self.module.KEY_SELECT, 1)
        self.assertEqual(len(probe.reported), 1)
        self.assertEqual(probe.reported[0]["keys"], [self.module.KEY_SELECT])
        self.stub.advance(self.module.HOLD_START_SELECT_SECONDS + 0.2)
        self.assertEqual(probe.exit_held(), "")

    def test_start_alone_is_still_recorded(self):
        probe = self.probe
        probe._on_key(self.module.KEY_START, 1)
        self.assertEqual(len(probe.reported), 1)
        self.stub.advance(self.module.HOLD_START_SELECT_SECONDS + 0.2)
        self.assertEqual(probe.exit_held(), "")

    def test_an_ordinary_button_held_long_never_signals_exit(self):
        """Giu A de thu nut phai khong thoat man hinh."""
        probe = self.probe
        probe._on_key(304, 1)
        self.stub.advance(8.0)
        self.assertEqual(probe.exit_held(), "")
        probe._on_key(304, 0)
        self.assertEqual(len(probe.reported), 1)

    def test_held_button_appears_once_however_long_it_is_held(self):
        """Giu mot nut 5 giay van chi ghi MOT lan, ma lap lai vao codes."""
        probe = self.probe
        probe._on_key(304, 1)
        for _ in range(40):
            self.stub.advance(0.1)
            probe._on_key(304, 2)
            probe._on_key(304, 1)
        probe._on_key(304, 0)
        probe._close_open()
        self.assertEqual(len(probe.reported), 1)
        entry = probe.reported[0]
        self.assertEqual(entry["keys"], [304])
        self.assertGreater(entry["held_ms"], 3800)
        # Ma lap lai cua chinh nut do khong duoc coi la nut moi.
        self.assertEqual([c for c in entry["codes"] if c != 304], [])

    def test_presses_inside_the_cooldown_merge_into_codes(self):
        probe = self.probe
        probe._on_key(304, 1)
        self.stub.advance(0.05)
        probe._on_key(308, 1)
        probe._on_key(308, 0)
        probe._on_key(304, 0)
        probe._close_open()
        self.assertEqual(len(probe.reported), 1)
        self.assertEqual(probe.reported[0]["keys"], [304])
        self.assertIn(308, probe.reported[0]["codes"])

    def test_two_separate_presses_are_two_entries(self):
        probe = self.probe
        probe._on_key(304, 1)
        probe._on_key(304, 0)
        probe._close_open()
        self.stub.advance(self.module.COOLDOWN_SECONDS + 0.1)
        probe._on_key(307, 1)
        probe._on_key(307, 0)
        probe._close_open()
        self.assertEqual(len(probe.reported), 2)
        self.assertEqual(probe.reported[0]["keys"], [304])
        self.assertEqual(probe.reported[1]["keys"], [307])

    def test_dpad_only_press_is_recorded(self):
        probe = self.probe
        probe.hat[16] = -1
        fresh = probe._on_hat()
        self.assertEqual(len(probe.reported), 1)
        self.assertEqual(probe.reported[0]["keys"], [])
        self.assertEqual(probe.reported[0]["hat"][0], -1)
        self.assertEqual(len(fresh), 1)

    def test_entries_are_numbered_from_one(self):
        for code in (304, 305, 307):
            self.stub.press(code, hold=0.05)
            self.stub.advance(self.module.COOLDOWN_SECONDS + 0.05)
        self.assertEqual([e["index"] for e in self.probe.reported], [1, 2, 3])


class ProbeLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="pad-log-tests-")
        cls.app_dir = os.path.join(cls.temp_dir, "files")
        shutil.copytree(FILES, cls.app_dir)
        sys.path.insert(0, cls.app_dir)
        cls.module = importlib.import_module("rh.pad_probe")

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(cls.app_dir)
        for name in list(sys.modules):
            if name == "rh" or name.startswith("rh."):
                sys.modules.pop(name, None)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pad-log-out-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _sample(self):
        return [
            {"index": 1, "elapsed": 1.2, "keys": [304], "hat": [0, 0],
             "codes": [304], "held_ms": 90},
            {"index": 2, "elapsed": 3.4, "keys": [305], "hat": [0, 0],
             "codes": [305, 318], "held_ms": 1500},
            {"index": 3, "elapsed": 6.0, "keys": [], "hat": [-1, 0],
             "codes": [], "held_ms": 0},
        ]

    def test_log_round_trips_through_parse(self):
        entries = self._sample()
        path = self.module.write_log(entries, path=os.path.join(self.dir, "b.log"),
                                     app_dir=self.dir)
        self.assertTrue(path)
        parsed = self.module.parse_log(path, app_dir=self.dir)
        self.assertEqual([e["index"] for e in parsed], [1, 2, 3])
        self.assertEqual(parsed[0]["keys"], [304])
        self.assertEqual(parsed[1]["keys"], [305])
        self.assertEqual(parsed[2]["hat"], [-1, 0])

    def test_log_lines_carry_codes_and_held(self):
        line = self.module.format_entry(self._sample()[1])
        self.assertIn("keys=305", line)
        self.assertIn("codes=", line)
        self.assertIn("318", line)
        self.assertIn("held=1500ms", line)

    def test_comment_lines_are_not_parsed_as_presses(self):
        path = os.path.join(self.dir, "b.log")
        self.module.write_log(self._sample(), path=path, app_dir=self.dir)
        self.module.append_note("device=TRIMUI Player1", path=path, app_dir=self.dir)
        parsed = self.module.parse_log(path, app_dir=self.dir)
        self.assertEqual(len(parsed), 3)

    def test_clear_log_removes_the_file(self):
        path = os.path.join(self.dir, "b.log")
        self.module.write_log(self._sample(), path=path, app_dir=self.dir)
        self.module.clear_log(path=path, app_dir=self.dir)
        self.assertFalse(os.path.exists(path))

    def test_build_map_needs_matching_counts(self):
        with self.assertRaises(ValueError):
            self.module.build_map(["a", "b"], self._sample(), app_dir=self.dir)

    def test_build_map_takes_the_first_gamepad_code(self):
        entries = [
            {"index": 1, "keys": [304, 305], "hat": [0, 0], "codes": []},
            {"index": 2, "keys": [307], "hat": [0, 0], "codes": []},
        ]
        target, notes = self.module.build_map(["a", "x"], entries, app_dir=self.dir)
        self.assertTrue(os.path.isfile(target))
        import json
        with open(target, encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(data["buttons"]["a"], 304)
        self.assertEqual(data["buttons"]["x"], 307)
        self.assertTrue(any("304,305" in n for n in notes))

    def test_build_map_reports_a_press_with_no_button_code(self):
        entries = [{"index": 1, "keys": [], "hat": [0, 1], "codes": []}]
        _target, notes = self.module.build_map(["a"], entries, app_dir=self.dir)
        self.assertTrue(any("hat" in n for n in notes))

    def test_default_buttons_match_the_go_table(self):
        """Bang mac dinh phai khop voi defaultMapping() cua backend Go.

        Gia tri doc tu may that ngay 2026-10-03, khong phai tu chuan Linux:
        firmware bao A=305, B=304, X=308, Y=307.
        """
        defaults = self.module._default_buttons()
        self.assertEqual(defaults["a"], 305)
        self.assertEqual(defaults["b"], 304)
        self.assertEqual(defaults["x"], 308)
        self.assertEqual(defaults["y"], 307)
        self.assertEqual(defaults["l1"], 310)
        self.assertEqual(defaults["r1"], 311)
        self.assertEqual(defaults["select"], 314)
        self.assertEqual(defaults["start"], 315)
        self.assertEqual(defaults["l3"], 317)
        self.assertEqual(defaults["r3"], 318)

    def test_analog_triggers_have_no_key_code(self):
        """L2/R2 la cam bien analog, nen khong duoc gan ma phim."""
        defaults = self.module._default_buttons()
        self.assertNotIn("l2", defaults)
        self.assertNotIn("r2", defaults)

    def test_the_button_map_has_no_duplicate_codes(self):
        """A=305 va B=304 la hai nut khac nhau, nen phai khong trung nhau."""
        defaults = self.module._default_buttons()
        codes = sorted(defaults.values())
        self.assertEqual(len(codes), len(set(codes)))


class DevicePickTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="pad-dev-tests-")
        cls.app_dir = os.path.join(cls.temp_dir, "files")
        shutil.copytree(FILES, cls.app_dir)
        sys.path.insert(0, cls.app_dir)
        cls.module = importlib.import_module("rh.pad_probe")

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(cls.app_dir)
        for name in list(sys.modules):
            if name == "rh" or name.startswith("rh."):
                sys.modules.pop(name, None)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_parse_proc_devices_blocks(self):
        text = (
            'I: Bus=0019 Vendor=0001 Product=0001\n'
            'N: Name="sunxi-keyboard"\n'
            'H: Handlers=kbd event0 \n'
            'B: KEY=1\n'
            '\n'
            'I: Bus=0003 Vendor=045e Product=028e\n'
            'N: Name="TRIMUI Player1"\n'
            'H: Handlers=kbd js0 event3 \n'
            'B: ABS=3003f\n'
            '\n'
        )
        path = os.path.join(self.temp_dir, "devices")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        original = self.module.DEVICES_FILE
        self.module.DEVICES_FILE = path
        try:
            blocks = self.module.read_devices()
        finally:
            self.module.DEVICES_FILE = original
        self.assertEqual([b.get("name") for b in blocks],
                         ["sunxi-keyboard", "TRIMUI Player1"])
        trimui = blocks[1]
        self.assertIn("event3", trimui["handlers"])
        self.assertEqual(trimui["abs"], "3003f")

    def test_find_gamepad_prefers_the_trimui_node(self):
        text = (
            'N: Name="audiocodec sunxi Audio Jack"\n'
            'H: Handlers=kbd event2 \n'
            'B: ABS=4\n'
            '\n'
            'N: Name="TRIMUI Player1"\n'
            'H: Handlers=kbd js0 event3 \n'
            'B: ABS=3003f\n'
            '\n'
        )
        path = os.path.join(self.temp_dir, "devices2")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        original = self.module.DEVICES_FILE
        self.module.DEVICES_FILE = path
        try:
            found, name = self.module.find_gamepad()
        finally:
            self.module.DEVICES_FILE = original
        self.assertEqual(found, "/dev/input/event3")
        self.assertEqual(name, "TRIMUI Player1")

    def test_is_gamepad_key_range(self):
        self.assertTrue(self.module.is_gamepad_key(304))
        self.assertTrue(self.module.is_gamepad_key(320))
        self.assertFalse(self.module.is_gamepad_key(319 - 16))
        self.assertFalse(self.module.is_gamepad_key(172))


if __name__ == "__main__":
    unittest.main()

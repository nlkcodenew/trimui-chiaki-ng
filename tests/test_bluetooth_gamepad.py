# -*- coding: utf-8 -*-

import importlib
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = os.path.join(ROOT, "files")

# Do NOT put the real files/ on sys.path. rh.paths resolves APP_DIR from the
# module's own location, so importing rh from here would make a test write a
# real device_id into the shipped settings.json. Every test class copies
# files/ into a temp dir and imports rh from there instead.
def _fresh_app_copy(prefix):
    """Import rh from a private copy of files/ so nothing touches the repo."""
    for name in list(sys.modules):
        if name == "rh" or name.startswith("rh."):
            sys.modules.pop(name, None)
    temp_dir = tempfile.mkdtemp(prefix=prefix)
    app_dir = os.path.join(temp_dir, "files")
    shutil.copytree(FILES, app_dir)
    sys.path.insert(0, app_dir)
    return temp_dir, app_dir


def _drop_app_copy(temp_dir, app_dir):
    if app_dir in sys.path:
        sys.path.remove(app_dir)
    for name in list(sys.modules):
        if name == "rh" or name.startswith("rh."):
            sys.modules.pop(name, None)
    shutil.rmtree(temp_dir, ignore_errors=True)


class BluetoothGamepadIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir, cls.app_dir = _fresh_app_copy("chiaki-bluetooth-tests-")
        cls.manager = importlib.import_module("rh.bluetooth_gamepad")
        cls.map_module = importlib.import_module("rh.gamepad_map")
        cls.screen_module = importlib.import_module("rh.screens.bluetooth")
        cls.home_module = importlib.import_module("rh.screens.home")
        cls.test_module = importlib.import_module("rh.screens.button_test")

    @classmethod
    def tearDownClass(cls):
        _drop_app_copy(cls.temp_dir, cls.app_dir)

    def test_b_while_session_running_is_ignored(self):
        """B la nut test tren dien thoai, nen dang chay ma bam B phai bo qua."""
        screen = self.screen_module.BluetoothScreen(mock.Mock())
        screen.session = mock.Mock()
        screen.session.running.return_value = True
        handled = screen.handle_input({"edges": ["btn_b"], "btn_b": True})
        self.assertFalse(handled)
        screen.session.stop.assert_not_called()
        screen.engine.pop_screen.assert_not_called()

    def test_b_while_idle_still_goes_back(self):
        screen = self.screen_module.BluetoothScreen(mock.Mock())
        screen.session = mock.Mock()
        screen.session.running.return_value = False
        handled = screen.handle_input({"edges": ["btn_b"], "btn_b": True})
        self.assertTrue(handled)
        screen.engine.pop_screen.assert_called_once_with()

    def test_quit_while_running_still_stops_as_emergency_exit(self):
        """Quit chi tu phim Q/SDL_QUIT, khong phai nut tay cam."""
        screen = self.screen_module.BluetoothScreen(mock.Mock())
        screen.session = mock.Mock()
        screen.session.running.return_value = True
        handled = screen.handle_input({"edges": ["quit"], "quit": True})
        self.assertTrue(handled)
        screen.session.stop.assert_called_once_with()

    def test_running_footer_offers_menu_hold_instead_of_b(self):
        screen = self.screen_module.BluetoothScreen(mock.Mock())
        screen.session = mock.Mock()
        screen.session.running.return_value = True
        actions = screen.get_footer_actions()
        self.assertEqual([key for key, _label in actions], ["MENU"])
        self.assertIn("2", actions[0][1])

    def test_profile_cycles_with_left_right_while_idle_and_persists(self):
        screen = self.screen_module.BluetoothScreen(mock.Mock())
        screen.session = mock.Mock()
        screen.session.running.return_value = False
        state = self.screen_module.state
        original = state.gamepad_profile
        try:
            state.gamepad_profile = "ps"
            with mock.patch.object(state, "save_settings") as save:
                self.assertTrue(screen.handle_input({"edges": ["btn_right"]}))
            self.assertEqual(state.gamepad_profile, "labels")
            save.assert_called_once_with()
            with mock.patch.object(state, "save_settings"):
                self.assertTrue(screen.handle_input({"edges": ["btn_left"]}))
            self.assertEqual(state.gamepad_profile, "ps")
        finally:
            state.gamepad_profile = original

    def test_profile_cycle_ignored_while_running(self):
        screen = self.screen_module.BluetoothScreen(mock.Mock())
        screen.session = mock.Mock()
        screen.session.running.return_value = True
        state = self.screen_module.state
        original = state.gamepad_profile
        try:
            state.gamepad_profile = "ps"
            with mock.patch.object(state, "save_settings") as save:
                self.assertFalse(
                    screen.handle_input({"edges": ["btn_right"]}))
            self.assertEqual(state.gamepad_profile, "ps")
            save.assert_not_called()
        finally:
            state.gamepad_profile = original

    def test_session_start_passes_profile_to_backend(self):
        session = self.manager.BluetoothGamepadSession()
        state = self.manager.state
        original = state.gamepad_profile
        state.gamepad_profile = "labels"
        try:
            with mock.patch.object(session, "available", return_value=True), \
                    mock.patch.object(session, "cleanup_runtime"), \
                    mock.patch.object(self.manager.subprocess, "Popen") as popen, \
                    mock.patch.object(self.manager.tempfile, "mkdtemp",
                                      return_value="/tmp/bt-test"):
                self.assertTrue(session.start())
            env = popen.call_args.kwargs["env"]
            self.assertEqual(env["CHIAKI_BT_PROFILE"], "labels")
        finally:
            state.gamepad_profile = original

    def test_backend_profile_falls_back_to_ps(self):
        state = self.manager.state
        original = state.gamepad_profile
        state.gamepad_profile = "nonsense"
        try:
            self.assertEqual(self.manager.BluetoothGamepadSession._bt_profile(),
                             "ps")
        finally:
            state.gamepad_profile = original

    def test_supervisor_passes_profile_flag_to_backend(self):
        script = os.path.join(FILES, "bluetooth-session.sh")
        with open(script, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("--profile", text)
        self.assertIn("CHIAKI_BT_PROFILE", text)

    def test_gamepad_profile_defaults_ps_persists_and_rejects_junk(self):
        state = self.manager.state
        original = state.gamepad_profile
        try:
            self.assertEqual(original, "ps")
            state.gamepad_profile = "labels"
            self.assertTrue(state.save_settings())
            state.gamepad_profile = "ps"
            state._load()
            self.assertEqual(state.gamepad_profile, "labels")
            with open(state.SETTINGS_FILE, "w", encoding="utf-8") as handle:
                json.dump({"gamepad_profile": "junk"}, handle)
            state._load()
            self.assertEqual(state.gamepad_profile, "ps")
        finally:
            state.gamepad_profile = original
            state.save_settings()

    def test_home_menu_opens_bluetooth_screen(self):
        engine = mock.Mock()
        screen = self.home_module.HomeScreen(engine)
        screen.selected = next(
            index for index, row in enumerate(screen.ITEMS)
            if row[0] == "bluetooth"
        )
        screen._activate()
        engine.push_screen.assert_called_once_with("bluetooth")

    def test_session_refuses_start_during_preflight(self):
        session = self.manager.BluetoothGamepadSession()
        session.checking = True
        with mock.patch.object(session, "available", return_value=True), \
                mock.patch.object(self.manager.subprocess, "Popen") as popen:
            self.assertFalse(session.start())
        popen.assert_not_called()

    def test_screen_shows_preflight_result_while_idle(self):
        screen = self.screen_module.BluetoothScreen(mock.Mock())
        screen.session.checking = False
        screen.session.check_result = "READY"
        with mock.patch.object(screen.session, "status", return_value="idle"):
            self.assertEqual(
                screen._status_text(),
                self.screen_module.tr("bluetooth_check_ready"),
            )

    def test_stop_waits_for_supervisor_cleanup(self):
        process = mock.Mock()
        process.poll.return_value = None
        process.wait.side_effect = [0]
        process.returncode = 0
        session = self.manager.BluetoothGamepadSession()
        session.process = process
        session.stop()
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=20)

    def test_supervisor_has_recovery_and_parent_watch(self):
        script = os.path.join(FILES, "bluetooth-session.sh")
        with open(script, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("--recover --recovery-file", text)
        self.assertIn("--parent-pid $$", text)
        self.assertIn("CHIAKI_PARENT_PID", text)
        self.assertIn("app_parent_alive", text)
        self.assertIn("trap cleanup 0", text)

    def test_supervisor_rotates_the_report_log(self):
        script = os.path.join(FILES, "bluetooth-session.sh")
        with open(script, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("rotate_log", text)
        # Rotation must happen before the session banner is appended.
        self.assertLess(text.index("rotate_log"),
                        text.index("=== Brick Pro Bluetooth session ==="))

    def test_terminate_during_stop_is_not_reported_as_a_backend_error(self):
        process = mock.Mock()
        process.poll.return_value = None
        process.wait.side_effect = [None]
        process.returncode = 143
        session = self.manager.BluetoothGamepadSession()
        session.run_dir = self.temp_dir
        session.process = process
        session.stop()
        process.terminate.assert_called_once()
        self.assertEqual(session.status(), "stopped")

    def test_unexpected_exit_code_is_still_an_error(self):
        process = mock.Mock()
        process.poll.return_value = None
        process.wait.side_effect = [None]
        process.returncode = 1
        session = self.manager.BluetoothGamepadSession()
        session.run_dir = self.temp_dir
        session.process = process
        session.stop()
        self.assertEqual(session.status(), "backend_error_1")

    def test_launcher_provides_a_setterm_shim(self):
        launcher = os.path.join(FILES, "launch.sh")
        with open(launcher, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("command -v setterm", text)
        self.assertIn("/tmp/setterm", text)
        # The shim is created only when the firmware lacks the command, and it
        # must not linger on the system after the app exits.
        self.assertIn("grep -q", text)
        self.assertIn("rm -f /tmp/setterm", text)


class ButtonMapTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="chiaki-map-tests-")
        self.temp_dir, self.app_dir = _fresh_app_copy("chiaki-map-tests-")
        self.manager = importlib.import_module("rh.gamepad_map")

    def tearDown(self):
        _drop_app_copy(self.temp_dir, self.app_dir)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_missing_file_yields_defaults(self):
        buttons, axes, error = self.manager.load_map(self.dir)
        self.assertEqual(error, "")
        self.assertEqual(buttons["a"], 304)
        self.assertEqual(axes["hat_x"], 16)

    def test_map_with_duplicate_codes_is_refused(self):
        """A mis-recorded map made three buttons light up at once.

        Loading it would keep sending that broken map to the phone, so the
        duplicates must be rejected and the built-in table used instead.
        """
        path = os.path.join(self.dir, self.manager.MAP_NAME)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('{"version":1,"buttons":{"x":305,"y":305,"l3":310,'
                         '"r3":310},"axes":{}}')
        buttons, _axes, error = self.manager.load_map(self.dir)
        self.assertIn("duplicate codes", error)
        self.assertEqual(buttons["x"], 307)
        self.assertEqual(buttons["y"], 308)
        self.assertEqual(buttons["l3"], 317)
        self.assertEqual(buttons["r3"], 318)

    def test_duplicate_buttons_reports_each_pair_once(self):
        buttons = dict(self.manager.DEFAULT_BUTTONS)
        buttons["r3"] = buttons["l3"]
        found = self.manager.duplicate_buttons(buttons, ["l3", "r3"])
        self.assertEqual(found, [("l3", "r3", buttons["l3"])])

    def test_duplicate_buttons_is_empty_for_a_good_map(self):
        self.assertEqual(
            self.manager.duplicate_buttons(self.manager.DEFAULT_BUTTONS,
                                          list(self.manager.DEFAULT_BUTTONS)),
            [])

    def test_saved_map_round_trips(self):
        buttons, axes, _ = self.manager.load_map(self.dir)
        buttons["l3"] = 318
        buttons["r3"] = 319
        self.manager.save_map(self.dir, buttons, axes)
        loaded_buttons, loaded_axes, error = self.manager.load_map(self.dir)
        self.assertEqual(error, "")
        self.assertEqual(loaded_buttons["l3"], 318)
        self.assertEqual(loaded_buttons["r3"], 319)
        self.assertEqual(loaded_axes, axes)

    def test_malformed_map_falls_back_to_defaults(self):
        path = os.path.join(self.dir, self.manager.MAP_NAME)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        buttons, _axes, error = self.manager.load_map(self.dir)
        self.assertTrue(error)
        self.assertEqual(buttons["a"], 304)

    def test_out_of_range_codes_are_ignored(self):
        path = os.path.join(self.dir, self.manager.MAP_NAME)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('{"version":1,"buttons":{"a":9999,"l3":330},'
                         '"axes":{"hat_x":99}}')
        buttons, axes, error = self.manager.load_map(self.dir)
        self.assertEqual(error, "")
        self.assertEqual(buttons["a"], 304)
        self.assertEqual(buttons["l3"], 330)
        self.assertEqual(axes["hat_x"], 16)

    def test_event_struct_is_24_bytes_on_this_abi(self):
        self.assertEqual(self.manager.EVENT_SIZE, 24)

    def test_gamepad_key_range(self):
        self.assertTrue(self.manager.is_gamepad_key(304))
        self.assertTrue(self.manager.is_gamepad_key(319))
        self.assertFalse(self.manager.is_gamepad_key(172))
        self.assertFalse(self.manager.is_gamepad_key(114))


class ButtonTestScreenTests(unittest.TestCase):
    """Man hinh GHI NUT: chi ghi tho, khong gan ban do.

    Cac test cua man hinh "hop nhan tung nut" da bi thay bang tests/test_pad_probe.py.
    """

    SCREEN_W = 1024
    SCREEN_H = 768

    @classmethod
    def setUpClass(cls):
        cls.temp_dir, cls.app_dir = _fresh_app_copy("chiaki-test-screen-")
        cls.module = importlib.import_module("rh.screens.button_test")

    @classmethod
    def tearDownClass(cls):
        _drop_app_copy(cls.temp_dir, cls.app_dir)

    def _engine(self):
        engine = mock.Mock()
        engine.screen_w = self.SCREEN_W
        engine.screen_h = self.SCREEN_H
        return engine

    def _screen(self):
        screen = self.module.ButtonTestScreen(mock.Mock())
        screen.device_path = "/dev/input/event3"
        screen.device_name = "TRIMUI Player1"
        screen.probe = mock.Mock()
        screen.probe.poll.return_value = []
        screen.probe.exit_held.return_value = ""
        screen.probe.reported = []
        return screen

    def _feed(self, screen, entry):
        """Ghi mot lan bam nhu PadProbe.poll() tra ve roi dua vao reported."""
        screen.probe.reported.append(entry)
        screen.probe.poll.return_value = [entry]

    def test_each_press_is_appended_to_the_list(self):
        screen = self._screen()
        for index in range(1, 4):
            self._feed(screen, {"index": index, "elapsed": float(index),
                                "keys": [300 + index], "hat": [0, 0],
                                "codes": [300 + index], "held_ms": 80})
            screen.update(0)
        self.assertEqual(len(screen.entries), 3)
        self.assertEqual(screen.last["keys"], [303])

    def test_each_press_survives_a_render_cycle(self):
        screen = self._screen()
        screen.probe.exit_held.return_value = ""
        self._feed(screen, {"index": 1, "elapsed": 1.0, "keys": [304],
                            "hat": [0, 0], "codes": [304], "held_ms": 70})
        screen.update(0)
        screen.render(self._engine())
        self.assertEqual(len(screen.entries), 1)

    def test_b_does_not_leave_the_screen(self):
        """B la nut can thu, nen bam B chi duoc ghi chu khong duoc thoat."""
        screen = self._screen()
        screen.probe.poll.return_value = []
        self.assertFalse(screen.handle_input({"edges": ["btn_b"], "btn_b": True}))
        screen.update(0)
        screen.engine.pop_screen.assert_not_called()

    def test_a_is_a_recorded_button_not_a_save_control(self):
        """A la nut can thu, nen khong duoc lam nut luu va khong duoc thoat."""
        screen = self._screen()
        screen.probe.poll.return_value = []
        with mock.patch.object(self.module, "write_log",
                               return_value="/tmp/BrickButtons.log") as writer:
            handled = screen.handle_input({"edges": ["btn_a"], "btn_a": True})
        self.assertFalse(handled)
        writer.assert_not_called()
        screen.engine.pop_screen.assert_not_called()

    def test_menu_is_the_only_footer_action_and_means_save_plus_exit(self):
        screen = self._screen()
        actions = screen.get_footer_actions()
        self.assertEqual([key for key, _label in actions], ["MENU"])
        self.assertEqual(actions[0][1], self.module.tr("button_test_save_exit"))
        self.assertIn("2", actions[0][1])

    def test_one_press_is_drawn_exactly_once(self):
        """Mot lan bam khong duoc hien hai dong giong het nhau."""
        screen = self._screen()
        entry = {"index": 1, "elapsed": 1.43, "keys": [305],
                 "hat": [0, 0], "codes": [305], "held_ms": 60}
        self._feed(screen, entry)
        screen.update(0)
        engine = self._engine()
        screen.render(engine)
        expected = self.module.format_entry(entry)
        drawn = [call.args[0] for call in engine.draw_text.call_args_list
                 if call.args and isinstance(call.args[0], str)]
        self.assertEqual(drawn.count(expected), 1)

    def test_holding_menu_saves_and_leaves(self):
        screen = self._screen()
        screen.probe.exit_held.return_value = "menu"
        self._feed(screen, {"index": 1, "elapsed": 1.0, "keys": [304],
                            "hat": [0, 0], "codes": [304], "held_ms": 60})
        with mock.patch.object(self.module, "write_log",
                               return_value="/tmp/BrickButtons.log") as writer, \
                mock.patch.object(self.module, "append_note"):
            screen.update(0)
        writer.assert_called_once()
        screen.engine.pop_screen.assert_called_once()

    def test_an_exit_key_dropped_by_the_probe_stays_out_of_the_log(self):
        """Probe lo phim thoat khoi ``reported``, thi log cung phai bo no."""
        screen = self._screen()
        self._feed(screen, {"index": 1, "elapsed": 1.0, "keys": [304],
                            "hat": [0, 0], "codes": [304], "held_ms": 60})
        screen.update(0)
        self.assertEqual(len(screen.entries), 1)
        # Gia lap tinh huong START an truoc, SELECT an sau: dong chi chua phim
        # thoat bi probe xoa khoi reported, nen man hinh phai bo theo.
        screen.probe.reported = []
        screen.update(0)
        self.assertEqual(screen.entries, [])
        with mock.patch.object(self.module, "write_log",
                               return_value="/tmp/BrickButtons.log") as writer:
            screen._save()
        writer.assert_not_called()

    def test_holding_start_select_also_leaves(self):
        screen = self._screen()
        screen.probe.exit_held.return_value = "start_select"
        screen.update(0)
        screen.engine.pop_screen.assert_called_once()

    def test_a_held_button_alone_never_leaves(self):
        screen = self._screen()
        screen.probe.exit_held.return_value = ""
        for _ in range(20):
            screen.update(0)
        screen.engine.pop_screen.assert_not_called()

    def test_a_is_never_treated_as_skip(self):
        """A van la nut thu, nen A chi luu log chu khong bo qua buoc nao."""
        screen = self._screen()
        screen.entries = []
        self._feed(screen, {"index": 1, "elapsed": 1.0, "keys": [305],
                            "hat": [0, 0], "codes": [305], "held_ms": 60})
        screen.update(0)
        self.assertEqual(len(screen.entries), 1)
        self.assertEqual(screen.entries[0]["keys"], [305])

    def test_no_device_leaves_an_error_and_no_crash(self):
        screen = self.module.ButtonTestScreen(mock.Mock())
        with mock.patch.object(self.module, "find_gamepad",
                               return_value=(None, "")):
            screen.on_enter()
        self.assertEqual(screen.error, self.module.tr("button_test_no_device"))
        self.assertIsNone(screen.probe)
        screen.render(self._engine())
        screen.update(0)
        # Khong co thiet bi thi khong duoc nhac, va van phai thoat duoc bang
        # duong an toan cua app.
        self.assertFalse(screen.handle_input({"edges": [], "btn_b": False}))
        self.assertTrue(screen.handle_input({"edges": ["quit"], "quit": True}))

    def test_the_report_order_lists_only_buttons_with_a_key_code(self):
        """L2/R2 la cam bien analog nen khong duoc cho vao danh sach nut."""
        order = self.module.DEFAULT_ORDER
        self.assertEqual(len(order), 10)
        self.assertNotIn("l2", order)
        self.assertNotIn("r2", order)
        self.assertNotIn("mode", order)

    def test_render_survives_an_empty_session(self):
        screen = self._screen()
        engine = self._engine()
        screen.render(engine)
        self.assertTrue(engine.draw_text.called)

    def test_render_draws_every_button_in_the_report_order(self):
        """Moi nut trong danh sach bao cao deu phai co duoc ve tren man hinh."""
        screen = self._screen()
        engine = self._engine()
        screen.render(engine)
        drawn = [call.args[0] for call in engine.draw_text.call_args_list
                 if call.args and isinstance(call.args[0], str)]
        for index, name in enumerate(self.module.DEFAULT_ORDER):
            label = "%d.%s" % (index + 1, name.upper())
            self.assertTrue(any(label in text for text in drawn),
                            "%s was not drawn" % label)

    def test_leaving_the_screen_still_saves_the_log(self):
        """Bam B khi chua bam A van giu du lieu, tranh mat ca phien thu."""
        screen = self._screen()
        self._feed(screen, {"index": 1, "elapsed": 1.0, "keys": [304],
                            "hat": [0, 0], "codes": [304], "held_ms": 60})
        with mock.patch.object(self.module, "write_log",
                               return_value="/tmp/BrickButtons.log") as writer, \
                mock.patch.object(self.module, "append_note"):
            screen.on_exit()
        writer.assert_called_once()

    def test_saving_twice_writes_once_per_press(self):
        screen = self._screen()
        screen.entries = [{"index": 1, "elapsed": 1.0, "keys": [304],
                           "hat": [0, 0], "codes": [304], "held_ms": 60}]
        with mock.patch.object(self.module, "write_log",
                               return_value="/tmp/BrickButtons.log") as writer, \
                mock.patch.object(self.module, "append_note"):
            screen._save()
        # writer duoc goi mot lan cho ca phien, khong phai mot lan moi bam.
        self.assertEqual(writer.call_count, 1)
        self.assertEqual(len(writer.call_args[0][0]), 1)


if __name__ == "__main__":
    unittest.main()

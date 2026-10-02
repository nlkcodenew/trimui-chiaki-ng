# -*- coding: utf-8 -*-

import importlib
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
    @classmethod
    def setUpClass(cls):
        cls.temp_dir, cls.app_dir = _fresh_app_copy("chiaki-test-screen-")
        cls.module = importlib.import_module("rh.screens.button_test")

    @classmethod
    def tearDownClass(cls):
        _drop_app_copy(cls.temp_dir, cls.app_dir)

    def _screen(self):
        screen = self.module.ButtonTestScreen(mock.Mock())
        screen.device_path = "/dev/input/event3"
        screen.device_name = "TRIMUI Player1"
        screen.reader = mock.Mock()
        screen.reader.poll.return_value = []
        return screen

    def _feed(self, screen, code, value):
        screen.reader.poll.return_value = [(1, code, value)]
        screen.update(0)

    def _press(self, screen, code, held_frames=1, released_frames=1):
        """Feed one physical press: held for N frames, then released."""
        for _ in range(held_frames):
            self._feed(screen, code, 1)
        for _ in range(released_frames):
            self._feed(screen, code, 0)

    def test_pressing_a_key_assigns_it_to_the_current_button(self):
        screen = self._screen()
        step = self.module.ASK_ORDER.index("l3")
        screen.step = step
        self.assertEqual(screen._current(), "l3")
        self._press(screen, 318)
        self.assertEqual(screen.buttons["l3"], 318)
        self.assertEqual(screen.step, step + 1)

    def test_one_press_assigns_exactly_one_button(self):
        """Regression: one press used to fill every following step.

        A held key was offered to each step in turn, so a single press wrote the
        same code into three buttons and the phone lit all three at once.
        """
        screen = self._screen()
        screen.step = self.module.ASK_ORDER.index("b")
        start = screen.step
        for _ in range(30):
            self._feed(screen, 305, 1)
        self.assertEqual(screen.step, start + 1)
        self.assertEqual(screen.buttons["b"], 305)
        for name in ("x", "y", "l1", "r1", "l3"):
            self.assertNotEqual(screen.buttons.get(name), 305,
                                "%s took a code that already belonged to b" % name)

    def test_a_press_that_is_still_held_needs_a_release_first(self):
        screen = self._screen()
        screen.step = self.module.ASK_ORDER.index("b")
        self._feed(screen, 305, 1)
        self.assertTrue(screen.wait_release)
        screen.step = self.module.ASK_ORDER.index("x")
        self._feed(screen, 307, 1)
        self.assertEqual(screen.buttons["x"], self.module.DEFAULT_BUTTONS["x"])
        # Nothing is accepted while a button from a previous step is held.
        for _ in range(10):
            self._feed(screen, 307, 1)
        self.assertEqual(screen.buttons["x"], self.module.DEFAULT_BUTTONS["x"])
        self._feed(screen, 305, 0)
        self._feed(screen, 307, 0)
        self.assertFalse(screen.wait_release)
        self._feed(screen, 307, 1)
        self.assertEqual(screen.buttons["x"], 307)

    def test_button_a_is_not_a_skip_key_while_it_is_being_tested(self):
        """Regression: pressing the asked-for A button skipped its own step."""
        screen = self._screen()
        self.assertEqual(screen.step, 0)
        self.assertEqual(screen._current(), "a")
        handled = screen.handle_input({"edges": ["btn_a"], "btn_a": True})
        self.assertFalse(handled)
        self.assertEqual(screen.step, 0)

    def test_dpad_up_skips_and_dpad_down_steps_back(self):
        screen = self._screen()
        screen.step = 2
        screen.hat[self.module.HAT_Y] = -1
        screen.update(0)
        self.assertEqual(screen.step, 3)
        screen.hat[self.module.HAT_Y] = 1
        screen.update(0)
        self.assertEqual(screen.step, 2)

    def test_all_steps_finish_and_offer_a_save(self):
        screen = self._screen()
        for index in range(len(self.module.ASK_ORDER)):
            screen.step = index
            screen._accept(1000 + index)
        self.assertTrue(screen.finished)
        self.assertEqual(self.module.tr("button_test_save"), "LUU")

    def test_saving_is_refused_while_two_buttons_share_a_code(self):
        screen = self._screen()
        screen.step = self.module.ASK_ORDER.index("l3")
        screen._accept(318)
        screen.step = self.module.ASK_ORDER.index("r3")
        screen._accept(318)
        with mock.patch.object(self.module, "save_map") as saver:
            screen._save()
        saver.assert_not_called()
        self.assertIn("dung mot ma phim", screen.flash)

    def test_saving_writes_the_map_and_returns(self):
        screen = self._screen()
        screen.step = self.module.ASK_ORDER.index("l3")
        screen._accept(330)
        screen.step = self.module.ASK_ORDER.index("r3")
        screen._accept(331)
        screen.finished = True
        with mock.patch.object(self.module, "save_map",
                               return_value="/tmp/map.json") as saver:
            screen._save()
        saver.assert_called_once()
        screen.engine.pop_screen.assert_called_once()

    def test_a_and_b_are_used_only_on_the_summary_screen(self):
        screen = self._screen()
        screen.finished = True
        screen.step = self.module.ASK_ORDER.index("l3")
        screen._accept(330)
        screen.step = self.module.ASK_ORDER.index("r3")
        screen._accept(331)
        screen.finished = True
        with mock.patch.object(self.module, "save_map",
                               return_value="/tmp/map.json"):
            self.assertTrue(screen.handle_input({"edges": ["btn_a"], "btn_a": True}))
        screen.finished = True
        self.assertTrue(screen.handle_input({"edges": ["btn_b"], "btn_b": True}))
        self.assertFalse(screen.finished)

    def test_holding_a_sideways_dpad_exits_without_saving(self):
        screen = self._screen()
        clock = [50.0]
        screen.clock = lambda: clock[0]
        screen.hat[self.module.HAT_X] = 1
        screen.update(0)
        clock[0] = 50.0 + self.module.HOLD_EXIT + 0.1
        screen.update(0)
        screen.engine.pop_screen.assert_called_once()


if __name__ == "__main__":
    unittest.main()

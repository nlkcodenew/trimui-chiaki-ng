# -*- coding: utf-8 -*-

import importlib
import json
import logging
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock


class LogUploaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="chiaki-tests-")
        source = os.path.join(os.path.dirname(os.path.dirname(__file__)), "files")
        cls.app_dir = os.path.join(cls.temp_dir, "files")
        shutil.copytree(source, cls.app_dir)
        sys.path.insert(0, cls.app_dir)
        cls.uploader = importlib.import_module("rh.log_uploader")
        cls.updater = importlib.import_module("rh.updater")
        cls.inputs = importlib.import_module("rh.inputs")
        cls.settings_module = importlib.import_module("rh.screens.settings")

    @classmethod
    def tearDownClass(cls):
        logging.shutdown()
        sys.path.remove(cls.app_dir)
        for name in list(sys.modules):
            if name == "rh" or name.startswith("rh."):
                sys.modules.pop(name, None)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.work_dir = tempfile.mkdtemp(dir=self.temp_dir)
        self.uploader.SECRETS_FILE = os.path.join(self.work_dir, "secrets.json")
        self.uploader.STATE_FILE = os.path.join(self.work_dir, "upload-state.json")
        self.uploader.PENDING_FILE = os.path.join(self.work_dir, "pending")
        self.log_path = os.path.join(self.work_dir, "Chiaki-loi.txt")
        self.uploader.state.auto_upload_logs = True
        self.uploader.state.github_issue_repo = "nlkcodenew/trimui-chiaki-ng"
        with open(self.uploader.SECRETS_FILE, "w", encoding="utf-8") as handle:
            json.dump({"github_token": "github_pat_TEST_TOKEN"}, handle)

    def tearDown(self):
        shutil.rmtree(self.work_dir, ignore_errors=True)

    def _pending_log(self):
        with open(self.uploader.PENDING_FILE, "w", encoding="utf-8"):
            pass
        with open(self.log_path, "w", encoding="utf-8") as handle:
            handle.write(
                "github_token=github_pat_SECRET_VALUE\n"
                "psn_online_id: PlayerName\n"
                "console 192.168.1.55 aa:bb:cc:dd:ee:ff crashed\n"
            )

    def test_success_sanitizes_and_deduplicates(self):
        self._pending_log()
        captured = []

        def fake_collect():
            with open(self.log_path, encoding="utf-8") as handle:
                text = handle.read()
            return [("Chiaki-loi.txt", self.uploader._sanitize(text))]

        def fake_post(token, repo, title, body):
            captured.append((token, repo, title, body))
            return "https://github.com/example/issues/1"

        with mock.patch.object(self.uploader, "_collect", side_effect=fake_collect), \
                mock.patch.object(self.uploader, "_post_issue", side_effect=fake_post):
            self.assertTrue(self.uploader.upload_pending("exit_1"))
            self.assertFalse(os.path.exists(self.uploader.PENDING_FILE))
            self.assertEqual(len(captured), 1)
            body = captured[0][3]
            self.assertNotIn("SECRET_VALUE", body)
            self.assertNotIn("PlayerName", body)
            self.assertNotIn("192.168.1.55", body)
            self.assertNotIn("aa:bb:cc:dd:ee:ff", body)

            with open(self.uploader.PENDING_FILE, "w", encoding="utf-8"):
                pass
            self.assertTrue(self.uploader.upload_pending("startup_retry"))
            self.assertEqual(len(captured), 1)
            self.assertFalse(os.path.exists(self.uploader.PENDING_FILE))

    def test_failed_upload_keeps_pending_marker(self):
        self._pending_log()
        sections = [("Chiaki-loi.txt", "traceback")]
        with mock.patch.object(self.uploader, "_collect", return_value=sections), \
                mock.patch.object(self.uploader, "_post_issue",
                                  side_effect=OSError("offline")):
            self.assertFalse(self.uploader.upload_pending("exit_1"))
        self.assertTrue(os.path.exists(self.uploader.PENDING_FILE))

    def test_updater_ignores_user_settings(self):
        manifest = {
            "files": [{"path": "settings.json", "sha256": "0" * 64}]
        }
        self.assertEqual(self.updater.pending_files(manifest), [])
        urls = self.updater.candidate_manifest_urls()
        self.assertIn("releases/latest/download/manifest.json", urls[0])

    def test_joystick_fallback_maps_profile_buttons(self):
        manager = self.inputs.InputManager()
        manager._map_joy_button(1, True)
        self.assertTrue(manager.poll()["btn_a"])
        manager._map_joy_button(1, False)
        self.assertFalse(manager.poll()["btn_a"])

    def test_gamecontroller_button_does_not_crash_on_first_press(self):
        manager = self.inputs.InputManager()
        fake_sdl = types.SimpleNamespace(
            SDL_QUIT=0x100,
            SDL_CONTROLLERBUTTONDOWN=0x651,
            SDL_CONTROLLERBUTTONUP=0x652,
        )
        event = types.SimpleNamespace(
            type=fake_sdl.SDL_CONTROLLERBUTTONDOWN,
            cbutton=types.SimpleNamespace(button=0),
        )
        with mock.patch.object(self.inputs, "sdl2", fake_sdl, create=True), \
                mock.patch.object(self.inputs, "SDL2_OK", True):
            manager.feed_event(event)
            state = manager.poll()
            self.assertTrue(state["btn_a"])
            self.assertIn("btn_a", state["edges"])
            event.type = fake_sdl.SDL_CONTROLLERBUTTONUP
            manager.feed_event(event)
            self.assertFalse(manager.poll()["btn_a"])

    def test_gamecontroller_axes_and_triggers(self):
        manager = self.inputs.InputManager()
        manager._map_controller_axis(0, 12345)
        manager._map_controller_axis(4, 9000)
        state = manager.poll()
        self.assertEqual(state["axis_left_x"], 12345)
        self.assertTrue(state["btn_l2"])

    def test_vietnamese_ui_uses_accented_text(self):
        i18n = importlib.import_module("rh.i18n")
        self.assertEqual(i18n.TEXTS["VI"]["settings"], "CÀI ĐẶT")
        self.assertEqual(i18n.TEXTS["VI"]["update"], "CẬP NHẬT")
        self.assertIn("Không", i18n.TEXTS["VI"]["scan_none"])

    def test_every_settings_row_has_a_runtime_state_value(self):
        screen = self.settings_module.SettingsScreen()
        for key, _, _ in screen.rows:
            self.assertTrue(hasattr(self.settings_module.state, key), key)

    def test_settings_language_row_updates_current_lang(self):
        screen = self.settings_module.SettingsScreen()
        screen.selected = next(
            index for index, row in enumerate(screen.rows)
            if row[0] == "current_lang"
        )
        original = self.settings_module.state.current_lang
        try:
            screen._change(1)
            self.assertIn(self.settings_module.state.current_lang, ("VI", "EN"))
            self.assertNotEqual(self.settings_module.state.current_lang, original)
        finally:
            self.settings_module.state.current_lang = original

    def test_settings_screen_renders_every_scroll_position(self):
        screen = self.settings_module.SettingsScreen()

        class FakeEngine:
            screen_w = 1280
            screen_h = 720
            font_title = object()
            font_sub = object()

            def fill_rect(self, *args, **kwargs):
                return None

            def draw_text(self, *args, **kwargs):
                return None

        engine = FakeEngine()
        for index in range(len(screen.rows)):
            screen.selected = index
            screen.render(engine)


if __name__ == "__main__":
    unittest.main()

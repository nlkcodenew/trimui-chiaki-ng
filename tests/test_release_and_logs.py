# -*- coding: utf-8 -*-

import importlib
import base64
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
        cls.update_modal_module = importlib.import_module("rh.modals.update")

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

    def test_payload_urls_include_repository_files_directory(self):
        urls = self.updater.payload_base_urls(
            {"release_tag": "v0.2.6/files"}, "app.py")
        self.assertEqual(
            urls[0],
            "https://raw.githubusercontent.com/nlkcodenew/trimui-chiaki-ng/"
            "v0.2.6/files",
        )
        self.assertTrue(all(not url.endswith("/files/files") for url in urls))

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
        # Nut A vat ly tren TrimUI = SDL_CONTROLLER_BUTTON_B (id 1).
        event = types.SimpleNamespace(
            type=fake_sdl.SDL_CONTROLLERBUTTONDOWN,
            cbutton=types.SimpleNamespace(button=1),
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

    def test_gamecontroller_physical_b_maps_to_btn_b_not_btn_a(self):
        # Regress P0 v0.2.9: nut B vat ly (SDL_CONTROLLER_BUTTON_A, id 0) phai
        # ra btn_b de man Cai dat thoat, khong duoc doi gia tri.
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
            self.assertTrue(state["btn_b"])
            self.assertFalse(state["btn_a"])
            self.assertIn("btn_b", state["edges"])
            self.assertNotIn("btn_a", state["edges"])

    def test_joystick_events_ignored_when_controller_attached(self):
        # Khi SDL da mo GameController, mot lan bam nut sinh ca CONTROLLER lan
        # JOY*. Neu xu ly ca JOY*, nut B vat ly se vua la btn_b (controller)
        # vua la btn_a (joy id 1 theo profile trimui) -> Cai dat doi gia tri.
        manager = self.inputs.InputManager()
        fake_sdl = types.SimpleNamespace(
            SDL_QUIT=0x100,
            SDL_CONTROLLERBUTTONDOWN=0x651,
            SDL_CONTROLLERBUTTONUP=0x652,
            SDL_CONTROLLERAXISMOTION=0x653,
            SDL_KEYDOWN=0x300,
            SDL_KEYUP=0x301,
            SDL_JOYBUTTONDOWN=0x600,
            SDL_JOYBUTTONUP=0x601,
            SDL_JOYHATMOTION=0x602,
            SDL_JOYAXISMOTION=0x603,
        )
        manager.attach_controller(object())
        joy_event = types.SimpleNamespace(
            type=fake_sdl.SDL_JOYBUTTONDOWN,
            jbutton=types.SimpleNamespace(button=1),
        )
        with mock.patch.object(self.inputs, "sdl2", fake_sdl, create=True), \
                mock.patch.object(self.inputs, "SDL2_OK", True):
            manager.feed_event(joy_event)
        state = manager.poll()
        self.assertFalse(state["btn_a"])
        self.assertFalse(state["btn_b"])
        self.assertEqual(state["edges"], [])

    def test_settings_integration_physical_buttons(self):
        # Mo phong dung chuoi su kien may that: bam B vat ly (controller id 0)
        # khi dang o Cai dat chi duoc pop, khong save; bam A vat ly (id 1) doi
        # gia tri va save ngay.
        manager = self.inputs.InputManager()
        fake_sdl = types.SimpleNamespace(
            SDL_QUIT=0x100,
            SDL_CONTROLLERBUTTONDOWN=0x651,
            SDL_CONTROLLERBUTTONUP=0x652,
            SDL_CONTROLLERAXISMOTION=0x653,
            SDL_KEYDOWN=0x300,
            SDL_KEYUP=0x301,
            SDL_JOYBUTTONDOWN=0x600,
            SDL_JOYBUTTONUP=0x601,
            SDL_JOYHATMOTION=0x602,
            SDL_JOYAXISMOTION=0x603,
        )
        manager.attach_controller(object())
        engine = mock.Mock()
        screen = self.settings_module.SettingsScreen(engine)
        screen.selected = next(
            index for index, row in enumerate(screen.rows)
            if row[0] == "auto_update"
        )

        def press_and_release(button_id):
            with mock.patch.object(self.inputs, "sdl2", fake_sdl, create=True), \
                    mock.patch.object(self.inputs, "SDL2_OK", True):
                evt = types.SimpleNamespace(
                    type=fake_sdl.SDL_CONTROLLERBUTTONDOWN,
                    cbutton=types.SimpleNamespace(button=button_id),
                )
                manager.feed_event(evt)
                down_state = manager.poll()
                evt.type = fake_sdl.SDL_CONTROLLERBUTTONUP
                manager.feed_event(evt)
                manager.poll()
            return down_state

        original = self.settings_module.state.auto_update
        try:
            with mock.patch.object(self.settings_module.state, "save_settings") as save:
                state_b = press_and_release(0)
                self.assertIn("btn_b", state_b["edges"])
                self.assertNotIn("btn_a", state_b["edges"])
                screen.handle_input(state_b)
                save.assert_not_called()
                engine.pop_screen.assert_called_once_with()

            engine.reset_mock()
            with mock.patch.object(self.settings_module.state, "save_settings") as save:
                state_a = press_and_release(1)
                self.assertIn("btn_a", state_a["edges"])
                self.assertNotIn("btn_b", state_a["edges"])
                screen.handle_input(state_a)
                save.assert_called_once_with()
                engine.pop_screen.assert_not_called()
                self.assertEqual(
                    self.settings_module.state.auto_update, not original)
        finally:
            self.settings_module.state.auto_update = original

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
            if key == "back":
                continue
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

    def test_settings_a_changes_value_without_leaving_screen(self):
        engine = mock.Mock()
        screen = self.settings_module.SettingsScreen(engine)
        screen.selected = next(
            index for index, row in enumerate(screen.rows)
            if row[0] == "auto_update"
        )
        original = self.settings_module.state.auto_update
        try:
            with mock.patch.object(self.settings_module.state, "save_settings") as save:
                handled = screen.handle_input({"edges": ["btn_a"]})
            self.assertTrue(handled)
            self.assertEqual(self.settings_module.state.auto_update, not original)
            save.assert_called_once_with()
            engine.pop_screen.assert_not_called()
        finally:
            self.settings_module.state.auto_update = original

    def test_settings_b_returns_to_home_without_extra_save(self):
        engine = mock.Mock()
        screen = self.settings_module.SettingsScreen(engine)
        with mock.patch.object(self.settings_module.state, "save_settings") as save:
            handled = screen.handle_input({"edges": ["btn_b"]})
        self.assertTrue(handled)
        save.assert_not_called()
        engine.pop_screen.assert_called_once_with()

    def test_settings_back_row_exits_on_a_and_renders(self):
        engine = mock.Mock()
        screen = self.settings_module.SettingsScreen(engine)
        back_index = next(
            index for index, row in enumerate(screen.rows)
            if row[0] == "back"
        )
        screen.selected = back_index
        handled = screen.handle_input({"edges": ["btn_a"]})
        self.assertTrue(handled)
        engine.pop_screen.assert_called_once_with()
        engine.reset_mock()
        handled = screen.handle_input({"edges": ["btn_b"]})
        self.assertTrue(handled)
        engine.pop_screen.assert_called_once_with()
        class FakeEngine:
            screen_w = 1280
            screen_h = 720
            font_title = object()
            font_sub = object()
            def fill_rect(self, *args, **kwargs):
                return None
            def draw_text(self, *args, **kwargs):
                return None
        screen.render(FakeEngine())

    def test_home_title_includes_app_version(self):
        home_module = importlib.import_module("rh.screens.home")
        version = importlib.import_module("rh.version").APP_VERSION
        screen = home_module.HomeScreen()
        self.assertIn(version, screen.get_header_title())
        self.assertTrue(screen.get_header_title().startswith("CHIAKI-NG"))

    def test_update_modal_uses_edges_and_closes_to_home(self):
        engine = types.SimpleNamespace(active_modal=None)
        modal = self.update_modal_module.UpdateModal(engine)
        engine.active_modal = modal
        modal.open({"manifest": {"version": "9.9.9"}, "files": []})

        modal.handle_input({"btn_right": True, "edges": []})
        self.assertEqual(modal.selected_opt, 0)
        modal.handle_input({"edges": ["btn_right"]})
        self.assertEqual(modal.selected_opt, 1)
        modal.handle_input({"edges": ["btn_a"]})
        self.assertIsNone(engine.active_modal)
        self.assertFalse(modal.active)

    def test_update_modal_skip_closes_and_records_version(self):
        engine = types.SimpleNamespace(active_modal=None)
        modal = self.update_modal_module.UpdateModal(engine)
        engine.active_modal = modal
        modal.open({"manifest": {"version": "9.9.9"}, "files": []})
        modal.selected_opt = 2
        with mock.patch.object(self.update_modal_module, "skip_version") as skip:
            modal.handle_input({"edges": ["btn_a"]})
        skip.assert_called_once_with("9.9.9")
        self.assertIsNone(engine.active_modal)

    def test_srch_packet_matches_upstream_format(self):
        chiaki = importlib.import_module("rh.chiaki")
        pkt = chiaki._build_srch(chiaki.PS4_PROTOCOL_VERSION)
        self.assertEqual(
            pkt,
            b"SRCH * HTTP/1.1\ndevice-discovery-protocol-version:00020020\n\x00",
        )
        self.assertEqual(chiaki.PS4_DISCOVERY_PORT, 987)
        self.assertEqual(chiaki.PS5_DISCOVERY_PORT, 9302)

    def test_discovery_sends_to_ps4_and_ps5_destination_ports(self):
        chiaki = importlib.import_module("rh.chiaki")
        sent_dests = []

        class FakeSocket:
            def __init__(self, *args, **kwargs):
                self._closed = False

            def setsockopt(self, *args, **kwargs):
                return None

            def settimeout(self, *args, **kwargs):
                return None

            def bind(self, addr):
                return None

            def getsockname(self):
                return ("0.0.0.0", 9303)

            def sendto(self, data, dest):
                sent_dests.append(dest[1])

            def recvfrom(self, size):
                raise OSError("timeout")

            def close(self):
                self._closed = True

        with mock.patch.object(chiaki.socket, "socket", FakeSocket), \
                mock.patch.object(chiaki.time, "sleep", lambda *_: None):
            chiaki.discovery_broadcast(timeout=0.1)
        self.assertIn(987, sent_dests)
        self.assertIn(9302, sent_dests)
        self.assertNotIn(9303, sent_dests)

    def test_parse_srch_response_ready_and_standby(self):
        chiaki = importlib.import_module("rh.chiaki")
        ready = (
            b"HTTP/1.1 200 OK\n"
            b"host-name:Living-Room-PS4\n"
            b"system-version:0900000\n"
            b"host-request-port:9295\n"
            b"device-discovery-protocol-version:00020020\n"
        )
        host = chiaki._parse_srch(ready, ("192.168.1.50", 987), False)
        self.assertIsNotNone(host)
        self.assertEqual(host.state, "ready")
        self.assertEqual(host.name, "Living-Room-PS4")
        self.assertFalse(host.is_ps5)
        self.assertEqual(host.addr, "192.168.1.50")
        self.assertEqual(host.host_request_port, 9295)
        # atoi("0900000") = 900000 < 7000000 -> PS4_8, giống upstream.
        self.assertEqual(host.target, 800)

        standby = b"HTTP/1.1 620 Standby\nhost-name:PS5\nsystem-version:08050001\n"
        host5 = chiaki._parse_srch(standby, ("192.168.1.60", 9302), True)
        self.assertIsNotNone(host5)
        self.assertEqual(host5.state, "standby")
        self.assertTrue(host5.is_ps5)
        self.assertEqual(host5.target, 1000100)  # PS5_1

    def test_ps4_registration_crypto_roundtrip_and_response_parse(self):
        regist = importlib.import_module("rh.ps4_regist")
        self.assertEqual(len(regist.PS4_KEYS_0), 512)
        self.assertEqual(len(regist.PS4_KEYS_1), 512)
        ambassador = bytes(range(16))
        payload, bright, used_ambassador = regist._build_payload(
            "12345678", b"\0" * 8, ambassador,
        )
        self.assertEqual(used_ambassador, ambassador)
        self.assertGreater(len(payload), regist.INNER_HEADER_OFFSET)
        encrypted = regist._aes_cfb(b"remote-play", bright, ambassador)
        self.assertEqual(
            regist._aes_cfb(encrypted, bright, ambassador, decrypt=True),
            b"remote-play",
        )
        response = (
            b"PS4-Nickname: PS4-896\r\n"
            b"PS4-RegistKey: 6134396430386564\r\n"
            b"RP-KeyType: 2\r\n"
            b"RP-Key: 000102030405060708090a0b0c0d0e0f\r\n"
            b"PS4-Mac: 001122334455\r\n"
        )
        result = regist._parse_result(response)
        self.assertEqual(result["regist_key"], "a49d08ed")
        self.assertEqual(result["rp_key_type"], 2)
        self.assertEqual(result["server_mac"], "001122334455")
        self.assertEqual(base64.b64decode(result["rp_key"]), bytes(range(16)))

    def test_regist_with_pin_never_returns_stub_keys(self):
        chiaki = importlib.import_module("rh.chiaki")
        host = chiaki.DiscoveredHost(
            name="PS4-896", addr="192.168.1.45", is_ps5=False, target=1000,
        )
        real = {
            "regist_key": "a49d08ed",
            "rp_key": base64.b64encode(bytes(range(16))).decode("ascii"),
            "rp_key_type": 2,
            "server_mac": "001122334455",
        }
        regist = importlib.import_module("rh.ps4_regist")
        with mock.patch.object(regist, "register", return_value=real):
            ok, result = chiaki.regist_with_pin(host, "12345678")
        self.assertTrue(ok)
        self.assertFalse(result["is_ps5"])
        self.assertNotIn("stub", result["rp_key"])
        with mock.patch.object(regist, "register", side_effect=regist.RegistError("HTTP 403")):
            ok, result = chiaki.regist_with_pin(host, "12345678")
        self.assertFalse(ok)
        self.assertEqual(result["error"], "HTTP 403")


if __name__ == "__main__":
    unittest.main()

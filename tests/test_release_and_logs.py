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
        cls.logger_module = importlib.import_module("rh.logger")
        cls.common_modals = importlib.import_module("rh.modals.common")
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

    def test_quality_report_is_not_described_as_crash(self):
        body = self.uploader._issue_body(
            [("Chiaki-debug.log", "quality: rendered=150 lost=0 fec=0 fps=30.0")],
            "native_stream_quality",
            "a" * 64,
        )
        self.assertIn("Báo cáo chất lượng stream", body)
        self.assertNotIn("sau khi ứng dụng lỗi", body)

    def test_exit_retry_is_described_as_pending_report(self):
        body = self.uploader._issue_body(
            [("Chiaki-debug.log", "quality: rendered=150 lost=0 fec=0 fps=30.0")],
            "user_exit_retry",
            "a" * 64,
        )
        self.assertIn("đang chờ được gửi lại", body)
        self.assertNotIn("sau khi ứng dụng lỗi", body)

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
            if key in ("back", "clear_logs"):
                continue
            self.assertTrue(hasattr(self.settings_module.state, key), key)

    def test_clear_logs_requires_confirmation(self):
        engine = mock.Mock()
        screen = self.settings_module.SettingsScreen(engine)
        screen.selected = next(
            index for index, row in enumerate(screen.rows)
            if row[0] == "clear_logs"
        )
        with mock.patch.object(self.settings_module, "runtime_log_size", return_value=2048):
            handled = screen.handle_input({"edges": ["btn_a"]})
        self.assertTrue(handled)
        engine.open_modal.assert_called_once()
        name, data = engine.open_modal.call_args.args
        self.assertEqual(name, "confirm")
        self.assertTrue(callable(data["on_yes"]))

    def test_clear_log_result_modal_waits_for_new_button_edge(self):
        engine = types.SimpleNamespace(active_modal=None)
        info = self.common_modals.InfoModal(engine)
        confirm = self.common_modals.ConfirmModal(engine)

        def show_result():
            info.open({"title": "XÓA LOG CŨ", "message": "Đã xóa"})
            engine.active_modal = info

        confirm.open({"title": "XÓA LOG CŨ", "on_yes": show_result})
        engine.active_modal = confirm
        self.assertFalse(confirm.handle_input({"btn_a": True, "edges": []}))
        self.assertIs(engine.active_modal, confirm)

        self.assertTrue(confirm.handle_input({"btn_a": True, "edges": ["btn_a"]}))
        self.assertIs(engine.active_modal, info)
        self.assertTrue(info.active)

        self.assertFalse(info.handle_input({"btn_a": True, "edges": []}))
        self.assertIs(engine.active_modal, info)
        self.assertTrue(info.handle_input({"edges": ["btn_a"]}))
        self.assertIsNone(engine.active_modal)

    def test_common_modals_ignore_held_buttons_without_edges(self):
        engine = types.SimpleNamespace(active_modal=None)
        loading = self.common_modals.StreamLoadingModal(engine)
        loading.open({})
        engine.active_modal = loading
        self.assertFalse(loading.handle_input({"btn_b": True, "edges": []}))
        self.assertIs(engine.active_modal, loading)
        self.assertTrue(loading.handle_input({"edges": ["btn_b"]}))
        self.assertIsNone(engine.active_modal)

    def test_clear_runtime_logs_protects_pending_report(self):
        error_path = os.path.join(self.work_dir, "error.log")
        debug_path = os.path.join(self.work_dir, "debug.log")
        pending_path = os.path.join(self.work_dir, "pending-clear")
        for path in (error_path, debug_path, error_path + ".1", debug_path + ".1"):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("old log")
        with open(pending_path, "w", encoding="utf-8"):
            pass
        with mock.patch.object(self.logger_module, "_detect_log_paths",
                               return_value=(error_path, debug_path)), \
                mock.patch.object(self.logger_module, "_PENDING_LOG_UPLOAD", pending_path), \
                mock.patch.object(self.logger_module, "_trim_files", []):
            ok, reason, _ = self.logger_module.clear_runtime_logs()
            self.assertFalse(ok)
            self.assertEqual(reason, "pending")
            self.assertTrue(os.path.getsize(debug_path) > 0)
            os.remove(pending_path)
            ok, reason, removed = self.logger_module.clear_runtime_logs()
        self.assertTrue(ok)
        self.assertEqual(reason, "cleared")
        self.assertGreater(removed, 0)
        self.assertEqual(os.path.getsize(error_path), 0)
        self.assertEqual(os.path.getsize(debug_path), 0)
        self.assertFalse(os.path.exists(error_path + ".1"))
        self.assertFalse(os.path.exists(debug_path + ".1"))

    def test_cap_runtime_log_keeps_tail(self):
        path = os.path.join(self.work_dir, "large.log")
        with open(path, "wb") as handle:
            handle.write((b"old-line\n" * 100) + b"last-line\n")
        self.assertTrue(self.logger_module._keep_tail(path, 80))
        with open(path, "rb") as handle:
            data = handle.read()
        self.assertLessEqual(len(data), 80)
        self.assertTrue(data.endswith(b"last-line\n"))

    def test_launcher_retries_pending_report_on_user_exit(self):
        launch_path = os.path.join(self.app_dir, "launch.sh")
        with open(launch_path, encoding="utf-8") as handle:
            script = handle.read()
        self.assertIn('--reason "user_exit_retry"', script)
        self.assertIn('-m rh.logger --cap-runtime', script)
        self.assertIn('grep -q "native stream preflight"', script)
        self.assertIn('if [ $IS_STREAM -eq 0 ]', script)

    def test_native_source_supports_trimui_exit_button_fallback(self):
        root = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root, "native", "chiaki-stream.c"),
                  encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("exit_start_pressed", source)
        self.assertIn("exit_select_pressed", source)
        self.assertIn("event->jbutton.button == 8", source)
        self.assertIn("event->jbutton.button == 9", source)
        self.assertIn("CHIAKI_CONTROLLER_BUTTON_OPTIONS, false", source)
        self.assertIn("CHIAKI_CONTROLLER_BUTTON_SHARE, false", source)

    def test_native_stream_face_buttons_follow_sdl_labels(self):
        root = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root, "native", "chiaki-stream.c"),
                  encoding="utf-8") as handle:
            source = handle.read()
        expected = (
            "case SDL_CONTROLLER_BUTTON_A: return CHIAKI_CONTROLLER_BUTTON_CROSS;",
            "case SDL_CONTROLLER_BUTTON_B: return CHIAKI_CONTROLLER_BUTTON_MOON;",
            "case SDL_CONTROLLER_BUTTON_X: return CHIAKI_CONTROLLER_BUTTON_BOX;",
            "case SDL_CONTROLLER_BUTTON_Y: return CHIAKI_CONTROLLER_BUTTON_PYRAMID;",
        )
        for mapping in expected:
            self.assertIn(mapping, source)
        joystick_fallback = (
            "case 1: return CHIAKI_CONTROLLER_BUTTON_CROSS;",
            "case 0: return CHIAKI_CONTROLLER_BUTTON_MOON;",
            "case 3: return CHIAKI_CONTROLLER_BUTTON_BOX;",
            "case 2: return CHIAKI_CONTROLLER_BUTTON_PYRAMID;",
        )
        for mapping in joystick_fallback:
            self.assertIn(mapping, source)

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

    def test_home_shows_stream_exit_guide(self):
        i18n = importlib.import_module("rh.i18n")
        guide = i18n.TEXTS["VI"]["stream_exit_guide"]
        self.assertIn("START + SELECT", guide)
        self.assertIn("1,2 giây", guide)

    def test_beta_patch_is_newer_for_ota(self):
        version = importlib.import_module("rh.version")
        self.assertTrue(version.is_newer("0.3.0-beta.1", "0.3.0-beta"))
        self.assertFalse(version.is_newer("0.3.0-beta", "0.3.0-beta.1"))

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
        self.assertEqual(host.target, 900)

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
        self.assertEqual(len(regist.AES_SBOX), 256)
        self.assertEqual(
            regist._aes_encrypt_block(
                bytes.fromhex("00112233445566778899aabbccddeeff"),
                bytes.fromhex("000102030405060708090a0b0c0d0e0f"),
            ).hex(),
            "69c4e0d86a7b0430d8cdb78070b4c55a",
        )
        ambassador = bytes(range(16))
        reference_key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
        reference_plain = b"test-remote-play"
        reference_cipher = regist._aes_cfb(reference_plain, reference_key, ambassador)
        self.assertEqual(reference_cipher.hex(), "0602fa3629a2cf61584ba9aee9bf8a13")
        self.assertEqual(
            regist._aes_cfb(reference_cipher, reference_key, ambassador, decrypt=True),
            reference_plain,
        )
        pre10_payload, pre10_bright, pre10_ambassador = regist._build_payload(
            "12345678", b"\0" * 8, ambassador, pre10=True,
        )
        self.assertEqual(pre10_ambassador, ambassador)
        self.assertEqual(pre10_payload[0x11C:0x12C], bytes(
            (((ambassador[index] - index - 0x29) & 0xFF) ^ regist.ECHO_B_PRE10[index])
            for index in range(16)
        ))
        pre10_cipher = regist._aes_cfb(
            b"remote-play", pre10_bright, pre10_ambassador, pre10=True,
        )
        self.assertEqual(
            regist._aes_cfb(
                pre10_cipher, pre10_bright, pre10_ambassador,
                decrypt=True, pre10=True,
            ),
            b"remote-play",
        )
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

    def test_native_stream_launcher_keeps_keys_out_of_script(self):
        chiaki = importlib.import_module("rh.chiaki")
        work_dir = tempfile.mkdtemp(dir=self.work_dir)
        launcher_path = os.path.join(work_dir, "launch_game.sh")
        binary_path = os.path.join(work_dir, "chiaki-stream")
        paired_path = os.path.join(self.app_dir, "paired_hosts.json")
        regist_key = "a49d08ed"
        rp_key = base64.b64encode(bytes(range(16))).decode("ascii")
        with open(binary_path, "wb") as handle:
            handle.write(b"binary")
        os.chmod(binary_path, 0o755)
        with open(paired_path, "w", encoding="utf-8") as handle:
            json.dump([{
                "addr": "192.168.1.45",
                "name": "PS4-896",
                "is_ps5": False,
                "target": 900,
                "regist_key": regist_key,
                "rp_key": rp_key,
            }], handle)
        host = chiaki.DiscoveredHost(name="PS4-896", addr="192.168.1.45", target=900)
        with mock.patch.object(chiaki, "find_chiaki_binary", return_value=binary_path), \
                mock.patch.dict(os.environ, {
                    "CHIAKI_SESSION_DIR": work_dir,
                    "CHIAKI_STREAM_LAUNCHER": launcher_path,
                }, clear=False):
            ok, _ = chiaki.prepare_stream_launch(host)
        self.assertTrue(ok)
        with open(launcher_path, encoding="utf-8") as handle:
            script = handle.read()
        self.assertNotIn(regist_key, script)
        self.assertNotIn(rp_key, script)
        session_line = next(line for line in script.splitlines() if line.startswith("SESSION="))
        session_path = session_line.split("=", 1)[1].strip("'")
        if os.name != "nt":
            self.assertEqual(os.stat(session_path).st_mode & 0o777, 0o600)
        else:
            self.assertTrue(os.path.isfile(session_path))
        with open(session_path, encoding="ascii") as handle:
            session = handle.read()
        self.assertIn("host=192.168.1.45", session)
        self.assertIn("width=1280", session)
        self.assertIn("fps=30", session)
        self.assertIn("bitrate=8000", session)
        self.assertIn("target=900", session)
        self.assertIn("rp_version=9.0", session)
        self.assertIn(regist_key, session)
        self.assertIn(rp_key, session)
        os.remove(session_path)
        os.remove(paired_path)

    def test_native_stream_rejects_pair_from_wrong_protocol_target(self):
        chiaki = importlib.import_module("rh.chiaki")
        paired_path = os.path.join(self.app_dir, "paired_hosts.json")
        with open(paired_path, "w", encoding="utf-8") as handle:
            json.dump([{
                "addr": "192.168.1.45",
                "name": "PS4-896",
                "is_ps5": False,
                "target": 1000,
                "regist_key": "a49d08ed",
                "rp_key": base64.b64encode(bytes(range(16))).decode("ascii"),
            }], handle)
        host = chiaki.DiscoveredHost(
            name="PS4-896", addr="192.168.1.45", target=900,
        )
        ok, message = chiaki.prepare_stream_launch(host)
        self.assertFalse(ok)
        self.assertIn("ghép lại", message)
        os.remove(paired_path)

    def test_video_profiles_include_1080p(self):
        chiaki = importlib.import_module("rh.chiaki")
        state = importlib.import_module("rh.state")
        old_resolution = state.video_resolution
        try:
            state.video_resolution = "1080p"
            profile = chiaki._video_profile_from_state()
        finally:
            state.video_resolution = old_resolution
        self.assertEqual(profile["width"], 1920)
        self.assertEqual(profile["height"], 1080)

    def test_settings_offer_1080p_and_low_bitrate(self):
        screen = self.settings_module.SettingsScreen.__new__(
            self.settings_module.SettingsScreen)
        screen.__init__()
        rows = {key: values for key, values, _ in screen.rows if values}
        self.assertIn("1080p", rows["video_resolution"])
        self.assertIn(3000, rows["video_bitrate"])


if __name__ == "__main__":
    unittest.main()

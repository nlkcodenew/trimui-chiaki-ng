# -*- coding: utf-8 -*-

import importlib
import importlib.util
import base64
import hashlib
import json
import logging
import os
import shutil
import ssl
import sys
import tempfile
import types
import unittest
import urllib.error
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
        cls.ssl_context = importlib.import_module("rh.ssl_context")
        cls.device_identity = importlib.import_module("rh.device_identity")
        cls.inputs = importlib.import_module("rh.inputs")
        cls.logger_module = importlib.import_module("rh.logger")
        cls.common_modals = importlib.import_module("rh.modals.common")
        cls.home_module = importlib.import_module("rh.screens.home")
        cls.guide_module = importlib.import_module("rh.screens.guide")
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
        self.uploader.REPORTING_FILE = os.path.join(self.work_dir, "reporting.json")
        self.uploader.STATE_FILE = os.path.join(self.work_dir, "upload-state.json")
        self.uploader.PENDING_FILE = os.path.join(self.work_dir, "pending")
        self.log_path = os.path.join(self.work_dir, "Chiaki-loi.txt")
        self.uploader.state.auto_upload_logs = True
        with open(self.uploader.REPORTING_FILE, "w", encoding="utf-8") as handle:
            json.dump({"issue_relay_url": "https://reports.example.test/"}, handle)

    def tearDown(self):
        shutil.rmtree(self.work_dir, ignore_errors=True)

    def _pending_log(self):
        with open(self.uploader.PENDING_FILE, "w", encoding="utf-8"):
            pass
        with open(self.log_path, "w", encoding="utf-8") as handle:
            handle.write(
                "github_token=github_pat_SECRET_VALUE\n"
                "psn_online_id: PlayerName\n"
                "serial_number=SERIAL-PRIVATE-123\n"
                "sunxi_chipid: CHIP-PRIVATE-456\n"
                "console 192.168.1.55 aa:bb:cc:dd:ee:ff crashed\n"
            )

    def test_success_sanitizes_and_deduplicates(self):
        self._pending_log()
        captured = []

        def fake_collect():
            with open(self.log_path, encoding="utf-8") as handle:
                text = handle.read()
            return [("Chiaki-loi.txt", self.uploader._sanitize(text))]

        def fake_post(relay_url, title, body, fingerprint):
            captured.append((relay_url, title, body, fingerprint))
            return ""

        identity = {
            "install_id": "CHI-ABCD",
            "hardware_id": "HW-0123456789AB",
            "model": "TrimUI Brick Pro",
        }
        with mock.patch.object(self.uploader, "_collect", side_effect=fake_collect), \
                mock.patch.object(self.uploader, "_post_relay", side_effect=fake_post), \
                mock.patch.object(self.uploader, "diagnostic_identity",
                                  return_value=identity):
            self.assertTrue(self.uploader.upload_pending("exit_1"))
            self.assertFalse(os.path.exists(self.uploader.PENDING_FILE))
            self.assertEqual(len(captured), 1)
            title = captured[0][1]
            body = captured[0][2]
            self.assertIn("[TrimUI Brick Pro]", title)
            self.assertIn("[CHI-ABCD]", title)
            self.assertIn("[HW-0123456789AB]", title)
            self.assertIn("Mã cài đặt", body)
            self.assertIn("Mã phần cứng băm", body)
            self.assertNotIn("SECRET_VALUE", body)
            self.assertNotIn("PlayerName", body)
            self.assertNotIn("SERIAL-PRIVATE-123", body)
            self.assertNotIn("CHIP-PRIVATE-456", body)
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
                mock.patch.object(self.uploader, "_post_relay",
                                  side_effect=OSError("offline")):
            self.assertFalse(self.uploader.upload_pending("exit_1"))
        self.assertTrue(os.path.exists(self.uploader.PENDING_FILE))

    def test_relay_is_the_only_upload_transport(self):
        self._pending_log()
        sections = [("Chiaki-loi.txt", "traceback")]
        with mock.patch.object(self.uploader, "_collect", return_value=sections), \
                mock.patch.object(self.uploader, "_post_relay",
                                  return_value="") as relay:
            self.assertTrue(self.uploader.upload_pending("exit_1"))
        relay.assert_called_once()
        self.assertEqual(relay.call_args.args[0], "https://reports.example.test/")

    def test_device_identity_hashes_hardware_without_exposing_raw_values(self):
        serial = "SERIAL-PRIVATE-123"
        mac = "12:34:56:78:9a:bc"
        values = {
            self.device_identity.SERIAL_PATHS[0]: serial,
            self.device_identity.MAC_PATHS[0]: mac,
        }
        old_device_id = self.device_identity.state.device_id
        self.device_identity.state.device_id = "CHI-TEST"
        try:
            with mock.patch.object(
                    self.device_identity, "_read_identity_file",
                    side_effect=lambda path: values.get(path, "")), \
                    mock.patch.dict(os.environ,
                                    {"DEVICE_NAME": "TrimUI Brick Pro"}, clear=False):
                first = self.device_identity.diagnostic_identity()
                second = self.device_identity.diagnostic_identity()
        finally:
            self.device_identity.state.device_id = old_device_id
        self.assertEqual(first, second)
        self.assertEqual(first["install_id"], "CHI-TEST")
        self.assertEqual(first["model"], "TrimUI Brick Pro")
        self.assertRegex(first["hardware_id"], r"^HW-[A-F0-9]{12}$")
        serialized = json.dumps(first)
        self.assertNotIn(serial, serialized)
        self.assertNotIn(mac, serialized)

    def test_device_identity_prefers_stable_serial_over_mac(self):
        serial = (
            "sunxi_platform : sun50iw9p1\n"
            "sunxi_secure : secure\n"
            "sunxi_chipid : 0123456789abcdef\n"
        )
        first_values = {
            self.device_identity.SERIAL_PATHS[3]: serial,
            self.device_identity.MAC_PATHS[1]: "12:34:56:78:9a:bc",
        }
        second_values = {
            self.device_identity.SERIAL_PATHS[3]: serial,
            self.device_identity.MAC_PATHS[1]: "98:76:54:32:10:fe",
        }
        with mock.patch.object(
                self.device_identity, "_read_identity_file",
                side_effect=lambda path: first_values.get(path, "")):
            first = self.device_identity.hardware_id()
        with mock.patch.object(
                self.device_identity, "_read_identity_file",
                side_effect=lambda path: second_values.get(path, "")):
            second = self.device_identity.hardware_id()
        self.assertEqual(first, second)
        self.assertRegex(first, r"^HW-[A-F0-9]{12}$")

    def test_device_identity_ignores_zero_sunxi_chipid(self):
        values = {
            self.device_identity.SERIAL_PATHS[3]: "sunxi_chipid : 0000000000000000",
            self.device_identity.MAC_PATHS[1]: "12:34:56:78:9a:bc",
        }
        with mock.patch.object(
                self.device_identity, "_read_identity_file",
                side_effect=lambda path: values.get(path, "")):
            actual = self.device_identity.hardware_id()
        expected_material = "trimui-chiaki-ng-device-v1\0mac=12:34:56:78:9a:bc"
        expected = "HW-%s" % __import__("hashlib").sha256(
            expected_material.encode("utf-8")).hexdigest()[:12].upper()
        self.assertEqual(actual, expected)

    def test_device_identity_falls_back_to_install_when_hardware_is_unavailable(self):
        old_device_id = self.device_identity.state.device_id
        self.device_identity.state.device_id = "CHI-CARD"
        try:
            with mock.patch.object(self.device_identity, "_read_identity_file",
                                   return_value=""):
                hardware_id = self.device_identity.hardware_id()
        finally:
            self.device_identity.state.device_id = old_device_id
        self.assertRegex(hardware_id, r"^APP-[A-F0-9]{12}$")

    def test_issue_identity_does_not_expose_raw_hardware_values(self):
        identity = {
            "install_id": "CHI-ABCD",
            "hardware_id": "HW-0123456789AB",
            "model": "TrimUI Brick Pro",
        }
        with mock.patch.object(self.uploader, "diagnostic_identity",
                               return_value=identity):
            body = self.uploader._issue_body(
                [("Chiaki-loi.txt", "minor failure")],
                "ota_download_failed", "a" * 64,
            )
        self.assertIn("TrimUI Brick Pro", body)
        self.assertIn("CHI-ABCD", body)
        self.assertIn("HW-0123456789AB", body)
        self.assertIn("MAC và serial thô đã được lọc", body)

    def test_pending_diagnostics_keep_multiple_distinct_reasons(self):
        with mock.patch.object(self.uploader, "start_pending_upload",
                               return_value="thread"):
            self.uploader.queue_diagnostic("ota_download_failed")
            self.uploader.queue_diagnostic("settings_save_failed")
            self.uploader.queue_diagnostic("ota_download_failed")
        self.assertEqual(
            self.uploader._pending_reasons(),
            ["ota_download_failed", "settings_save_failed"],
        )

    def test_distinct_error_reasons_are_not_deduplicated(self):
        sections = [("Chiaki-loi.txt", "same log tail")]
        posted = []

        def fake_post(_relay_url, title, _body, _fingerprint):
            posted.append(title)
            return ""

        self._pending_log()
        with mock.patch.object(self.uploader, "_collect", return_value=sections), \
                mock.patch.object(self.uploader, "_post_relay", side_effect=fake_post):
            self.uploader._remember_pending_reason("ota_download_failed")
            self.assertTrue(self.uploader.upload_pending("ota_download_failed"))
            self.uploader._remember_pending_reason("settings_save_failed")
            self.assertTrue(self.uploader.upload_pending("settings_save_failed"))
        self.assertEqual(len(posted), 2)
        self.assertIn("ota_download_failed", posted[0])
        self.assertIn("settings_save_failed", posted[1])

    def test_ssl_context_keeps_certificate_and_hostname_verification(self):
        context = self.ssl_context.create_ssl_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreater(len(context.get_ca_certs()), 0)
        self.assertTrue(os.path.isfile(self.ssl_context.CA_BUNDLE_FILE))

    def test_ssl_context_loads_bundle_when_system_store_is_empty(self):
        empty_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.assertEqual(len(empty_context.get_ca_certs()), 0)
        with mock.patch.object(self.ssl_context.ssl, "create_default_context",
                               return_value=empty_context):
            context = self.ssl_context.create_ssl_context()
        self.assertIs(context, empty_context)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreater(len(context.get_ca_certs()), 0)

    def test_updater_https_uses_shared_verified_context(self):
        context = object()

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, _size):
                return b""

        with mock.patch.object(self.updater, "create_ssl_context",
                               return_value=context), \
                mock.patch.object(self.updater.urllib.request, "urlopen",
                                  return_value=FakeResponse()) as urlopen:
            self.assertEqual(self.updater._get("https://example.com/a", 10), b"")
        self.assertIs(urlopen.call_args.kwargs["context"], context)

    def test_relay_https_uses_verified_context_without_authorization(self):
        context = object()

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, _size):
                return b'{"accepted":true}'

        with mock.patch.object(self.uploader, "create_ssl_context",
                               return_value=context), \
                mock.patch.object(self.uploader.urllib.request, "urlopen",
                                  return_value=FakeResponse()) as urlopen:
            result = self.uploader._post_relay(
                "https://reports.example.test/", "title", "body", "a" * 64)
        request = urlopen.call_args.args[0]
        self.assertEqual(result, "")
        self.assertIs(urlopen.call_args.kwargs["context"], context)
        self.assertNotIn("Authorization", request.headers)
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["fingerprint"], "a" * 64)

    def test_relay_rejects_insecure_or_credentialed_urls(self):
        for url in (
                "http://reports.example.test/",
                "https://user:secret@reports.example.test/",
                "https://reports.example.test/?token=secret"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.uploader._post_relay(url, "title", "body", "a" * 64)

    def test_relay_requires_explicit_acceptance(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, _size):
                return b'{"ok":true}'

        with mock.patch.object(self.uploader.urllib.request, "urlopen",
                               return_value=FakeResponse()), \
                self.assertRaisesRegex(ValueError, "did not accept"):
            self.uploader._post_relay(
                "https://reports.example.test/", "title", "body", "a" * 64)

    def test_manifest_tls_failures_have_distinct_status(self):
        reason = ssl.SSLCertVerificationError(
            1, "certificate verify failed: unable to get local issuer certificate")
        with mock.patch.object(self.updater, "candidate_manifest_urls",
                               return_value=["https://example.com/manifest.json"]), \
                mock.patch.object(self.updater, "_get",
                                  side_effect=urllib.error.URLError(reason)), \
                mock.patch.object(self.updater, "_report_error") as report, \
                mock.patch.object(self.updater.log, "warning") as warning:
            self.assertIsNone(self.updater.fetch_manifest())
        self.assertEqual(self.updater.last_check_status(), "tls_error")
        report.assert_called_once_with("ota_manifest_tls_error")
        warning.assert_called_once()

    def test_manifest_fallback_success_does_not_report_transient_failure(self):
        manifest = json.dumps({"version": "99.0.0", "files": []}).encode("utf-8")
        with mock.patch.object(
                self.updater, "candidate_manifest_urls",
                return_value=["https://first.invalid/manifest.json",
                              "https://second.example/manifest.json"]), \
                mock.patch.object(
                    self.updater, "_get",
                    side_effect=[urllib.error.URLError("offline"), manifest]), \
                mock.patch.object(self.updater, "_report_error") as report, \
                mock.patch.object(self.updater.log, "warning") as warning:
            result = self.updater.fetch_manifest()
        self.assertEqual(result["version"], "99.0.0")
        report.assert_not_called()
        warning.assert_not_called()

    def test_release_tools_exclude_misnamed_secrets_file(self):
        root = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root, "tools", "make_release.py"),
                  encoding="utf-8") as handle:
            make_release = handle.read()
        with open(os.path.join(root, "tools", "verify_release.py"),
                  encoding="utf-8") as handle:
            verify_release = handle.read()
        self.assertIn('"secrets..json"', make_release)
        self.assertIn('"secrets..json"', verify_release)

    def test_release_bytes_normalize_text_but_preserve_binary(self):
        root = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(root, "tools", "make_release.py")
        spec = importlib.util.spec_from_file_location("release_builder_test", path)
        release_builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(release_builder)
        text_path = os.path.join(self.work_dir, "sample.py")
        binary_path = os.path.join(self.work_dir, "sample.bin")
        with open(text_path, "wb") as handle:
            handle.write(b"first\r\nsecond\rthird\n")
        with open(binary_path, "wb") as handle:
            handle.write(b"first\r\nsecond\rthird\n")
        self.assertEqual(
            release_builder.release_bytes(text_path),
            b"first\nsecond\nthird\n",
        )
        self.assertEqual(
            release_builder.release_bytes(binary_path),
            b"first\r\nsecond\rthird\n",
        )

    def test_manual_update_check_reports_tls_failure(self):
        screen = self.home_module.HomeScreen(types.SimpleNamespace())
        with mock.patch.object(self.updater, "check_for_update", return_value=None), \
                mock.patch.object(self.updater, "last_check_status",
                                  return_value="tls_error"):
            screen._force_update_check()
        self.assertEqual(
            screen.toast,
            self.home_module.tr("update_tls_failed"),
        )

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

    def test_same_version_hash_drift_does_not_offer_update(self):
        manifest = {
            "version": self.updater.APP_VERSION,
            "files": [{"path": "app.py", "sha256": "0" * 64}],
        }
        with mock.patch.object(self.updater, "fetch_manifest",
                               return_value=manifest), \
                mock.patch.object(self.updater, "pending_files") as pending:
            self.assertIsNone(self.updater.check_for_update(force=False))
            self.assertIsNone(self.updater.check_for_update(force=True))
        pending.assert_not_called()

    def test_newer_version_still_offers_pending_files(self):
        manifest = {
            "version": "99.0.0",
            "files": [{"path": "app.py", "sha256": "0" * 64}],
        }
        expected = manifest["files"]
        with mock.patch.object(self.updater, "fetch_manifest",
                               return_value=manifest), \
                mock.patch.object(self.updater, "pending_files",
                                  return_value=expected):
            self.assertEqual(
                self.updater.check_for_update(force=True),
                (manifest, expected),
            )

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
        self.assertIn('APP_ERRLOG="$APP/Chiaki-loi.txt"', script)
        self.assertIn(': >> "$APP_ERRLOG"', script)
        self.assertIn(': > "$ERRLOG"', script)
        self.assertIn('--reason "user_exit_retry"', script)
        self.assertIn('-m rh.logger --cap-runtime', script)
        self.assertIn('grep -q "native stream preflight"', script)
        self.assertIn('if [ $IS_STREAM -eq 0 ]', script)

    def test_app_initializes_logger_before_loading_settings(self):
        app_path = os.path.join(self.app_dir, "app.py")
        with open(app_path, encoding="utf-8") as handle:
            source = handle.read()
        self.assertLess(source.index("init_logger()"),
                        source.index("from rh import state"))

    def test_app_bootstrap_error_is_written_after_logger_starts(self):
        app_path = os.path.join(self.app_dir, "app.py")
        with open(app_path, encoding="utf-8") as handle:
            source = handle.read()
        main_body = source[source.index("def main():"):]
        self.assertLess(main_body.index("init_logger()"),
                        main_body.index("from rh import state"))
        self.assertIn('log_path = os.path.join(paths.APP_DIR, "Chiaki-loi.txt")',
                      source)

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
        state = importlib.import_module("rh.state")
        original_id = state.device_id
        state.device_id = "CHI-ABCD"
        screen = home_module.HomeScreen()
        try:
            title = screen.get_header_title()
        finally:
            state.device_id = original_id
        self.assertIn(version, title)
        self.assertIn("ID: CHI-ABCD", title)
        self.assertTrue(title.startswith("CHIAKI-NG"))

    def test_header_install_id_matches_issue_identity(self):
        state = importlib.import_module("rh.state")
        original_id = state.device_id
        state.device_id = "CHI-E2E1"
        try:
            title = self.home_module.HomeScreen().get_header_title()
            identity = self.device_identity.diagnostic_identity()
        finally:
            state.device_id = original_id
        self.assertIn(identity["install_id"], title)
        self.assertEqual(identity["install_id"], "CHI-E2E1")

    def test_home_menu_opens_user_guide(self):
        engine = mock.Mock()
        screen = self.home_module.HomeScreen(engine)
        screen.selected = next(
            index for index, row in enumerate(screen.ITEMS)
            if row[0] == "guide"
        )
        screen._activate()
        engine.push_screen.assert_called_once_with("guide")

    def test_guide_has_complete_ps4_flow_and_ps5_limit(self):
        i18n = importlib.import_module("rh.i18n")
        screen = self.guide_module.GuideScreen(mock.Mock())
        self.assertEqual(len(screen.STEPS), 8)
        vietnamese = " ".join(
            i18n.TEXTS["VI"][key]
            for step in screen.STEPS for key in step
        )
        self.assertIn("đăng nhập tự động", vietnamese)
        self.assertIn("PIN 8 số", vietnamese)
        self.assertIn("START + SELECT", vietnamese)
        self.assertIn("chưa hỗ trợ ghép nối/stream PS5", vietnamese)
        self.assertIn("mã ID trên tiêu đề", vietnamese)

    def test_guide_navigation_stays_in_bounds_and_b_returns(self):
        engine = mock.Mock()
        screen = self.guide_module.GuideScreen(engine)
        screen.on_enter()
        self.assertTrue(screen.handle_input({"edges": ["btn_up"]}))
        self.assertEqual(screen.selected, 0)
        for _ in range(20):
            screen.handle_input({"edges": ["btn_a"]})
        self.assertEqual(screen.selected, len(screen.STEPS) - 1)
        self.assertTrue(screen.handle_input({"edges": ["btn_b"]}))
        engine.pop_screen.assert_called_once_with()

    def test_guide_renders_every_step_on_target_heights(self):
        class FakeEngine:
            screen_w = 1280
            font_title = object()
            font_sub = object()

            def __init__(self, screen_h):
                self.screen_h = screen_h
                self.drawn = []

            def fill_rect(self, *args, **kwargs):
                return None

            def measure_text(self, text, _font):
                return len(str(text)) * 13

            def draw_text(self, text, *args, **kwargs):
                self.drawn.append(str(text))

        screen = self.guide_module.GuideScreen()
        for height in (720, 768):
            engine = FakeEngine(height)
            for index in range(len(screen.STEPS)):
                screen.selected = index
                screen.render(engine)
            self.assertTrue(any("8 / 8" in text for text in engine.drawn))

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
                mock.patch.object(chiaki.time, "sleep", lambda *_: None), \
                mock.patch.object(chiaki, "_report_error"):
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

    def test_ps4_wakeup_packet_uses_discovery_port(self):
        chiaki = importlib.import_module("rh.chiaki")
        sent = []

        class FakeSocket:
            def bind(self, addr):
                self.bound = addr

            def getsockname(self):
                return ("0.0.0.0", getattr(self, "bound", ("", 9303))[1])

            def setsockopt(self, *args, **kwargs):
                return None

            def settimeout(self, *args, **kwargs):
                return None

            def sendto(self, data, dest):
                sent.append((data, dest))

            def close(self):
                return None

        with mock.patch.object(chiaki.socket, "socket", return_value=FakeSocket()):
            with mock.patch.object(chiaki.time, "sleep", return_value=None):
                self.assertTrue(chiaki.send_wakeup("192.168.1.45", "a49d08ed"))
        self.assertEqual(sent[0][1], ("192.168.1.45", 987))
        self.assertEqual(sent[1][1], ("255.255.255.255", 987))
        self.assertEqual(sent[2][1], ("192.168.1.45", 987))
        self.assertEqual(sent[3][1], ("255.255.255.255", 987))
        self.assertEqual(len(sent), 4)
        self.assertIn(b"WAKEUP * HTTP/1.1", sent[0][0])
        self.assertIn(b"device-discovery-protocol-version:00020020", sent[0][0])
        self.assertTrue(sent[0][0].endswith(b"\n\x00"))
        self.assertNotIn(b"\r", sent[0][0])

    def test_ps5_wakeup_remains_unicast(self):
        chiaki = importlib.import_module("rh.chiaki")
        sent = []

        class FakeSocket:
            def setsockopt(self, *args, **kwargs):
                return None

            def settimeout(self, *args, **kwargs):
                return None

            def bind(self, addr):
                return None

            def sendto(self, data, dest):
                sent.append(dest)

            def close(self):
                return None

        with mock.patch.object(chiaki.socket, "socket", return_value=FakeSocket()), \
                mock.patch.object(chiaki.time, "sleep", return_value=None):
            self.assertTrue(
                chiaki.send_wakeup("192.168.1.60", "a49d08ed", ps5=True),
            )
        self.assertEqual(sent, [("192.168.1.60", 9302)] * 2)

    def test_wakeup_diagnostic_is_queued_without_blocking(self):
        with mock.patch.object(self.uploader, "start_pending_upload", return_value="thread") as start:
            self.assertEqual(self.uploader.queue_diagnostic("wakeup_timeout"), "thread")
        self.assertTrue(os.path.exists(self.uploader.PENDING_FILE))
        start.assert_called_once_with("wakeup_timeout")

    def test_diagnostic_cannot_be_disabled_by_legacy_setting(self):
        original = self.uploader.state.auto_upload_logs
        try:
            self.uploader.state.auto_upload_logs = False
            with mock.patch.object(self.uploader, "start_pending_upload", return_value="thread") as start:
                self.assertEqual(self.uploader.queue_diagnostic("pair_ps5_failed"), "thread")
            self.assertTrue(os.path.exists(self.uploader.PENDING_FILE))
            start.assert_called_once_with("pair_ps5_failed")
        finally:
            self.uploader.state.auto_upload_logs = original

    def test_wakeup_report_is_described_as_diagnostic(self):
        body = self.uploader._issue_body(
            [("Chiaki-debug.log", "wakeup timeout: attempts=6")],
            "wakeup_timeout", "a" * 64,
        )
        self.assertIn("chẩn đoán đánh thức", body)
        self.assertNotIn("sau khi ứng dụng lỗi", body)

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

    def test_ps5_registration_limit_is_reported(self):
        chiaki = importlib.import_module("rh.chiaki")
        host = chiaki.DiscoveredHost(
            name="PS5", addr="192.168.1.60", is_ps5=True, target=1000100,
        )
        with mock.patch.object(chiaki, "_report_error") as report:
            ok, result = chiaki.regist_with_pin(host, "12345678")
        self.assertFalse(ok)
        self.assertIn("da xep hang gui chan doan len GitHub", result["error"])
        report.assert_called_once_with("pair_ps5_registration_unavailable")

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
                    "CHIAKI_DEVICE_MODEL": "sun50iw10",
                }, clear=False):
            ok, _ = chiaki.prepare_stream_launch(host)
        self.assertTrue(ok)
        with open(launcher_path, encoding="utf-8") as handle:
            script = handle.read()
        self.assertNotIn(regist_key, script)
        self.assertNotIn(rp_key, script)
        self.assertIn("native runtime: brick-stock", script)
        self.assertIn("LD_LIBRARY_PATH=", script)
        self.assertIn(os.path.join("libs", "brick-stock"), script)
        self.assertIn('${LD_LIBRARY_PATH%:}:$RUNTIME', script)
        self.assertIn(
            'OPENSSL_PRELOAD="$RUNTIME/libcrypto.so.1.1:$RUNTIME/libssl.so.1.1',
            script,
        )
        self.assertIn('LD_PRELOAD="${OPENSSL_PRELOAD:+', script)
        self.assertNotIn("export LD_PRELOAD", script)
        self.assertIn("native OpenSSL: bundled 1.1.1", script)
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

    def test_brick_stock_uses_isolated_native_runtime(self):
        chiaki = importlib.import_module("rh.chiaki")
        runtime_dir = os.path.join(self.app_dir, "libs", "brick-stock")
        os.makedirs(runtime_dir, exist_ok=True)
        name, path = chiaki._native_runtime(self.app_dir, "sun50iw10")
        self.assertEqual(name, "brick-stock")
        self.assertEqual(path, runtime_dir)

    def test_spruce_keeps_system_native_runtime(self):
        chiaki = importlib.import_module("rh.chiaki")
        runtime_dir = os.path.join(self.app_dir, "libs", "brick-stock")
        os.makedirs(runtime_dir, exist_ok=True)
        name, path = chiaki._native_runtime(self.app_dir, "sun55iw3")
        self.assertEqual(name, "system")
        self.assertEqual(path, "")
        self.assertEqual(chiaki._native_preload_prefix(path), "")

    def test_brick_preloads_only_bundled_openssl(self):
        chiaki = importlib.import_module("rh.chiaki")
        prefix = chiaki._native_preload_prefix("/app/libs/brick-stock")
        self.assertIn("OPENSSL_PRELOAD", prefix)
        self.assertIn("LD_PRELOAD", prefix)
        self.assertTrue(prefix.endswith(" "))

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

    def test_saved_paired_host_remains_visible_when_discovery_is_empty(self):
        chiaki = importlib.import_module("rh.chiaki")
        paired_path = os.path.join(self.app_dir, "paired_hosts.json")
        with open(paired_path, "w", encoding="utf-8") as handle:
            json.dump([{
                "addr": "192.168.1.45",
                "name": "PS4-896",
                "is_ps5": False,
                "target": 900,
                "regist_key": "a49d08ed",
                "rp_key": base64.b64encode(bytes(range(16))).decode("ascii"),
            }], handle)
        try:
            hosts = chiaki.paired_hosts_for_discovery([])
        finally:
            os.remove(paired_path)
        self.assertEqual(len(hosts), 1)
        self.assertEqual(hosts[0].addr, "192.168.1.45")
        self.assertEqual(hosts[0].state, "offline")
        self.assertFalse(hasattr(hosts[0], "regist_key"))

    def test_discovered_host_wins_over_saved_offline_host(self):
        chiaki = importlib.import_module("rh.chiaki")
        paired_path = os.path.join(self.app_dir, "paired_hosts.json")
        with open(paired_path, "w", encoding="utf-8") as handle:
            json.dump([{
                "addr": "192.168.1.45",
                "name": "PS4-896",
                "is_ps5": False,
                "target": 900,
                "regist_key": "a49d08ed",
                "rp_key": base64.b64encode(bytes(range(16))).decode("ascii"),
            }], handle)
        ready = chiaki.DiscoveredHost(
            name="PS4-896", addr="192.168.1.45", state="ready", target=900,
        )
        try:
            hosts = chiaki.paired_hosts_for_discovery([ready])
        finally:
            os.remove(paired_path)
        self.assertEqual(hosts, [ready])

    def test_wake_paired_host_uses_saved_credential(self):
        chiaki = importlib.import_module("rh.chiaki")
        paired_path = os.path.join(self.app_dir, "paired_hosts.json")
        regist_key = "a49d08ed"
        with open(paired_path, "w", encoding="utf-8") as handle:
            json.dump([{
                "addr": "192.168.1.45",
                "name": "PS4-896",
                "is_ps5": False,
                "target": 900,
                "regist_key": regist_key,
                "rp_key": base64.b64encode(bytes(range(16))).decode("ascii"),
            }], handle)
        host = chiaki.DiscoveredHost(
            name="PS4-896", addr="192.168.1.45", state="offline", target=900,
        )
        try:
            with mock.patch.object(chiaki, "send_wakeup", return_value=True) as wake:
                self.assertTrue(chiaki.wake_paired_host(host))
        finally:
            os.remove(paired_path)
        wake.assert_called_once_with("192.168.1.45", regist_key, False)

    def test_home_scan_does_not_show_saved_offline_host(self):
        chiaki = importlib.import_module("rh.chiaki")
        home = importlib.import_module("rh.screens.home")
        i18n = importlib.import_module("rh.i18n")
        screen = home.HomeScreen(mock.Mock())
        with mock.patch.object(chiaki, "discovery_broadcast", return_value=[]), \
                mock.patch.object(chiaki, "paired_hosts_for_discovery") as merge:
            screen._do_scan()
        self.assertEqual(screen.hosts, [])
        self.assertEqual(screen.toast, i18n.TEXTS["VI"]["scan_none"])
        merge.assert_not_called()

    def test_home_ready_host_starts_stream_without_wakeup(self):
        chiaki = importlib.import_module("rh.chiaki")
        home = importlib.import_module("rh.screens.home")
        engine = mock.Mock()
        screen = home.HomeScreen(engine)
        host = chiaki.DiscoveredHost(
            name="PS4-896", addr="192.168.1.45", state="ready", target=900,
        )
        with mock.patch.object(screen, "_is_paired", return_value=True), \
                mock.patch.object(
                    chiaki, "prepare_stream_launch", return_value=(True, "ok"),
                ) as prepare:
            screen._start_stream(host)
        prepare.assert_called_once_with(host)
        engine.quit.assert_called_once_with("stream_launch")

    def test_legacy_1080p_profile_is_capped_at_720p(self):
        chiaki = importlib.import_module("rh.chiaki")
        state = importlib.import_module("rh.state")
        old_resolution = state.video_resolution
        try:
            state.video_resolution = "1080p"
            profile = chiaki._video_profile_from_state()
        finally:
            state.video_resolution = old_resolution
        self.assertEqual(profile["width"], 1280)
        self.assertEqual(profile["height"], 720)

    def test_settings_cap_resolution_at_720p_and_offer_low_bitrate(self):
        screen = self.settings_module.SettingsScreen.__new__(
            self.settings_module.SettingsScreen)
        screen.__init__()
        rows = {key: values for key, values, _ in screen.rows if values}
        self.assertEqual(rows["video_resolution"], ["360p", "540p", "720p"])
        self.assertIn(3000, rows["video_bitrate"])

    def test_settings_load_normalizes_legacy_1080p_to_720p(self):
        state = importlib.import_module("rh.state")
        original_path = state.SETTINGS_FILE
        original_resolution = state.video_resolution
        original_auto_upload = state.auto_upload_logs
        legacy_path = os.path.join(self.work_dir, "legacy-settings.json")
        with open(legacy_path, "w", encoding="utf-8") as handle:
            json.dump({"video_resolution": "1080p", "auto_upload_logs": False}, handle)
        try:
            state.SETTINGS_FILE = legacy_path
            state._load()
            self.assertEqual(state.video_resolution, "720p")
            self.assertTrue(state.auto_upload_logs)
        finally:
            state.SETTINGS_FILE = original_path
            state.video_resolution = original_resolution
            state.auto_upload_logs = original_auto_upload


if __name__ == "__main__":
    unittest.main()

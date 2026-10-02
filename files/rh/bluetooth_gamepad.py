# -*- coding: utf-8 -*-
"""Manage the Brick Pro Bluetooth HID backend without blocking the SDL UI."""

import os
import shutil
import subprocess
import tempfile
import threading

from .logger import get_logger
from .paths import APP_DIR

log = get_logger()

BACKEND = os.path.join(APP_DIR, "bin", "brick-pro-bt")
SESSION_SCRIPT = os.path.join(APP_DIR, "bluetooth-session.sh")
REPORT_FILE = os.path.join(APP_DIR, "BrickBluetooth.log")
MAP_FILE = os.path.join(APP_DIR, "bluetooth-map.json")

# The report is on the SD card and grows by a few kilobytes per session. Rotate
# instead of letting it fill the card.
REPORT_LIMIT = 512 * 1024


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read(256).strip()
    except OSError:
        return ""


def _rotate_report():
    try:
        if os.path.getsize(REPORT_FILE) <= REPORT_LIMIT:
            return
    except OSError:
        return
    try:
        os.replace(REPORT_FILE, REPORT_FILE + ".1")
        log.info("BrickBluetooth.log da dat nguong, xoa ban .1")
    except OSError as exc:
        log.warning("khong xoay vong log: %s", exc)


def _append_report(text):
    try:
        with open(REPORT_FILE, "a", encoding="utf-8") as handle:
            handle.write(text)
    except OSError as exc:
        log.warning("khong ghi BrickBluetooth.log: %s", exc)


def map_present():
    return os.path.isfile(MAP_FILE)


class BluetoothGamepadSession:
    def __init__(self):
        self.process = None
        self.run_dir = ""
        self.check_result = ""
        self.check_detail = ""
        self.checking = False
        self.last_exit_code = None
        # The launcher shell exits 143 when it is asked to stop, which is a
        # normal outcome rather than a backend failure.
        self.stop_requested = False
        self._check_thread = None

    @property
    def status_file(self):
        return os.path.join(self.run_dir, "status") if self.run_dir else ""

    @property
    def result_file(self):
        return os.path.join(self.run_dir, "result") if self.run_dir else ""

    def available(self):
        return os.path.isfile(BACKEND) and os.path.isfile(SESSION_SCRIPT)

    def running(self):
        return self.process is not None and self.process.poll() is None

    def status(self):
        if self.running():
            return _read_text(self.status_file) or "starting"
        result = _read_text(self.result_file)
        if result:
            return result
        if self.last_exit_code in (None, 0):
            return "idle"
        if self.stop_requested and self.last_exit_code in (143, 130):
            # stop() terminates the launcher shell, so 143/130 is the expected
            # exit here and not something the user has to act on.
            return "stopped"
        return "backend_error_%d" % self.last_exit_code

    def start_check(self):
        if self.checking or self.running():
            return False
        self.checking = True
        self.check_result = ""
        self.check_detail = ""
        self._check_thread = threading.Thread(target=self._run_check, daemon=True)
        self._check_thread.start()
        return True

    def _run_check(self):
        result_path = ""
        try:
            if not self.available():
                self.check_result = "BACKEND_MISSING"
                return
            file_handle, result_path = tempfile.mkstemp(prefix="chiaki-bt-check-")
            os.close(file_handle)
            os.unlink(result_path)
            completed = subprocess.run(
                [BACKEND, "--check", "--result", result_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=18,
                check=False,
            )
            self.check_detail = (completed.stdout or "")[-4000:]
            self.check_result = _read_text(result_path) or "CHECK_ERROR"
            _append_report("\n=== Bluetooth preflight ===\n"
                           + (self.check_detail or "")
                           + "\nresult=%s\n" % self.check_result)
            log.info("bluetooth preflight=%s exit=%s", self.check_result,
                     completed.returncode)
        except subprocess.TimeoutExpired:
            self.check_result = "CHECK_TIMEOUT"
            log.warning("bluetooth preflight timed out")
        except OSError as exc:
            self.check_result = "CHECK_ERROR"
            self.check_detail = str(exc)
            log.warning("bluetooth preflight failed: %s", exc)
        finally:
            self.checking = False
            if result_path:
                try:
                    os.unlink(result_path)
                except OSError:
                    pass

    def start(self):
        if self.checking or self.running() or not self.available():
            return False
        self.cleanup_runtime()
        _rotate_report()
        self.run_dir = tempfile.mkdtemp(prefix="chiaki-brick-pro-bt-", dir="/tmp")
        self.last_exit_code = None
        self.stop_requested = False
        environment = os.environ.copy()
        environment["CHIAKI_PARENT_PID"] = str(os.getpid())
        try:
            self.process = subprocess.Popen(
                ["/bin/sh", SESSION_SCRIPT, self.run_dir],
                cwd=APP_DIR,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                env=environment,
            )
        except OSError as exc:
            log.error("cannot start Bluetooth supervisor: %s", exc)
            self.process = None
            self.last_exit_code = 127
            return False
        log.info("Bluetooth gamepad supervisor started pid=%s map=%s",
                self.process.pid, "custom" if map_present() else "built-in")
        return True

    def poll(self):
        if self.process is None:
            return self.last_exit_code
        code = self.process.poll()
        if code is not None:
            self.last_exit_code = code
            log.info("Bluetooth gamepad supervisor exited code=%s result=%s",
                     code, _read_text(self.result_file))
            self.process = None
        return code

    def stop(self):
        process = self.process
        if process is None:
            return
        self.stop_requested = True
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        self.last_exit_code = process.returncode
        self.process = None
        log.info("Bluetooth gamepad supervisor stopped code=%s", self.last_exit_code)

    def cleanup_runtime(self):
        if self.running() or not self.run_dir:
            return
        shutil.rmtree(self.run_dir, ignore_errors=True)
        self.run_dir = ""

    def close(self):
        self.stop()
        self.cleanup_runtime()

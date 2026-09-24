# -*- coding: utf-8 -*-
"""Privacy-preserving device identity for diagnostics."""

import hashlib
import os
import platform
import re

from . import state


MODEL_PATHS = (
    "/sys/firmware/devicetree/base/model",
    "/proc/device-tree/model",
    "/sys/devices/soc0/machine",
)
SERIAL_PATHS = (
    "/sys/firmware/devicetree/base/serial-number",
    "/proc/device-tree/serial-number",
    "/sys/devices/soc0/serial_number",
    "/sys/class/sunxi_info/sys_info",
    "/sys/class/dmi/id/product_uuid",
)
MAC_PATHS = (
    "/sys/class/net/wlan0/perm_address",
    "/sys/class/net/wlan0/address",
    "/sys/class/net/wlan1/perm_address",
    "/sys/class/net/wlan1/address",
)
MACHINE_ID_PATHS = (
    "/etc/machine-id",
    "/var/lib/dbus/machine-id",
)


def _read_identity_file(path):
    try:
        with open(path, "rb") as handle:
            value = handle.read(512).replace(b"\x00", b"").decode(
                "utf-8", errors="replace")
        return value.strip()
    except OSError:
        return ""


def _safe_label(value, fallback="Unknown TrimUI"):
    value = re.sub(r"[^A-Za-z0-9 ._()+/-]+", " ", str(value or ""))
    value = " ".join(value.split())[:80]
    return value or fallback


def device_model():
    for name in ("CHIAKI_DEVICE_MODEL", "DEVICE_NAME"):
        value = os.environ.get(name, "")
        if value.strip():
            return _safe_label(value)
    for path in MODEL_PATHS:
        value = _read_identity_file(path)
        if value:
            return _safe_label(value)
    return _safe_label(platform.machine())


def install_id():
    return _safe_label(getattr(state, "device_id", ""), "CHI-UNKNOWN")


def _first_identity(paths, invalid_values=()):
    invalid = {str(value).lower() for value in invalid_values}
    for path in paths:
        value = _read_identity_file(path).strip().lower()
        if path == "/sys/class/sunxi_info/sys_info":
            match = re.search(r"(?im)^\s*sunxi_chipid\s*:\s*([0-9a-f]+)\s*$", value)
            value = match.group(1) if match else ""
        compact = re.sub(r"[^a-z0-9]", "", value)
        if value and value not in invalid and compact and set(compact) != {"0"}:
            return value
    return ""


def hardware_id():
    identity = _first_identity(SERIAL_PATHS)
    kind = "serial"
    if not identity:
        identity = _first_identity(
            MAC_PATHS,
            ("00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"),
        )
        kind = "mac"
    if not identity:
        identity = _first_identity(MACHINE_ID_PATHS)
        kind = "machine"
    if identity:
        material = "trimui-chiaki-ng-device-v1\0%s=%s" % (kind, identity)
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
        return "HW-%s" % digest.upper()
    fallback = "%s\0%s" % (install_id(), platform.machine())
    digest = hashlib.sha256(fallback.encode("utf-8")).hexdigest()[:12]
    return "APP-%s" % digest.upper()


def diagnostic_identity():
    return {
        "install_id": install_id(),
        "hardware_id": hardware_id(),
        "model": device_model(),
    }

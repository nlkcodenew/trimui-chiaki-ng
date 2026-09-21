# -*- coding: utf-8 -*-
"""LAN Remote Play registration for PS4 firmware 8.0 and newer."""

import base64
import hashlib
import hmac
import os
import shutil
import socket
import subprocess
import time


REGIST_PORT = 9295
INNER_HEADER_OFFSET = 0x1E0
HMAC_KEY_PS4 = bytes.fromhex("20d66f5904ea7c14e557ffc52e488ac8")
CLIENT_TYPE = "dabfa2ec873de5839bee8d3f4c0239c4282c07c25c6077a2931afcf0adc0d34f"

PS4_KEYS_1 = bytes.fromhex(
    "c848c2b408eb88f75f4a092d591f09cd1c18f47a284a966db3597153757e8250"
    "57e459b3f4496940eb17c99f179771aec9607ff82e0894e843eada6be5195933"
    "1f89ae47577b1c66feff95bf556bd59327eaa62467399fd30caa2642e7664dd8"
    "1875fe440346ee3ef83cb7859703070692ff5917270b21f7057f69900e3891c6"
    "672348ba088e57dd91d040471c5bbfc8063f96a0dc00e59af53b908066bb0f93"
    "30072b5645a09ab1b0720ce4dd70dd7c5abfd4e80dca37e50efd12ee799a5ea7"
    "1e31af1f4652caf342003df2897c1c7760b74a8076474b3fb6912f9cc2f1ad44"
    "29cb328c0a8d057546a1f8da1aa720de3259fe70b587f392fdb4dff4a6e37d98"
    "3be1ba18db61d1c2a6ee0825fa868a7bfebc02bd225f2530515d28365a298e52"
    "eb4914287f0ac46925856bec333357ab5013cfe7737823064d1fbb3811b16e6c"
    "6fcd4b0e428580bba83968c95bbb4658868857885eea7c37dffd023945892ef2"
    "e4f008c0b6eb9c6e7a81a32646fee1703c3e117a32ce45027d32cd080706a3a8"
    "f734feee06b014d66b2d2e01af7711ec1f3138179cd0e0c54da4d6adb9e6e1e"
    "3e29e44919a5e26caccda4dd7786a75a619adcc62c7b60d14b1beebcb10cfa9"
    "eee24208358a5cbcf149fe647803490c85f0e47726d25ef5c13b3d2dcccf2aac"
    "ed8852746dbfb2b9f758511c50f63df2c4470a213047812de4750d8f2d22b06327"
)

PS4_KEYS_0 = bytes.fromhex(
    "bece5df0c17db5d0cb30135daa5623fbc4bcf18f3857fbd4d43f2638b5ceed6a"
    "21bc38d01e68cc7b45d1be421a08aa16fdb0c0f4da35e912fd21074834c1fc9f"
    "8cb6cb5db29c84e01afaa0c7eb3a93b3b3f115af13bd21abea5b80506b311d7"
    "c1d40ba3c560ee7943a5ba14080740aad28cf47df42a669e95ebbc0c00eb2c58"
    "aee0803d284e591001d460655099d399fd8e7fdad9e9397c5eae7a310a7f2a29"
    "37f0704b4eebbbf88239c6ea762b14b671eb83b1f64935a99ecdafd0c6ab7fee"
    "412763265b84123d117099c242d5c9d1279dea1ce69aca4bc392f573884612d2a"
    "e804f8d59d0bff7e560cec870a1eabdf938113eecf32025abfb017b7bab57ff0"
    "017be1cb397e606da4756e299245a64f7400867873befd3ee0d10c6c0b490983"
    "6c858a1dcb16ce817c49c92c6361dee23f98b273f09aec7b7cf1c9e17fa5198"
    "b4be838a4347df428fe0d4d11570c95f1afd73480f4eb9b50e66a5deace0c854"
    "ec55b9344c4249880fcf7729c310bee8967b3a2694fb3795a140270ed50137500"
    "6af3c6051a003334f5ac9e04dbc200b01bc4f3979d7fbeb8238d99e7cb74374c"
    "57ecd26949467574af5140a4117bb32f51dae2ef3373121825390309ca49dc8ef"
    "194d780179e8746c10478d1e53d2588ec723a284168146e10e4c9577590fe221"
    "a638ef4b88d1a36fdb6cb72c297529f91721b7557903bfd5a938cdbfca303df"
)


class RegistError(Exception):
    pass


def _openssl_path():
    candidates = (
        "/usr/bin/openssl",
        "/usr/local/bin/openssl",
        shutil.which("openssl"),
        r"C:\Program Files\Git\mingw64\bin\openssl.exe",
        r"C:\Program Files\Git\usr\bin\openssl.exe",
    )
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    raise RegistError("OpenSSL not found")


def _iv(ambassador, counter=0):
    message = ambassador + int(counter).to_bytes(8, "big")
    return hmac.new(HMAC_KEY_PS4, message, hashlib.sha256).digest()[:16]


def _aes_cfb(data, key, ambassador, decrypt=False):
    command = [
        _openssl_path(), "enc", "-aes-128-cfb", "-K", key.hex(),
        "-iv", _iv(ambassador).hex(), "-nopad",
    ]
    if decrypt:
        command.append("-d")
    try:
        result = subprocess.run(
            command, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RegistError("cannot run OpenSSL: %s" % exc) from exc
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="ignore").strip()
        raise RegistError("OpenSSL failed: %s" % (message or result.returncode))
    if len(result.stdout) != len(data):
        raise RegistError("OpenSSL returned an invalid size")
    return result.stdout


def decode_account_id(value):
    text = str(value or "").strip()
    if not text or text.startswith("stub-rp-key-"):
        return b"\0" * 8, True
    try:
        decoded = base64.b64decode(text, validate=True)
    except (ValueError, TypeError):
        decoded = b""
    if len(decoded) != 8:
        raise RegistError("PSN Account-ID must be base64 for exactly 8 bytes")
    return decoded, False


def _build_payload(pin, account_id, ambassador=None):
    ambassador = ambassador or os.urandom(16)
    payload = bytearray(b"A" * INNER_HEADER_OFFSET)
    key_0_offset = payload[0x18D] & 0x1F
    key_1_offset = payload[0] >> 3
    bright = bytearray(PS4_KEYS_0[index * 0x20 + key_0_offset] for index in range(16))
    pin_bytes = int(pin).to_bytes(4, "big")
    for index in range(4):
        bright[12 + index] ^= pin_bytes[index]
    aeropause = bytes(
        ((ambassador[index] ^ PS4_KEYS_1[index * 0x20 + key_1_offset]) + 0x29 + index) & 0xFF
        for index in range(16)
    )
    payload[0xC7:0xCF] = aeropause[8:]
    payload[0x191:0x199] = aeropause[:8]
    account_id_b64 = base64.b64encode(account_id).decode("ascii")
    inner = (
        "Client-Type: %s\r\nNp-AccountId: %s\r\n" %
        (CLIENT_TYPE, account_id_b64)
    ).encode("ascii")
    payload.extend(_aes_cfb(inner, bytes(bright), ambassador))
    return bytes(payload), bytes(bright), ambassador


def _search(host, timeout):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as search_socket:
        search_socket.settimeout(timeout)
        search_socket.connect((host, REGIST_PORT))
        search_socket.send(b"SRC2\0")
        response, address = search_socket.recvfrom(256)
    if not response.startswith(b"RES2"):
        raise RegistError("invalid PS4 registration search response")
    return address


def _parse_headers(data):
    text = data.decode("latin-1", errors="replace").replace("\r\n", "\n")
    lines = text.split("\n")
    headers = {"_status": lines[0].strip() if lines else ""}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def _recv_http(connection, timeout):
    connection.settimeout(timeout)
    data = bytearray()
    header_end = -1
    content_length = None
    while len(data) < 65536:
        chunk = connection.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if header_end < 0:
            header_end = data.find(b"\r\n\r\n")
            if header_end >= 0:
                header_end += 4
                headers = _parse_headers(bytes(data[:header_end]))
                try:
                    content_length = int(headers.get("content-length", "0"))
                except ValueError as exc:
                    raise RegistError("invalid Content-Length from PS4") from exc
        if header_end >= 0 and content_length is not None:
            if len(data) >= header_end + content_length:
                break
    if header_end < 0:
        raise RegistError("incomplete HTTP header from PS4")
    if content_length is None:
        raise RegistError("missing Content-Length from PS4")
    if len(data) < header_end + content_length:
        raise RegistError("incomplete PS4 response body")
    return bytes(data[:header_end]), bytes(data[header_end:header_end + content_length])


def _parse_result(payload):
    headers = _parse_headers(payload)
    required = ("ps4-registkey", "rp-key", "ps4-mac")
    missing = [key for key in required if not headers.get(key)]
    if missing:
        raise RegistError("response missing %s" % ", ".join(missing))
    try:
        regist_raw = bytes.fromhex(headers["ps4-registkey"])
        rp_key = bytes.fromhex(headers["rp-key"])
        server_mac = bytes.fromhex(headers["ps4-mac"])
        rp_key_type = int(headers.get("rp-keytype", "0"), 0)
    except (ValueError, TypeError) as exc:
        raise RegistError("invalid key in PS4 response") from exc
    regist_key = regist_raw.rstrip(b"\0").decode("ascii", errors="strict")
    if not regist_key or len(regist_key) > 8:
        raise RegistError("invalid PS4-RegistKey")
    if any(c not in "0123456789abcdefABCDEF" for c in regist_key):
        raise RegistError("invalid PS4-RegistKey")
    if len(rp_key) != 16 or len(server_mac) != 6:
        raise RegistError("invalid RP-Key or PS4-Mac size")
    return {
        "regist_key": regist_key,
        "rp_key": base64.b64encode(rp_key).decode("ascii"),
        "rp_key_type": rp_key_type,
        "server_mac": server_mac.hex(),
        "name": headers.get("ps4-nickname", ""),
    }


def register(host, pin, account_id_b64="", timeout=10.0):
    account_id, used_offline_default = decode_account_id(account_id_b64)
    payload, bright, ambassador = _build_payload(pin, account_id)
    address = _search(host, min(timeout, 3.0))
    time.sleep(0.1)
    request = (
        "POST /sie/ps4/rp/sess/rgst HTTP/1.1\r\n HTTP/1.1\r\n"
        "HOST: 10.0.2.15\r\n"
        "User-Agent: remoteplay Windows\r\n"
        "Connection: close\r\n"
        "Content-Length: %d\r\n"
        "RP-Version: 10.0\r\n\r\n" % len(payload)
    ).encode("ascii")
    try:
        with socket.create_connection(address, timeout=min(timeout, 3.0)) as connection:
            connection.sendall(request)
            connection.sendall(payload)
            response_header, response_payload = _recv_http(connection, min(timeout, 3.0))
    except socket.timeout as exc:
        raise RegistError("timed out waiting for PS4") from exc
    except OSError as exc:
        raise RegistError("registration network error: %s" % exc) from exc
    response_headers = _parse_headers(response_header)
    status = response_headers.get("_status", "")
    status_parts = status.split()
    code = status_parts[1] if len(status_parts) > 1 else "?"
    if code != "200":
        reason = response_headers.get("rp-application-reason", "")
        detail = "HTTP %s" % code
        if reason:
            detail += ", reason %s" % reason
        if used_offline_default:
            detail += "; offline Account-ID may be required"
        raise RegistError(detail)
    if not response_payload:
        raise RegistError("empty registration response from PS4")
    decrypted = _aes_cfb(response_payload, bright, ambassador, decrypt=True)
    result = _parse_result(decrypted)
    result["used_offline_account"] = used_offline_default
    return result

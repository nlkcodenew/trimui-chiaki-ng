# -*- coding: utf-8 -*-
"""Phien ban cua app. Tool release doc file nay de dat ten tag va manifest."""

APP_VERSION = "0.4.0-beta1"


def _normalize_version(v):
    s = str(v or APP_VERSION).strip().lstrip("vV")
    # Tach suffix prerelease nhu -alpha, -beta
    suffix = ""
    if "-" in s:
        s, suffix = s.split("-", 1)
        suffix = "-" + suffix
    parts = []
    for chunk in s.split("."):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            parts.append(int(chunk))
        except ValueError:
            # Chuoi la nhu 0-alpha thi bo qua
            nums = "".join(c for c in chunk if c.isdigit())
            parts.append(int(nums) if nums else 0)
    return tuple(parts), suffix


def version_tuple(v=None):
    base, _ = _normalize_version(v)
    return base if base else (0,)


def is_newer(remote, local=None):
    rb, rs = _normalize_version(remote)
    lb, ls = _normalize_version(local)
    if rb != lb:
        return rb > lb
    # 0.3.0 > 0.3.0-alpha ; alpha < release
    if rs == ls:
        return False
    if not rs and ls:
        return True
    if rs and not ls:
        return False
    return rs > ls

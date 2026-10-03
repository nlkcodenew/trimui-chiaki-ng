# -*- coding: utf-8 -*-
"""Phien ban cua app. Tool release doc file nay de dat ten tag va manifest."""

APP_VERSION = "0.3.32-beta1"


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
    return tuple(parts), _suffix_key(suffix)


def _suffix_key(suffix):
    """Khoa so sanh hau to prerelease, hieu so cuoi nhu beta10 > beta9.

    Ban release (suffix rong) luon moi hon prerelease cung base. So cuoi
    duoc so sanh dang so, khong phai dang chuoi, vi "beta10" > "beta9".
    """
    if not suffix:
        return (1,)
    body = suffix[1:]
    prefix = "".join(c for c in body if not c.isdigit())
    digits = "".join(c for c in body if c.isdigit())
    return (0, prefix, int(digits) if digits else -1)


def version_tuple(v=None):
    base, _ = _normalize_version(v)
    return base if base else (0,)


def is_newer(remote, local=None):
    rb, rs = _normalize_version(remote)
    lb, ls = _normalize_version(local)
    if rb != lb:
        return rb > lb
    # 0.3.0 > 0.3.0-alpha ; alpha < release ; beta10 > beta9.
    return rs > ls

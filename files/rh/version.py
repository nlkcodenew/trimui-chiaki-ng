# -*- coding: utf-8 -*-
"""Phien ban cua app. Tool release doc file nay de dat ten tag va manifest."""

APP_VERSION = "0.2.5"


def version_tuple(v=None):
    try:
        return tuple(int(p) for p in str(v or APP_VERSION).strip().lstrip("v").split("."))
    except (TypeError, ValueError):
        return (0,)


def is_newer(remote, local=None):
    return version_tuple(remote) > version_tuple(local)

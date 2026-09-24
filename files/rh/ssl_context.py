# -*- coding: utf-8 -*-
"""Create verified TLS contexts for all application HTTPS clients."""

import os
import ssl

from .paths import APP_DIR


CA_BUNDLE_FILE = os.path.join(APP_DIR, "certs", "cacert.pem")


def create_ssl_context():
    """Keep system trust roots and add the CA bundle shipped with the app."""
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=CA_BUNDLE_FILE)
    return context

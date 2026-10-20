"""Fixtures. Live tests run against a real HyperHDR when HYPERHDR_HOST is set."""

from __future__ import annotations

import os

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]

LIVE_HOST = os.environ.get("HYPERHDR_HOST")
LIVE_PORT = int(os.environ.get("HYPERHDR_PORT", "8090"))
LIVE_PASSWORD = os.environ.get("HYPERHDR_PASSWORD", "hyperhdr")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Loads custom_components/ in every test."""
    return


live = pytest.mark.skipif(LIVE_HOST is None, reason="HYPERHDR_HOST is not set")

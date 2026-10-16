"""Skutečný HA plugin, ne náhrada homeassistant modulu testovacími stuby."""

import pytest


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield

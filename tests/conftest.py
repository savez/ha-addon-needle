"""Fixture comuni per i test dell'integrazione."""
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Abilita le integrazioni custom in tutti i test."""
    return

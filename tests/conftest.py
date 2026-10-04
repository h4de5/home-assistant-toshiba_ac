"""Shared Home Assistant stubs.

The integration imports Home Assistant at module load, but Home Assistant is
not installed in the test venv. All test modules therefore need the same stubs,
and they have to exist before the first import of the integration. pytest loads
this file first, so the stubs are installed here exactly once.
"""
import sys
from unittest.mock import MagicMock


class ConfigEntryNotReady(Exception):
    """Stub for homeassistant.exceptions.ConfigEntryNotReady."""


class ConfigEntryAuthFailed(Exception):
    """Stub for homeassistant.exceptions.ConfigEntryAuthFailed."""


class ConfigEntryError(Exception):
    """Stub for homeassistant.exceptions.ConfigEntryError."""


class HomeAssistantError(Exception):
    """Stub for homeassistant.exceptions.HomeAssistantError."""


def _install() -> None:
    ha_mock = MagicMock()
    ha_mock.ConfigEntry = MagicMock
    ha_mock.HomeAssistant = MagicMock
    ha_mock.ServiceCall = MagicMock
    ha_mock.ConfigEntryNotReady = ConfigEntryNotReady
    ha_mock.ConfigEntryAuthFailed = ConfigEntryAuthFailed
    ha_mock.ConfigEntryError = ConfigEntryError
    ha_mock.HomeAssistantError = HomeAssistantError

    # persistent_notification.async_create and async_dismiss are @callback
    # functions, i.e. synchronous. The mocks must stay synchronous as well:
    # awaiting a MagicMock raises TypeError, exactly as in production. Using
    # AsyncMock here would hide that mistake.
    notification_mock = MagicMock()

    components_mock = MagicMock()
    components_mock.persistent_notification = notification_mock

    sys.modules["homeassistant"] = ha_mock
    sys.modules["homeassistant.config_entries"] = ha_mock
    sys.modules["homeassistant.core"] = ha_mock
    sys.modules["homeassistant.exceptions"] = ha_mock
    sys.modules["homeassistant.components"] = components_mock
    sys.modules["homeassistant.components.persistent_notification"] = notification_mock
    sys.modules["homeassistant.components.climate"] = MagicMock()
    sys.modules["homeassistant.const"] = MagicMock()


_install()


def persistent_notification_mock() -> MagicMock:
    """Return the stub used for homeassistant.components.persistent_notification."""
    return sys.modules["homeassistant.components.persistent_notification"]
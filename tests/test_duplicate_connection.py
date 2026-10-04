"""Tests for the duplicate-connection message.

Two Home Assistant instances on one Toshiba account make IoT Hub refuse the
connection. The library reports that as "Credentials invalid, could not
connect", which reads like a wrong password. These tests pin the translation.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from azure.iot.device.common.transport_exceptions import (
    ConnectionDroppedError,
    UnauthorizedError,
)
from azure.iot.device.exceptions import CredentialError
from conftest import persistent_notification_mock
import pytest

from custom_components.toshiba_ac import (  # noqa: E402
    NOTIFICATION_ID,
    ONE_CONNECTION_HINT,
    async_setup_entry,
)
from homeassistant.exceptions import (  # noqa: E402
    ConfigEntryNotReady,
    HomeAssistantError,
)

VALID_TOKEN = "SharedAccessSignature sr=hub%2Fdevices%2Fu&sig=abc&se=9999999999"


def create_mock_entry(sas_token=VALID_TOKEN):
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    entry.data = {
        "username": "test@example.com",
        "password": "testpass",
        "device_id": "device123",
        "sas_token": sas_token,
    }
    return entry


def create_mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {"toshiba_ac": {}}
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_update_entry = MagicMock()
    hass.services.has_service = MagicMock(return_value=True)
    return hass


def create_mock_device_manager(connect_side_effect):
    """Create a mock device manager."""
    manager = MagicMock()
    manager.sas_token = "stored_token"
    manager.connect = AsyncMock(side_effect=connect_side_effect)
    manager.on_sas_token_updated_callback = MagicMock()
    return manager


class TestCommandErrorMessage:
    """The message a user sees when a command is sent over a refused connection."""

    def make_api(self):
        """Build a stand-in for the library's AMQP wrapper."""
        api = MagicMock()
        api.device = MagicMock()
        return api

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error",
        [
            CredentialError("Credentials invalid, could not connect"),
            UnauthorizedError("Connection Refused: not authorised"),
            ConnectionDroppedError("Unexpected disconnection"),
        ],
    )
    async def test_error_is_translated(self, error):
        """Raw Azure errors become a HomeAssistantError that names the cause."""
        from toshiba_ac.utils import amqp_api as patched_module

        api = self.make_api()
        api.device.send_message = AsyncMock(side_effect=error)

        with pytest.raises(HomeAssistantError) as excinfo:
            await patched_module.ToshibaAcAmqpApi.send_message(api, "{}")

        message = str(excinfo.value)
        assert ONE_CONNECTION_HINT in message
        assert "only one active connection" in message
        assert "toshiba_ac.reconnect" in message

    @pytest.mark.asyncio
    async def test_valid_send_passes_through(self):
        """A working connection is not touched."""
        from toshiba_ac.utils import amqp_api as patched_module

        api = self.make_api()
        api.device.send_message = AsyncMock(return_value=None)

        await patched_module.ToshibaAcAmqpApi.send_message(api, "{}")

        api.device.send_message.assert_awaited_once_with("{}")


class TestNotificationApiShape:
    """persistent_notification.async_create/async_dismiss are callbacks.

    They are synchronous, so awaiting them raises
    TypeError: 'NoneType' object can't be awaited, which broke setup until it
    was noticed in production.
    """

    def test_helpers_are_not_coroutines(self):
        """The helpers must not be coroutine functions."""
        import inspect

        from custom_components.toshiba_ac import (
            _clear_connection_notice,
            _notify_connection_refused,
        )

        assert not inspect.iscoroutinefunction(_clear_connection_notice)
        assert not inspect.iscoroutinefunction(_notify_connection_refused)

    @pytest.mark.asyncio
    async def test_successful_setup_does_not_raise(self):
        """Regression: awaiting the dismiss call broke every successful setup."""
        hass = create_mock_hass()
        entry = create_mock_entry()
        manager = create_mock_device_manager(["new_token"])

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=manager,
        ):
            assert await async_setup_entry(hass, entry) is True


class TestSetupNotice:
    """Setup must point at the competing instance, not at the login."""

    @pytest.mark.asyncio
    async def test_refused_after_reregistration_creates_notice(self):
        """A fresh token that is still refused means somebody else is connected."""
        hass = create_mock_hass()
        entry = create_mock_entry()
        manager = create_mock_device_manager(
            [
                CredentialError("Credentials invalid, could not connect"),
                UnauthorizedError("Connection Refused: not authorised"),
            ]
        )

        notification_mock = persistent_notification_mock()
        notification_mock.reset_mock()

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=manager,
        ):
            with pytest.raises(ConfigEntryNotReady) as excinfo:
                await async_setup_entry(hass, entry)

        assert ONE_CONNECTION_HINT in str(excinfo.value)
        notification_mock.async_create.assert_called_once()
        assert (
            notification_mock.async_create.call_args.kwargs["notification_id"]
            == NOTIFICATION_ID
        )

    @pytest.mark.asyncio
    async def test_network_error_creates_no_notice(self):
        """A plain network failure must not accuse another instance."""
        hass = create_mock_hass()
        entry = create_mock_entry()
        manager = create_mock_device_manager(
            [
                CredentialError("Credentials invalid, could not connect"),
                ConnectionError("Network unreachable"),
            ]
        )

        notification_mock = persistent_notification_mock()
        notification_mock.reset_mock()

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=manager,
        ):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(hass, entry)

        notification_mock.async_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_setup_clears_notice(self):
        """A working setup removes a notice from an earlier failure."""
        hass = create_mock_hass()
        entry = create_mock_entry()
        manager = create_mock_device_manager(["new_token"])

        notification_mock = persistent_notification_mock()
        notification_mock.reset_mock()

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=manager,
        ):
            assert await async_setup_entry(hass, entry) is True

        notification_mock.async_dismiss.assert_called_once_with(hass, NOTIFICATION_ID)
"""Tests for SAS token recovery (integration must heal from a lost token)."""
import time
from unittest.mock import AsyncMock, MagicMock, patch

from azure.iot.device.common.transport_exceptions import UnauthorizedError
from azure.iot.device.exceptions import CredentialError
import pytest

from custom_components.toshiba_ac import (  # noqa: E402
    _create_device_manager,
    _sas_token_is_expired,
    async_setup_entry,
)
from homeassistant.exceptions import ConfigEntryNotReady


def make_sas_token(expiry: int) -> str:
    """Build a token with the same field layout as Toshiba's."""
    return (
        "SharedAccessSignature sr=hub%2Fdevices%2Funit&sig=abc123&"
        f"se={expiry}"
    )


def create_mock_entry(sas_token):
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


def create_mock_device_manager(connect_side_effect=None):
    """Create a mock device manager."""
    manager = MagicMock()
    manager.sas_token = "stored_token"
    manager.connect = AsyncMock(return_value="new_token")
    manager.on_sas_token_updated_callback = MagicMock()

    if connect_side_effect is not None:
        manager.connect = AsyncMock(side_effect=connect_side_effect)

    return manager


class TestSasTokenExpiry:
    """Detection of an expired SAS token."""

    def test_expired_token_detected(self):
        assert _sas_token_is_expired(make_sas_token(int(time.time()) - 10))

    def test_token_expiring_within_margin_detected(self):
        assert _sas_token_is_expired(make_sas_token(int(time.time()) + 60))

    def test_valid_token_kept(self):
        assert not _sas_token_is_expired(make_sas_token(int(time.time()) + 3600))

    def test_unparsable_token_kept(self):
        assert not _sas_token_is_expired("not-a-token")

    def test_expired_token_not_handed_to_device_manager(self):
        entry = create_mock_entry(make_sas_token(int(time.time()) - 10))

        with patch("custom_components.toshiba_ac.ToshibaAcDeviceManager") as manager:
            _create_device_manager(entry)

        assert manager.call_args.args[3] is None

    def test_valid_token_handed_to_device_manager(self):
        sas_token = make_sas_token(int(time.time()) + 3600)
        entry = create_mock_entry(sas_token)

        with patch("custom_components.toshiba_ac.ToshibaAcDeviceManager") as manager:
            _create_device_manager(entry)

        assert manager.call_args.args[3] == sas_token


class TestSasTokenRecovery:
    """Recovery from a SAS token that IoT Hub rejects."""

    def setup_method(self):
        """Set up test fixtures."""
        self.hass = create_mock_hass()
        self.valid_token = make_sas_token(int(time.time()) + 3600)
        self.entry = create_mock_entry(self.valid_token)

    @pytest.mark.asyncio
    async def test_rejected_token_triggers_registration(self):
        """A rejected token is replaced and setup succeeds."""
        manager = create_mock_device_manager(
            connect_side_effect=[CredentialError("Credentials invalid"), "new_token"]
        )

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=manager,
        ):
            assert await async_setup_entry(self.hass, self.entry) is True

        assert manager.connect.call_count == 2
        assert manager.sas_token is None
        self.hass.config_entries.async_update_entry.assert_called_once()
        assert self.hass.config_entries.async_update_entry.call_args.kwargs["data"][
            "sas_token"
        ] == "new_token"

    @pytest.mark.asyncio
    async def test_unauthorized_triggers_registration(self):
        """An UnauthorizedError from IoT Hub triggers a new registration."""
        manager = create_mock_device_manager(
            connect_side_effect=[UnauthorizedError("not authorised"), "new_token"]
        )

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=manager,
        ):
            assert await async_setup_entry(self.hass, self.entry) is True

        assert manager.connect.call_count == 2

    @pytest.mark.asyncio
    async def test_expired_token_error_triggers_registration(self):
        """The ValueError raised for an expired token triggers a registration."""
        manager = create_mock_device_manager(
            connect_side_effect=[
                ValueError("Provided SasToken has already expired"),
                "new_token",
            ]
        )

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=manager,
        ):
            assert await async_setup_entry(self.hass, self.entry) is True

        assert manager.connect.call_count == 2

    @pytest.mark.asyncio
    async def test_failed_registration_raises_not_ready(self):
        """A failing re-registration is reported for retry."""
        manager = create_mock_device_manager(
            connect_side_effect=[
                CredentialError("Credentials invalid"),
                ConnectionError("Network unreachable"),
            ]
        )

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=manager,
        ):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(self.hass, self.entry)

    @pytest.mark.asyncio
    async def test_network_error_is_not_retried(self):
        """A network failure must not trigger an extra registration."""
        manager = create_mock_device_manager(
            connect_side_effect=ConnectionError("Network unreachable")
        )

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=manager,
        ):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(self.hass, self.entry)

        assert manager.connect.call_count == 1

    @pytest.mark.asyncio
    async def test_token_error_without_stored_token_is_not_retried(self):
        """Without a stored token there is nothing to replace, so no retry."""
        entry = create_mock_entry(self.valid_token)
        manager = create_mock_device_manager(
            connect_side_effect=CredentialError("Credentials invalid")
        )
        manager.sas_token = None

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=manager,
        ):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(self.hass, entry)

        assert manager.connect.call_count == 1
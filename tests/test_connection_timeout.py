"""Tests for Toshiba AC connection timeout (Issue #283)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from custom_components.toshiba_ac import async_setup_entry
from custom_components.toshiba_ac.const import DOMAIN
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady


def create_mock_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    entry.data = {
        "username": "test@example.com",
        "password": "testpass",
        "device_id": "device123",
        "sas_token": None,
    }
    return entry


def create_mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {"toshiba_ac": {}}  # Domain data must be pre-initialized
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_update_entry = MagicMock()
    hass.services.has_service = MagicMock(return_value=True)
    return hass


class TestConnectionTimeout:
    """Test cases for connection timeout handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.hass = create_mock_hass()
        self.entry = create_mock_entry()

    @pytest.mark.asyncio
    async def test_connect_success_within_timeout(self):
        """Integration loads when connect() completes within 30s."""
        mock_device_manager = MagicMock()
        mock_device_manager.connect = AsyncMock(return_value="new_token")
        mock_device_manager.on_sas_token_updated_callback = MagicMock()

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=mock_device_manager,
        ):
            result = await async_setup_entry(self.hass, self.entry)
            assert result is True
            mock_device_manager.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_timeout_raises_not_ready(self):
        """Timeout after 30s raises ConfigEntryNotReady."""
        async def slow_connect():
            await asyncio.sleep(60)  # Simulate hanging connection
            return None

        mock_device_manager = MagicMock()
        mock_device_manager.connect = slow_connect

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=mock_device_manager,
        ):
            with pytest.raises(ConfigEntryNotReady) as exc_info:
                await async_setup_entry(self.hass, self.entry)
            assert "timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_connect_auth_error_raises_auth_failed(self):
        """401/403 errors raise ConfigEntryAuthFailed."""
        mock_device_manager = MagicMock()
        mock_device_manager.connect = AsyncMock(side_effect=Exception("401 Unauthorized"))

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=mock_device_manager,
        ):
            with pytest.raises(ConfigEntryAuthFailed):
                await async_setup_entry(self.hass, self.entry)

    @pytest.mark.asyncio
    async def test_connect_other_error_raises_not_ready(self):
        """Other exceptions raise ConfigEntryNotReady for HA retry."""
        mock_device_manager = MagicMock()
        mock_device_manager.connect = AsyncMock(
            side_effect=ConnectionError("Network unreachable")
        )

        with patch(
            "custom_components.toshiba_ac.ToshibaAcDeviceManager",
            return_value=mock_device_manager,
        ):
            with pytest.raises(ConfigEntryNotReady) as exc_info:
                await async_setup_entry(self.hass, self.entry)
            assert "Failed to connect" in str(exc_info.value)

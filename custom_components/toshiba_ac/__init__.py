"""The Toshiba AC integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from toshiba_ac.device_manager import ToshibaAcDeviceManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

PLATFORMS = ["climate", "select", "sensor", "switch"]
RECONNECT_INTERVAL = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Toshiba AC component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Toshiba AC from a config entry."""
    device_manager = ToshibaAcDeviceManager(
        entry.data["username"],
        entry.data["password"],
        entry.data["device_id"],
        entry.data.get("sas_token"),
    )

    try:
        new_sas_token = await device_manager.connect()
        # Save updated SAS token if we got a new one
        if new_sas_token and new_sas_token != entry.data.get("sas_token"):
            _LOGGER.info("SAS token updated during connection")
            new_data = {**entry.data, "sas_token": new_sas_token}
            hass.config_entries.async_update_entry(entry, data=new_data)
    except Exception as ex:
        error_str = str(ex).lower()
        # Check for authentication-related errors
        if "401" in error_str or "403" in error_str or "auth" in error_str:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {ex}. Please reconfigure the integration."
            ) from ex
        # For other errors, let HA retry with exponential backoff
        raise ConfigEntryNotReady(
            f"Failed to connect to Toshiba AC service: {ex}"
        ) from ex

    # Set up SAS token update callback
    async def sas_token_updated(new_sas_token: str) -> None:
        """Handle SAS token update from the device manager."""
        _LOGGER.info("SAS token updated by device manager")
        new_data = {**entry.data, "sas_token": new_sas_token}
        hass.config_entries.async_update_entry(entry, data=new_data)

    device_manager.on_sas_token_updated_callback.add(sas_token_updated)

    # Store device manager
    hass.data[DOMAIN][entry.entry_id] = {
        "device_manager": device_manager,
        "unsub_reconnect": None,
    }

    # Set up periodic connectivity check and auto-reconnect
    async def _async_check_connectivity(_now=None) -> None:
        """Check AMQP connectivity and reconnect if needed."""
        devices = device_manager.devices
        if not devices:
            return

        # Check if any device has lost its AMQP connection
        any_unavailable = any(
            not (d.amqp_api.sas_token and d.http_api.access_token)
            for d in devices
        )

        if any_unavailable:
            _LOGGER.warning(
                "Toshiba AC connectivity lost, attempting reconnect"
            )
            try:
                new_token = await device_manager.connect()
                if new_token and new_token != entry.data.get("sas_token"):
                    new_data = {**entry.data, "sas_token": new_token}
                    hass.config_entries.async_update_entry(entry, data=new_data)
                _LOGGER.info("Toshiba AC reconnected successfully")
            except Exception as ex:
                _LOGGER.debug("Toshiba AC reconnect failed: %s", ex)

    unsub = async_track_time_interval(hass, _async_check_connectivity, RECONNECT_INTERVAL)
    hass.data[DOMAIN][entry.entry_id]["unsub_reconnect"] = unsub

    # Register reconnect service (once per domain)
    await _async_register_services(hass)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    if hass.services.has_service(DOMAIN, "reconnect"):
        return

    async def handle_reconnect(call: ServiceCall) -> None:
        """Handle the reconnect service call."""
        _LOGGER.info("Reconnect service called - reloading all config entries")
        # Reload all config entries for this domain
        for entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_reload(entry.entry_id)

    hass.services.async_register(DOMAIN, "reconnect", handle_reconnect)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Toshiba AC integration")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        # Handle both old format (direct manager) and new format (dict)
        if isinstance(entry_data, dict):
            device_manager = entry_data["device_manager"]
            unsub = entry_data.get("unsub_reconnect")
            if unsub:
                unsub()
        else:
            device_manager = entry_data
        try:
            await device_manager.shutdown()
        except Exception as ex:
            _LOGGER.warning("Error while shutting down device manager: %s", ex)

    return unload_ok

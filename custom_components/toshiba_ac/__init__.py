"""The Toshiba AC integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from toshiba_ac.device_manager import ToshibaAcDeviceManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

PLATFORMS = ["climate", "select", "sensor", "switch"]

_LOGGER = logging.getLogger(__name__)

# Timeout for initial connection (seconds)
CONNECTION_TIMEOUT = 30
# Connection health check interval
CONNECTION_CHECK_INTERVAL = timedelta(minutes=5)
# Maximum reconnection attempts before giving up (will reload config entry)
MAX_RECONNECT_ATTEMPTS = 3

# Separate storage key for connection state (to not break existing platform code)
DOMAIN_CONNECTION_STATE = f"{DOMAIN}_connection_state"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Toshiba AC component."""
    hass.data.setdefault(DOMAIN, {})
    hass.data.setdefault(DOMAIN_CONNECTION_STATE, {})
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
        # Wrap connect() with a timeout to prevent indefinite hangs
        new_sas_token = await asyncio.wait_for(
            device_manager.connect(),
            timeout=CONNECTION_TIMEOUT
        )
        # Save updated SAS token if we got a new one
        if new_sas_token and new_sas_token != entry.data.get("sas_token"):
            _LOGGER.info("SAS token updated during connection")
            new_data = {**entry.data, "sas_token": new_sas_token}
            hass.config_entries.async_update_entry(entry, data=new_data)
    except asyncio.TimeoutError:
        _LOGGER.warning(
            "Connection to Toshiba AC cloud timed out after %d seconds",
            CONNECTION_TIMEOUT
        )
        # Clean up partial state
        try:
            await device_manager.shutdown()
        except Exception:
            pass
        raise ConfigEntryNotReady(
            f"Connection timed out after {CONNECTION_TIMEOUT}s. Will retry."
        )
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

    # Store device manager directly (for backward compatibility with platform code)
    hass.data[DOMAIN][entry.entry_id] = device_manager

    # Store connection state separately
    hass.data[DOMAIN_CONNECTION_STATE][entry.entry_id] = {
        "reconnect_attempts": 0,
        "connection_check_unsub": None,
    }

    # Set up connection health monitoring
    async def check_connection_health(now=None) -> None:
        """Periodically check connection health and reconnect if needed."""
        conn_state = hass.data[DOMAIN_CONNECTION_STATE].get(entry.entry_id)
        dm = hass.data[DOMAIN].get(entry.entry_id)
        if not conn_state or not dm:
            return

        # Check if connections are still alive
        try:
            connection_ok = True

            # Check AMQP connection (Azure IoT Hub)
            if dm.amqp_api and dm.amqp_api.device:
                # The Azure IoT Hub client has a connected property
                if hasattr(dm.amqp_api.device, "connected"):
                    if not dm.amqp_api.device.connected:
                        _LOGGER.warning("Azure IoT Hub connection lost")
                        connection_ok = False
            elif not dm.amqp_api:
                # AMQP API not initialized
                _LOGGER.warning("AMQP API not initialized")
                connection_ok = False

            # Check HTTP API
            if not dm.http_api:
                _LOGGER.warning("HTTP API not initialized")
                connection_ok = False

            if not connection_ok:
                _LOGGER.info("Connection health check failed, attempting reconnect...")
                await _attempt_reconnect(hass, entry, dm, conn_state)
            else:
                # Reset reconnect counter on successful check
                conn_state["reconnect_attempts"] = 0

        except Exception as ex:
            _LOGGER.debug("Connection health check error: %s", ex)
            # If we can't even check, the connection is likely dead
            await _attempt_reconnect(hass, entry, dm, conn_state)

    # Start connection monitoring
    unsub = async_track_time_interval(
        hass,
        check_connection_health,
        CONNECTION_CHECK_INTERVAL,
    )
    hass.data[DOMAIN_CONNECTION_STATE][entry.entry_id]["connection_check_unsub"] = unsub

    # Register reconnect service (once per domain)
    await _async_register_services(hass)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _attempt_reconnect(
    hass: HomeAssistant,
    entry: ConfigEntry,
    dm: ToshibaAcDeviceManager,
    conn_state: dict,
) -> None:
    """Attempt to reconnect to Toshiba cloud."""
    conn_state["reconnect_attempts"] += 1
    attempts = conn_state["reconnect_attempts"]

    if attempts > MAX_RECONNECT_ATTEMPTS:
        _LOGGER.error(
            "Failed to reconnect after %d attempts, reloading integration",
            MAX_RECONNECT_ATTEMPTS,
        )
        # Reset attempts and trigger full reload
        conn_state["reconnect_attempts"] = 0
        await hass.config_entries.async_reload(entry.entry_id)
        return

    _LOGGER.info("Reconnection attempt %d of %d", attempts, MAX_RECONNECT_ATTEMPTS)

    try:
        # Shutdown existing connection gracefully
        try:
            await asyncio.wait_for(dm.shutdown(), timeout=10)
        except asyncio.TimeoutError:
            _LOGGER.debug("Shutdown timed out, forcing cleanup")
        except Exception as ex:
            _LOGGER.debug("Error during shutdown before reconnect: %s", ex)

        # Reset internal state
        dm.http_api = None
        dm.amqp_api = None
        dm.devices = {}

        # Reconnect with timeout
        new_sas_token = await asyncio.wait_for(
            dm.connect(),
            timeout=CONNECTION_TIMEOUT
        )

        if new_sas_token and new_sas_token != entry.data.get("sas_token"):
            _LOGGER.info("SAS token updated during reconnection")
            new_data = {**entry.data, "sas_token": new_sas_token}
            hass.config_entries.async_update_entry(entry, data=new_data)

        # Re-fetch devices to restore state
        await asyncio.wait_for(dm.get_devices(), timeout=CONNECTION_TIMEOUT)

        _LOGGER.info("Successfully reconnected to Toshiba AC cloud")
        conn_state["reconnect_attempts"] = 0

    except asyncio.TimeoutError:
        _LOGGER.warning("Reconnection attempt %d timed out", attempts)
    except Exception as ex:
        _LOGGER.warning("Reconnection attempt %d failed: %s", attempts, ex)
        # Will retry on next health check interval


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
        # Get and clean up connection state
        conn_state = hass.data[DOMAIN_CONNECTION_STATE].pop(entry.entry_id, {})
        if conn_state.get("connection_check_unsub"):
            conn_state["connection_check_unsub"]()

        # Get and clean up device manager
        device_manager = hass.data[DOMAIN].pop(entry.entry_id)
        try:
            await asyncio.wait_for(device_manager.shutdown(), timeout=10)
        except asyncio.TimeoutError:
            _LOGGER.warning("Shutdown timed out during unload")
        except Exception as ex:
            _LOGGER.warning("Error while shutting down device manager: %s", ex)

    return unload_ok

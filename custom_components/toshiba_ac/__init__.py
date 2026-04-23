"""The Toshiba AC integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from toshiba_ac.device_manager import ToshibaAcDeviceManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

PLATFORMS = ["climate", "select", "sensor", "switch"]

_LOGGER = logging.getLogger(__name__)

# Timeout for initial connection / reconnection attempts (seconds)
CONNECTION_TIMEOUT = 30

# Delay before first reconnect attempt after a disconnect (seconds)
RECONNECT_DELAY = 10

# Backoff multiplier between retries (10s, 60s, 300s)
RECONNECT_BACKOFF = [10, 60, 300]

# Maximum reconnection attempts before reloading the config entry
MAX_RECONNECT_ATTEMPTS = 3


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Toshiba AC component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Toshiba AC from a config entry."""
    # Never pass a stored SAS token on startup — it may have expired while HA
    # was stopped. Always fetch a fresh one via RegisterMobileDevice. The token
    # is saved back to config entry after successful connect for future use.
    device_manager = ToshibaAcDeviceManager(
        entry.data["username"],
        entry.data["password"],
        entry.data["device_id"],
        sas_token=None,
    )

    # Reconnect state — lives outside device_manager so it survives reconnects
    reconnect_state = {
        "attempts": 0,
        "cancel_retry": None,   # cancels a pending async_call_later callback
        "reloading": False,
    }

    async def _do_reconnect(now=None) -> None:
        """Actually attempt a reconnect. Called via async_call_later."""
        reconnect_state["cancel_retry"] = None

        if reconnect_state["reloading"]:
            return

        dm: ToshibaAcDeviceManager = hass.data[DOMAIN].get(entry.entry_id)
        if dm is None:
            return  # Entry was unloaded

        attempt = reconnect_state["attempts"] + 1
        reconnect_state["attempts"] = attempt

        if attempt > MAX_RECONNECT_ATTEMPTS:
            _LOGGER.error(
                "Failed to reconnect after %d attempts, reloading integration",
                MAX_RECONNECT_ATTEMPTS,
            )
            reconnect_state["reloading"] = True
            reconnect_state["attempts"] = 0
            await hass.config_entries.async_reload(entry.entry_id)
            return

        _LOGGER.info("Reconnection attempt %d of %d", attempt, MAX_RECONNECT_ATTEMPTS)

        try:
            # Graceful shutdown of broken connection
            try:
                await asyncio.wait_for(dm.shutdown(), timeout=10)
            except (asyncio.TimeoutError, Exception) as ex:
                _LOGGER.debug("Shutdown before reconnect: %s", ex)

            # *** BUG FIX: clear expired SAS token so connect() fetches a new one ***
            dm.sas_token = None
            dm.http_api = None
            dm.amqp_api = None
            dm.devices = {}

            new_sas_token = await asyncio.wait_for(
                dm.connect(), timeout=CONNECTION_TIMEOUT
            )

            if new_sas_token and new_sas_token != entry.data.get("sas_token"):
                _LOGGER.info("SAS token updated during reconnection")
                new_data = {**entry.data, "sas_token": new_sas_token}
                hass.config_entries.async_update_entry(entry, data=new_data)

            # Re-attach disconnect handler on new AMQP client
            _attach_disconnect_handler(dm)

            # Re-fetch devices to restore state callbacks
            await asyncio.wait_for(dm.get_devices(), timeout=CONNECTION_TIMEOUT)

            _LOGGER.info("Successfully reconnected to Toshiba AC cloud")
            reconnect_state["attempts"] = 0

        except asyncio.TimeoutError:
            _LOGGER.warning("Reconnection attempt %d timed out", attempt)
            _schedule_retry()
        except Exception as ex:
            _LOGGER.warning("Reconnection attempt %d failed: %s", attempt, ex)
            _schedule_retry()

    def _schedule_retry() -> None:
        """Schedule the next reconnect attempt with backoff."""
        if reconnect_state["reloading"]:
            return
        if reconnect_state["cancel_retry"] is not None:
            return  # Already scheduled

        attempt = reconnect_state["attempts"]
        delay = RECONNECT_BACKOFF[min(attempt, len(RECONNECT_BACKOFF) - 1)]
        _LOGGER.info("Scheduling reconnect in %d seconds", delay)
        reconnect_state["cancel_retry"] = async_call_later(
            hass, delay, _do_reconnect
        )

    def _on_disconnect_in_thread() -> None:
        """Called from the azure-iot-device background thread on disconnect.

        We cannot await here — schedule the reconnect on the HA event loop.
        This fires immediately when the SDK detects a drop, unlike polling.
        """
        _LOGGER.warning(
            "Azure IoT Hub connection lost — scheduling reconnect"
        )
        # Guard: don't pile up multiple reconnect tasks
        if reconnect_state["cancel_retry"] is not None:
            return
        if reconnect_state["reloading"]:
            return
        # Thread-safe: hand off to the asyncio event loop
        hass.loop.call_soon_threadsafe(_schedule_retry)

    def _attach_disconnect_handler(dm: ToshibaAcDeviceManager) -> None:
        """Wire up the disconnect callback on the IoTHub client.

        on_connection_state_change takes NO arguments — check .connected after.
        """
        if dm.amqp_api and dm.amqp_api.device:
            def _on_state_change() -> None:
                if not dm.amqp_api.device.connected:
                    _on_disconnect_in_thread()

            dm.amqp_api.device.on_connection_state_change = _on_state_change

    try:
        new_sas_token = await asyncio.wait_for(
            device_manager.connect(),
            timeout=CONNECTION_TIMEOUT,
        )
        if new_sas_token and new_sas_token != entry.data.get("sas_token"):
            _LOGGER.info("SAS token updated during connection")
            new_data = {**entry.data, "sas_token": new_sas_token}
            hass.config_entries.async_update_entry(entry, data=new_data)

    except asyncio.TimeoutError:
        _LOGGER.warning(
            "Connection to Toshiba AC cloud timed out after %d seconds",
            CONNECTION_TIMEOUT,
        )
        try:
            await device_manager.shutdown()
        except Exception:
            pass
        raise ConfigEntryNotReady(
            f"Connection timed out after {CONNECTION_TIMEOUT}s. Will retry."
        )
    except Exception as ex:
        error_str = str(ex).lower()
        # UnauthorizedError / 401 / 403 = bad credentials → ask user to reconfigure
        # "credential" covers azure SDK's "Credentials invalid, could not connect"
        if any(k in error_str for k in ("401", "unauthorize", "credential", "password")):
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {ex}. Please reconfigure the integration."
            ) from ex
        # 403 at startup is typically a WAF rate-limit, not a credential issue → retry
        # Don't raise ConfigEntryAuthFailed for 403 — let ConfigEntryNotReady handle it
        raise ConfigEntryNotReady(
            f"Failed to connect to Toshiba AC service: {ex}"
        ) from ex

    # Save updated SAS token into config entry so it survives HA restarts
    async def sas_token_updated(new_token: str) -> None:
        """Handle SAS token proactive renewal from the device manager."""
        _LOGGER.info("SAS token proactively renewed by device manager")
        new_data = {**entry.data, "sas_token": new_token}
        hass.config_entries.async_update_entry(entry, data=new_data)

    device_manager.on_sas_token_updated_callback.add(sas_token_updated)

    # Attach the event-driven disconnect handler
    _attach_disconnect_handler(device_manager)

    # Store in hass.data for platform access
    hass.data[DOMAIN][entry.entry_id] = device_manager

    # Store reconnect helpers so unload can cancel any pending retry
    hass.data[DOMAIN][f"{entry.entry_id}_reconnect"] = reconnect_state

    # Register manual reconnect service (once per domain)
    await _async_register_services(hass)

    # Pre-fetch devices HERE, before forwarding to platforms.
    #
    # Why: each platform (climate, select, sensor, switch) calls get_devices()
    # independently. The first call makes HTTP requests per device; the rest
    # get a cached result. By doing it once here with a proper timeout, we:
    #   1. Cache the result so all 4 platforms get it instantly (no 60s deadline risk)
    #   2. Raise ConfigEntryNotReady if the server is unreachable at startup,
    #      triggering HA's built-in exponential backoff retry
    #
    # Small delay avoids WAF 403s from simultaneous startup of all integrations.
    await asyncio.sleep(2)

    try:
        await asyncio.wait_for(
            device_manager.get_devices(),
            timeout=CONNECTION_TIMEOUT,
        )
    except asyncio.TimeoutError:
        _LOGGER.warning(
            "Timed out fetching device list after %ds — will retry",
            CONNECTION_TIMEOUT,
        )
        try:
            await device_manager.shutdown()
        except Exception:
            pass
        raise ConfigEntryNotReady(
            f"Timed out fetching devices after {CONNECTION_TIMEOUT}s. Will retry."
        )
    except Exception as ex:
        _LOGGER.warning("Failed to fetch device list: %s — will retry", ex)
        try:
            await device_manager.shutdown()
        except Exception:
            pass
        raise ConfigEntryNotReady(f"Failed to fetch devices: {ex}") from ex

    # Forward setup to platforms (get_devices() result is now cached)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    if hass.services.has_service(DOMAIN, "reconnect"):
        return

    async def handle_reconnect(call: ServiceCall) -> None:
        """Handle the reconnect service call."""
        _LOGGER.info("Reconnect service called — reloading all config entries")
        for entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_reload(entry.entry_id)

    hass.services.async_register(DOMAIN, "reconnect", handle_reconnect)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Toshiba AC integration")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Cancel any pending reconnect timer
        reconnect_state = hass.data[DOMAIN].pop(
            f"{entry.entry_id}_reconnect", {}
        )
        reconnect_state["reloading"] = True
        if reconnect_state.get("cancel_retry"):
            reconnect_state["cancel_retry"]()

        device_manager: ToshibaAcDeviceManager = hass.data[DOMAIN].pop(
            entry.entry_id
        )
        try:
            await asyncio.wait_for(device_manager.shutdown(), timeout=10)
        except asyncio.TimeoutError:
            _LOGGER.warning("Shutdown timed out during unload")
        except Exception as ex:
            _LOGGER.warning("Error while shutting down device manager: %s", ex)

    return unload_ok

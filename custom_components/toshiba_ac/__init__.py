"""The Toshiba AC integration."""

from __future__ import annotations

import logging

from toshiba_ac.device_manager import ToshibaAcDeviceManager
from toshiba_ac.utils.http_api import ToshibaAcHttpApiAuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN

PLATFORMS = ["climate", "select", "sensor", "switch"]

_LOGGER = logging.getLogger(__name__)

try:
    from azure.iot.device import exceptions as azure_exceptions
except ImportError:  # pragma: no cover
    azure_exceptions = None


def _is_auth_error(exc: Exception) -> bool:
    """Check whether exception chain indicates authentication/credential failure."""
    seen: set[int] = set()
    current: Exception | None = exc

    while current and id(current) not in seen:
        seen.add(id(current))

        if isinstance(current, ToshibaAcHttpApiAuthError):
            return True

        if azure_exceptions and isinstance(current, azure_exceptions.CredentialError):
            return True

        message = str(current).lower()
        if any(
            marker in message
            for marker in (
                "credentials invalid",
                "invalid username or password",
                "invalid_grant",
                "unauthorized",
                "authentication failed",
                " 401",
                " 403",
            )
        ):
            return True

        next_exc = current.__cause__ or current.__context__
        current = next_exc if isinstance(next_exc, Exception) else None

    return False


async def _connect_with_token_refresh_fallback(
    entry: ConfigEntry,
) -> tuple[ToshibaAcDeviceManager, str]:
    """Connect using stored token, then retry once with refreshed token on auth failure."""
    username = entry.data["username"]
    password = entry.data["password"]
    device_id = entry.data["device_id"]
    stored_sas_token = entry.data.get("sas_token")

    device_manager = ToshibaAcDeviceManager(
        username,
        password,
        device_id,
        stored_sas_token,
    )

    try:
        sas_token = await device_manager.connect()
        return device_manager, sas_token
    except Exception as first_error:
        if not stored_sas_token or not _is_auth_error(first_error):
            await device_manager.shutdown()
            raise

        _LOGGER.warning(
            "Initial Toshiba connect failed with stored SAS token. "
            "Retrying once with token refresh: %s",
            first_error,
        )

        await device_manager.shutdown()

        refreshed_manager = ToshibaAcDeviceManager(
            username,
            password,
            device_id,
            None,
        )

        try:
            sas_token = await refreshed_manager.connect()
            return refreshed_manager, sas_token
        except Exception:
            await refreshed_manager.shutdown()
            raise


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Toshiba AC component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Toshiba AC from a config entry."""
    try:
        device_manager, new_sas_token = await _connect_with_token_refresh_fallback(entry)

        if new_sas_token and new_sas_token != entry.data.get("sas_token"):
            _LOGGER.info("SAS token updated during connection")
            new_data = {**entry.data, "sas_token": new_sas_token}
            hass.config_entries.async_update_entry(entry, data=new_data)
    except Exception as ex:
        if _is_auth_error(ex):
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {ex}. Please reconfigure the integration."
            ) from ex

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
    hass.data[DOMAIN][entry.entry_id] = device_manager

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
        device_manager: ToshibaAcDeviceManager = hass.data[DOMAIN].pop(entry.entry_id)
        try:
            await device_manager.shutdown()
        except Exception as ex:
            _LOGGER.warning("Error while shutting down device manager: %s", ex)

    return unload_ok

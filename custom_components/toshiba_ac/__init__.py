"""The Toshiba AC integration."""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import time

import aiohttp
from azure.iot.device.common.transport_exceptions import (
    ConnectionDroppedError,
    UnauthorizedError,
)
from azure.iot.device.exceptions import CredentialError
from toshiba_ac.device_manager import ToshibaAcDeviceManager
from toshiba_ac.utils import amqp_api as toshiba_amqp_api, http_api as toshiba_http_api

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)

from .const import DOMAIN

# Monkey-patch: Toshiba's WAF requires a Device-ID header since ~2026-07-17.
# The upstream library (v0.3.11) doesn't include it, so we patch _ensure_session
# to add a random Device-ID to the aiohttp session headers.


async def _patched_ensure_session(self: toshiba_http_api.ToshibaAcHttpApi) -> None:
    """Patched session creation with Device-ID header for WAF compatibility."""
    async with self._session_lock:
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=20, connect=10, sock_read=15)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"Device-ID": secrets.token_hex(8)},
            )


toshiba_http_api.ToshibaAcHttpApi._ensure_session = _patched_ensure_session

# Monkey-patch: translate the raw Azure connection errors into something the
# user can act on. IoT Hub allows only one active connection per device, so a
# second instance - another Home Assistant or the Toshiba app - makes the
# library report "Credentials invalid, could not connect", which reads like a
# wrong password but is not one.

ONE_CONNECTION_HINT = (
    "Toshiba allows only one active connection per account. Another Home "
    "Assistant instance or the Toshiba app is most likely holding it. Stop "
    "that one and call the toshiba_ac.reconnect service here."
)

CONNECTION_REFUSED_ERROR = (
    f"Toshiba refused the cloud connection: {{err}}. {ONE_CONNECTION_HINT}"
)

CONNECTION_DROPPED_ERROR = (
    "The connection to the Toshiba cloud dropped while sending a command. "
    f"{ONE_CONNECTION_HINT}"
)

NOTIFICATION_ID = "toshiba_ac_connection_refused"


async def _patched_send_message(
    self: toshiba_amqp_api.ToshibaAcAmqpApi, msg: str
) -> None:
    """Patched AMQP send that names the real cause instead of "Credentials invalid"."""
    try:
        await self.device.send_message(msg)
    except CredentialError as ex:
        raise HomeAssistantError(CONNECTION_REFUSED_ERROR.format(err=ex)) from ex
    except (UnauthorizedError, ConnectionDroppedError) as ex:
        raise HomeAssistantError(CONNECTION_REFUSED_ERROR.format(err=ex)) from ex


toshiba_amqp_api.ToshibaAcAmqpApi.send_message = _patched_send_message

PLATFORMS = ["climate", "select", "sensor", "switch"]

# The upstream AMQP connect has no timeout of its own
CONNECT_TIMEOUT_S = 30

# Azure asks for a new SAS token 120s before expiry, add some margin on top
SAS_TOKEN_RENEWAL_MARGIN_S = 300

# Raised by the Azure client when the SAS token itself is the problem: a
# malformed one (ValueError), one that is expired, or one IoT Hub refuses.
SAS_TOKEN_ERRORS = (ValueError, CredentialError, UnauthorizedError)

_LOGGER = logging.getLogger(__name__)


def _sas_token_is_expired(sas_token: str) -> bool:
    """Check the expiry carried by a SAS token.

    An unparsable token counts as usable, so an unknown token format never
    causes an endless re-registration.
    """
    match = re.search(r"[?&]se=(\d+)", sas_token)

    if not match:
        return False

    return int(match.group(1)) - time.time() <= SAS_TOKEN_RENEWAL_MARGIN_S


def _create_device_manager(entry: ConfigEntry) -> ToshibaAcDeviceManager:
    """Build the device manager, discarding a SAS token that is already expired."""
    sas_token = entry.data.get("sas_token")

    if sas_token and _sas_token_is_expired(sas_token):
        _LOGGER.warning("Stored SAS token has expired, a new one will be registered")
        sas_token = None

    return ToshibaAcDeviceManager(
        entry.data["username"],
        entry.data["password"],
        entry.data["device_id"],
        sas_token,
    )


async def _async_connect(device_manager: ToshibaAcDeviceManager) -> str:
    """Connect and return the SAS token that is in use."""
    return await asyncio.wait_for(device_manager.connect(), timeout=CONNECT_TIMEOUT_S)


def _setup_error(ex: Exception, token_was_refreshed: bool = False) -> ConfigEntryError:
    """Translate a connect failure into the error Home Assistant reacts to."""
    if isinstance(ex, asyncio.TimeoutError):
        return ConfigEntryNotReady(
            f"Connection to Toshiba AC service timed out after {CONNECT_TIMEOUT_S} seconds"
        )

    if isinstance(ex, SAS_TOKEN_ERRORS):
        detail = (
            "The SAS token was just re-registered and IoT Hub refused it anyway, "
            "so the token is not the problem. "
            if token_was_refreshed
            else ""
        )
        return ConfigEntryNotReady(
            f"Failed to connect to Toshiba AC service: {ex}. {detail}{ONE_CONNECTION_HINT}"
        )

    error_str = str(ex).lower()
    if "401" in error_str or "403" in error_str or "auth" in error_str:
        return ConfigEntryAuthFailed(
            f"Authentication failed: {ex}. Please reconfigure the integration."
        )

    return ConfigEntryNotReady(f"Failed to connect to Toshiba AC service: {ex}")


def _notify_connection_refused(hass: HomeAssistant, message: str) -> None:
    """Surface the refusal in the UI, the log alone is easy to miss.

    `persistent_notification.async_create` is a callback, not a coroutine.
    Awaiting it raises TypeError: 'NoneType' object can't be awaited.
    """
    persistent_notification.async_create(
        hass,
        message,
        title="Toshiba AC: cloud connection refused",
        notification_id=NOTIFICATION_ID,
    )


def _clear_connection_notice(hass: HomeAssistant) -> None:
    """Remove the notice once the integration works again. Callback, not coroutine."""
    persistent_notification.async_dismiss(hass, NOTIFICATION_ID)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Toshiba AC component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Toshiba AC from a config entry."""
    device_manager = _create_device_manager(entry)

    try:
        new_sas_token = await _async_connect(device_manager)
    except SAS_TOKEN_ERRORS as ex:
        if not device_manager.sas_token:
            raise _setup_error(ex) from ex

        # IoT Hub refused the stored token. Registering a new one is the only
        # way back, keeping the token would fail the same way on every retry.
        _LOGGER.warning("Stored SAS token was rejected (%s), registering a new one", ex)
        device_manager.sas_token = None

        try:
            new_sas_token = await _async_connect(device_manager)
        except SAS_TOKEN_ERRORS as retry_ex:
            # A token that Toshiba's own API issued seconds ago is almost
            # certainly valid, so a refusal points at a competing connection.
            refusal = CONNECTION_REFUSED_ERROR.format(err=retry_ex)
            _LOGGER.error("%s", refusal)
            _notify_connection_refused(hass, refusal)
            raise _setup_error(retry_ex, token_was_refreshed=True) from retry_ex
        except Exception as retry_ex:
            raise _setup_error(retry_ex) from retry_ex
    except Exception as ex:
        raise _setup_error(ex) from ex

    _clear_connection_notice(hass)

    # Save updated SAS token if we got a new one
    if new_sas_token and new_sas_token != entry.data.get("sas_token"):
        _LOGGER.info("SAS token updated during connection")
        new_data = {**entry.data, "sas_token": new_sas_token}
        hass.config_entries.async_update_entry(entry, data=new_data)

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

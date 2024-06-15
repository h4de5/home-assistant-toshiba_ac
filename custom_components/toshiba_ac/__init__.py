"""The Toshiba AC integration."""
from __future__ import annotations

import logging

from toshiba_ac.device_manager import ToshibaAcDeviceManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = ["climate", "select", "sensor", "switch"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Hello World component."""
    # Ensure our name space for storing objects is a known type. A dict is
    # common/preferred as it allows a separate instance of your class for each
    # instance that has been created in the UI.
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Toshiba AC from a config entry."""
    # TODO : sas_token removed from intialization as it causes rejects. It will be regenerated automatically
    # by the library (so at each restart of HASS)
    device_manager = ToshibaAcDeviceManager(
        entry.data["username"],
        entry.data["password"],
        entry.data["device_id"],
        #entry.data["sas_token"],
    )

    try:
        _LOGGER.debug("Connect to Toshiba server")
        await device_manager.connect()
        _LOGGER.debug("Toshiba connection successful")
    except Exception as ex:
        _LOGGER.error("Error during connection to Toshiba server %s", ex)
        return False

    hass.data[DOMAIN][entry.entry_id] = device_manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.error("Unload Toshiba integration")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        device_manager: ToshibaAcDeviceManager = hass.data[DOMAIN][entry.entry_id]
        try:
            await device_manager.shutdown()
        except Exception as ex:
            _LOGGER.error("Error while unloading Toshiba integration %s", ex)
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

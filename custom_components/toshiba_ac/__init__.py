"""The Toshiba AC integration."""

from __future__ import annotations

import logging

from .toshiba_ac.device_manager import ToshibaAcDeviceManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

PLATFORMS = ["climate", "select", "sensor", "switch"]

_LOGGER = logging.getLogger(__name__)


async def sas_token_updated_for_entry(
    hass: HomeAssistant, entry: ConfigEntry, new_sas_token: str
):
    """Update SAS token."""
    _LOGGER.info("SAS token updated")

    new_data = {**entry.data, "sas_token": new_sas_token}
    hass.config_entries.async_update_entry(entry, data=new_data)


def add_sas_token_updated_callback_for_entry(
    hass: HomeAssistant, entry: ConfigEntry, device_manager: ToshibaAcDeviceManager
):
    """Set up SAS token update callback."""

    async def wrapper_callback(new_sas_token: str):
        await sas_token_updated_for_entry(hass, entry, new_sas_token)

    device_manager.on_sas_token_updated_callback.add(wrapper_callback)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Hello World component."""
    # Ensure our name space for storing objects is a known type. A dict is
    # common/preferred as it allows a separate instance of your class for each
    # instance that has been created in the UI.
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Toshiba AC from a config entry."""
    device_manager = ToshibaAcDeviceManager(
        entry.data["username"],
        entry.data["password"],
        entry.data["device_id"],
        entry.data["sas_token"],
    )

    try:
        await device_manager.connect()
    except Exception:
        _LOGGER.warning("Initial connection failed, trying to get new sas_token...")
        # If it fails to connect, try to get a new sas_token
        device_manager = ToshibaAcDeviceManager(
            entry.data["username"], entry.data["password"], entry.data["device_id"]
        )

        try:
            new_sas_token = await device_manager.connect()

            _LOGGER.info("Successfully got new sas_token!")

            # Save new sas_token
            new_data = {**entry.data, "sas_token": new_sas_token}
            hass.config_entries.async_update_entry(entry, data=new_data)
        except Exception:
            _LOGGER.warning("Connection failed on second try, aborting!")
            return False

    add_sas_token_updated_callback_for_entry(hass, entry, device_manager)

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

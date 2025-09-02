"""The Toshiba AC integration."""

from __future__ import annotations

import logging

from toshiba_ac.device_manager import ToshibaAcDeviceManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

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

    # Register reconnect service if not already registered
    if not hass.services.has_service(DOMAIN, "reconnect"):
        async def _handle_reconnect(call):
            """Handle reconnect service call."""
            _LOGGER.info("Reconnect service called, restarting all setup tasks")

            # Cancel and restart all setup tasks for all entries
            for entry_id in hass.data[DOMAIN]:
                if isinstance(hass.data[DOMAIN][entry_id], ToshibaAcDeviceManager):
                    # Cancel existing setup tasks
                    for task_name in ["setup_task", "sensor_setup_task", "select_setup_task", "switch_setup_task"]:
                        task_key = f"{entry_id}_{task_name}"
                        task = hass.data[DOMAIN].get(task_key)
                        if task and not task.done():
                            task.cancel()
                            _LOGGER.info(f"Cancelled {task_name} for entry {entry_id}")

            # Reload the entire integration
            await hass.config_entries.async_reload(entry.entry_id)

        hass.services.async_register(DOMAIN, "reconnect", _handle_reconnect)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Toshiba integration for entry %s", entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Cancel all setup tasks for this entry
        for task_name in ["setup_task", "sensor_setup_task", "select_setup_task", "switch_setup_task"]:
            task_key = f"{entry.entry_id}_{task_name}"
            setup_task = hass.data[DOMAIN].pop(task_key, None)
            if setup_task is not None and not setup_task.done():
                setup_task.cancel()
                _LOGGER.info(f"Cancelled {task_name} for entry {entry.entry_id}")

        device_manager: ToshibaAcDeviceManager = hass.data[DOMAIN][entry.entry_id]
        try:
            await device_manager.shutdown()
        except Exception as ex:
            _LOGGER.error("Error while unloading Toshiba integration %s", ex)
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

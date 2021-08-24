"""The Toshiba AC integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# from .toshiba_ac_control import toshiba_ac
# from .toshiba_ac_control.toshiba_ac.device_manager import ToshibaAcDeviceManager
from toshiba_ac.device_manager import ToshibaAcDeviceManager

PLATFORMS = ["climate"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Hello World component."""
    # Ensure our name space for storing objects is a known type. A dict is
    # common/preferred as it allows a separate instance of your class for each
    # instance that has been created in the UI.
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Toshiba AC from a config entry."""
    # TODO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    device_manager = ToshibaAcDeviceManager(entry.data["username"], entry.data["password"])

    try:
        await device_manager.connect()

    except Exception:
        return False

    # if not await device_manager.connect():
    #     return False

    hass.data[DOMAIN][entry.entry_id] = device_manager

    # for component in PLATFORMS:
    #     hass.async_create_task(
    #         hass.config_entries.async_forward_entry_setup(entry, component)
    #     )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][entry.entry_id].shutdown()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
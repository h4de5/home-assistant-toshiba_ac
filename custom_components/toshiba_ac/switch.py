"""Switch platform for the Toshiba AC integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from toshiba_ac.device import (
    ToshibaAcDevice,
    ToshibaAcStatus,
    ToshibaAcAirPureIon,
)

from .const import DOMAIN
from .entity import ToshibaAcStateEntity

_LOGGER = logging.getLogger(__name__)


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add all sensors for passed config_entry in HA."""
    # The hub is loaded from the associated hass.data entry that was created in the
    # __init__.async_setup_entry function
    device_manager = hass.data[DOMAIN][config_entry.entry_id]
    new_entites = []

    devices: list[ToshibaAcDevice] = await device_manager.get_devices()
    for device in devices:
        if ToshibaAcAirPureIon.ON in device.supported.ac_air_pure_ion:
            switch_entity = ToshibaAirPureIonSwitch(device)
            new_entites.append(switch_entity)
        else:
            _LOGGER.info("AC device does not support air purification")

    if new_entites:
        _LOGGER.info("Adding %d %s", len(new_entites), "switches")
        async_add_devices(new_entites)


class ToshibaAirPureIonSwitch(ToshibaAcStateEntity, SwitchEntity):
    """Provides a switch to toggle the air purifier."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, toshiba_device: ToshibaAcDevice):
        """Initialize the switch."""
        super().__init__(toshiba_device)

        self._attr_unique_id = f"{self._device.ac_unique_id}_air_purifier"
        self._attr_name = f"{self._device.name} Air Purifier"
        self.update_attrs()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._device.ac_status == ToshibaAcStatus.ON

    async def async_turn_off(self, **kwargs: Any):
        await self._device.set_ac_air_pure_ion(ToshibaAcAirPureIon.OFF)

    async def async_turn_on(self, **kwargs: Any):
        await self._device.set_ac_air_pure_ion(ToshibaAcAirPureIon.ON)

    def update_attrs(self):
        self._attr_is_on = self._device.ac_air_pure_ion == ToshibaAcAirPureIon.ON
        self._attr_icon = "mdi:air-purifier" if self.is_on else "mdi:air-purifier-off"

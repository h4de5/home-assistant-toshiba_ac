"""Switch platform for Toshiba AC integration."""
from __future__ import annotations

import logging
from typing import Any

from toshiba_ac.device import (
    ToshibaAcDevice,
    ToshibaAcStatus,
    ToshibaAcMeritA,
    ToshibaAcAirPureIon,
)

from custom_components.toshiba_ac.entity import ToshibaAcEntity
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensor for passed config_entry in HA."""
    # The hub is loaded from the associated hass.data entry that was created in the
    # __init__.async_setup_entry function
    device_manager = hass.data[DOMAIN][config_entry.entry_id]
    new_devices = []

    devices: list[ToshibaAcDevice] = await device_manager.get_devices()
    for device in devices:
        if ToshibaAcAirPureIon.ON in device.supported.ac_air_pure_ion:
            switch_entity = ToshibaAirPureIonSwitch(device)
            new_devices.append(switch_entity)
        else:
            _LOGGER.info("AC device does not support air purification")

        if ToshibaAcMeritA.HEATING_8C in device.supported.ac_merit_a:
            switch_entity = Toshiba8CModeSwitch(device)
            new_devices.append(switch_entity)
        else:
            _LOGGER.info("AC device does not support 8 °C mode")

    if new_devices:
        _LOGGER.info("Adding %d %s", len(new_devices), "switches")
        async_add_devices(new_devices)


class ToshibaAirPureIonSwitch(ToshibaAcEntity, SwitchEntity):
    """Provides a switch to toggle the air purifier."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, toshiba_device: ToshibaAcDevice):
        """Initialize the switch."""
        super().__init__(toshiba_device)

        self._attr_unique_id = f"{self._device.ac_unique_id}_air_purifier"
        self._attr_name = f"{self._device.name} Air Purifier"
        self._update_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._device.ac_status == ToshibaAcStatus.ON

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._device.on_state_changed_callback.add(self._state_changed)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._device.on_state_changed_callback.remove(self._state_changed)

    async def async_turn_off(self, **kwargs: Any):
        await self._device.set_ac_air_pure_ion(ToshibaAcAirPureIon.OFF)

    async def async_turn_on(self, **kwargs: Any):
        await self._device.set_ac_air_pure_ion(ToshibaAcAirPureIon.ON)

    async def _state_changed(self, _dev: ToshibaAcDevice):
        """Call if we need to change the ha state."""
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        self._attr_is_on = self._device.ac_air_pure_ion == ToshibaAcAirPureIon.ON
        self._attr_icon = "mdi:air-purifier" if self.is_on else "mdi:air-purifier-off"


class Toshiba8CModeSwitch(ToshibaAcEntity, SwitchEntity):
    """Provides a switch to toggle the 8 °C mode."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:snowflake-melt"

    def __init__(self, toshiba_device: ToshibaAcDevice):
        super().__init__(toshiba_device)
        self._attr_unique_id = f"{self._device.ac_unique_id}_8C_mode"
        self._attr_name = f"{self._device.name} 8 °C Mode"
        self._update_state()

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._device.ac_status == ToshibaAcStatus.ON
            and ToshibaAcMeritA.HEATING_8C
            in self._device.supported.for_ac_mode(self._device.ac_mode).ac_merit_a
        )

    async def async_added_to_hass(self):
        self._device.on_state_changed_callback.add(self._state_changed)

    async def async_will_remove_from_hass(self):
        self._device.on_state_changed_callback.remove(self._state_changed)

    async def async_turn_off(self, **kwargs: Any):
        await self._device.set_ac_merit_a(ToshibaAcMeritA.OFF)

    async def async_turn_on(self, **kwargs: Any):
        await self._device.set_ac_merit_a(ToshibaAcMeritA.HEATING_8C)

    async def _state_changed(self, _dev: ToshibaAcDevice):
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self):
        self._attr_is_on = self._device.ac_merit_a == ToshibaAcMeritA.HEATING_8C

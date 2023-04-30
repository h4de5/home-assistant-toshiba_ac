"""Switch platform for the Toshiba AC integration."""
from __future__ import annotations
from dataclasses import dataclass

import logging
from typing import Any, Sequence

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from toshiba_ac.device import (
    ToshibaAcAirPureIon,
    ToshibaAcDevice,
    ToshibaAcFeatures,
    ToshibaAcMeritA,
    ToshibaAcStatus,
)

from .const import DOMAIN
from .entity import ToshibaAcStateEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class ToshibaAcSwitchDescription(SwitchEntityDescription):
    """Describes a Toshiba AC switch entity type"""

    device_class = SwitchDeviceClass.SWITCH
    off_icon: str | None = None

    async def async_turn_on(self, _device: ToshibaAcDevice):
        """Turns the switch on"""

    async def async_turn_off(self, _device: ToshibaAcDevice):
        """Turns the switch off"""

    def is_on(self, _device: ToshibaAcDevice):
        """Return True if the switch is on"""
        return False

    def is_available(self, _features: ToshibaAcFeatures):
        """Return True if the switch is available. Called to determine
        if the switch should be created in the first place, and then
        later to determine if it should be available based on the current AC mode"""
        return False


@dataclass
class ToshibaAcMeritASwitchDescription(ToshibaAcSwitchDescription):
    """Describes a Toshiba AC switch that is controlled using an ac_merit_a flag"""

    ac_merit_a: ToshibaAcMeritA = ToshibaAcMeritA.NONE

    async def async_turn_off(self, device: ToshibaAcDevice):
        await device.set_ac_merit_a(ToshibaAcMeritA.OFF)

    async def async_turn_on(self, device: ToshibaAcDevice):
        if self.ac_merit_a != ToshibaAcMeritA.NONE:
            await device.set_ac_merit_a(self.ac_merit_a)

    def is_on(self, device: ToshibaAcDevice):
        if self.ac_merit_a == ToshibaAcMeritA.NONE:
            return False
        return device.ac_merit_a == self.ac_merit_a

    def is_available(self, features: ToshibaAcFeatures):
        if self.ac_merit_a == ToshibaAcMeritA.NONE:
            return False
        return self.ac_merit_a in features.ac_merit_a


class ToshibaAcAirPureIonDescription(ToshibaAcSwitchDescription):
    """Describes the Toshiba AC air purifier switch"""

    async def async_turn_off(self, device: ToshibaAcDevice):
        await device.set_ac_air_pure_ion(ToshibaAcAirPureIon.OFF)

    async def async_turn_on(self, device: ToshibaAcDevice):
        await device.set_ac_air_pure_ion(ToshibaAcAirPureIon.ON)

    def is_on(self, device: ToshibaAcDevice):
        return device.ac_air_pure_ion == ToshibaAcAirPureIon.ON

    def is_available(self, features: ToshibaAcFeatures):
        return ToshibaAcAirPureIon.ON in features.ac_air_pure_ion


_SWITCH_DESCRIPTIONS: Sequence[ToshibaAcSwitchDescription] = [
    ToshibaAcMeritASwitchDescription(
        key="8_degc_mode",
        icon="mdi:snowflake-melt",
        ac_merit_a=ToshibaAcMeritA.HEATING_8C,
        translation_key="8_degc_mode",
        name="8 °C mode",
    ),
    ToshibaAcAirPureIonDescription(
        key="air_purifier",
        icon="mdi:air-purifier",
        off_icon="mdi:air-purifier-off",
        translation_key="air_purifier",
        name="Air purifier",
    ),
]


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
        for entity_description in _SWITCH_DESCRIPTIONS:
            if entity_description.is_available(device.supported):
                new_entites.append(ToshibaAcSwitchEntity(device, entity_description))
            else:
                _LOGGER.info(
                    "AC device %s does not support %s",
                    device.name,
                    entity_description.key,
                )

        if ToshibaAcMeritA.HEATING_8C in device.supported.ac_merit_a:
            switch_entity = Toshiba8CModeSwitch(device)
            new_entites.append(switch_entity)
        else:
            _LOGGER.info("AC device does not support 8 °C mode")

    if new_entites:
        _LOGGER.info("Adding %d %s", len(new_entites), "switches")
        async_add_devices(new_entites)


class ToshibaAcSwitchEntity(ToshibaAcStateEntity, SwitchEntity):
    """Provides a switch entity based on a ToshibaAcSwitchDescription."""

    entity_description: ToshibaAcSwitchDescription
    _attr_has_entity_name = True

    def __init__(
        self, device: ToshibaAcDevice, entity_description: ToshibaAcSwitchDescription
    ):
        """Initialize the switch."""
        super().__init__(device)

        self.entity_description = entity_description
        self._attr_unique_id = f"{device.ac_unique_id}_{entity_description.key}"
        self.update_attrs()

    @property
    def available(self):
        return (
            super().available
            and self._device.ac_status == ToshibaAcStatus.ON
            and self.entity_description.is_available(
                self._device.supported.for_ac_mode(self._device.ac_mode)
            )
        )

    @property
    def icon(self):
        if self.entity_description.off_icon and not self.is_on:
            return self.entity_description.off_icon
        return super().icon

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on(self._device)

    async def async_turn_off(self, **kwargs: Any):
        await self.entity_description.async_turn_off(self._device)

    async def async_turn_on(self, **kwargs: Any):
        await self.entity_description.async_turn_on(self._device)

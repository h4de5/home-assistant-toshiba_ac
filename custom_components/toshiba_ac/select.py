"""Select platform for Toshiba AC integration."""
from __future__ import annotations

import logging
from typing import Any

from toshiba_ac.device import (
    ToshibaAcDevice,
    ToshibaAcStatus,
    ToshibaAcMeritB,
    ToshibaAcFeatures,
)
from toshiba_ac.utils import pretty_enum_name

from custom_components.toshiba_ac.entity import ToshibaAcEntity
from homeassistant.components.select import SelectEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_FIREPLACE_MERIT_B = [
    ToshibaAcMeritB.OFF,
    ToshibaAcMeritB.FIREPLACE_1,
    ToshibaAcMeritB.FIREPLACE_2,
]


def _supports_fireplace(features: ToshibaAcFeatures):
    return (
        ToshibaAcMeritB.FIREPLACE_1 in features.ac_merit_b
        or ToshibaAcMeritB.FIREPLACE_2 in features.ac_merit_b
    )


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensor for passed config_entry in HA."""
    # The hub is loaded from the associated hass.data entry that was created in the
    # __init__.async_setup_entry function
    device_manager = hass.data[DOMAIN][config_entry.entry_id]
    new_entities = []

    devices: list[ToshibaAcDevice] = await device_manager.get_devices()
    for device in devices:
        if _supports_fireplace(device.supported):
            select_entity = ToshibaFireplaceSelect(device)
            new_entities.append(select_entity)
        else:
            _LOGGER.info("AC device does not support fireplace operation")

    if new_entities:
        _LOGGER.info("Adding %d %s", len(new_entities), "selects")
        async_add_devices(new_entities)


class ToshibaFireplaceSelect(ToshibaAcEntity, SelectEntity):
    """Provides a select to toggle the fireplace mode."""

    def __init__(self, toshiba_device: ToshibaAcDevice):
        """Initialize the select."""
        super().__init__(toshiba_device)

        self._attr_unique_id = f"{self._device.ac_unique_id}_fireplace"
        self._attr_name = f"{self._device.name} Fireplace Mode"
        self._attr_options = self.get_feature_list(
            [
                value
                for value in _FIREPLACE_MERIT_B
                if value in self._device.supported.ac_merit_b
            ]
        )
        self._update_state()

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._device.on_state_changed_callback.add(self._state_changed)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._device.on_state_changed_callback.remove(self._state_changed)

    async def async_select_option(self, option: str) -> None:
        await self._device.set_ac_merit_b(
            self.get_feature_list_id(_FIREPLACE_MERIT_B, option)
        )

    async def _state_changed(self, _dev: ToshibaAcDevice):
        """Call if we need to change the ha state."""
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        value = (
            self._device.ac_merit_b
            if self._device.ac_merit_b in _FIREPLACE_MERIT_B
            else ToshibaAcMeritB.OFF
        )
        self._attr_icon = (
            "mdi:fireplace-off" if value == ToshibaAcMeritB.OFF else "mdi:fireplace"
        )
        self._attr_current_option = pretty_enum_name(value)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and _supports_fireplace(
            self._device.supported.for_ac_mode(self._device.ac_mode)
        )

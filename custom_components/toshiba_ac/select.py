"""Select platform for Toshiba AC integration."""
from __future__ import annotations

import logging
from typing import Any, Generic, List, TypeVar

from toshiba_ac.device import (
    ToshibaAcDevice,
    ToshibaAcStatus,
    ToshibaAcMeritA,
    ToshibaAcMeritB,
    ToshibaAcFeatures,
)
from toshiba_ac.utils import pretty_enum_name

from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .entity import ToshibaAcEntity, ToshibaAcStateEntity

_LOGGER = logging.getLogger(__name__)

_FIREPLACE_MERIT_B = [
    ToshibaAcMeritB.OFF,
    ToshibaAcMeritB.FIREPLACE_1,
    ToshibaAcMeritB.FIREPLACE_2,
]

_CDU_SILENT_MERIT_A = [
    ToshibaAcMeritA.OFF,
    ToshibaAcMeritA.CDU_SILENT_1,
    ToshibaAcMeritA.CDU_SILENT_2,
]


def _supports_cdu_silent(features: ToshibaAcFeatures):
    return (
        ToshibaAcMeritA.CDU_SILENT_1 in features.ac_merit_a
        or ToshibaAcMeritA.CDU_SILENT_2 in features.ac_merit_a
    )


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
            _LOGGER.info("AC device does not support fireplace mode")

        if _supports_cdu_silent(device.supported):
            select_entity = ToshibaCduSilentSelect(device)
            new_entities.append(select_entity)
        else:
            _LOGGER.info("AC device does not support outdoor unit silent mode")

    if new_entities:
        _LOGGER.info("Adding %d %s", len(new_entities), "selects")
        async_add_devices(new_entities)


class ToshibaCduSilentSelect(ToshibaAcStateEntity, SelectEntity):
    """Provides a select to toggle the outdoor unit silent mode"""

    _attr_icon = "mdi:home-sound-in-outline"

    def __init__(self, toshiba_device: ToshibaAcDevice):
        super().__init__(toshiba_device)
        self._attr_unique_id = f"{self._device.ac_unique_id}_cdu_silent"
        self._attr_name = f"{self._device.name} Outdoor Unit Silent Mode"
        self._attr_options = self.get_feature_list(
            [
                value
                for value in _CDU_SILENT_MERIT_A
                if value in self._device.supported.ac_merit_a
            ]
        )
        self.update_attrs()

    async def async_select_option(self, option: str) -> None:
        await self._device.set_ac_merit_a(
            self.get_feature_list_id(_CDU_SILENT_MERIT_A, option)
        )

    def update_attrs(self):
        value = (
            self._device.ac_merit_a
            if self._device.ac_merit_a in _CDU_SILENT_MERIT_A
            else ToshibaAcMeritA.OFF
        )
        self._attr_current_option = pretty_enum_name(value)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and _supports_cdu_silent(
            self._device.supported.for_ac_mode(self._device.ac_mode)
        )


class ToshibaFireplaceSelect(ToshibaAcStateEntity, SelectEntity):
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
        self.update_attrs()

    async def async_select_option(self, option: str) -> None:
        await self._device.set_ac_merit_b(
            self.get_feature_list_id(_FIREPLACE_MERIT_B, option)
        )

    def update_attrs(self):
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

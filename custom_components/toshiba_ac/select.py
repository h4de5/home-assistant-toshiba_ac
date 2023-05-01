"""Select platform for Toshiba AC integration."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum

import logging
from typing import Generic, Sequence, TypeVar

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from toshiba_ac.device import (
    ToshibaAcDevice,
    ToshibaAcMeritA,
    ToshibaAcMeritB,
    ToshibaAcFeatures,
)

from .const import DOMAIN
from .entity import ToshibaAcStateEntity
from .entity_description import ToshibaAcEnumEntityDescriptionMixin

_LOGGER = logging.getLogger(__name__)

TEnum = TypeVar("TEnum", bound=Enum)


@dataclass(kw_only=True)
class ToshibaAcSelectDescription(SelectEntityDescription):
    """Describes a Toshiba AC select entity type"""

    icon_mapping: dict[str, str] = field(default_factory=dict)

    async def async_select_option_name(self, device: ToshibaAcDevice, name: str):
        """Selects the provided option"""

    def current_option_name(self, _device: ToshibaAcDevice) -> str | None:
        """Returns the currently selected option"""
        return None

    def get_option_names(self, _features: ToshibaAcFeatures) -> list[str]:
        """Returns the available options for given Toshiba AC device features"""
        return []

    def is_available(self, _features: ToshibaAcFeatures):
        """Return True if the switch is available. Called to determine
        if the switch should be created in the first place, and then
        later to determine if it should be available based on the current AC mode"""
        return False


TEnum = TypeVar("TEnum", bound=Enum)


@dataclass(kw_only=True)
class ToshibaAcEnumSelectDescription(
    ToshibaAcSelectDescription,
    ToshibaAcEnumEntityDescriptionMixin[TEnum],
    Generic[TEnum],
):
    """Describes a Toshiba AC select entity type based on an enum"""

    ac_attr_name: str = ""
    ac_attr_setter: str = ""
    off_value: TEnum | None = None
    values: list[TEnum] = field(default_factory=list)

    async def async_select_option_name(self, device: ToshibaAcDevice, name: str):
        for value in self.values:
            if value.name.lower() == name:
                await self.async_set_attr(device, value)
                return

    def current_option_name(self, device: ToshibaAcDevice) -> str | None:
        value = self.get_device_attr(device)
        if value and value in self.values:
            return value.name
        if self.off_value:
            return self.off_value.name
        return None

    def get_option_names(self, features: ToshibaAcFeatures):
        return [v.name.lower() for v in self.get_option_values(features)]

    def get_option_values(self, features: ToshibaAcFeatures):
        """Returns all the supported option enum values"""
        values = self.get_features_attr(features)
        return [v for v in self.values if v in values]

    def is_available(self, features: ToshibaAcFeatures):
        options = self.get_option_values(features)
        if self.off_value is not None and self.off_value in options:
            options.remove(self.off_value)
        return len(options) != 0


_SELECT_DESCRIPTIONS: Sequence[ToshibaAcSelectDescription] = [
    ToshibaAcEnumSelectDescription(
        key="cdu_silent",
        icon="mdi:home-sound-in-outline",
        translation_key="cdu_silent",
        ac_attr_name="ac_merit_a",
        values=[
            ToshibaAcMeritA.OFF,
            ToshibaAcMeritA.CDU_SILENT_1,
            ToshibaAcMeritA.CDU_SILENT_2,
        ],
        off_value=ToshibaAcMeritA.OFF,
    ),
    ToshibaAcEnumSelectDescription(
        key="fireplace",
        translation_key="fireplace",
        icon="mdi:fireplace",
        icon_mapping={"Off": "mdi:fireplace-off"},
        ac_attr_name="ac_merit_b",
        values=[
            ToshibaAcMeritB.OFF,
            ToshibaAcMeritB.FIREPLACE_1,
            ToshibaAcMeritB.FIREPLACE_2,
        ],
        off_value=ToshibaAcMeritB.OFF,
    ),
]


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
        for entity_description in _SELECT_DESCRIPTIONS:
            if entity_description.is_available(device.supported):
                new_entities.append(ToshibaAcSelectEntity(device, entity_description))
            else:
                _LOGGER.info(
                    "AC device %s does not support %s",
                    device.name,
                    entity_description.key,
                )

    if new_entities:
        _LOGGER.info("Adding %d %s", len(new_entities), "selects")
        async_add_devices(new_entities)


class ToshibaAcSelectEntity(ToshibaAcStateEntity, SelectEntity):
    """Provides a select based on a ToshibaAcSelectDescription"""

    entity_description: ToshibaAcSelectDescription
    _attr_has_entity_name = True

    def __init__(
        self, device: ToshibaAcDevice, entity_description: ToshibaAcSelectDescription
    ):
        super().__init__(device)
        self._attr_unique_id = f"{device.ac_unique_id}_{entity_description.key}"
        self.entity_description = entity_description
        self.update_attrs()

    async def async_select_option(self, option: str) -> None:
        await self.entity_description.async_select_option_name(self._device, option)

    def update_attrs(self):
        features = self._device.supported.for_ac_mode(self._device.ac_mode)
        self._attr_options = self.entity_description.get_option_names(features)
        self._attr_current_option = self.entity_description.current_option_name(
            self._device
        )

    @property
    def available(self) -> bool:
        features = self._device.supported.for_ac_mode(self._device.ac_mode)
        return super().available and self.entity_description.is_available(features)

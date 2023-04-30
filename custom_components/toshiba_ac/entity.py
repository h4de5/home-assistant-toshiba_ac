"""Parent class for every Toshiba AC device."""

from __future__ import annotations
import logging
from typing import Any

from toshiba_ac.device import ToshibaAcDevice
from toshiba_ac.utils import pretty_enum_name

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ToshibaAcEntity(Entity):
    """Representation of an Toshiba AC device entity."""

    def __init__(self, toshiba_device: ToshibaAcDevice) -> None:
        """Initialize the device."""
        self._device = toshiba_device

        self._attr_should_poll = False
        self._attr_device_info = self.generate_device_info()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(
            self._device.ac_id
            and self._device.amqp_api.sas_token
            and self._device.http_api.access_token
        )

    def generate_device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.ac_unique_id)},
            account=self._device.ac_id,
            device_id=self._device.device_id,
            manufacturer="Toshiba",
            name=self._device.name,
            sw_version=self._device.firmware_version,
        )

    def get_feature_list(self, feature_list: list[Any]) -> list[Any]:
        """Return a list of features supported by the device."""
        return [
            pretty_enum_name(e) for e in feature_list if pretty_enum_name(e) != "None"
        ]

    def get_feature_list_id(self, feature_list: list[Any], feature_name: str) -> Any:
        """Return the enum value of that item with the given name from a feature list."""
        _LOGGER.debug("searching %s for %s", feature_list, feature_name)

        feature_list = [e for e in feature_list if pretty_enum_name(e) == feature_name]
        _LOGGER.debug("and found %s", feature_list)

        if len(feature_list) > 0:
            return feature_list[0]
        return None

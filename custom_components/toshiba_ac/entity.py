"""Parent class for every Toshiba AC device."""

from __future__ import annotations

from toshiba_ac.device import ToshibaAcDevice

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN


class ToshibaAcEntity(Entity):
    """Representation of an Toshiba AC device entity."""

    def __init__(self, toshiba_device: ToshibaAcDevice) -> None:
        """Initialize the device."""
        self._device = toshiba_device

        self._attr_should_poll = False
        self._attr_device_info = self.generate_device_info()

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

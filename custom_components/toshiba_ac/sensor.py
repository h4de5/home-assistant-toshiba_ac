"""Platform for sensor integration."""
from __future__ import annotations

from datetime import date, datetime
import logging

from toshiba_ac.device import ToshibaAcDevice, ToshibaAcDeviceEnergyConsumption

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .entity import ToshibaAcEntity, ToshibaAcStateEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensor entities for passed config_entry in HA."""
    device_manager = hass.data[DOMAIN][config_entry.entry_id]
    new_entities = []

    devices: list[ToshibaAcDevice] = await device_manager.get_devices()
    for device in devices:
        if device.supported.ac_energy_report:
            new_entities.append(ToshibaPowerSensor(device))
        else:
            _LOGGER.debug(
                "AC device %s does not support energy monitoring", device.name
            )

        # Outdoor temperature sensor - value may be None when outdoor unit is off
        new_entities.append(ToshibaTempSensor(device))

    if new_entities:
        _LOGGER.info("Adding %d sensor entities", len(new_entities))
        async_add_devices(new_entities)


class ToshibaPowerSensor(ToshibaAcEntity, SensorEntity):
    """Provides a Toshiba Sensors."""

    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _ac_energy_consumption: ToshibaAcDeviceEnergyConsumption | None = None

    def __init__(self, toshiba_device: ToshibaAcDevice):
        """Initialize the sensor."""
        super().__init__(toshiba_device)
        self._attr_unique_id = f"{self._device.ac_unique_id}_sensor"
        self._attr_name = f"{self._device.name} Power Consumption"

    async def state_changed(self, _dev: ToshibaAcDevice):
        """Call if we need to change the ha state."""
        self._ac_energy_consumption = self._device.ac_energy_consumption
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        # Importantly for a push integration, the module that will be getting updates
        # needs to notify HA of changes. The dummy device has a registercallback
        # method, so to this we add the 'self.async_write_ha_state' method, to be
        # called where ever there are changes.
        # The call back registration is done once this entity is registered with HA
        # (rather than in the __init__)
        # self._device.register_callback(self.async_write_ha_state)
        self._device.on_energy_consumption_changed_callback.add(self.state_changed)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        # self._device.remove_callback(self.async_write_ha_state)
        self._device.on_energy_consumption_changed_callback.remove(self.state_changed)

    @property
    def native_value(self) -> StateType | date | datetime:
        """Return the value reported by the sensor."""
        if self._ac_energy_consumption:
            return self._ac_energy_consumption.energy_wh
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self._ac_energy_consumption:
            return {"last_reset": self._ac_energy_consumption.since}
        return {}


class ToshibaTempSensor(ToshibaAcStateEntity, SensorEntity):
    """Provides a Toshiba Temperature Sensors."""

    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(self, device: ToshibaAcDevice):
        """Initialize the sensor."""
        super().__init__(device)
        self._attr_unique_id = f"{device.ac_unique_id}_outdoor_temperature"
        self._attr_translation_key = "outdoor_temperature"

    @property
    def available(self) -> bool:
        """Return True if sensor is available."""
        if self._device.ac_outdoor_temperature is None:
            return False
        return super().available

    @property
    def native_value(self) -> int | None:
        """Return the value reported by the sensor."""
        return self._device.ac_outdoor_temperature

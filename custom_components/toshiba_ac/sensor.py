"""Platform for sensor integration."""
from __future__ import annotations

import asyncio
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


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensor for passed config_entry in HA."""
    device_manager = hass.data[DOMAIN][config_entry.entry_id]

    async def _run_setup():
        backoff = [1, 3, 7, 30, 60, 300, 1800]
        attempt = 0
        while True:
            try:
                devices: list[ToshibaAcDevice] = await device_manager.get_devices()
                new_devices = []

                for device in devices:
                    # _LOGGER.debug("device %s", device)
                    # _LOGGER.debug("energy_consumption %s", device.ac_energy_consumption)

                    # if device.ac_energy_consumption:
                    if device.supported.ac_energy_report:
                        sensor_entity = ToshibaPowerSensor(device)
                        new_devices.append(sensor_entity)
                    else:
                        _LOGGER.info("AC device does not support energy monitoring")

                    # We cannot check for device.ac_outdoor_temperature not being None
                    # as it will report None when outdoor unit is off
                    # i.e. when AC is in Fan mode or Off
                    sensor_entity = ToshibaTempSensor(device)
                    new_devices.append(sensor_entity)

                # If we have any new devices, add them
                if new_devices:
                    _LOGGER.info("Adding %d %s", len(new_devices), "sensors")
                    async_add_devices(new_devices)
                return
            except Exception as ex:
                wait = backoff[min(attempt, len(backoff) - 1)]
                attempt += 1
                _LOGGER.warning(
                    "Toshiba AC: sensor setup attempt %s failed: %r. Retrying in %s sec",
                    attempt,
                    ex,
                    wait,
                )

                # Try to reconnect on specific failures that might indicate token issues
                if attempt == 1 and ("403" in str(ex) or "Forbidden" in str(ex) or "TimeoutError" in str(ex)):
                    _LOGGER.info("Attempting to refresh connection due to potential token issue")
                    try:
                        await device_manager.connect()
                        _LOGGER.info("Successfully refreshed connection")
                        # Reset wait time for immediate retry after successful reconnect
                        wait = 1
                    except Exception as connect_ex:
                        _LOGGER.warning("Failed to refresh connection: %r", connect_ex)

                await asyncio.sleep(wait)

    async def _start_setup_task():
        task = hass.loop.create_task(_run_setup())
        hass.data[DOMAIN][f"{config_entry.entry_id}_sensor_setup_task"] = task

    await _start_setup_task()


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

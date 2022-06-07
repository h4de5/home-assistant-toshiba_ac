"""Platform for sensor integration."""

import logging

from custom_components.toshiba_ac.entity import ToshibaAcEntity
from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_WATT_HOUR,
    TEMP_CELSIUS,
)

try:
    from homeassistant.components.sensor import STATE_CLASS_TOTAL_INCREASING
except ImportError:
    from homeassistant.components.sensor import (
        STATE_CLASS_MEASUREMENT as STATE_CLASS_TOTAL_INCREASING,
    )

try:
    from homeassistant.components.sensor import SensorEntity
except ImportError:
    from homeassistant.helpers.entity import Entity as SensorEntity

from toshiba_ac.device import ToshibaAcDevice, ToshibaAcDeviceEnergyConsumption

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensor for passed config_entry in HA."""
    # The hub is loaded from the associated hass.data entry that was created in the
    # __init__.async_setup_entry function
    device_manager = hass.data[DOMAIN][config_entry.entry_id]

    # The next few lines find all of the entities that will need to be added
    # to HA. Note these are all added to a list, so async_add_devices can be
    # called just once.
    new_devices = []
    outdoor_done = False

    devices: list[ToshibaAcDevice] = await device_manager.get_devices()
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
        if not outdoor_done:
            sensor_entity = ToshibaTempSensor(device)
            new_devices.append(sensor_entity)
            outdoor_done = True

    # If we have any new devices, add them
    if new_devices:
        _LOGGER.info("Adding %d %s", len(new_devices), "sensors")
        async_add_devices(new_devices)


class ToshibaPowerSensor(ToshibaAcEntity, SensorEntity):
    """Provides a Toshiba Sensors."""

    _attr_unit_of_measurement = ENERGY_WATT_HOUR
    _attr_device_class = DEVICE_CLASS_ENERGY
    _attr_state_class = STATE_CLASS_TOTAL_INCREASING

    def __init__(self, toshiba_device: ToshibaAcDevice):
        """Initialize the sensor."""
        super().__init__(toshiba_device)

        self._ac_energy_consumption: ToshibaAcDeviceEnergyConsumption = None

        self._attr_unique_id = f"{self._device.ac_unique_id}_sensor"
        self._attr_name = f"{self._device.name} Power Consumption"
        self.available = (
            self._device.ac_id
            and self._device.amqp_api.sas_token
            and self._device.http_api.access_token
        )

    # default entity properties

    async def state_changed(self, dev):
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
    def state(self) -> float:
        """Return the value of the sensor."""
        if self._ac_energy_consumption:
            return self._ac_energy_consumption.energy_wh
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self._ac_energy_consumption:
            return {"last_reset": self._ac_energy_consumption.since}


class ToshibaTempSensor(ToshibaAcEntity, SensorEntity):
    """Provides a Toshiba Temperature Sensors."""

    _attr_unit_of_measurement = TEMP_CELSIUS
    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, toshiba_device: ToshibaAcDevice):
        """Initialize the sensor."""
        super().__init__(toshiba_device)
        self._ac_energy_consumption: ToshibaAcDeviceEnergyConsumption = None

        self._attr_unique_id = f"{self._device.ac_unique_id}_outdoor_temperature"
        self._attr_name = f"{self._device.name} Outdoor Temperature"

    async def state_changed(self, dev):
        """Call if we need to change the ha state."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._device.on_state_changed_callback.add(self.state_changed)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._device.on_state_changed_callback.remove(self.state_changed)

    @property
    def available(self) -> bool:
        """Return True if sensor is available."""
        if (
            self._device.ac_outdoor_temperature
            or self._device.ac_outdoor_temperature == 0
        ):
            return (
                self._device.ac_id
                and self._device.amqp_api.sas_token
                and self._device.http_api.access_token
            )
        return False

    @property
    def state(self) -> float:
        """Return the value of the sensor."""
        if (
            self._device.ac_outdoor_temperature
            or self._device.ac_outdoor_temperature == 0
        ):
            return self._device.ac_outdoor_temperature
        return None

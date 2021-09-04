"""Platform for sensor integration."""

import logging
from datetime import datetime
from homeassistant.const import DEVICE_CLASS_ENERGY, ENERGY_WATT_HOUR

try:
    from homeassistant.components.sensor import STATE_CLASS_TOTAL_INCREASING
except ImportError:
    from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT as STATE_CLASS_TOTAL_INCREASING

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

    devices = await device_manager.get_devices()
    for device in devices:

        _LOGGER.debug("device %s", device)
        _LOGGER.debug("energy_consumption %s", device.ac_energy_consumption)

        if device.ac_energy_consumption:
            sensor_entity = ToshibaSensor(device)
            new_devices.append(sensor_entity)
        else:
            _LOGGER.warning("AC device does not seem to support energy monitoring")
    # If we have any new devices, add them
    if new_devices:
        _LOGGER.info("Adding %d %s", len(new_devices), "sensors")
        async_add_devices(new_devices)


class ToshibaSensor(SensorEntity):
    """Provides a Toshiba Sensors."""

    # Our dummy class is PUSH, so we tell HA that it should not be polled
    should_poll = False

    _device: ToshibaAcDevice = None
    _ac_energy_consumption: ToshibaAcDeviceEnergyConsumption = None

    def __init__(self, toshiba_device: ToshibaAcDevice):
        """Initialize the sensor."""
        self._device = toshiba_device

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

    # A unique_id for this entity with in this domain. This means for example if you
    # have a sensor on this cover, you must ensure the value returned is unique,
    # which is done here by appending "_cover". For more information, see:
    # https://developers.home-assistant.io/docs/entity_registry_index/#unique-id-requirements
    # Note: This is NOT used to generate the user visible Entity ID used in automations.
    @property
    def unique_id(self):
        """Return Unique ID string."""
        return f"{self._device.ac_unique_id}_sensor"

    # Information about the devices that is partially visible in the UI.
    # The most critical thing here is to give this entity a name so it is displayed
    # as a "device" in the HA UI. This name is used on the Devices overview table,
    # and the initial screen when the device is added (rather than the entity name
    # property below). You can then associate other Entities (eg: a battery
    # sensor) with this device, so it shows more like a unified element in the UI.
    # For example, an associated battery sensor will be displayed in the right most
    # column in the Configuration > Devices view for a device.
    # To associate an entity with this device, the device_info must also return an
    # identical "identifiers" attribute, but not return a name attribute.
    # See the sensors.py file for the corresponding example setup.
    # Additional meta data can also be returned here, including sw_version (displayed
    # as Firmware), model and manufacturer (displayed as <model> by <manufacturer>)
    # shown on the device info screen. The Manufacturer and model also have their
    # respective columns on the Devices overview table. Note: Many of these must be
    # set when the device is first added, and they are not always automatically
    # refreshed by HA from it's internal cache.
    # For more information see:
    # https://developers.home-assistant.io/docs/device_registry_index/#device-properties
    @property
    def device_info(self):
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._device.ac_unique_id)},
            # If desired, the name for the device could be different to the entity
            # "name": self.name,
            "account": self._device.ac_id,
            "device_id": self._device.device_id,
            # "sw_version": self._roller.firmware_version,
            # "model": self._roller.model,
            "manufacturer": "Toshiba",
        }

    # This is the name for this *entity*, the "name" attribute from "device_info"
    # is used as the device name for device screens in the UI. This name is used on
    # entity screens, and used to build the Entity ID that's used is automations etc.
    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name + " Power Consumption"

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
    @property
    def available(self) -> bool:
        """Return True if sensor is available."""
        return self._device.ac_id and self._device.amqp_api.sas_token and self._device.http_api.access_token

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_WATT_HOUR

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_ENERGY

    @property
    def state_class(self) -> str:
        """Return the state class of this entity."""
        return STATE_CLASS_TOTAL_INCREASING

    @property
    def last_reset(self) -> datetime:
        """Return the time when the sensor was last reset, if any."""
        if self._ac_energy_consumption:
            return self._ac_energy_consumption.since
        else:
            return datetime.now().date()

    @property
    def state(self) -> float:
        """Return the value of the sensor."""
        if self._ac_energy_consumption:
            return self._ac_energy_consumption.energy_wh
        else:
            # We have to return None so HA won't see this as new cycle
            return None

    # @property
    # def device_state_attributes(self):
    #     """Return the state attributes."""
    #     self._ac_energy_consumption = self._device.ac_energy_consumption

    #     _LOGGER.debug("is it set in attributes:? %s", self._ac_energy_consumption)

    #     if self._ac_energy_consumption:
    #         return {"last_reset": self._ac_energy_consumption.since}
    #     else:
    #         return {"last_reset": datetime.utcnow().date()}


# end class ToshibaSensor

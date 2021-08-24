"""Platform for climate integration."""

import logging
from homeassistant.components.climate.const import (
    CURRENT_HVAC_OFF,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_DRY,
    # CURRENT_HVAC_IDLE,
    CURRENT_HVAC_FAN,
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE,
    # SUPPORT_PRESET_MODE,
    # SUPPORT_AUX_HEAT,
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_ON,
    FAN_OFF,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

# , TEMP_FAHRENHEIT
# from voluptuous.validators import Switch
from .const import DOMAIN

# from .toshiba_ac_control.toshiba_ac.fcu_state import ToshibaAcFcuState.AcStatus, AcMode, AcFanMode
# from toshiba_ac.fcu_state import AcStatus, AcMode, AcFanMode
from toshiba_ac.fcu_state import ToshibaAcFcuState


try:
    from homeassistant.components.climate import ClimateEntity
except ImportError:
    from homeassistant.components.climate import ClimateDevice as ClimateEntity

_LOGGER = logging.getLogger(__name__)


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add climate for passed config_entry in HA."""
    # The hub is loaded from the associated hass.data entry that was created in the
    # __init__.async_setup_entry function
    device_manager = hass.data[DOMAIN][config_entry.entry_id]

    # The next few lines find all of the entities that will need to be added
    # to HA. Note these are all added to a list, so async_add_devices can be
    # called just once.
    new_devices = []

    devices = await device_manager.get_devices()
    for device in devices:
        climate_entity = ToshibaClimate(device)
        new_devices.append(climate_entity)
    # If we have any new devices, add them
    if new_devices:
        _LOGGER.info("Adding %d %s", len(new_devices), "climates")
        async_add_devices(new_devices)


# async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
#     """Set up the Toshiba Climate platform."""
#     toshiba_setup_platform(ToshibaClimate, hass, async_add_entities, discovery_info)


class ToshibaClimate(ClimateEntity):
    """Provides a Toshiba climates."""

    # Our dummy class is PUSH, so we tell HA that it should not be polled
    should_poll = False
    # The supported features of a cover are done using a bitmask. Using the constants
    # imported above, we can tell HA the features that are supported by this entity.
    # If the supported features were dynamic (ie: different depending on the external
    # device it connected to), then this should be function with an @property decorator.
    supported_features = SUPPORT_FAN_MODE | SUPPORT_TARGET_TEMPERATURE

    _device = None

    # _platform = "climate"

    def __init__(self, toshiba_climate):
        """Initialize the climate."""
        self._device = toshiba_climate

        # ToshibaEntity.__init__(self, device_id, toshibaconnection, toshibaproject, coordinator)
        # self.entity_id = "climate." + self._name.lower() + "_" + self._device_id

    # default entity properties

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        # Importantly for a push integration, the module that will be getting updates
        # needs to notify HA of changes. The dummy device has a registercallback
        # method, so to this we add the 'self.async_write_ha_state' method, to be
        # called where ever there are changes.
        # The call back registration is done once this entity is registered with HA
        # (rather than in the __init__)
        # self._device.register_callback(self.async_write_ha_state)
        self._device.on_state_changed = lambda _: self.schedule_update_ha_state()

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        # self._device.remove_callback(self.async_write_ha_state)
        self._device.on_state_changed = None

    # A unique_id for this entity with in this domain. This means for example if you
    # have a sensor on this cover, you must ensure the value returned is unique,
    # which is done here by appending "_cover". For more information, see:
    # https://developers.home-assistant.io/docs/entity_registry_index/#unique-id-requirements
    # Note: This is NOT used to generate the user visible Entity ID used in automations.
    @property
    def unique_id(self):
        """Return Unique ID string."""
        return f"{self._device.device_id}_climate"

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
            "identifiers": {(DOMAIN, self._device.device_id)},
            # If desired, the name for the device could be different to the entity
            "name": self.name,
            "account": self._device.ac_id,
            "unique_id": self._device.ac_unique_id,
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
        return self._device.name

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
    @property
    def available(self) -> bool:
        """Return True if climate is available."""
        return self._device.ac_id and self._device.amqp_api.sas_token and self._device.http_api.access_token

    # climate properties

    @property
    def is_on(self):
        """Return True if the device is on or completely off."""
        return (False, True)[self._device.ac_status == ToshibaAcFcuState.AcStatus.ON]

    # MISSING !
    # @property
    # def current_temperature(self):
    #     """Return current temperature."""
    #     return float(self._device.ac_temperature)

    # @property
    # def current_humidity(self):
    #     """Return current humidity."""
    #     if self.has_state("umidita"):
    #         return float(self._device.ac_temperature)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.ac_temperature.name

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def temperature_unit(self):
        """Return unit of temperature measurement for the system (TEMP_CELSIUS or TEMP_FAHRENHEIT)."""
        return TEMP_CELSIUS

    @property
    def hvac_mode(self):
        """Return target operation (e.g.heat, cool, auto, off). Used to determine state."""
        if not self.is_on:
            return HVAC_MODE_OFF

        if self._device.ac_mode == ToshibaAcFcuState.AcMode.AUTO:
            return HVAC_MODE_AUTO
        elif self._device.ac_mode == ToshibaAcFcuState.AcMode.COOL:
            return HVAC_MODE_COOL
        elif self._device.ac_mode == ToshibaAcFcuState.AcMode.HEAT:
            return HVAC_MODE_HEAT
        elif self._device.ac_mode == ToshibaAcFcuState.AcMode.DRY:
            return HVAC_MODE_DRY
        elif self._device.ac_mode == ToshibaAcFcuState.AcMode.FAN:
            return HVAC_MODE_FAN_ONLY
        else:
            return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """List of available operation modes. See below."""
        # button for auto is still there, to clear manual mode, but will not change highlighted icon
        return [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_OFF, HVAC_MODE_DRY, HVAC_MODE_FAN_ONLY]

    @property
    def hvac_action(self):
        """Return current HVAC action (heating, cooling, idle, off)."""
        if not self.is_on:
            return CURRENT_HVAC_OFF

        if self._device.ac_mode == ToshibaAcFcuState.AcMode.AUTO:
            return CURRENT_HVAC_COOL  # CURRENT_HVAC_IDLE
        elif self._device.ac_mode == ToshibaAcFcuState.AcMode.COOL:
            return CURRENT_HVAC_COOL
        elif self._device.ac_mode == ToshibaAcFcuState.AcMode.HEAT:
            return CURRENT_HVAC_HEAT
        elif self._device.ac_mode == ToshibaAcFcuState.AcMode.DRY:
            return CURRENT_HVAC_DRY
        elif self._device.ac_mode == ToshibaAcFcuState.AcMode.FAN:
            return CURRENT_HVAC_FAN
        else:
            return CURRENT_HVAC_OFF

    @property
    def fan_modes(self):
        """Return the list of available fan modes. Requires SUPPORT_FAN_MODE."""
        return (FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_DIFFUSE)

    @property
    def fan_mode(self):
        """Return the current fan mode. Requires SUPPORT_FAN_MODE."""
        if self._device.ac_fan_mode == ToshibaAcFcuState.AcFanMode.AUTO:
            return FAN_AUTO
        elif self._device.ac_fan_mode in [ToshibaAcFcuState.AcFanMode.LOW, ToshibaAcFcuState.AcFanMode.MEDIUM_LOW]:
            return FAN_LOW
        elif self._device.ac_fan_mode == ToshibaAcFcuState.AcFanMode.MEDIUM:
            return FAN_MEDIUM
        elif self._device.ac_fan_mode == [ToshibaAcFcuState.AcFanMode.MEDIUM_HIGH, ToshibaAcFcuState.AcFanMode.HIGH]:
            return FAN_HIGH
        elif self._device.ac_fan_mode == ToshibaAcFcuState.AcFanMode.QUIET:
            return FAN_DIFFUSE
        else:
            return FAN_ON

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        _LOGGER.info("Toshiba Climate setting fan_mode: %s", fan_mode)

        if fan_mode == FAN_OFF:
            await self._device.set_ac_status(ToshibaAcFcuState.AcStatus.OFF)
        else:
            if not self.is_on:
                await self._device.set_ac_status(ToshibaAcFcuState.AcStatus.ON)

            if fan_mode == FAN_LOW:
                await self._device.set_ac_fan_mode(ToshibaAcFcuState.AcFanMode.LOW)
            elif fan_mode == FAN_MEDIUM:
                await self._device.set_ac_fan_mode(ToshibaAcFcuState.AcFanMode.MEDIUM)
            elif fan_mode == FAN_HIGH:
                await self._device.set_ac_fan_mode(ToshibaAcFcuState.AcFanMode.HIGH)
            elif fan_mode == FAN_AUTO:
                await self._device.set_ac_fan_mode(ToshibaAcFcuState.AcFanMode.AUTO)
            elif fan_mode == FAN_DIFFUSE:
                await self._device.set_ac_fan_mode(ToshibaAcFcuState.AcFanMode.QUIET)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        _LOGGER.info("Toshiba Climate setting hvac_mode: %s", hvac_mode)

        if hvac_mode == HVAC_MODE_OFF:
            await self._device.set_ac_status(ToshibaAcFcuState.AcStatus.OFF)

        else:
            if not self.is_on:
                await self._device.set_ac_status(ToshibaAcFcuState.AcStatus.ON)
            if hvac_mode == HVAC_MODE_AUTO:
                await self._device.set_ac_mode(ToshibaAcFcuState.AcMode.AUTO)
            elif hvac_mode == HVAC_MODE_COOL:
                await self._device.set_ac_mode(ToshibaAcFcuState.AcMode.COOL)
            elif hvac_mode == HVAC_MODE_HEAT:
                await self._device.set_ac_mode(ToshibaAcFcuState.AcMode.HEAT)
            elif hvac_mode == HVAC_MODE_DRY:
                await self._device.set_ac_mode(ToshibaAcFcuState.AcMode.DRY)
            elif hvac_mode == HVAC_MODE_FAN_ONLY:
                await self._device.set_ac_mode(ToshibaAcFcuState.AcMode.FAN)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        set_temperature = kwargs.get(ATTR_TEMPERATURE)
        if set_temperature is None:
            return
        # upper limit for target temp
        if set_temperature > 40:
            set_temperature = 40
        if set_temperature < 10:
            set_temperature = 10

        await self._device.set_ac_temperature(int(set_temperature))


# end class ToshibaClimate

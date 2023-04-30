"""Platform for climate integration."""
from __future__ import annotations

import logging
from typing import Any, Mapping

from toshiba_ac.device import (
    ToshibaAcDevice,
    ToshibaAcFanMode,
    ToshibaAcMeritA,
    ToshibaAcMode,
    ToshibaAcPowerSelection,
    ToshibaAcSelfCleaning,
    ToshibaAcStatus,
    ToshibaAcSwingMode,
)
from toshiba_ac.utils import pretty_enum_name

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_OFF,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .const import DOMAIN
from .entity import ToshibaAcStateEntity

_LOGGER = logging.getLogger(__name__)

TOSHIBA_TO_HVAC_MODE = {
    ToshibaAcMode.AUTO: HVACMode.AUTO,
    ToshibaAcMode.COOL: HVACMode.COOL,
    ToshibaAcMode.HEAT: HVACMode.HEAT,
    ToshibaAcMode.DRY: HVACMode.DRY,
    ToshibaAcMode.FAN: HVACMode.FAN_ONLY,
}

HVAC_MODE_TO_TOSHIBA = {v: k for k, v in TOSHIBA_TO_HVAC_MODE.items()}


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add climate for passed config_entry in HA."""
    device_manager = hass.data[DOMAIN][config_entry.entry_id]
    new_devices = []

    devices = await device_manager.get_devices()
    for device in devices:
        climate_entity = ToshibaClimate(device)
        new_devices.append(climate_entity)
    # If we have any new devices, add them
    if new_devices:
        _LOGGER.info("Adding %d %s", len(new_devices), "climates")
        async_add_devices(new_devices)


class ToshibaClimate(ToshibaAcStateEntity, ClimateEntity):
    """Provides a Toshiba climates."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(self, toshiba_device: ToshibaAcDevice):
        """Initialize the climate."""
        super().__init__(toshiba_device)

        self._attr_unique_id = f"{self._device.ac_unique_id}_climate"
        self._attr_name = self._device.name
        self._attr_target_temperature_step = 1
        self._attr_fan_modes = self.get_feature_list(self._device.supported.ac_fan_mode)
        self._attr_swing_modes = self.get_feature_list(
            self._device.supported.ac_swing_mode
        )
        # _LOGGER.debug("###########################")
        # _LOGGER.debug(
        #     "Supported features: ac_mode %s, ac_swing_mode %s, ac_merit_b %s, ac_merit_a %s, ac_energy_report %s",
        #     self._device.supported.ac_mode,
        #     self._device.supported.ac_swing_mode,
        #     self._device.supported.ac_merit_b,
        #     self._device.supported.ac_merit_a,
        #     # self._device.supported.ac_pure_ion,
        #     self._device.supported.ac_energy_report,
        # )

        # # _LOGGER.debug("Test get current power selection %s", self._device.ac_power_selection)
        # # _LOGGER.debug("Test get list of power selections %s", list(ToshibaAcPowerSelection))

        # # ac_power_selection_nice = [pretty_enum_name(e) for e in self._device.supported.ac_swing_mode]

        # # self._device.supported.ac_swing_mode

        # _LOGGER.debug("Test get list of swing modes %s", self.get_feature_list(self._device.supported.ac_swing_mode))

        # # _LOGGER.debug(
        # #     "Test get list of swing modes %s %s",
        # #     self._device.supported.ac_swing_mode,
        # #     list(self._device.supported.ac_swing_mode),
        # # )

        # _LOGGER.debug("###########################")

        # ToshibaEntity.__init__(self, device_id, toshibaconnection, toshibaproject, coordinator)
        # self.entity_id = "climate." + self._name.lower() + "_" + self._device_id

    # default entity properties

    @property
    def is_on(self):
        """Return True if the device is on or completely off."""
        return self._device.ac_status == ToshibaAcStatus.ON

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        set_temperature = kwargs[ATTR_TEMPERATURE]

        # if hasattr(self._device, "ac_merit_a") and ToshibaAcMeritA.HEATING_8C in self._device.supported.ac_merit_a:
        if (
            hasattr(self._device, "ac_merit_a")
            and self._device.ac_merit_a == ToshibaAcMeritA.HEATING_8C
        ):
            # upper limit for target temp
            if set_temperature > 13:
                set_temperature = 13
            # lower limit for target temp
            elif set_temperature < 5:
                set_temperature = 5
        else:
            # upper limit for target temp
            if set_temperature > 30:
                set_temperature = 30
            # lower limit for target temp
            elif set_temperature < 17:
                set_temperature = 17

        await self._device.set_ac_temperature(set_temperature)

    # PRESET MODE / POWER SETTING

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        if self._device.ac_self_cleaning == ToshibaAcSelfCleaning.ON:
            return "cleaning"

        if not self.is_on:
            return None

        return pretty_enum_name(self._device.ac_power_selection)

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
        """
        return self.get_feature_list(self._device.supported.ac_power_selection)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.info("Toshiba Climate setting preset_mode: %s", preset_mode)

        feature_list_id = self.get_feature_list_id(
            list(ToshibaAcPowerSelection), preset_mode
        )
        if feature_list_id is not None:
            await self._device.set_ac_power_selection(feature_list_id)

    @property
    def hvac_mode(self) -> HVACMode | str | None:
        """Return hvac operation ie. heat, cool mode."""
        if not self.is_on:
            return HVACMode.OFF

        return TOSHIBA_TO_HVAC_MODE[self._device.ac_mode]

    @property
    def hvac_modes(self) -> list[HVACMode] | list[str]:
        """Return the list of available hvac operation modes."""
        available_modes = [HVACMode.OFF]
        for toshiba_mode, hvac_mode in TOSHIBA_TO_HVAC_MODE.items():
            if toshiba_mode in self._device.supported.ac_mode:
                available_modes.append(hvac_mode)
        return available_modes

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        _LOGGER.info("Toshiba Climate setting hvac_mode: %s", hvac_mode)

        if hvac_mode == HVACMode.OFF:
            await self._device.set_ac_status(ToshibaAcStatus.OFF)
        else:
            if not self.is_on:
                await self._device.set_ac_status(ToshibaAcStatus.ON)
            await self._device.set_ac_mode(HVAC_MODE_TO_TOSHIBA[hvac_mode])

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        _LOGGER.info("Toshiba Climate setting fan_mode: %s", fan_mode)
        if fan_mode == FAN_OFF:
            await self._device.set_ac_fan_mode(ToshibaAcStatus.OFF)
        else:
            if not self.is_on:
                await self._device.set_ac_status(ToshibaAcStatus.ON)

            feature_list_id = self.get_feature_list_id(list(ToshibaAcFanMode), fan_mode)
            if feature_list_id is not None:
                await self._device.set_ac_fan_mode(feature_list_id)

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return pretty_enum_name(self._device.ac_fan_mode)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        feature_list_id = self.get_feature_list_id(list(ToshibaAcSwingMode), swing_mode)
        if feature_list_id is not None:
            await self._device.set_ac_swing_mode(feature_list_id)

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        return pretty_enum_name(self._device.ac_swing_mode)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.ac_indoor_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._device.ac_temperature

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if (
            hasattr(self._device, "ac_merit_a")
            and self._device.ac_merit_a == ToshibaAcMeritA.HEATING_8C
        ):
            return 5
        return 17

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if (
            hasattr(self._device, "ac_merit_a")
            and self._device.ac_merit_a == ToshibaAcMeritA.HEATING_8C
        ):
            return 13
        return 30

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes.

        Implemented by platform classes. Convention for attribute names
        is lowercase snake_case.
        """
        return {
            "merit_a_feature": self._device.ac_merit_a.name,
            "merit_b_feature": self._device.ac_merit_b.name,
            "air_pure_ion": self._device.ac_air_pure_ion.name,
            "self_cleaning": self._device.ac_self_cleaning.name,
            "outdoor_temperature": self._device.ac_outdoor_temperature,
        }

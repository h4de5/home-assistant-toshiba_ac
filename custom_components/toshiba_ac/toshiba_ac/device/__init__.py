# Copyright 2021 Kamil Sroka

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import asyncio
import logging
import struct
import typing as t
from dataclasses import dataclass

from toshiba_ac.device.fcu_state import ToshibaAcFcuState
from toshiba_ac.device.features import ToshibaAcFeatures
from toshiba_ac.device.properties import (
    ToshibaAcAirPureIon,
    ToshibaAcDeviceEnergyConsumption,
    ToshibaAcFanMode,
    ToshibaAcMeritA,
    ToshibaAcMeritB,
    ToshibaAcMode,
    ToshibaAcPowerSelection,
    ToshibaAcSelfCleaning,
    ToshibaAcStatus,
    ToshibaAcSwingMode,
)
from toshiba_ac.utils import async_sleep_until_next_multiply_of_minutes, pretty_enum_name, ToshibaAcCallback
from toshiba_ac.utils.amqp_api import ToshibaAcAmqpApi, JSONSerializable
from toshiba_ac.utils.http_api import ToshibaAcHttpApi

logger = logging.getLogger(__name__)


class ToshibaAcDeviceError(Exception):
    pass


class ToshibaAcDeviceCallback(ToshibaAcCallback["ToshibaAcDevice"]):
    pass


class ToshibaAcDevice:
    STATE_RELOAD_PERIOD_MINUTES = 30

    def __init__(
        self,
        name: str,
        device_id: str,
        ac_id: str,
        ac_unique_id: str,
        initial_ac_state: str,
        firmware_version: str,
        merit_feature: str,
        ac_model_id: str,
        amqp_api: ToshibaAcAmqpApi,
        http_api: ToshibaAcHttpApi,
    ) -> None:
        self.name = name
        self.device_id = device_id
        self.ac_id = ac_id
        self.ac_unique_id = ac_unique_id
        self.firmware_version = firmware_version
        self.amqp_api = amqp_api
        self.http_api = http_api

        self.fcu_state = ToshibaAcFcuState.from_hex_state(initial_ac_state)

        self.cdu: t.Optional[str] = None
        self.fcu: t.Optional[str] = None
        self._supported = ToshibaAcFeatures.from_merit_string_and_model(merit_feature, ac_model_id)
        self._on_state_changed_callback = ToshibaAcDeviceCallback()
        self._on_energy_consumption_changed_callback = ToshibaAcDeviceCallback()
        self._ac_energy_consumption: t.Optional[ToshibaAcDeviceEnergyConsumption] = None
        self.periodic_reload_state_task: t.Optional[asyncio.Task[None]] = None

        logger.debug(f"[{self.name}] {self.supported}")

    async def connect(self) -> None:
        await self.load_additional_device_info()
        self.periodic_reload_state_task = asyncio.get_running_loop().create_task(self.periodic_state_reload())

    async def shutdown(self) -> None:
        if self.periodic_reload_state_task:
            self.periodic_reload_state_task.cancel()
            await self.periodic_reload_state_task

    async def load_additional_device_info(self) -> None:
        additional_info = await self.http_api.get_device_additional_info(self.ac_id)
        self.cdu = additional_info.cdu
        self.fcu = additional_info.fcu
        await self.on_state_changed_callback(self)

    async def state_reload(self) -> None:
        hex_state = await self.http_api.get_device_state(self.ac_id)
        logger.debug(f"[{self.name}] AC state from HTTP: {hex_state}")
        if self.fcu_state.update(hex_state):
            await self.state_changed()

    async def state_changed(self) -> None:
        logger.info(f"[{self.name}] Current state: {self.fcu_state}")
        await self.on_state_changed_callback(self)

    async def periodic_state_reload(self) -> None:
        while True:
            await async_sleep_until_next_multiply_of_minutes(self.STATE_RELOAD_PERIOD_MINUTES)
            try:
                await self.state_reload()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"State reload failed: {e}")
                pass

    async def handle_cmd_fcu_from_ac(self, payload: dict[str, JSONSerializable]) -> None:
        if not isinstance(payload["data"], str):
            logger.error(f'[{self.name}] malformed AC state from AMQP: {payload["data"]}')
            return
        logger.debug(f'[{self.name}] AC state from AMQP: {payload["data"]}')
        if self.fcu_state.update(payload["data"]):
            await self.state_changed()

    async def handle_cmd_heartbeat(self, payload: dict[str, t.Any]) -> None:
        # Use signed conversion for temperatures, unsigned otherwise.
        hb_data = {k: struct.unpack("b" if "Temp" in k else "B", bytes.fromhex(v))[0] for k, v in payload.items()}
        logger.debug(f"[{self.name}] AC heartbeat from AMQP: {hb_data}")

        if self.fcu_state.update_from_hbt(hb_data):
            await self.state_changed()

    async def handle_update_ac_energy_consumption(self, val: ToshibaAcDeviceEnergyConsumption) -> None:
        if self._ac_energy_consumption != val:
            self._ac_energy_consumption = val

            logger.debug(f"[{self.name}] New energy consumption: {val.energy_wh}Wh")

            await self.on_energy_consumption_changed_callback(self)

    async def send_state_to_ac(self, state: ToshibaAcFcuState) -> None:
        future_state = ToshibaAcFcuState.from_hex_state(self.fcu_state.encode())
        future_state.update(state.encode())

        if future_state.ac_status not in self.supported.ac_status:
            raise ToshibaAcDeviceError(
                f"[{self.name}] Trying to set unsupported ac status: {pretty_enum_name(future_state.ac_status)}"
            )

        if future_state.ac_mode not in self.supported.ac_mode:
            raise ToshibaAcDeviceError(
                f"[{self.name}] Trying to set unsupported ac mode: {pretty_enum_name(future_state.ac_mode)}"
            )

        supported_for_mode = self.supported.for_ac_mode(future_state.ac_mode)

        def warn_if_same_mode(msg: str) -> None:
            if future_state.ac_mode == self.ac_mode:
                logger.warning(msg)

        if future_state.ac_fan_mode not in supported_for_mode.ac_fan_mode:
            warn_if_same_mode(
                f"[{self.name}] Trying to set unsupported ac fan mode: {pretty_enum_name(future_state.ac_fan_mode)}"
            )

            state.ac_fan_mode = ToshibaAcFanMode.NONE

        if future_state.ac_swing_mode not in supported_for_mode.ac_swing_mode:
            warn_if_same_mode(
                f"[{self.name}] Trying to set unsupported ac swing mode: {pretty_enum_name(future_state.ac_swing_mode)}"
            )

            state.ac_swing_mode = ToshibaAcSwingMode.NONE

        if future_state.ac_power_selection not in supported_for_mode.ac_power_selection:
            warn_if_same_mode(
                f"[{self.name}] Trying to set unsupported ac power selection: {pretty_enum_name(future_state.ac_power_selection)}"
            )

            state.ac_power_selection = ToshibaAcPowerSelection.NONE

        if future_state.ac_merit_b not in supported_for_mode.ac_merit_b:
            warn_if_same_mode(
                f"[{self.name}] Trying to set unsupported ac merit b: {pretty_enum_name(future_state.ac_merit_b)}"
            )

            state.ac_merit_b = ToshibaAcMeritB.OFF

        if future_state.ac_merit_a not in supported_for_mode.ac_merit_a:
            warn_if_same_mode(
                f"[{self.name}] Trying to set unsupported ac merit a: {pretty_enum_name(future_state.ac_merit_a)}"
            )

            state.ac_merit_a = ToshibaAcMeritA.OFF

        if future_state.ac_air_pure_ion not in supported_for_mode.ac_air_pure_ion:
            warn_if_same_mode(
                f"[{self.name}] Trying to set unsupported ac merit a: {pretty_enum_name(future_state.ac_air_pure_ion)}"
            )

            state.ac_air_pure_ion = ToshibaAcAirPureIon.NONE

        if future_state.ac_self_cleaning not in supported_for_mode.ac_self_cleaning:
            warn_if_same_mode(
                f"[{self.name}] Trying to set unsupported ac self cleaning: {pretty_enum_name(future_state.ac_self_cleaning)}"
            )

            state.ac_self_cleaning = ToshibaAcSelfCleaning.NONE

        # If we are requesting to turn on, we have to clear self cleaning flag
        if state.ac_status == ToshibaAcStatus.ON and self.ac_self_cleaning == ToshibaAcSelfCleaning.ON:
            state.ac_self_cleaning = ToshibaAcSelfCleaning.OFF

        # In HEATING_8C mode reported temperatures are 16 degrees higher than actual setpoint (only when heating)
        if state.ac_temperature is not None:
            if future_state.ac_mode == ToshibaAcMode.HEAT:
                if future_state.ac_merit_a == ToshibaAcMeritA.HEATING_8C:
                    state.ac_temperature = state.ac_temperature + 16

        logger.debug(f"[{self.name}] Sending command: {state}")

        fcu_to_ac = {
            "sourceId": self.device_id,
            "messageId": "0000000",
            "targetId": [self.ac_unique_id],
            "cmd": "CMD_FCU_TO_AC",
            "payload": {"data": state.encode()},
            "timeStamp": "0000000",
        }

        await self.amqp_api.send_message(str(fcu_to_ac))

    @property
    def ac_status(self) -> ToshibaAcStatus:
        return self.fcu_state.ac_status

    async def set_ac_status(self, val: ToshibaAcStatus) -> None:
        state = ToshibaAcFcuState()
        state.ac_status = val

        await self.send_state_to_ac(state)

    @property
    def ac_mode(self) -> ToshibaAcMode:
        return self.fcu_state.ac_mode

    async def set_ac_mode(self, val: ToshibaAcMode) -> None:
        state = ToshibaAcFcuState()
        state.ac_mode = val

        await self.send_state_to_ac(state)

    @property
    def ac_temperature(self) -> t.Optional[int]:
        # In HEATING_8C mode reported temperatures are 16 degrees higher than actual setpoint (only when heating)

        ret = self.fcu_state.ac_temperature

        if self.fcu_state.ac_mode == ToshibaAcMode.HEAT:
            if self.fcu_state.ac_merit_a == ToshibaAcMeritA.HEATING_8C:
                if isinstance(ret, int):
                    ret = ret - 16

        return ret

    async def set_ac_temperature(self, val: t.Optional[int]) -> None:
        state = ToshibaAcFcuState()
        state.ac_temperature = val

        await self.send_state_to_ac(state)

    @property
    def ac_fan_mode(self) -> ToshibaAcFanMode:
        return self.fcu_state.ac_fan_mode

    async def set_ac_fan_mode(self, val: ToshibaAcFanMode) -> None:
        state = ToshibaAcFcuState()
        state.ac_fan_mode = val

        await self.send_state_to_ac(state)

    @property
    def ac_swing_mode(self) -> ToshibaAcSwingMode:
        return self.fcu_state.ac_swing_mode

    async def set_ac_swing_mode(self, val: ToshibaAcSwingMode) -> None:
        state = ToshibaAcFcuState()
        state.ac_swing_mode = val

        await self.send_state_to_ac(state)

    @property
    def ac_power_selection(self) -> ToshibaAcPowerSelection:
        return self.fcu_state.ac_power_selection

    async def set_ac_power_selection(self, val: ToshibaAcPowerSelection) -> None:
        state = ToshibaAcFcuState()
        state.ac_power_selection = val

        await self.send_state_to_ac(state)

    @property
    def ac_merit_b(self) -> ToshibaAcMeritB:
        return self.fcu_state.ac_merit_b

    async def set_ac_merit_b(self, val: ToshibaAcMeritB) -> None:
        state = ToshibaAcFcuState()
        state.ac_merit_b = val

        await self.send_state_to_ac(state)

    @property
    def ac_merit_a(self) -> ToshibaAcMeritA:
        return self.fcu_state.ac_merit_a

    async def set_ac_merit_a(self, val: ToshibaAcMeritA) -> None:
        state = ToshibaAcFcuState()
        state.ac_merit_a = val

        await self.send_state_to_ac(state)

    @property
    def ac_air_pure_ion(self) -> ToshibaAcAirPureIon:
        return self.fcu_state.ac_air_pure_ion

    async def set_ac_air_pure_ion(self, val: ToshibaAcAirPureIon) -> None:
        state = ToshibaAcFcuState()
        state.ac_air_pure_ion = val

        await self.send_state_to_ac(state)

    @property
    def ac_indoor_temperature(self) -> t.Optional[int]:
        return self.fcu_state.ac_indoor_temperature

    @property
    def ac_outdoor_temperature(self) -> t.Optional[int]:
        return self.fcu_state.ac_outdoor_temperature

    @property
    def ac_self_cleaning(self) -> ToshibaAcSelfCleaning:
        return self.fcu_state.ac_self_cleaning

    @property
    def ac_energy_consumption(self) -> t.Optional[ToshibaAcDeviceEnergyConsumption]:
        return self._ac_energy_consumption

    @property
    def on_state_changed_callback(self) -> ToshibaAcDeviceCallback:
        return self._on_state_changed_callback

    @property
    def on_energy_consumption_changed_callback(self) -> ToshibaAcDeviceCallback:
        return self._on_energy_consumption_changed_callback

    @property
    def supported(self) -> ToshibaAcFeatures:
        return self._supported

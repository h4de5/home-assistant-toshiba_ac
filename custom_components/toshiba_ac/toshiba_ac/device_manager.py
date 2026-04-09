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

import asyncio
import logging
import typing as t

from toshiba_ac.device import ToshibaAcDevice
from toshiba_ac.utils import async_sleep_until_next_multiply_of_minutes, ToshibaAcCallback
from toshiba_ac.utils.amqp_api import ToshibaAcAmqpApi, JSONSerializable
from toshiba_ac.utils.http_api import ToshibaAcHttpApi

logger = logging.getLogger(__name__)


class ToshibaAcDeviceManagerError(Exception):
    pass


class ToshibaAcSasTokenUpdatedCallback(ToshibaAcCallback[str]):
    pass


class ToshibaAcDeviceManager:
    FETCH_ENERGY_CONSUMPTION_PERIOD_MINUTES = 10

    def __init__(
        self,
        username: str,
        password: str,
        device_id: t.Optional[str] = None,
        sas_token: t.Optional[str] = None,
    ):
        self.username = username
        self.password = password
        self.http_api: t.Optional[ToshibaAcHttpApi] = None
        self.reg_info = None
        self.amqp_api: t.Optional[ToshibaAcAmqpApi] = None
        self.device_id = self.username + "_" + (device_id or "3e6e4eb5f0e5aa46")
        self.sas_token = sas_token
        self.devices: t.Dict[str, ToshibaAcDevice] = {}
        self.periodic_fetch_energy_consumption_task: t.Optional[asyncio.Task[None]] = None
        self.lock = asyncio.Lock()
        self.loop = asyncio.get_running_loop()
        self._on_sas_token_updated_callback = ToshibaAcSasTokenUpdatedCallback()

    async def connect(self) -> str:
        try:
            async with self.lock:
                if not self.http_api:
                    self.http_api = ToshibaAcHttpApi(self.username, self.password)
                    await self.http_api.connect()

                if not self.sas_token:
                    self.sas_token = await self.http_api.register_client(self.device_id)

                if not self.amqp_api:
                    self.amqp_api = ToshibaAcAmqpApi(self.sas_token, self.renew_sas_token)
                    self.amqp_api.register_command_handler("CMD_FCU_FROM_AC", self.handle_cmd_fcu_from_ac)
                    self.amqp_api.register_command_handler("CMD_HEARTBEAT", self.handle_cmd_heartbeat)
                    await self.amqp_api.connect()

                return self.sas_token

        except:
            await self.shutdown()
            raise

    async def shutdown(self) -> None:
        async with self.lock:
            tasks: t.List[t.Awaitable[None]] = []

            if self.periodic_fetch_energy_consumption_task:
                self.periodic_fetch_energy_consumption_task.cancel()
                tasks.append(self.periodic_fetch_energy_consumption_task)

            tasks.extend(device.shutdown() for device in self.devices.values())

            if self.amqp_api:
                tasks.append(self.amqp_api.shutdown())

            if self.http_api:
                tasks.append(self.http_api.shutdown())

            try:
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    def raise_all_errors(res: t.Any, *args: t.Any) -> None:
                        try:
                            if isinstance(res, Exception):
                                raise res
                        finally:
                            if args:
                                raise_all_errors(*args)

                    raise_all_errors(*results)
            finally:
                self.periodic_fetch_energy_consumption_task = None
                self.amqp_api = None
                self.http_api = None

    async def periodic_fetch_energy_consumption(self) -> None:
        while True:
            await async_sleep_until_next_multiply_of_minutes(self.FETCH_ENERGY_CONSUMPTION_PERIOD_MINUTES)
            try:
                await self.fetch_energy_consumption()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Fetching energy consumption failed: {e}")
                pass

    async def fetch_energy_consumption(self) -> None:
        if not self.http_api:
            raise ToshibaAcDeviceManagerError("Not connected")

        consumptions = await self.http_api.get_devices_energy_consumption(
            [ac_unique_id for ac_unique_id in self.devices.keys()]
        )

        logger.debug(
            "Power consumption for devices: {"
            + " ,".join(
                f"{self.devices[ac_unique_id].name}: {consumption.energy_wh}Wh"
                for ac_unique_id, consumption in consumptions.items()
            )
            + "}"
        )

        updates = []

        for ac_unique_id, consumption in consumptions.items():
            update = self.devices[ac_unique_id].handle_update_ac_energy_consumption(consumption)
            updates.append(update)

        await asyncio.gather(*updates)

    async def get_devices(self) -> t.List[ToshibaAcDevice]:
        if not self.http_api or not self.amqp_api:
            raise ToshibaAcDeviceManagerError("Not connected")

        async with self.lock:
            if not self.devices:
                devices_info = await self.http_api.get_devices()

                logger.debug(
                    "Found devices: {"
                    + " ,".join(
                        f"{device.ac_name}: {{MeritFeature: {device.merit_feature}, "
                        + f"Model id: {device.ac_model_id}, "
                        + f"Firmware version: {device.firmware_version}, "
                        + f"Initial state: {device.initial_ac_state}}}"
                        for device in devices_info
                    )
                )

                connects = []

                for device_info in devices_info:
                    device = ToshibaAcDevice(
                        device_info.ac_name,
                        self.device_id,
                        device_info.ac_id,
                        device_info.ac_unique_id,
                        device_info.initial_ac_state,
                        device_info.firmware_version,
                        device_info.merit_feature,
                        device_info.ac_model_id,
                        self.amqp_api,
                        self.http_api,
                    )

                    connects.append(device.connect())

                    logger.debug(f"Adding device {device.name}")

                    self.devices[device.ac_unique_id] = device

                await asyncio.gather(*connects)

                if any(device.supported.ac_energy_report for device in self.devices.values()):
                    await self.fetch_energy_consumption()

                    if not self.periodic_fetch_energy_consumption_task:
                        self.periodic_fetch_energy_consumption_task = asyncio.get_running_loop().create_task(
                            self.periodic_fetch_energy_consumption()
                        )

            return list(self.devices.values())

    async def renew_sas_token(self) -> str:
        if self.http_api:
            self.sas_token = await self.http_api.register_client(self.device_id)
            await self.on_sas_token_updated_callback(self.sas_token)
            return self.sas_token

        raise ToshibaAcDeviceManagerError("Not connected")

    def handle_cmd_fcu_from_ac(
        self,
        source_id: str,
        message_id: str,
        target_id: list[JSONSerializable],
        payload: dict[str, JSONSerializable],
        timestamp: str,
    ) -> None:
        asyncio.run_coroutine_threadsafe(self.devices[source_id].handle_cmd_fcu_from_ac(payload), self.loop).result()

    def handle_cmd_heartbeat(
        self,
        source_id: str,
        message_id: str,
        target_id: list[JSONSerializable],
        payload: dict[str, JSONSerializable],
        timestamp: str,
    ) -> None:
        asyncio.run_coroutine_threadsafe(self.devices[source_id].handle_cmd_heartbeat(payload), self.loop).result()

    @property
    def on_sas_token_updated_callback(self) -> ToshibaAcSasTokenUpdatedCallback:
        return self._on_sas_token_updated_callback

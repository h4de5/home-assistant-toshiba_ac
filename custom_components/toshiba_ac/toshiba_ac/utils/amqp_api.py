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

import logging
import typing as t

from azure.iot.device import Message, MethodRequest, MethodResponse
from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device.custom_typing import JSONSerializable

logger = logging.getLogger(__name__)


class ToshibaAcAmqpApi:
    COMMANDS = ["CMD_FCU_FROM_AC", "CMD_HEARTBEAT"]
    _HANDLER_TYPE = t.Callable[[str, str, list[JSONSerializable], dict[str, JSONSerializable], str], None]

    def __init__(self, sas_token: str, new_sas_token_required_callback: t.Callable[[], t.Awaitable[str]]) -> None:
        self.sas_token = sas_token
        self.handlers: t.Dict[str, ToshibaAcAmqpApi._HANDLER_TYPE] = {}

        self.device = IoTHubDeviceClient.create_from_sastoken(self.sas_token)
        self.device.on_method_request_received = self.method_request_received
        self.device.on_new_sastoken_required = self.new_sas_token_required  # type: ignore
        self.on_new_sastoken_required_callback = new_sas_token_required_callback

    async def connect(self) -> None:
        await self.device.connect()

    async def shutdown(self) -> None:
        await self.device.shutdown()

    def register_command_handler(self, command: str, handler: ToshibaAcAmqpApi._HANDLER_TYPE) -> None:
        if command not in self.COMMANDS:
            raise AttributeError(f'Unknown command: {command}, should be one of {" ".join(self.COMMANDS)}')
        self.handlers[command] = handler

    async def new_sas_token_required(self) -> None:
        logger.info(f"SAS token is about to expire")
        new_token = await self.on_new_sastoken_required_callback()
        await self.device.update_sastoken(new_token)

    async def method_request_received(self, method_data: MethodRequest) -> None:
        if method_data.name != "smmobile":
            return logger.info(f"Unknown method name: {method_data.name} full data: {method_data.payload}")

        if not isinstance(method_data.payload, dict):
            # Currently supported payloads are dicts
            return
        data = method_data.payload
        command = data["cmd"]
        if not isinstance(command, str):
            return
        handler = self.handlers.get(command, None)

        if handler:
            source_id = data["sourceId"]
            message_id = data["messageId"]
            target_id = data["targetId"]
            payload = data["payload"]
            time_stamp = data["timeStamp"]

            if not isinstance(source_id, str):
                logger.error(f'Malformed sourceId in command {command} with payload: {data["payload"]}')
                return

            if not isinstance(message_id, str):
                logger.error(f'Malformed messageId in command {command} with payload: {data["payload"]}')
                return

            if not isinstance(target_id, list):
                logger.error(f'Malformed targetId in command {command} with payload: {data["payload"]}')
                return

            if not isinstance(payload, dict):
                logger.error(f'Malformed payload in command {command} with payload: {data["payload"]}')
                return

            if not isinstance(time_stamp, str):
                logger.error(f'Malformed timeStamp in command {command} with payload: {data["payload"]}')
                return

            handler(source_id, message_id, target_id, payload, time_stamp)

            await self.device.send_method_response(MethodResponse.create_from_method_request(method_data, 0))
        else:
            logger.info(f'Unhandled command {command} with payload: {data["payload"]}')

    async def send_message(self, message: str) -> None:
        msg = Message(str(message))  # type: ignore
        msg.custom_properties["type"] = "mob"
        msg.content_type = "application/json"
        msg.content_encoding = "utf-8"
        await self.device.send_message(msg)

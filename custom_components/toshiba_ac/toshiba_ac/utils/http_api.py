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

import datetime
import logging
import typing as t
from dataclasses import dataclass

import aiohttp
from toshiba_ac.device.properties import ToshibaAcDeviceEnergyConsumption
from toshiba_ac.utils import retry_with_timeout, retry_on_exception

logger = logging.getLogger(__name__)


@dataclass
class ToshibaAcDeviceInfo:
    ac_id: str
    ac_unique_id: str
    ac_name: str
    initial_ac_state: str
    firmware_version: str
    merit_feature: str
    ac_model_id: str


@dataclass
class ToshibaAcDeviceAdditionalInfo:
    cdu: t.Optional[str]
    fcu: t.Optional[str]


class ToshibaAcHttpApiError(Exception):
    pass


class ToshibaAcHttpApiAuthError(ToshibaAcHttpApiError):
    pass


class ToshibaAcHttpApi:
    BASE_URL = "https://mobileapi.toshibahomeaccontrols.com"
    LOGIN_PATH = "/api/Consumer/Login"
    REGISTER_PATH = "/api/Consumer/RegisterMobileDevice"
    AC_MAPPING_PATH = "/api/AC/GetConsumerACMapping"
    AC_STATE_PATH = "/api/AC/GetCurrentACState"
    AC_ENERGY_CONSUMPTION_PATH = "/api/AC/GetGroupACEnergyConsumption"

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self.access_token: t.Optional[str] = None
        self.access_token_type: t.Optional[str] = None
        self.consumer_id: t.Optional[str] = None
        self.session: t.Optional[aiohttp.ClientSession] = None

    @retry_with_timeout(timeout=5, retries=3, backoff=60)
    @retry_on_exception(exceptions=ToshibaAcHttpApiError, retries=3, backoff=60)
    async def request_api(
        self,
        path: str,
        get: dict[str, str] | None = None,
        post: t.Mapping[str, str | t.Sequence[str]] | None = None,
        headers: t.Any = None,
    ) -> t.Any:
        if not isinstance(headers, dict):
            if not self.access_token_type or not self.access_token:
                raise ToshibaAcHttpApiError("Failed to send request, missing access token")

            headers = {}
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = self.access_token_type + " " + self.access_token
            headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )

        url = self.BASE_URL + path

        if not self.session:
            self.session = aiohttp.ClientSession()

        method_args = {"params": get, "headers": headers}

        if post:
            logger.debug(f"Sending POST to {url}")
            method_args["json"] = post
            method = self.session.post
        else:
            logger.debug(f"Sending GET to {url}")
            method = self.session.get

        async with method(url, **method_args) as response:
            logger.debug(f"Response code: {response.status}")

            if response.status == 200:
                json = await response.json()

                if json["IsSuccess"]:
                    return json["ResObj"]
                else:
                    if json["StatusCode"] == "InvalidUserNameorPassword":
                        raise ToshibaAcHttpApiAuthError(json["Message"])

                    raise ToshibaAcHttpApiError(json["Message"])

            raise ToshibaAcHttpApiError(await response.text())

    async def connect(self) -> None:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }
        post = {"Username": self.username, "Password": self.password}

        res = await self.request_api(self.LOGIN_PATH, post=post, headers=headers)

        self.access_token = res["access_token"]
        self.access_token_type = res["token_type"]
        self.consumer_id = res["consumerId"]

    async def shutdown(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None

    async def get_devices(self) -> t.List[ToshibaAcDeviceInfo]:
        if not self.consumer_id:
            raise ToshibaAcHttpApiError("Failed to send request, missing consumer id")

        get = {"consumerId": self.consumer_id}

        res = await self.request_api(self.AC_MAPPING_PATH, get=get)

        devices = []

        for group in res:
            for device in group["ACList"]:
                devices.append(
                    ToshibaAcDeviceInfo(
                        device["Id"],
                        device["DeviceUniqueId"],
                        device["Name"],
                        device["ACStateData"],
                        device["FirmwareVersion"],
                        device["MeritFeature"],
                        device["ACModelId"],
                    )
                )

        return devices

    async def get_device_state(self, ac_id: str) -> str:
        get = {
            "ACId": ac_id,
        }

        res = await self.request_api(self.AC_STATE_PATH, get=get)

        if "ACStateData" not in res:
            raise ToshibaAcHttpApiError("Missing ACStateData in response")

        if not isinstance(res["ACStateData"], str):
            raise ToshibaAcHttpApiError("Malformed ACStateData in response")

        return res["ACStateData"]

    async def get_device_additional_info(self, ac_id: str) -> ToshibaAcDeviceAdditionalInfo:
        get = {
            "ACId": ac_id,
        }

        res = await self.request_api(self.AC_STATE_PATH, get=get)

        try:
            cdu = res["Cdu"]["model_name"]
        except (KeyError, TypeError):
            cdu = None

        try:
            fcu = res["Fcu"]["model_name"]
        except (KeyError, TypeError):
            fcu = None

        return ToshibaAcDeviceAdditionalInfo(cdu=cdu, fcu=fcu)

    async def get_devices_energy_consumption(
        self, ac_unique_ids: t.List[str]
    ) -> t.Dict[str, ToshibaAcDeviceEnergyConsumption]:
        year = int(datetime.datetime.now().year)
        since = datetime.datetime(year, 1, 1).astimezone(datetime.timezone.utc)

        post = {
            "ACDeviceUniqueIdList": ac_unique_ids,
            "FromUtcTime": str(year),
            "Timezone": "UTC",
            "ToUtcTime": str(year + 1),
            "Type": "EnergyYear",
        }

        res = await self.request_api(self.AC_ENERGY_CONSUMPTION_PATH, post=post)

        ret = {}

        try:
            for ac in res:
                try:
                    consumption = sum(int(consumption["Energy"]) for consumption in ac["EnergyConsumption"])
                    ret[ac["ACDeviceUniqueId"]] = ToshibaAcDeviceEnergyConsumption(consumption, since)
                except (KeyError, ValueError):
                    pass
        except TypeError:
            pass

        return ret

    async def register_client(self, device_id: str) -> str:
        post = {"DeviceID": device_id, "DeviceType": "1", "Username": self.username}

        res = await self.request_api(self.REGISTER_PATH, post=post)

        if "SasToken" not in res:
            raise ToshibaAcHttpApiError("Missing SasToken in response")

        if not isinstance(res["SasToken"], str):
            raise ToshibaAcHttpApiError("Malformed SasToken in response")

        return res["SasToken"]

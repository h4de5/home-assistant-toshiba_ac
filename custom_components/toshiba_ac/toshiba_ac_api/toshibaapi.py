"""Connection to toshiba ac web service."""

# import json as Json
import datetime
import logging
from typing import List, Tuple
from urllib.parse import urlencode
import requests
from requests.exceptions import HTTPError
from const import BASE_URL, LOGIN_PATH, MAPPING_PATH, PROGRAM_GET_PATH, PROGRAM_SET_PATH, PROGRAM_GROUP_SET_PATH, STATUS_PATH


_LOGGER = logging.getLogger(__name__)


class ToshibaApiError(Exception):
    """Toshiba API General Exception."""

    err_args = []

    def __init__(self, *args, **kwargs):
        """Init a default Toshiba api exception."""
        self.err_args = args
        super().__init__(*args)

    def __str__(self):
        """Stringify exception text."""
        return f"{self.__class__.__name__}: {self.err_args[0]}" % self.err_args[1:]


class ToshibaConfigError(ToshibaApiError):
    """Toshiba API Configuration Exception."""

    pass


class ToshibaConnectionError(ToshibaApiError):
    """Toshiba API Connection Exception."""

    pass


class ToshibaACApi:
    """Link to communicate with the Toshiba webserver."""

    # private - from config
    __username = ""
    __password = ""
    timeout = 8

    # private - from api
    access_token = ""
    _expires_in = ""
    consumerId = ""
    _countryId = 0
    _consumerMasterId = ""
    last_update = None

    def __init__(
        self,
        username=None,
        password=None,
    ):
        """Prepare connections instance for toshiba web service."""
        _LOGGER.info("Toshiba link initialized")

        if username is not None:
            self.__username = username
        if password is not None:
            self.__password = password

    def check_login(self):
        """Check if session is available - if not, aquire a new one."""
        if not self.access_token:  # and _expires_in > now()
            self.login()

        return self.access_token is not None

    def login(self):
        """Call login and store the session id."""
        headers = {
            "Content-Type": "application/json",
        }

        if not self.__username or not self.__password:
            raise ToshibaApiError("Missing credentials - please set username and password")

        post = {"Username": self.__username, "Password": self.__password}

        json = self._request_toshiba_api(LOGIN_PATH, None, post, headers)
        if json is not None:
            self.access_token = json["ResObj"]["access_token"]
            self.consumerId = json["ResObj"]["consumerId"].lower()
            self._countryId = json["ResObj"]["countryId"]
            self._consumerMasterId = json["ResObj"]["consumerMasterId"].lower()
            self._expires_in = json["ResObj"]["expires_in"]
        else:
            raise ToshibaConfigError("Login failed - check username and password")

        return json

    def read_mapping(self) -> Tuple[dict, dict]:
        """Get groups and devices from consumer mapping."""
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + self.access_token}

        if not self.consumerId:
            raise ToshibaApiError("Missing consumer id - please login first")

        get = {
            "consumerId": self.consumerId,
        }

        # groups: List[ToshibaACGroup] = []
        # devices: List[ToshibaACDevice] = []
        groups: dict = {}
        devices: dict = {}

        json = self._request_toshiba_api(MAPPING_PATH, get, None, headers)
        if json is not None:
            for group in json["ResObj"]:
                # each device could be in multiple groups, therefor normal lists are not enough
                groups[group["GroupId"].lower()] = group
                # groups.append(ToshibaACGroup(group))
                if group["ACList"]:
                    for device in group["ACList"]:
                        # link device into given group
                        device["GroupId"] = group["GroupId"]
                        device["ConsumerId"] = group["ConsumerId"]
                        devices[device["Id"].lower()] = device

        else:
            # _LOGGER.warning("Empty Response from toshiba service")
            raise ToshibaConnectionError("Mapping failed - check connection to Toshiba services")

        return [groups, devices]

    def get_device_status(self, device_id: int):
        """Get the status of a single device."""
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + self.access_token}

        if not device_id:
            raise ToshibaApiError("Missing device or device id to request state")

        get = {
            "ACId": device_id,
        }

        json = self._request_toshiba_api(STATUS_PATH, get, None, headers)
        if json is not None:
            item = self.get_device_by_id(json["ResObj"]["ACId"])
            if item:
                item.parse_status(json["ResObj"])
            else:
                _LOGGER.warning("Cound not find device with id [%s] - please run mapping first" % (device_id))
        else:
            # _LOGGER.warning("Empty Response from toshiba service")
            raise ToshibaConnectionError("Device Status update failed - check connection to Toshiba services")

        return json

    def get_program(self) -> Tuple[List[dict], List[dict]]:
        """Get the program setting of all devices and groups."""
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + self.access_token}

        if not self.consumerId:
            raise ToshibaApiError("Missing consumer id - please login first")

        get = {
            "consumerId": self.consumerId,
        }

        json: dict = self._request_toshiba_api(PROGRAM_GET_PATH, get, None, headers)
        if json is not None:
            group_programs: List = []
            device_programs: List = []

            for program in json["ResObj"]["ACGroupProgramSettings"]:
                group_programs.append(program)
                # group = self.get_group_by_id(program["GroupId"])
                # if group:
                #     group.set_program(program)

                for program_ac in program["ACProgramSettingList"]:
                    device_programs.append(program_ac)
                    # device = self.get_device_by_id(program_ac["ACId"])
                    # if device:
                    #     device.set_program(program_ac)

            return group_programs, device_programs

        else:
            # _LOGGER.warning("Empty Response from toshiba service")
            raise ToshibaConnectionError("Device Status update failed - check connection to Toshiba services")

    def set_program(self, program: dict, device_id: str = None, group_id: str = None) -> bool:
        """Set a given program for a selected device or group."""
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + self.access_token}

        if not self.consumerId:
            raise ToshibaApiError("Missing consumer id - please login first")

        # print("send new program", Json.dumps(program, indent=2, sort_keys=True))
        post = program

        json: dict = None

        if device_id is not None:
            json = self._request_toshiba_api(PROGRAM_SET_PATH, None, post, headers)
        elif group_id is not None:
            json = self._request_toshiba_api(PROGRAM_GROUP_SET_PATH, None, post, headers)

        if json is not None:
            # print("response from program_set_path: ", json)
            return True
        else:
            # _LOGGER.warning("Empty Response from toshiba service")
            raise ToshibaConnectionError("Mapping failed - check connection to Toshiba services")
        return False

    def switch(self, when: datetime = None, on: bool = True, setting: str = "ffffffffff", part: int = 1) -> dict:
        """Create a program if necessary, and switch AC on or off with given program setting."""
        pass

    def _request_toshiba_api(self, path, get=None, post=None, headers=None) -> dict:
        """Call web service using post variables."""
        try:
            json = self._request(BASE_URL + path, get, post, headers)

            if json is not None and json is not False:
                if json["IsSuccess"] is True:
                    return json
                else:
                    _LOGGER.warning("Call to %s failed - %s [%s]" % (path, json["Message"], json["StatusCode"]))
                    # raise ToshibaConfigError("Call to %s failed - %s #%s" % (path, json['Message'], json['StatusCode']))
            else:
                # _LOGGER.warning("Empty Response from Toshiba Web Service")
                _LOGGER.warning("Empty Response from API call - check Connection to Toshiba services")
                # raise ToshibaConnectionError("API Call failed - check Connection to Toshiba services")
        except BaseException as err:
            raise ToshibaConnectionError("Exception parsing api response: %s - %s", err, str(json))

        return None

    def _request(self, url, get=None, post=None, headers=None) -> dict:
        """Call url using post variables."""
        # _LOGGER.info("request to " + url)
        try:
            # connection, read timeout
            timeouts = (int(self.timeout / 2), self.timeout)

            if get is not None:
                url = url + "?" + urlencode(get, doseq=False)

            if post is None:
                response = requests.get(url, headers=headers, timeout=timeouts)
            else:
                response = requests.post(
                    url,
                    json=post,
                    #  data=json.dumps(post),
                    headers=headers,
                    timeout=timeouts,
                )

            # If the response was successful, no Exception will be raised
            response.raise_for_status()

        except HTTPError as http_err:
            _LOGGER.error("HTTP error occurred: %s", str(http_err))
            return False
        # except ReadTimeoutError:
        except requests.exceptions.Timeout:
            _LOGGER.error("HTTP timeout occurred")
            return False
        except BaseException as err:
            _LOGGER.error("Error occurred: %s", str(err))
            return False
        else:
            if response is None:
                _LOGGER.warning("Empty Response from toshiba service")
                return ""
            else:
                return response.json()

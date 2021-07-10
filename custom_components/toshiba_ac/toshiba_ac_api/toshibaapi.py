"""Connection to toshiba ac web service."""

import datetime
import logging
from enum import Enum
from typing import Dict, List
from urllib.parse import urlencode

import requests
# import json
from requests.exceptions import HTTPError

from const import (BASE_URL, LOGIN_PATH, MAPPING_PATH, PROGRAM_GET_PATH,
                   STATUS_PATH)

# PROGRAM_SET_PATH)

# DOMAIN
# DEVICE_PATH,
# MAPPING_PATH,
# ,
# SETTINGS_PATH,
# CONSUMER_PATH,
# SCHEDULER_PATH


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
        return f'{self.__class__.__name__}: {self.err_args[0]}' % self.err_args[1:]


class ToshibaConfigError(ToshibaApiError):
    """Toshiba API Configuration Exception."""

    pass


class ToshibaConnectionError(ToshibaApiError):
    """Toshiba API Connection Exception."""

    pass


class ToshibaACEnums(Enum):
    """Toshiba AC constants and enumerations."""

    def __str__(self):
        """Convert object to string."""
        # return str(self.value)
        return '%s' % self.value

    ON = 30
    OFF = 31


class ToshibaACProgramm():
    """Toshiba AC program settings."""

    _state: str
    _days: Dict
    _scheduler_status: str
    _dst: Dict[str, str]

    # # group
    # _time: str
    # _timeZone: str

    # # device
    # _merit_feature: str
    # _ac_id

    # _programSetting:
    # _ACProgramSettingList

    # _mon: str[]
    # _tue: str
    # _wed: str
    # _thu: str
    # _fri: str
    # _sat: str
    # _sun: str

    def __init__(self, json):
        """Create an object from api response."""
        self.parse(json)

    def parse(self, json):
        """Read out necessary information from json object."""
        if 'ACStateDataForProgram' in json:
            self._state = json['ACStateDataForProgram']
        if 'schedulerStatus' in json:
            self._scheduler_status = json['schedulerStatus']
        if 'dst' in json:
            self._dst = json['dst']
        if 'programSetting' in json:
            self._days = json['programSetting']
            # for day in json['programSetting']:
            #     self._days.append(day)

    def __str__(self) -> str:
        """Convert object to string."""
        result = ''
        for day in self._days:
            setting = self._days[day]

            result += "[%s: " % day
            for p in range(1, 5):
                state = setting['p' + str(p)]
                result += "%s%s" % (self._get_date(state), self._get_onoff(state))
            result += "]"

        return result

    def switch(self, when: datetime = None, on: bool = True, setting: str = "ffffffffff", part: int = 1) -> Dict:
        """Create program to switch AC on or off with a given program setting."""
        program: str = ''
        if when is None:
            when = datetime.datetime.now()
        program = when.strftime("%H%M")

        if on:
            program = program + str(ToshibaACEnums.ON)
        else:
            program = program + str(ToshibaACEnums.OFF)
        program = program + setting[:10]

        if part < 1 or part > 4:
            part = 1

        # 113031ffffffffff
        self._days[when.strftime("%A")]['p' + str(part)] = program
        return self._days

    def reset(self, today=True, week=False, day=str) -> Dict:
        """Reset program for a given day or the whole week."""
        if today:
            day = datetime.datetime.now().strftime("%A")
        if day in self._days:
            self._days[day] = {'p1': '', 'p2': '', 'p3': '', 'p4': ''}
        if week:
            for day in self._days:
                self._days[day] = {'p1': '', 'p2': '', 'p3': '', 'p4': ''}

    def __json__(self) -> str:
        """Return the days object of the program."""
        return self._days

    def _get_date(self, state) -> str:
        """Return the time part from a state."""
        if state and len(state) >= 4:
            return state[0:2] + ':' + state[2:4]
        else:
            return ''

    def _get_onoff(self, state) -> str:
        """Return if the state is on or off or not set."""
        if state and len(state) >= 6:
            if state[4:6] == str(ToshibaACEnums.ON):
                return '↑'
            elif state[4:6] == str(ToshibaACEnums.OFF):
                return '↓'
            else:
                return ''
        else:
            return ''


class ToshibaACGroup():
    """Toshiba AC Group."""

    group_id: str
    group_name: str
    _program: ToshibaACProgramm

    def __init__(self, json):
        """Create an object from api response."""
        self.parse(json)

    def parse(self, json):
        """Read out necessary information from json object."""
        self.group_id = json['GroupId']
        self.group_name = json['GroupName']

    def set_program(self, json):
        """Set program from api response."""
        self._program = ToshibaACProgramm(json)

    def get_program(self) -> ToshibaACProgramm:
        """Return program as json object."""
        return self._program

    def __str__(self):
        """Convert object to string."""
        return("%s #%s" % (self.group_name, self.group_id))


class ToshibaACDevice():
    """Toshiba AC Device."""

    group_id: str = ''
    ac_id: str = ''
    device_unique_id: str
    name: str
    state: str
    merit_feature: str
    _program: ToshibaACProgramm

    def __init__(self, json: dict = None, group_id: str = None):
        """Create an object from api response and a corresponding group id."""
        self.parse(json)
        self.group_id = group_id

    def parse_status(self, json):
        """Read out necessary information from json object."""
        self.ac_id = json['ACId'].lower()
        self.device_unique_id = json['ACDeviceUniqueId'].lower()
        self.state = json['ACStateData'].lower()
        self.merit_feature = json['MeritFeature'].lower()
        self._last_update = json['UpdatedDate']

    def parse(self, json):
        """Read out necessary information from json object."""
        self.ac_id = json['Id'].lower()
        self.device_unique_id = json['DeviceUniqueId'].lower()
        self.name = json['Name']
        self.state = json['ACStateData'].lower()
        self.merit_feature = json['MeritFeature'].lower()
        self._last_update = json['CreatedDate']

    def set_program(self, json):
        """Set program from api response."""
        self._program = ToshibaACProgramm(json)

    def get_program(self) -> ToshibaACProgramm:
        """Return program as json object."""
        return self._program

    def __str__(self):
        """Convert object to string."""
        return ("%s #%s: %s - last Update: %s" % (self.name, self.ac_id, self.state, self._last_update))


class ToshibaApi():
    """Link to communicate with the Toshiba webserver."""

    # private - from config
    __username = ''
    __password = ''
    timeout = 8

    # private - from api
    access_token = ""
    _expires_in = ""
    consumerId = ""
    _countryId = 0
    _consumerMasterId = ""
    last_update = None

    groups: List[ToshibaACGroup] = []
    devices: List[ToshibaACDevice] = []

    def __init__(
            self,
            username=None,
            password=None,):
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
            'Content-Type': 'application/json',
        }

        if not self.__username or not self.__password:
            raise ToshibaApiError("Missing credentials - please set username and password")

        post = {
            'Username': self.__username,
            'Password': self.__password
        }

        json = self._request_toshiba_api(LOGIN_PATH, None, post, headers)
        if json is not None:
            self.access_token = json['ResObj']['access_token']
            self.consumerId = json['ResObj']['consumerId'].lower()
            self._countryId = json['ResObj']['countryId']
            self._consumerMasterId = json['ResObj']['consumerMasterId'].lower()
            self._expires_in = json['ResObj']['expires_in']
        else:
            raise ToshibaConfigError("Login failed - check username and password")

        return json

    def get_mapping(self):
        """Get groups and devices from consumer mapping."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.access_token
        }

        if not self.consumerId:
            raise ToshibaApiError("Missing consumer id - please login first")

        get = {
            'consumerId': self.consumerId,
        }

        json = self._request_toshiba_api(MAPPING_PATH, get, None, headers)
        if json is not None:
            for group in json['ResObj']:
                self.groups.append(ToshibaACGroup(group))
                if group['ACList']:
                    for device in group['ACList']:
                        self.devices.append(ToshibaACDevice(device, group['GroupId']))
        else:
            _LOGGER.warning("Empty Response from toshiba service")
            raise ToshibaConnectionError("Mapping failed - check connection to Toshiba services")

        return json

    def get_device_status(self, device: ToshibaACDevice = None, device_id: int = None):
        """Get the status of a single device."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.access_token
        }

        dev = device.ac_id if device is not None else device_id

        if not dev:
            raise ToshibaApiError("Missing device or device id to request state")

        get = {
            'ACId': dev,
        }

        json = self._request_toshiba_api(STATUS_PATH, get, None, headers)
        if json is not None:
            item = self.get_device_by_id(json['ResObj']['ACId'])
            if item:
                item.parse_status(json['ResObj'])
            else:
                _LOGGER.warning("Cound not find device with id [%s] - please run mapping first" % (dev))
        else:
            _LOGGER.warning("Empty Response from toshiba service")
            raise ToshibaConnectionError("Device Status update failed - check connection to Toshiba services")

        return json

    def get_program(self):
        """Get the program setting of all devices and groups."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.access_token
        }

        if not self.consumerId:
            raise ToshibaApiError("Missing consumer id - please login first")

        get = {
            'consumerId': self.consumerId,
        }

        json = self._request_toshiba_api(PROGRAM_GET_PATH, get, None, headers)
        if json is not None:
            for program in json['ResObj']['ACGroupProgramSettings']:
                group = self.get_group_by_id(program['GroupId'])
                if group:
                    group.set_program(program)

                for program_ac in program['ACProgramSettingList']:
                    device = self.get_device_by_id(program_ac['ACId'])
                    if device:
                        device.set_program(program_ac)

        else:
            _LOGGER.warning("Empty Response from toshiba service")
            raise ToshibaConnectionError("Device Status update failed - check connection to Toshiba services")

        return json

    def set_program(self, program: ToshibaACProgramm, device_id: str = None, group_id: str = None) -> bool:
        """Set a given program for a selected device or group."""
        if device_id is not None:
            device = self.get_device_by_id(device_id)
            if device:
                device.set_program(program)
        if group_id is not None:
            group = self.get_group_by_id(group_id)
            if group:
                group.set_program(program)
        # TODO - send to api

    def get_device_by_id(self, device_id) -> ToshibaACGroup:
        """Return device of mapped devices by id."""
        for item in self.devices:
            if item.ac_id.lower() == device_id.lower():
                return item
        return None

    def get_group_by_id(self, group_id) -> ToshibaACDevice:
        """Return group of mapped groups by id."""
        for group in self.groups:
            if group.group_id.lower() == group_id.lower():
                return group
        return None

    def _request_toshiba_api(self, path, get=None, post=None, headers=None):
        """Call web service using post variables."""
        try:
            json = self._request(BASE_URL + path, get, post, headers)

            if json is not None and json is not False:
                # print("json", json)
                if json['IsSuccess'] is True:
                    return json
                else:
                    _LOGGER.warning("Call to %s failed - %s [%s]" % (path, json['Message'], json['StatusCode']))
                    # raise ToshibaConfigError("Call to %s failed - %s #%s" % (path, json['Message'], json['StatusCode']))
            else:
                # _LOGGER.warning("Empty Response from Toshiba Web Service")
                _LOGGER.warning("Empty Response from API call - check Connection to Toshiba services")
                # raise ToshibaConnectionError("API Call failed - check Connection to Toshiba services")
        except BaseException as err:
            raise ToshibaConnectionError("Exception parsing api response: %s - %s", err, str(json))

        return None

    def _request(
            self,
            url,
            get=None,
            post=None,
            headers=None):
        """Call url using post variables."""
        # _LOGGER.info("request to " + url)
        try:
            # connection, read timeout
            timeouts = (int(self.timeout / 2), self.timeout)

            if get is not None:
                url = url + '?' + urlencode(get, doseq=False)

            if post is None:
                response = requests.get(url,
                                        headers=headers,
                                        timeout=timeouts)
            else:
                response = requests.post(url,
                                         json=post,
                                         #  data=json.dumps(post),
                                         headers=headers,
                                         timeout=timeouts)

            # If the response was successful, no Exception will be raised
            response.raise_for_status()

        except HTTPError as http_err:
            _LOGGER.error('HTTP error occurred: %s', str(http_err))
            return False
        # except ReadTimeoutError:
        except requests.exceptions.Timeout:
            _LOGGER.error('HTTP timeout occurred')
            return False
        except BaseException as err:
            _LOGGER.error('Error occurred: %s', str(err))
            return False
        else:
            return response.json()

        return None

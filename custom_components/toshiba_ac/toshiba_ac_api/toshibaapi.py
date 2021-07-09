""""Connection to toshiba ac web service."""

import logging
import requests
# import json
from requests.exceptions import HTTPError
from urllib.parse import urlencode
from .const import (
    BASE_URL,
    LOGIN_PATH,
    MAPPING_PATH,
    STATUS_PATH,
    PROGRAM_GET_PATH)
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


class ToshibaACProgramm():
    "Toshiba AC program settings"

    _state: str
    _days: {}
    _scheduler_status: str
    _dst: {}

    # _mon: str[]
    # _tue: str
    # _wed: str
    # _thu: str
    # _fri: str
    # _sat: str
    # _sun: str

    def __init__(self, json):
        self.parse(json)

    def parse(self, json):
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

    def __str__(self):
        result = ''
        for day in self._days:
            setting = self._days[day]
            # print('found day', day, self._days[day])
            # TODO - reformat to day: 11:00-12:00-15:00-19:00 ..
            result = result + "[%s: %s-%s-%s-%s]" % \
                (day,
                    self.get_date(setting['p1']),
                    self.get_date(setting['p2']),
                    self.get_date(setting['p3']),
                    self.get_date(setting['p4']))
        return result

    def get_date(self, state):
        if state and len(state) > 4:
            return state[0:2] + ':' + state[2:4]
        else:
            return ''


class ToshibaACGroup():
    """Toshiba AC Group"""

    _group_id: str
    _group_name: str
    _program: ToshibaACProgramm

    def __init__(self, json):
        self.parse(json)

    def parse(self, json):
        self._group_id = json['GroupId']
        self._group_name = json['GroupName']

    def set_program(self, json):
        self._program = ToshibaACProgramm(json)

    def __str__(self):
        return("%s #%s" % (self._group_name, self._group_id))


# class ToshibaACDevice(TypedDict):
class ToshibaACDevice():
    """Toshiba AC Device"""

    _group_id: str
    _ACId: str
    _device_unique_id: str
    _name: str
    _state: str
    _merit_feature: str
    _program: ToshibaACProgramm

    def __init__(self, json: dict = None, group_id: str = None):
        self.parse(json)
        self._group_id = group_id

    def parse_status(self, json):
        self._ACId = json['ACId'].lower()
        self._device_unique_id = json['ACDeviceUniqueId'].lower()
        self._state = json['ACStateData'].lower()
        self._merit_feature = json['MeritFeature'].lower()
        self._last_update = json['UpdatedDate']

    def parse(self, json):
        self._ACId = json['Id'].lower()
        self._device_unique_id = json['DeviceUniqueId'].lower()
        self._name = json['Name']
        self._state = json['ACStateData'].lower()
        self._merit_feature = json['MeritFeature'].lower()
        self._last_update = json['CreatedDate']

    def set_program(self, json):
        self._program = ToshibaACProgramm(json)

    def __str__(self):
        return ("%s #%s: %s - last Update: %s" % (self._name, self._ACId, self._state, self._last_update))


class ToshibaApi():
    """Link to communicate with the Toshiba webserver."""

    # private - from config
    _username = ''
    _password = ''
    _timeout = 8

    # private - from api
    _access_token = ""
    _expires_in = ""
    _consumerId = ""
    _countryId = 0
    _consumerMasterId = ""
    _last_update = None

    _groups = []
    _devices = []

    def __init__(
            self,
            username=None,
            password=None,):
        """Prepare connections instance for toshiba web service."""
        _LOGGER.info("Toshiba link initialized")

        if username is not None:
            self._username = username
        if password is not None:
            self._password = password

    def check_login(self):
        """Check if session is available - if not, aquire a new one."""
        if not self._access_token:  # and _expires_in > now()
            self.login()

        return self._access_token is not None

    def login(self):
        """Call login and store the session id."""
        headers = {
            'Content-Type': 'application/json',
        }

        if not self._username or not self._password:
            raise ToshibaApiError("Missing credentials - please set username and password")

        post = {
            'Username': self._username,
            'Password': self._password
        }

        json = self._request_toshiba_api(LOGIN_PATH, None, post, headers)
        if json is not None:
            self._access_token = json['ResObj']['access_token']
            self._consumerId = json['ResObj']['consumerId'].lower()
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
            'Authorization': 'Bearer ' + self._access_token
        }

        if not self._consumerId:
            raise ToshibaApiError("Missing consumer id - please login first")

        get = {
            'consumerId': self._consumerId,
        }

        json = self._request_toshiba_api(MAPPING_PATH, get, None, headers)
        if json is not None:
            for group in json['ResObj']:
                self._groups.append(ToshibaACGroup(group))
                if group['ACList']:
                    for device in group['ACList']:
                        self._devices.append(ToshibaACDevice(device, group['GroupId']))
        else:
            _LOGGER.warning("Empty Response from toshiba service")
            raise ToshibaConnectionError("Mapping failed - check connection to Toshiba services")

        return json

    def get_device_status(self, device: ToshibaACDevice = None, device_id: int = None):
        """Gets the status of a single device."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self._access_token
        }

        dev = device._ACId if device is not None else device_id

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
        """Gets the program setting of all devices and groups."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self._access_token
        }

        if not self._consumerId:
            raise ToshibaApiError("Missing consumer id - please login first")

        get = {
            'consumerId': self._consumerId,
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

    def get_device_by_id(self, device_id) -> ToshibaACGroup:
        for item in self._devices:
            if item._ACId.lower() == device_id.lower():
                return item
        return None

    def get_group_by_id(self, group_id) -> ToshibaACDevice:
        for group in self._groups:
            if group._group_id.lower() == group_id.lower():
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
            timeouts = (int(self._timeout / 2), self._timeout)

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

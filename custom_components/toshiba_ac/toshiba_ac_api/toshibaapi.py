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
    STATUS_PATH)

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


class ToshibaACGroup():
    """Toshiba AC Group"""

    _group_id: str
    _group_name: str

    def __init__(self, json):
        self.parse(json)

    def parse(self, json):
        self._group_id = json['GroupId']
        self._group_name = json['GroupName']

    def print(self):
        return("%s #%s" % (self._group_name, self._group_id))


# class ToshibaACDevice(TypedDict):
class ToshibaACDevice():
    """Toshiba AC Device"""

    _group_id: str
    _id: str
    _device_unique_id: str
    _name: str
    _state: str
    _merit_feature: str

    def __init__(self, json: dict = None, group_id: str = None):
        self.parse(json)
        self._group_id = group_id

    def parse_status(self, json):
        self._id = json['ACId'].lower()
        self._device_unique_id = json['ACDeviceUniqueId'].lower()
        self._state = json['ACStateData'].lower()
        self._merit_feature = json['MeritFeature'].lower()
        self._last_update = json['UpdatedDate']

    def parse(self, json):
        self._id = json['Id'].lower()
        self._device_unique_id = json['DeviceUniqueId'].lower()
        self._name = json['Name']
        self._state = json['ACStateData'].lower()
        self._merit_feature = json['MeritFeature'].lower()
        self._last_update = json['CreatedDate']

    def print(self):
        return ("%s #%s: %s - last Update: %s" % (self._name, self._id, self._state, self._last_update))


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

        json = self._request_toshiba_api(LOGIN_PATH, post, headers)
        if json is not None:
            self._access_token = json['ResObj']['access_token']
            self._consumerId = json['ResObj']['consumerId'].lower()
            self._countryId = json['ResObj']['countryId']
            self._consumerMasterId = json['ResObj']['consumerMasterId'].lower()
            self._expires_in = json['ResObj']['expires_in']
        else:
            raise ToshibaConfigError("Login failed - check username and password - %s #%s" % (json['Message'], json['StatusCode']))

        return json

    def get_mapping(self):
        """Get groups and devices from consumer mapping."""
        # url = "%s%s?consumerId=" % (BASE_URL, MAPPING_PATH, self._consumerId)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self._access_token
        }

        if not self._consumerId:
            raise ToshibaApiError("Missing consumer id - please login first")

        get = {
            'consumerId': self._consumerId,
        }

        json = self._request_toshiba_api(MAPPING_PATH + '?' + urlencode(get, doseq=False), None, headers)
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
        # url = "%s%s?consumerId=" % (BASE_URL, MAPPING_PATH, self._consumerId)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self._access_token
        }

        dev = device._id if device is not None else device_id

        if not dev:
            raise ToshibaApiError("Missing device or device id to request state")

        get = {
            'ACId': dev,
        }

        json = self._request_toshiba_api(STATUS_PATH + '?' + urlencode(get, doseq=False), None, headers)
        if json is not None:
            found = False
            for item in self._devices:
                if item._id == json['ResObj']['ACId'].lower():
                    item.parse_status(json['ResObj'])
                    found = True
                else:
                    print(item._id, ' != ', json['ResObj']['ACId'])

            if found is False:
                _LOGGER.warning("Cound not find device with id [%s] - please run mapping first" % (dev))

        else:
            _LOGGER.warning("Empty Response from toshiba service")
            raise ToshibaConnectionError("Device Status update failed - check connection to Toshiba services")

        return json

    def _request_toshiba_api(self, path, post=None, headers=None):
        """Call web service using post variables."""

        try:
            json = self._request(BASE_URL + path, post, headers)

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
            post=None,
            headers=None):
        """Call url using post variables."""
        # _LOGGER.info("request to " + url)
        try:
            # connection, read timeout
            timeouts = (int(self._timeout / 2), self._timeout)

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

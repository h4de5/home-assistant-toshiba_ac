"""Constant for Toshiba AC API."""


DOMAIN = "toshiba_ac"

BASE_URL = 'https://toshibamobileservice.azurewebsites.net'
LOGIN_PATH = '/api/Consumer/Login'
DEVICE_PATH = '/api/AC/GetRegisteredACByUniqueId'
MAPPING_PATH = '/api/AC/GetConsumerACMapping'
STATUS_PATH = '/api/AC/GetCurrentACState'
SETTINGS_PATH = '/api/AC/GetConsumerProgramSettings'
CONSUMER_PATH = '/api/Consumer/GetConsumerSetting'
SCHEDULER_PATH = '/api/AC/SaveACProgramSetting'

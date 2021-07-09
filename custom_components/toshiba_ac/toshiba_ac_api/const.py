"""Constant for Toshiba AC API."""


DOMAIN = "toshiba_ac"

BASE_URL = 'https://toshibamobileservice.azurewebsites.net'
LOGIN_PATH = '/api/Consumer/Login'
DEVICE_PATH = '/api/AC/GetRegisteredACByUniqueId'
MAPPING_PATH = '/api/AC/GetConsumerACMapping'
STATUS_PATH = '/api/AC/GetCurrentACState'
CONSUMER_PATH = '/api/Consumer/GetConsumerSetting'
PROGRAM_GET_PATH = '/api/AC/GetConsumerProgramSettings'
PROGRAM_SET_PATH = '/api/AC/SaveACProgramSetting'
PROGRAM_GROUP_SET_PATH = '/api/AC/SaveGroupProgramSetting'

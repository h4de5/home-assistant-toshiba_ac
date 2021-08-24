"""Constant for Toshiba AC API."""

from enum import Enum

DOMAIN = "toshiba_ac"

BASE_URL = "https://toshibamobileservice.azurewebsites.net"
LOGIN_PATH = "/api/Consumer/Login"
DEVICE_PATH = "/api/AC/GetRegisteredACByUniqueId"
MAPPING_PATH = "/api/AC/GetConsumerACMapping"
STATUS_PATH = "/api/AC/GetCurrentACState"
CONSUMER_PATH = "/api/Consumer/GetConsumerSetting"
PROGRAM_GET_PATH = "/api/AC/GetConsumerProgramSettings"
PROGRAM_SET_PATH = "/api/AC/SaveACProgramSetting"
PROGRAM_GROUP_SET_PATH = "/api/AC/SaveGroupProgramSetting"


class ToshibaACEnums(Enum):
    """Toshiba AC constants and enumerations."""

    def __str__(self):
        """Convert object to string."""
        # return str(self.value)
        return "%s" % self.value

    ON = 30
    OFF = 31

    Auto = 41
    Cool = 42
    Heat = 43
    Dry = 44
    Fan = 45
    Off = 46

    UseAirPureIon = 18
    UseAirPureIonOff = 10

    hundreadPercent = 40
    seventyFivePercent = 65
    fiftyPercent = 66

    schedulerOff = "02"
    schedulerOn = "01"

"""Connection to toshiba ac web service."""

import datetime
from typing import Dict
from const import ToshibaACEnums
import json as Json


class ToshibaACProgramm:
    """Toshiba AC program settings."""

    _state: str
    _days: dict
    scheduler_status: str
    _dst: Dict[str, str]

    __original: dict

    def __init__(self, json):
        """Create an object from api response."""
        self.parse(json)
        self.__original = json

    def parse(self, json):
        """Read out necessary information from json object."""
        if "ACStateDataForProgram" in json:
            self._state = json["ACStateDataForProgram"]
        if "schedulerStatus" in json:
            self.scheduler_status = json["schedulerStatus"]
        if "dst" in json:
            self._dst = json["dst"]
        if "programSetting" in json:
            self._days = json["programSetting"]
            # for day in json['programSetting']:
            #     self._days.append(day)

    def __str__(self) -> str:
        """Convert object to string."""
        result = ""
        for day in self._days:
            setting = self._days[day]

            result += "[%s: " % day
            for p in range(1, 5):
                state = setting["p" + str(p)]
                result += "%s%s" % (self._get_date(state), self._get_onoff(state))
            result += "]"

        return result

    def switch(self, when: datetime.time = None, On: bool = True, setting: str = "ffffffffff", part: int = None) -> dict:
        """Create program to switch AC on or off with a given program setting."""
        program: str = ""
        if when is None:
            when = datetime.datetime.now()
        program = when.strftime("%H%M")

        if On:
            program = program + str(ToshibaACEnums.ON)
        else:
            program = program + str(ToshibaACEnums.OFF)
        program = program + setting[2:12]

        # for some reasons byte 12+13 are ff - keep unchanged
        program = program[:12] + "ff" + program[14:]

        if part is None:
            for i in range(1, 5):
                if self._days[when.strftime("%A")]["p" + str(i)] == "":
                    part = i
                    break

        if part < 1 or part > 4:
            part = 1

        if not self._days:
            self.reset(week=True)

        # 113031ffffffffff
        self._days[when.strftime("%A")]["p" + str(part)] = program
        return self._days

    def reset(self, today=True, week=False, day=str) -> dict:
        """Reset program for a given day or the whole week."""
        if today:
            day = datetime.datetime.now().strftime("%A")
        if day in self._days:
            self._days[day] = {"p1": "", "p2": "", "p3": "", "p4": ""}
        if week:
            for day in self._days:
                self._days[day] = {"p1": "", "p2": "", "p3": "", "p4": ""}
        return self._days

    def set_device_list_program(self, json: dict):
        """Update the device program list for group programs."""
        self.__original["ACProgramSettingList"] = [json]

    # def toJson(self, parent: Union(ToshibaACDevice, ToshibaACGroup)) -> dict:
    def toJson(self, parent) -> dict:
        """Return program in json form."""
        json = self.__original

        if hasattr(parent, "state"):
            json["ACStateDataForProgram"] = parent.state
            json["schedulerStatus"] = self.scheduler_status
            json["programSetting"] = self._days
            json["ConsumerId"] = parent.consumer_id
            # trying to make call compatible with mobile app call
            if "Type" in json:
                json.pop("Type")
            if "time" in json:
                json.pop("time")
            if "PartitionKey" in json:
                json.pop("PartitionKey")
        else:
            json["programSetting"] = self._days

        return json

    def _get_date(self, state) -> str:
        """Return the time part from a state."""
        if state and len(state) >= 4:
            return state[0:2] + ":" + state[2:4]
        else:
            return ""

    def _get_onoff(self, state) -> str:
        """Return if the state is on or off or not set."""
        if state and len(state) >= 6:
            if state[4:6] == str(ToshibaACEnums.ON):
                return "↑"
            elif state[4:6] == str(ToshibaACEnums.OFF):
                return "↓"
            else:
                return ""
        else:
            return ""


class ToshibaACGroup:
    """Toshiba AC Group."""

    group_id: str
    group_name: str
    _program: ToshibaACProgramm

    def __init__(self, json):
        """Create an object from api response."""
        self.parse(json)

    def parse(self, json):
        """Read out necessary information from json object."""
        self.group_id = json["GroupId"].lower()
        self.group_name = json["GroupName"]

    def set_program(self, json):
        """Set program from api response."""
        print("get initial program", Json.dumps(json, indent=2, sort_keys=True))
        self._program = ToshibaACProgramm(json)

    def update_program(self, program: ToshibaACProgramm):
        """Set updated program."""
        self._program = program

    def get_program(self) -> ToshibaACProgramm:
        """Return program toshiba type."""
        return self._program

    def get_program_json(self) -> dict:
        """Return program as json object."""
        return self._program.toJson(self)

    def __str__(self):
        """Convert object to string."""
        return "%s #%s" % (self.group_name, self.group_id)


class ToshibaACDevice:
    """Toshiba AC Device."""

    group_id: str = ""
    ac_id: str = ""
    device_unique_id: str
    name: str
    state: str
    merit_feature: str
    consumer_id: str
    _program: ToshibaACProgramm = {}
    # _api: ToshibaACApi

    # def __init__(self, json: dict = None, group_id: str = None):
    def __init__(self, json: dict = None):
        """Create an object from api response and a corresponding group id."""
        # self.api = api
        self.parse(json)

        # print("parsing device json", json)
        # self.group_id = group_id

    def parse_status(self, json):
        """Read out necessary information from json object."""
        self.ac_id = json["ACId"].lower()
        self.device_unique_id = json["ACDeviceUniqueId"].lower()
        self.state = json["ACStateData"].lower()
        self.merit_feature = json["MeritFeature"].lower()
        self._last_update = json["UpdatedDate"]

    def parse(self, json):
        """Read out necessary information from json object."""
        self.ac_id = json["Id"].lower()
        self.device_unique_id = json["DeviceUniqueId"].lower()
        self.name = json["Name"]
        self.state = json["ACStateData"].lower()
        self.merit_feature = json["MeritFeature"].lower()
        self._last_update = json["CreatedDate"]

        # non-standard keys
        if "GroupId" in json:
            self.group_id = json["GroupId"].lower()

        if "ConsumerId" in json:
            self.consumer_id = json["ConsumerId"].lower()

    def set_program(self, json):
        """Set program from api response."""
        self._program = ToshibaACProgramm(json)

    def update_program(self, program: ToshibaACProgramm):
        """Set updated program."""
        self._program = program

    def get_program(self) -> ToshibaACProgramm:
        """Return program toshiba type."""
        return self._program

    def get_program_json(self) -> dict:
        """Return program as json object."""
        return self._program.toJson(self)

    def __str__(self):
        """Convert object to string."""
        return "%s #%s: %s - last Update: %s" % (self.name, self.ac_id, self.state, self._last_update)

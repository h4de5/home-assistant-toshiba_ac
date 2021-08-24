"""Connection to toshiba ac web service."""

import datetime
import logging
from typing import List
from const import ToshibaACEnums
from toshibadevice import ToshibaACDevice, ToshibaACGroup, ToshibaACProgramm
from toshibaapi import ToshibaACApi

_LOGGER = logging.getLogger(__name__)


class ToshibaACProject:
    """Toshiba AC project holding devices and groups bound together by a consumer id."""

    groups: List[ToshibaACGroup] = []
    devices: List[ToshibaACDevice] = []
    _api: ToshibaACApi

    def __init__(self, api: ToshibaACApi) -> None:
        """Create a new project based using a given toshiba API."""
        self._api = api

    def update(self):
        """Iterate through all given groups and devices and updates that state."""
        # TODO - needs iteration through devices
        # self.groups, self.devices = self._api.read_mapping()
        # self.groups, self.devices = self._api.read_mapping()
        self.read_mapping()

    def read_mapping(self):
        """Start initial processing of all mappings."""
        groups = List[dict]
        devices = List[dict]

        groups, devices = self._api.read_mapping()

        for groupid in groups:
            self.groups.append(ToshibaACGroup(groups[groupid]))

        for deviceid in devices:
            self.devices.append(ToshibaACDevice(devices[deviceid]))

    # def read_program(self, device_id: None, group_id: None):
    def read_program(self):
        """Start initial processing of all scheduler programs."""
        group_programs = List[dict]
        device_programs = List[dict]

        group_programs, device_programs = self._api.get_program()

        for program in group_programs:
            # group_programs.append(program)
            group = self.get_group_by_id(program["GroupId"])
            if group:
                group.set_program(program)
            else:
                _LOGGER.warning("Cound not find group with id [%s] - please run mapping first" % (program["GroupId"]))

        for program_ac in device_programs:
            # device_programs.append(program_ac)
            device = self.get_device_by_id(program_ac["ACId"])
            if device:
                device.set_program(program_ac)
            else:
                _LOGGER.warning("Cound not find device with id [%s] - please run mapping first" % (program_ac["ACId"]))

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

    def check_login(self):
        """Check if login is valid."""
        pass

    def set_program(self, device_id=None, group_id=None, On: bool = None, when: datetime.time = None, reset: bool = None):
        """Set given program to a device or group."""
        group: ToshibaACGroup = None
        device: ToshibaACDevice = None

        if group_id is not None:
            group = self.get_group_by_id(group_id)
        elif device_id is not None:
            device = self.get_device_by_id(device_id)

        if group is None and device is None:
            _LOGGER.warning("Cound not find group or device with id [%s %s] - please run mapping first" % (group_id, device_id))
            return

        if group is None:
            group = self.get_group_by_id(device.group_id)

        program_group = group.get_program()
        program_device: ToshibaACProgramm = None

        if device is not None:
            program_device = device.get_program()

        if On is not None:

            # reset program for today
            if reset:
                program_device.reset()
                program_group.reset()

            if program_device is not None:
                program_device.scheduler_status = str(ToshibaACEnums.schedulerOn)
                program_device.switch(On=On, setting=device.state, when=when)
                program_group.set_device_list_program(device.get_program_json())

                device.update_program(program_device)
            else:
                program_group.switch(On=On, when=when)

            group.update_program(program_group)

            # now = datetime.now()
            # upstate = now.strftime("%H%M")

            # if On is True:
            #     upstate += ToshibaACEnums.On
            # else:
            #     upstate += ToshibaACEnums.Off

            # upstate += ToshibaACEnums.Cool + ToshibaACEnums.UseAirPureIon + "32ff41"

            # 1030 30 42 18 41ff41
            # 31421741316400101a7ffe0b0000100202000

            # program["_days"][datetime.today().weekday()] = {"p1": upstate, "p2": "", "p3": "", "p4": ""}
            # print(program)
            # print(program.toJson())

        # print("found updated program:", device.get_program())
        # print("sending updated program:", Json.dumps(group.get_program_json(), indent=2, sort_keys=True))

        if device_id is not None:
            self._api.set_program(device.get_program_json(), device_id, None)
        else:
            self._api.set_program(group.get_program_json(), None, group_id)

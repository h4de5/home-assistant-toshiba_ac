"""Toshiba AC example without HA."""

import argparse
import datetime
from toshibaapi import ToshibaACApi
from toshibaproject import ToshibaACProject


def main():
    """Create example calls for toshiba ac api."""
    parser = argparse.ArgumentParser(description="Command line client for controlling a vimar webserver")
    parser.add_argument("-u", "--username", type=str, dest="username", help="Your username that you use in the toshiba app")
    parser.add_argument("-p", "--password", type=str, dest="password", help="Your password that you use in the toshiba app")
    args = parser.parse_args()

    if args.username is None or args.password is None:
        print("Please provice --username and --password")
        exit(1)

    # try:
    toshibaapi = ToshibaACApi(args.username, args.password)

    valid_login = toshibaapi.check_login()
    if not valid_login:
        print("Login failed")
        exit(1)

    print("generated access_token: ", toshibaapi.access_token)

    project = ToshibaACProject(toshibaapi)

    project.read_mapping()

    if project.devices:
        for group in project.groups:
            print("found group: ", group)

        for device in project.devices:
            print("found device: ", device)

        # for device in project.devices:
        #     toshibaapi.get_device_status(device_id=device.ac_id)
        #     print("updated device: ", device)

        project.read_program()
        for device in project.devices:
            print("found program: ", device.ac_id, " ", device.get_program())

        for device in project.devices:

            # set all AC to start in one minute
            project.set_program(device_id=device.ac_id, On=True, when=(datetime.datetime.now() + datetime.timedelta(minutes=1)), reset=True)
            print("found program: ", device.ac_id, " ", device.get_program())

            # set all AC to stop in 5 minutes
            project.set_program(device_id=device.ac_id, On=False, when=(datetime.datetime.now() + datetime.timedelta(minutes=5)))
            print("found program: ", device.ac_id, " ", device.get_program())

    # except BaseException as err:
    #     print("Exception: %s" % err)


if __name__ == "__main__":
    main()

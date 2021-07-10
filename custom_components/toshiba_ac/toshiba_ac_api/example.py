"""Toshiba AC example without HA."""

import argparse
from toshibaapi import (ToshibaApi)
# from toshibaapi import *


def main():
    """Create example calls for toshiba ac api."""
    parser = argparse.ArgumentParser(description='Command line client for controlling a vimar webserver')
    parser.add_argument('-u', '--username', type=str, dest="username", help="Your username that you use in the toshiba app")
    parser.add_argument('-p', '--password', type=str, dest="password", help="Your password that you use in the toshiba app")
    args = parser.parse_args()

    if args.username is None or args.password is None:
        print('Please provice --username and --password')
        exit(1)

    # try:
    toshibaapi = ToshibaApi(args.username, args.password)

    valid_login = toshibaapi.check_login()
    if not valid_login:
        print("Login failed")
        exit(1)

    print('generated access_token: ', toshibaapi.access_token)

    toshibaapi.get_mapping()
    if toshibaapi.devices:
        for device in toshibaapi.devices:
            print('found device: ', device)

        for device in toshibaapi.devices:
            toshibaapi.get_device_status(device_id=device.ac_id)
            print('updated device: ', device)

        toshibaapi.get_program()
        for device in toshibaapi.devices:

            print('found program: ', device.ac_id, ' ', device.get_program())

            device.get_program().switch(on=True)
            print('found program: ', device.ac_id, ' ', device.get_program())

            device.get_program().reset(week=True)

            device.get_program().switch(on=False)
            print('found program: ', device.ac_id, ' ', device.get_program())

            # print('program details: ', device._program.__json__())

    # except BaseException as err:
    #     print("Exception: %s" % err)


if __name__ == "__main__":
    main()

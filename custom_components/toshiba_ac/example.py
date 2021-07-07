"""Toshiba AC example without HA."""

import argparse
from toshiba_ac_api.toshibaapi import (ToshibaApi)


def main():

    parser = argparse.ArgumentParser(description='Command line client for controlling a vimar webserver')
    parser.add_argument('-u', '--username', type=str, dest="username", help="Your username that you use in the toshiba app")
    parser.add_argument('-p', '--password', type=str, dest="password", help="Your password that you use in the toshiba app")
    args = parser.parse_args()

    if args.username is None or args.password is None:
        print('Please provice --username and --password')
        exit(1)

    toshibaapi = ToshibaApi(args.username, args.password)

    # try:

    valid_login = toshibaapi.check_login()
    print('generated access_token: ', toshibaapi._access_token)

    if (not valid_login):
        print("Login failed")
        exit(1)

    toshibaapi.get_mapping()
    if toshibaapi._devices:
        for device in toshibaapi._devices:
            print('found device: ', device.print())

    if toshibaapi._devices:
        for device in toshibaapi._devices:
            toshibaapi.get_device_status(device_id=device._id)
            print('found device: ', device.print())

    # except BaseException as err:
    #     print("Exception: %s" % err)
    #     valid_login = False


if __name__ == "__main__":
    main()

[![HACS Validate](https://github.com/h4de5/home-assistant-toshiba_ac/actions/workflows/validate.yml/badge.svg)](https://github.com/h4de5/home-assistant-toshiba_ac/actions/workflows/validate.yml)
[![hassfest Validate](https://github.com/h4de5/home-assistant-toshiba_ac/actions/workflows/hassfest.yml/badge.svg)](https://github.com/h4de5/home-assistant-toshiba_ac/actions/workflows/hassfest.yml)
[![Github Release](https://img.shields.io/github/release/h4de5/home-assistant-toshiba_ac.svg)](https://github.com/h4de5/home-assistant-toshiba_ac/releases)
[![Github Commit since](https://img.shields.io/github/commits-since/h4de5/home-assistant-toshiba_ac/latest?sort=semver)](https://github.com/h4de5/home-assistant-toshiba_ac/releases)
[![Github Open Issues](https://img.shields.io/github/issues/h4de5/home-assistant-toshiba_ac.svg)](https://github.com/h4de5/home-assistant-toshiba_ac/issues)
[![Github Open Pull Requests](https://img.shields.io/github/issues-pr/h4de5/home-assistant-toshiba_ac.svg)](https://github.com/h4de5/home-assistant-toshiba_ac/pulls)

# Toshiba - Air conditioning

Toshiba AC integration into home-assistant.io

## Requirements

You need a supported (or compatible) Toshiba AC device with either a built-in Wifi module or an adapter. See [list of compatible devices](#compatible-devices)

## Installation

### Installation with HACS

- In HACS go to integrations and search for 'Toshiba AC'
- Click `Install`
- Reboot Home Assistant
- Follow common integration manual

### or: Manual installation

- Download [latest release](https://github.com/h4de5/home-assistant-toshiba_ac/releases)
- Create a folder: `custom_components` in your home-assistant config directory
- Extract content (the folder `toshiba_ac`) of the release zip into the newly created directory
- Reboot Home Assistant
- Follow common integration manual

### Common manual to activate the integration

- The integration should be available as `Toshiba AC` in the `Add integration dialog`
- You need to enter your Toshiba AC account credentials (same as within the app)
- There is no bounding/registering of new AC units possible with this code - please continue to use the app for this

## Compatible devices

If your device is compatible with the [official Toshiba AC mobile app](https://play.google.com/store/apps/details?id=jp.co.toshiba_carrier.ac_control&gl=US) it has good chances to be supported by this integration. Furthermore it has been tested with the following hardware:

- Suzumi Plus R32 18G

  - Indoor device: RAS-18PKVSG-E
  - Outdoor device: RAS-18PAVSG-E
  - Wifi: RB-N103S-G or similar/compatible

- Seiya

  - Indoor device: Console J2FG RAS-B10J2FVG-E
  - Indoor device: Split Seiya RAS-Bxx-J2KVG-E / RAS-B07-B13-J2KVG-E
  - Outdoor device: RAS-4M27U2AVG-E
  - Wifi: RB-102S-G

- Haori

  - Indoor device: RAS-B16N4KVRG-E
  - Outdoor device: RAS-16J2AVSG-E1
  - WiFi: built-in

- Toshiba Signatur 25
  - Indoor unit: RAS-25N4KVRG-ND
  - Outdoor: RAS-25J2AVSG-ND1
  - Wifi: built-in

## More links and resources

- Feature Request in the [home-assistant community](https://community.home-assistant.io/t/toshiba-home-ac-control/137698)
- my first draft to communicate with the rest service using an [Toshiba API client in PHP](https://gist.github.com/h4de5/7f97db0f4efc265e48904d4a84dab4fb)
- extended example to retrieve state of the AC unit and update the timeprogram using an [Toshiba API client in python](https://github.com/h4de5/home-assistant-toshiba_ac/tree/keep-http-api/custom_components/toshiba_ac/toshiba_ac_api)
- finally using AMQP interface to send state changes directly in [updated python package](https://github.com/KaSroka/Toshiba-AC-control)

[![HACS Validate](https://github.com/h4de5/home-assistant-toshiba_ac/actions/workflows/validate.yml/badge.svg)](https://github.com/h4de5/home-assistant-toshiba_ac/actions/workflows/validate.yml)
[![hassfest Validate](https://github.com/h4de5/home-assistant-toshiba_ac/actions/workflows/hassfest.yml/badge.svg)](https://github.com/h4de5/home-assistant-toshiba_ac/actions/workflows/hassfest.yml)
[![Github Release](https://img.shields.io/github/release/h4de5/home-assistant-toshiba_ac.svg)](https://github.com/h4de5/home-assistant-toshiba_ac/releases)
[![Github Commit since](https://img.shields.io/github/commits-since/h4de5/home-assistant-toshiba_ac/latest?sort=semver)](https://github.com/h4de5/home-assistant-toshiba_ac/releases)
[![Github Open Issues](https://img.shields.io/github/issues/h4de5/home-assistant-toshiba_ac.svg)](https://github.com/h4de5/home-assistant-toshiba_ac/issues)
[![Github Open Pull Requests](https://img.shields.io/github/issues-pr/h4de5/home-assistant-toshiba_ac.svg)](https://github.com/h4de5/home-assistant-toshiba_ac/pulls)

# Toshiba - Air conditioning

## Requirements

Toshiba AC integration into home-assistant.io

Tested with the following Hardware:

- Suzumi Plus R32 18G
    - Indoor device: RAS-18PKVSG-E
    - Outdoor device: RAS-18PAVSG-E
    - Wifi Adapter: RB-N103S-G or similar/compatible
- Haori
    - Indoor device: RAS-B16N4KVRG-E
    - Outdoor device: RAS-16J2AVSG-E1
    - WiFi Adapter: built-in

## Installation

### Installation with HACS

- In HACS go to integrations and click three dots in upper right corner
- Select `Custom repositories`
- Paste URL of this repository (https://github.com/h4de5/home-assistant-toshiba_ac.git) in `Add custom repository URL`
- Select `Integration` in `Category` drop-down list
- Click `Add`
- `Toshiba AC` should appear on the list above, click it
- Click `INSTALL THIS REPOSITORY IN HACS`
- Reboot Home Assistant
- The integration should be available as `Toshiba AC` in the `Add integration dialog` after a restart
- The integration will automatically install dependencies (like [toshiba controller](https://github.com/KaSroka/Toshiba-AC-control)) upon activating it
- You need to enter your Toshiba AC account credentials (same as within the app)
- There is no bounding/registering of new AC units possible with this code - please continue to use the app for this

### Manual installation

- Download [latest release](https://github.com/h4de5/home-assistant-toshiba_ac/releases)
- Create a folder: `custom_components` in your home-assistant config directory
- Extract content (the folder `toshiba_ac`) of the release zip into the newly created directory
- The integration should be available as `Toshiba AC` in the `Add integration dialog` after a restart
- The integration will automatically install dependencies (like [toshiba controller](https://github.com/KaSroka/Toshiba-AC-control)) upon activating it
- You need to enter your Toshiba AC account credentials (same as within the app)
- There is no bounding/registering of new AC units possible with this code - please continue to use the app for this

## More links and resources

- Feature Request in the [home-assistant community](https://community.home-assistant.io/t/toshiba-home-ac-control/137698)
- my first draft to communicate with the rest service using an [Toshiba API client in PHP](https://gist.github.com/h4de5/7f97db0f4efc265e48904d4a84dab4fb)
- extended example to retrieve state of the AC unit and update the timeprogram using an [Toshiba API client in python](https://github.com/h4de5/home-assistant-toshiba_ac/tree/keep-http-api/custom_components/toshiba_ac/toshiba_ac_api)
- finally using AMQP interface to send state changes directly in [updated python package](https://github.com/KaSroka/Toshiba-AC-control)

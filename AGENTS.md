# GitHub-Toshiba-AC

Home Assistant Custom Integration for Toshiba air conditioners. Enables control of Toshiba AC units via Home Assistant.

## Project Overview

- **Domain:** `toshiba_ac`
- **Version:** 2026.1.0
- **Home Assistant IoT Class:** `cloud_push`
- **HACS Compatible:** Yes
- **Repository:** https://github.com/h4de5/home-assistant-toshiba_ac

## Dependencies

- `toshiba-ac` (v0.3.11) - Toshiba AC Control Library
- `janus` (1.0.0) - Thread-safe queue

## File Structure

```
custom_components/toshiba_ac/
├── __init__.py          # Integration setup
├── climate.py           # Climate entity (main functionality)
├── config_flow.py       # Config flow
├── const.py             # Constants
├── diagnostics.py       # Diagnostics data
├── entity.py            # Base entity class
├── entity_description.py # Entity descriptions
├── feature_list.py      # Supported features
├── manifest.json        # Integration manifest
├── select.py            # Select entities
├── sensor.py            # Sensor entities
├── services.yaml        # Service definitions
├── strings.json         # UI strings
├── switch.py            # Switch entities
└── translations/        # Translations
toshibaamqp.py           # MQTT/AMQP messaging component
```

## Development

### Pre-commit Hooks

The project uses pre-commit with the following tools:
- `black` - Code formatter
- `isort` - Import sorting
- `flake8` - Linter
- `yamllint` - YAML validation
- `codespell` - Spell checking
- `pyupgrade` - Python upgrade

### Commands

```bash
# Install pre-commit
pre-commit install

# Run all hooks
pre-commit run --all-files

# Single hook
pre-commit run black --all-files
pre-commit run flake8 --all-files
pre-commit run isort --all-files
```

## Technical Details

- Communication via AMQP/MQTT (RabbitMQ)
- Uses web interface calls (TLSv1, HTTP)
- Supports multiple AC units
- Debug logging enabled in Home Assistant

## Known Limitations

- No binding/registering of new AC units via integration needed (use the app instead)
- North America devices are supported via separate integration (midea_ac_lan)

## Important Files

- `toshibaamqp.py` - MQTT messaging component
- `requirements.txt` - Python dependencies
- `requirements_dev.txt` - Development alternatives
- `custom_components/toshiba_ac/` - Main integration
- `README.md` - Full documentation

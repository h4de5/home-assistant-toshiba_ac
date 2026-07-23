# GitHub-Toshiba-AC

Home Assistant Custom Integration for Toshiba air conditioners. Enables control of Toshiba AC units via Home Assistant.

## Project Overview

- **Domain:** `toshiba_ac`
- **Version:** 2026.7.0
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

**Before presenting any code changes, run pre-commit hooks and fix issues:**
```bash
.venv/bin/pre-commit run --all-files
```

### Environment Setup

System packages required (Debian/Ubuntu):
```bash
apt install python3 python3-pip python3.11-venv
```

Create venv and install dependencies:
```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
# Install toshiba-ac from git (PyPI version has broken git dependency)
.venv/bin/pip install "toshiba-ac @ git+https://github.com/KaSroka/Toshiba-AC-control@v0.3.11" janus==1.0.0
# Install dev tools
.venv/bin/pip install pre-commit black isort flake8 yamllint codespell pyupgrade
```

### Pre-commit Hooks

The project uses pre-commit with the following tools:
- `black` - Code formatter
- `isort` - Import sorting
- `flake8` - Linter
- `yamllint` - YAML validation
- `codespell` - Spell checking
- `pyupgrade` - Python upgrade

### Commands

All commands use the venv:
```bash
# Install pre-commit hooks
.venv/bin/pre-commit install

# Run all hooks
.venv/bin/pre-commit run --all-files

# Single hook
.venv/bin/pre-commit run black --all-files
.venv/bin/pre-commit run flake8 --all-files
.venv/bin/pre-commit run isort --all-files
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

## Release

When creating a new version, update the version in **both** files:
1. `custom_components/toshiba_ac/manifest.json` → `"version": "YYYY.M.PATCH"`
2. `AGENTS.md` → `**Version:** YYYY.M.PATCH`

Format: `YYYY.M.PATCH` (e.g., `2026.7.0`)
- One version per release, based on current month
- Multiple releases in same month: increment patch (e.g., `2026.7.0`, `2026.7.1`, `2026.7.2`)

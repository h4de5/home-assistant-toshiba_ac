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

## Documentation

`docs/` contains publishable documentation only — anything that may be copied out
of the repo and shared. No local test setups, no issue analysis, no source-code
internals, no IPs, no credentials.

**Public** (English, committed):

| File | Content |
|------|---------|
| `docs/codebase-architecture.md` | Platforms, transports, component files, error handling |
| `docs/authentication.md` | Credentials, token and auth flow, setup phases and failure handling |

**Internal** (German, gitignored — local test setups, issue analysis, credentials):

| File | Content |
|------|---------|
| `docs-internal/testumgebung.md` | Test instance access, entities, test scenarios, version drift |
| `docs-internal/analyse.md` | Open issue analysis, workarounds, PR triage |
| `secrets.env` (repo root) | HA API token (`HA_TOKEN`) for the test instance |

The workspace-wide rules in `/workspace/development/AGENTS.md` apply here too.

## Release

When creating a new version, update the version in **both** files:
1. `custom_components/toshiba_ac/manifest.json` → `"version": "YYYY.M.PATCH"`
2. `AGENTS.md` → `**Version:** YYYY.M.PATCH`

Format: `YYYY.M.PATCH` (e.g., `2026.7.0`)
- One version per release, based on current month
- Multiple releases in same month: increment patch (e.g., `2026.7.0`, `2026.7.1`, `2026.7.2`)

---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant custom component integration for Toshiba AC units. Connects to Toshiba's cloud service via the `toshiba_ac` library to control air conditioning units and retrieve status.

## Development Environment

This repository uses the `ghcr.io/ludeeus/devcontainer/integration:stable` devcontainer image which provides a full Home Assistant development environment with the `container` CLI tool.

```bash
# Setup virtual environment (alternative to devcontainer)
./venv-create
source .venv/bin/activate
pip install -r requirements_dev.txt

# In devcontainer - start Home Assistant on port 9123
container start

# In devcontainer - validate configuration
container check

# Run linting (pre-commit hooks)
pre-commit run --all-files
```

## CI/CD Validation

The repository has no local test suite. Validation happens via GitHub Actions:
- **hassfest**: Home Assistant integration manifest validation (`home-assistant/actions/hassfest@master`)
- **HACS**: HACS repository validation (`hacs/action@main`)
- **Linting**: Pre-commit hooks (black, isort, flake8, pyupgrade, codespell, yamllint)

## Dependencies

### External Library
The integration depends on the `toshiba_ac` PyPI library (fork: `github.com/KaSroka/Toshiba-AC-control`):
- Handles authentication with Toshiba cloud HTTP API
- Manages Azure AMQP connection for real-time device state updates
- Provides `ToshibaAcDeviceManager` and `ToshibaAcDevice` classes

All AC communication logic lives in that library, not in this repo.

### Requirements Files
- `requirements.txt` - Runtime: `toshiba-ac==0.3.11`, `janus==1.0.0`
- `requirements_dev.txt` - Development: `homeassistant==2026.1.2` + pre-commit + git install of toshiba-ac fork

## Home Assistant Imports

Current imports used throughout (verified against HA 2026.1):
```python
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.device_registry import DeviceInfo  # Correct location
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode, FAN_OFF
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription, SwitchDeviceClass
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature, UnitOfEnergy
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError, ConfigEntryNotReady, ConfigEntryAuthFailed
```

### Import Notes

All imports follow the [official HA documentation](https://developers.home-assistant.io/docs/device_registry_index/):
- `DeviceInfo` imported from `homeassistant.helpers.device_registry` (correct location)
- All climate, sensor, select, switch imports from their respective `homeassistant.components.*` modules

## Architecture

**Platforms** (defined in `__init__.py`): `climate`, `select`, `sensor`, `switch`

**Entry Point (`__init__.py`)**
- Creates `ToshibaAcDeviceManager` with credentials from config entry
- Uses `ConfigEntryNotReady` for connection failures (HA handles retry with exponential backoff)
- Uses `ConfigEntryAuthFailed` for auth failures (triggers reauth flow)
- Handles SAS token refresh and persistence via callback
- Registers `reconnect` service for manual recovery
- Stores manager in `hass.data[DOMAIN][entry.entry_id]`

**Base Entity Classes (`entity.py`)**
- `ToshibaAcEntity`: Base with `_attr_should_poll = False`, device info setup, availability check
- `ToshibaAcStateEntity`: Adds state change callback subscription via `on_state_changed_callback`

**Entity Description Pattern (`entity_description.py`, `select.py`, `switch.py`)**
- Uses dataclass-based entity descriptions with `is_supported()` method
- `ToshibaAcEnumEntityDescriptionMixin`: Generic mixin for enum-based device attributes
- Entities check `device.supported` feature flags before creation

**Services (`services.yaml`)**
- `toshiba_ac.reconnect`: Force reconnection to Toshiba cloud (reloads all config entries)

**Diagnostics (`diagnostics.py`)**
- Provides diagnostic data for troubleshooting via HA's diagnostics feature
- Redacts sensitive data (username, password, tokens, device IDs)

**State Flow**
1. `ToshibaAcDevice` receives state update via AMQP
2. Device triggers `on_state_changed_callback`
3. Entity's `_state_changed()` calls `async_write_ha_state()`

## Error Handling

The integration uses HA's built-in retry mechanisms:
- **Connection failures**: Raise `ConfigEntryNotReady` → HA retries with exponential backoff
- **Auth failures (401/403)**: Raise `ConfigEntryAuthFailed` → triggers reauth flow
- **Manual recovery**: Call `toshiba_ac.reconnect` service to reload the integration

## Related Resources

- **API Repository**: [KaSroka/Toshiba-AC-control](https://github.com/KaSroka/Toshiba-AC-control) - All device communication logic lives here. Issues related to API/device communication should be reported there, not in this repo.
- **Compatible Devices**: [Issue #45](https://github.com/h4de5/home-assistant-toshiba_ac/issues/45) contains the community-maintained list of compatible devices.

## Common User Issues

When handling bug reports or making changes, be aware of these frequent problems:

1. **Toshiba cloud unavailability**: Most connection issues are caused by Toshiba's cloud being temporarily unreachable. Users should wait 1-2 hours before reporting.

2. **Rate limiting**: Users who restart HA repeatedly when setup fails trigger rate limiting on Toshiba's servers, making things worse.

3. **Password complexity**: Long passwords or passwords with special characters can cause authentication failures during initial setup.

4. **North America incompatibility**: Toshiba AC NA (North America) devices use a completely different system and will NOT work with this integration. Those users should use [midea-ac-py](https://github.com/mill1000/midea-ac-py) instead.

## Development Notes

- **No Python/pip in devcontainer**: The default devcontainer environment doesn't have pip installed. Black and other linters run in the CI pipeline, not locally.
- **Formatting**: Black formatting is enforced via GitHub Actions. Check CI output for formatting errors if commits fail.

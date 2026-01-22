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

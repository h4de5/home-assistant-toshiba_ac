from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {"username", "password", "token", "refresh_token", "serial", "mac"}

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: dict[str, Any] = {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
            "state": str(entry.state),
        },
        "devices": [],
    }

    device_manager = hass.data[DOMAIN].get(entry.entry_id)
    if device_manager is None:
        return data

    try:
        devices = await device_manager.get_devices()
    except Exception as exc:  # pragma: no cover - best-effort
        data["error"] = repr(exc)
        return data

    for dev in devices:
        data["devices"].append(
            async_redact_data(
                {
                    "name": getattr(dev, "name", None),
                    "unique_id": getattr(dev, "ac_unique_id", None),
                    "supported": getattr(dev, "supported", None).__dict__
                    if getattr(dev, "supported", None)
                    else None,
                    "status": {
                        "ac_status": getattr(dev, "ac_status", None).name if getattr(dev, "ac_status", None) else None,
                        "mode": getattr(dev, "ac_mode", None).name if getattr(dev, "ac_mode", None) else None,
                        "temp": getattr(dev, "ac_temperature", None),
                        "indoor_temp": getattr(dev, "ac_indoor_temperature", None),
                        "outdoor_temp": getattr(dev, "ac_outdoor_temperature", None),
                    },
                },
                TO_REDACT,
            )
        )
    return data

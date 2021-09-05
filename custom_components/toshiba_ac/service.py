"""Toshiba AC services."""
from custom_components.toshiba_ac.const import SERVICE_SET_EXTENDED_FEATURE
import logging
import voluptuous as vol
from homeassistant.const import ATTR_COMMAND, ATTR_ENTITY_ID

_LOGGER = logging.getLogger(__name__)

AVAILABLE_COMMANDS = ["PURE_ION", "HIGH_POWER", "SILENT_1", "SILENT_2", "SLEEP", "SAVE", "SLEEP_CARE", "FLOOR", "COMFORT", "FIREPLACE_1", "FIREPLACE_2", "OFF"]

SERVICE_SET_EXTENDED_FEATURE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): vol.All(vol.Coerce(str)),
        vol.Required(ATTR_COMMAND): vol.All(vol.Coerce(str), vol.In(AVAILABLE_COMMANDS)),
    }
)

SERVICES = {
    SERVICE_SET_EXTENDED_FEATURE: {
        "schema": SERVICE_SET_EXTENDED_FEATURE_SCHEMA,
    }
}


class ToshibaServiceHandler:
    """Service implementation."""

    # def __init__(self, hub: MultimaticApi, hass) -> None:
    #     """Init."""
    #     self.api = hub
    #     self._hass = hass

    # async def service_call(self, call):
    #     """Handle service calls."""
    #     service = call.service
    #     method = getattr(self, service)
    #     await method(data=call.data)

    # async def remove_quick_mode(self, data):
    #     """Remove quick mode. It has impact on all components."""
    #     await self.api.remove_quick_mode()

    # async def set_holiday_mode(self, data):
    #     """Set holiday mode."""
    #     start_str = data.get(ATTR_START_DATE, None)
    #     end_str = data.get(ATTR_END_DATE, None)
    #     temp = data.get(ATTR_TEMPERATURE)
    #     start = parse_date(start_str.split("T")[0])
    #     end = parse_date(end_str.split("T")[0])
    #     if end is None or start is None:
    #         raise ValueError(f"dates are incorrect {start_str} {end_str}")
    #     await self.api.set_holiday_mode(start, end, temp)

    # async def remove_holiday_mode(self, data):
    #     """Remove holiday mode."""
    #     await self.api.remove_holiday_mode()

    # async def set_quick_mode(self, data):
    #     """Set quick mode, it may impact the whole system."""
    #     quick_mode = data.get(ATTR_QUICK_MODE, None)
    #     duration = data.get(ATTR_DURATION, None)
    #     await self.api.set_quick_mode(quick_mode, duration)

    # async def request_hvac_update(self, data):
    #     """Ask multimatic API to get data from the installation."""
    #     await self.api.request_hvac_update()

"""Config flow for Pentair RS485 pump integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PORT
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_APP_ADDRESS,
    CONF_PUMP_INDEX,
    CONF_PUMP_NAME,
    CONF_PUMP_TYPE,
    CONF_PUMPS,
    DEFAULT_APP_ADDRESS,
    DOMAIN,
    PUMP_TYPES,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PORT): str,
        vol.Optional(CONF_APP_ADDRESS, default=DEFAULT_APP_ADDRESS): cv.positive_int,
    }
)


class PentairRS485ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pentair RS485 pumps."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            port = user_input[CONF_PORT]
            await self.async_set_unique_id(port)
            self._abort_if_unique_id_configured()

            self.context["port"] = port
            self.context["app_address"] = user_input[CONF_APP_ADDRESS]
            self.context["pumps"] = []
            return await self.async_step_pump()

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

    async def async_step_pump(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure one or more pumps."""
        errors: dict[str, str] = {}
        pumps: list[dict[str, Any]] = self.context.setdefault("pumps", [])

        if user_input is not None:
            index = user_input[CONF_PUMP_INDEX]
            if any(p[CONF_PUMP_INDEX] == index for p in pumps):
                errors["base"] = "pump_exists"
            else:
                pump_entry = {
                    CONF_PUMP_INDEX: index,
                    CONF_PUMP_TYPE: user_input[CONF_PUMP_TYPE],
                    CONF_PUMP_NAME: user_input[CONF_PUMP_NAME],
                }
                pumps.append(pump_entry)
                if user_input.get("add_another"):
                    return self.async_show_form(
                        step_id="pump",
                        data_schema=self._pump_schema(),
                    )
                return self._create_entry()

        return self.async_show_form(
            step_id="pump",
            data_schema=self._pump_schema(),
            errors=errors,
        )

    @staticmethod
    def _pump_schema() -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_PUMP_INDEX, default=1): vol.All(
                    cv.positive_int, vol.Range(min=1, max=16)
                ),
                vol.Required(CONF_PUMP_TYPE, default="VS"): vol.In(PUMP_TYPES),
                vol.Required(CONF_PUMP_NAME, default="Pool Pump"): str,
                vol.Optional("add_another", default=False): bool,
            }
        )

    def _create_entry(self) -> config_entries.ConfigFlowResult:
        """Create the config entry."""
        port = self.context["port"]
        return self.async_create_entry(
            title=f"Pentair RS485 ({port})",
            data={
                CONF_PORT: port,
                CONF_APP_ADDRESS: self.context.get("app_address", DEFAULT_APP_ADDRESS),
                CONF_PUMPS: self.context.get("pumps", []),
            },
        )

"""Config flow for Pentair RS485 pump integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PORT
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_APP_ADDRESS,
    CONF_COVER_ENTITY,
    CONF_COVER_INVERT,
    CONF_PUMP_INDEX,
    CONF_PUMP_NAME,
    CONF_PUMP_TYPE,
    CONF_PUMPS,
    DEFAULT_APP_ADDRESS,
    DEFAULT_COVER_INVERT,
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


def _pump_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_PUMP_INDEX, default=defaults.get(CONF_PUMP_INDEX, 1)
            ): vol.All(cv.positive_int, vol.Range(min=1, max=16)),
            vol.Required(
                CONF_PUMP_TYPE, default=defaults.get(CONF_PUMP_TYPE, "VS")
            ): vol.In(PUMP_TYPES),
            vol.Required(
                CONF_PUMP_NAME, default=defaults.get(CONF_PUMP_NAME, "Pool Pump")
            ): str,
            vol.Optional("add_another", default=False): bool,
        }
    )


class PentairRS485ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pentair RS485 pumps."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
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
        errors: dict[str, str] = {}
        pumps: list[dict[str, Any]] = self.context.setdefault("pumps", [])

        if user_input is not None:
            index = user_input[CONF_PUMP_INDEX]
            if any(p[CONF_PUMP_INDEX] == index for p in pumps):
                errors["base"] = "pump_exists"
            else:
                pumps.append(
                    {
                        CONF_PUMP_INDEX: index,
                        CONF_PUMP_TYPE: user_input[CONF_PUMP_TYPE],
                        CONF_PUMP_NAME: user_input[CONF_PUMP_NAME],
                    }
                )
                if user_input.get("add_another"):
                    return self.async_show_form(
                        step_id="pump",
                        data_schema=_pump_schema(),
                    )
                if self.context.get("reconfigure"):
                    return await self._async_finish_reconfigure()
                return self._create_entry()

        return self.async_show_form(
            step_id="pump",
            data_schema=_pump_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Change serial port / app address, then re-enter pump list."""
        entry = self._reconfigure_entry()
        self.context["reconfigure"] = True

        if user_input is not None:
            port = user_input[CONF_PORT]
            await self.async_set_unique_id(port)
            self.context["port"] = port
            self.context["app_address"] = user_input[CONF_APP_ADDRESS]
            self.context["pumps"] = []
            return await self.async_step_pump()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PORT, default=entry.data.get(CONF_PORT, "")
                    ): str,
                    vol.Optional(
                        CONF_APP_ADDRESS,
                        default=entry.data.get(CONF_APP_ADDRESS, DEFAULT_APP_ADDRESS),
                    ): cv.positive_int,
                }
            ),
        )

    def _reconfigure_entry(self) -> config_entries.ConfigEntry:
        if hasattr(self, "_get_reconfigure_entry"):
            return self._get_reconfigure_entry()  # type: ignore[attr-defined]
        entry_id = self.context["entry_id"]
        entry = self.hass.config_entries.async_get_entry(entry_id)
        assert entry is not None
        return entry

    async def _async_finish_reconfigure(self) -> config_entries.ConfigFlowResult:
        entry = self._reconfigure_entry()
        data = {
            CONF_PORT: self.context["port"],
            CONF_APP_ADDRESS: self.context.get("app_address", DEFAULT_APP_ADDRESS),
            CONF_PUMPS: self.context.get("pumps", []),
        }
        title = f"Pentair RS485 ({data[CONF_PORT]})"
        if hasattr(self, "async_update_reload_and_abort"):
            return self.async_update_reload_and_abort(
                entry,
                data=data,
                title=title,
                unique_id=data[CONF_PORT],
                reason="reconfigure_successful",
            )
        self.hass.config_entries.async_update_entry(
            entry, data=data, title=title, unique_id=data[CONF_PORT]
        )
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reconfigure_successful")

    def _create_entry(self) -> config_entries.ConfigFlowResult:
        port = self.context["port"]
        return self.async_create_entry(
            title=f"Pentair RS485 ({port})",
            data={
                CONF_PORT: port,
                CONF_APP_ADDRESS: self.context.get("app_address", DEFAULT_APP_ADDRESS),
                CONF_PUMPS: self.context.get("pumps", []),
            },
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return PentairRS485OptionsFlow(config_entry)


class PentairRS485OptionsFlow(config_entries.OptionsFlow):
    """Configure pool cover sensor used for speed boost."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            entity = user_input.get(CONF_COVER_ENTITY)
            if not entity:
                entity = None
            return self.async_create_entry(
                title="",
                data={
                    CONF_COVER_ENTITY: entity,
                    CONF_COVER_INVERT: bool(
                        user_input.get(CONF_COVER_INVERT, DEFAULT_COVER_INVERT)
                    ),
                },
            )

        current = self._config_entry.options
        schema_dict: dict[Any, Any] = {
            vol.Optional(
                CONF_COVER_INVERT,
                default=current.get(CONF_COVER_INVERT, DEFAULT_COVER_INVERT),
            ): bool,
        }
        cover_default = current.get(CONF_COVER_ENTITY)
        entity_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["binary_sensor", "cover", "input_boolean"],
                multiple=False,
            )
        )
        if cover_default:
            schema_dict[vol.Optional(CONF_COVER_ENTITY, default=cover_default)] = (
                entity_selector
            )
        else:
            schema_dict[vol.Optional(CONF_COVER_ENTITY)] = entity_selector

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema_dict))

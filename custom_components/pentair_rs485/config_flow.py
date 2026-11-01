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
    CONF_ADD_ANOTHER,
    CONF_APP_ADDRESS,
    CONF_COVER_ENTITY,
    CONF_COVER_INVERT,
    CONF_KEEP_PUMPS,
    CONF_PUMP_INDEX,
    CONF_PUMP_NAME,
    CONF_PUMP_TYPE,
    CONF_PUMPS,
    CONF_SCAN_INTERVAL,
    CONF_SETUP_MODE,
    DEFAULT_APP_ADDRESS,
    DEFAULT_COVER_INVERT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    PUMP_TYPES,
    SETUP_MODE_DISPLAY,
    SETUP_MODE_PUMP,
    default_setup_mode as _default_mode_from_ports,
    is_display_entry,
)
from .device_cleanup import filter_kept_pumps

_LOGGER = logging.getLogger(__name__)


def _list_serial_ports() -> list[str]:
    import glob

    paths: list[str] = []
    for pattern in (
        "/dev/serial/by-id/*",
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
        "/dev/ttyAMA*",
    ):
        paths.extend(sorted(glob.glob(pattern)))
    unique: list[str] = []
    for path in paths:
        if path not in unique:
            unique.append(path)
    return unique


def default_setup_mode(ports: list[str] | None = None) -> str:
    """Prefer display-only when no USB-serial adapter is visible."""
    return _default_mode_from_ports(
        ports if ports is not None else _list_serial_ports()
    )


def _port_schema(
    default: str | None = None, app_address: int = DEFAULT_APP_ADDRESS
) -> vol.Schema:
    ports = _list_serial_ports()
    if ports:
        port_field: Any = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=ports,
                custom_value=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
        port_default = default if default else ports[0]
        schema: dict[Any, Any] = {
            vol.Required(CONF_PORT, default=port_default): port_field,
        }
    else:
        schema = {
            vol.Required(CONF_PORT, default=default or "/dev/ttyUSB0"): str,
        }
    schema[vol.Optional(CONF_APP_ADDRESS, default=app_address)] = cv.positive_int
    return vol.Schema(schema)


async def _async_test_port(hass, port: str) -> str | None:
    """Return an error string if the serial port cannot be opened."""

    def _try_open() -> str | None:
        try:
            import serial

            ser = serial.Serial(port, 9600, timeout=0.2, write_timeout=1)
            ser.close()
            return None
        except Exception as err:  # noqa: BLE001 — surface any serial open failure
            return str(err)

    return await hass.async_add_executor_job(_try_open)


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
            vol.Optional(CONF_ADD_ANOTHER, default=False): bool,
        }
    )


def _reconfigure_schema(
    entry: config_entries.ConfigEntry,
    port: str | None = None,
    app_address: int | None = None,
    keep: list[str] | None = None,
) -> vol.Schema:
    schema = _port_schema(
        port if port is not None else entry.data.get(CONF_PORT),
        app_address
        if app_address is not None
        else entry.data.get(CONF_APP_ADDRESS, DEFAULT_APP_ADDRESS),
    )
    pumps = list(entry.data.get(CONF_PUMPS, []))
    extra: dict[Any, Any] = {}
    if pumps:
        options = [
            selector.SelectOptionDict(
                value=str(p[CONF_PUMP_INDEX]),
                label=(
                    f"{p[CONF_PUMP_NAME]} ({p[CONF_PUMP_TYPE]}, "
                    f"index {p[CONF_PUMP_INDEX]})"
                ),
            )
            for p in pumps
        ]
        default_keep = (
            keep
            if keep is not None
            else [str(p[CONF_PUMP_INDEX]) for p in pumps]
        )
        extra[
            vol.Required(CONF_KEEP_PUMPS, default=default_keep)
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=options,
                multiple=True,
                mode=selector.SelectSelectorMode.LIST,
            )
        )
    extra[vol.Optional(CONF_ADD_ANOTHER, default=False)] = bool
    return vol.Schema({**schema.schema, **extra})


class PentairRS485ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pentair RS485 pumps."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            if user_input[CONF_SETUP_MODE] == SETUP_MODE_DISPLAY:
                await self.async_set_unique_id("display")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Pentair afficheur pompe",
                    data={CONF_SETUP_MODE: SETUP_MODE_DISPLAY},
                )
            return await self.async_step_port()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SETUP_MODE, default=default_setup_mode()
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=SETUP_MODE_PUMP,
                                    label="Pompe — USB RS485",
                                ),
                                selector.SelectOptionDict(
                                    value=SETUP_MODE_DISPLAY,
                                    label="Afficheur — Remote HA (sans USB)",
                                ),
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_port(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            port = user_input[CONF_PORT]
            error = await _async_test_port(self.hass, port)
            if error:
                _LOGGER.warning("Cannot open RS485 port %s: %s", port, error)
                return self.async_show_form(
                    step_id="port",
                    data_schema=_port_schema(port),
                    errors={"base": "cannot_connect"},
                )
            await self.async_set_unique_id(port)
            self._abort_if_unique_id_configured()

            self.context["port"] = port
            self.context["app_address"] = user_input[CONF_APP_ADDRESS]
            self.context["pumps"] = []
            return await self.async_step_pump()

        return self.async_show_form(step_id="port", data_schema=_port_schema())

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
                if user_input.get(CONF_ADD_ANOTHER):
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
        """Change port / address, keep or drop listed pumps, optionally add."""
        entry = self._reconfigure_entry()
        if is_display_entry(entry.data):
            return self.async_abort(reason="reconfigure_successful")
        self.context["reconfigure"] = True
        errors: dict[str, str] = {}

        if user_input is not None:
            port = user_input[CONF_PORT]
            error = await _async_test_port(self.hass, port)
            if error:
                _LOGGER.warning("Cannot open RS485 port %s: %s", port, error)
                errors["base"] = "cannot_connect"
            else:
                kept = filter_kept_pumps(
                    list(entry.data.get(CONF_PUMPS, [])),
                    user_input.get(CONF_KEEP_PUMPS, []),
                )
                add_another = bool(user_input.get(CONF_ADD_ANOTHER))
                if not kept and not add_another:
                    errors["base"] = "keep_one_pump"
                else:
                    await self.async_set_unique_id(port)
                    self.context["port"] = port
                    self.context["app_address"] = user_input[CONF_APP_ADDRESS]
                    self.context["pumps"] = kept
                    if add_another:
                        return await self.async_step_pump()
                    return await self._async_finish_reconfigure()

        keep = None
        if user_input is not None:
            raw_keep = user_input.get(CONF_KEEP_PUMPS)
            if raw_keep is None:
                keep = []
            elif isinstance(raw_keep, (str, int)):
                keep = [str(raw_keep)]
            else:
                keep = [str(x) for x in raw_keep]
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_reconfigure_schema(
                entry,
                user_input[CONF_PORT] if user_input else None,
                (
                    user_input.get(CONF_APP_ADDRESS, DEFAULT_APP_ADDRESS)
                    if user_input
                    else None
                ),
                keep,
            ),
            errors=errors,
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
            CONF_SETUP_MODE: SETUP_MODE_PUMP,
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
                CONF_SETUP_MODE: SETUP_MODE_PUMP,
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
        if is_display_entry(self._config_entry.data):
            return self.async_create_entry(
                title="", data=dict(self._config_entry.options)
            )

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
                    CONF_SCAN_INTERVAL: int(
                        user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                    ),
                },
            )

        current = self._config_entry.options
        schema_dict: dict[Any, Any] = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(
                cv.positive_int,
                vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
            ),
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

"""Single-step setup: register the Lovelace card, no hardware."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries

from .const import DOMAIN


class PentairPumpDisplayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Pentair afficheur pompe", data={})

        return self.async_show_form(step_id="user")

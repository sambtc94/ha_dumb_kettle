"""Config flow for the Dumb Kettle integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BOIL_COMPLETE_DURATION,
    CONF_BOILING_THRESHOLD,
    CONF_IDLE_THRESHOLD,
    CONF_MIN_BOIL_DURATION,
    CONF_POWER_SENSOR,
    DEFAULT_BOIL_COMPLETE_DURATION,
    DEFAULT_BOILING_THRESHOLD,
    DEFAULT_IDLE_THRESHOLD,
    DEFAULT_MIN_BOIL_DURATION,
    DOMAIN,
)


class KettleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow for Dumb Kettle."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Show the setup form and validate the user's input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the selected power sensor exists
            if not self.hass.states.get(user_input[CONF_POWER_SENSOR]):
                errors[CONF_POWER_SENSOR] = "entity_not_found"
            else:
                return self.async_create_entry(
                    title=user_input.get("name", "Kettle"),
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required("name", default="Kettle"): str,
                vol.Required(CONF_POWER_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["sensor"],
                        device_class=["power"],
                    )
                ),
                vol.Optional(
                    CONF_BOILING_THRESHOLD, default=DEFAULT_BOILING_THRESHOLD
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=5000, step=10, unit_of_measurement="W", mode="box"
                    )
                ),
                vol.Optional(
                    CONF_IDLE_THRESHOLD, default=DEFAULT_IDLE_THRESHOLD
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=500, step=1, unit_of_measurement="W", mode="box"
                    )
                ),
                vol.Optional(
                    CONF_MIN_BOIL_DURATION, default=DEFAULT_MIN_BOIL_DURATION
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=300, step=1, unit_of_measurement="s", mode="box"
                    )
                ),
                vol.Optional(
                    CONF_BOIL_COMPLETE_DURATION, default=DEFAULT_BOIL_COMPLETE_DURATION
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5, max=3600, step=5, unit_of_measurement="s", mode="box"
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return KettleOptionsFlow(config_entry)


class KettleOptionsFlow(config_entries.OptionsFlow):
    """Handle options updates (re-configure thresholds without re-adding)."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self._config_entry.options or self._config_entry.data

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_BOILING_THRESHOLD,
                    default=data.get(CONF_BOILING_THRESHOLD, DEFAULT_BOILING_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=5000, step=10, unit_of_measurement="W", mode="box"
                    )
                ),
                vol.Optional(
                    CONF_IDLE_THRESHOLD,
                    default=data.get(CONF_IDLE_THRESHOLD, DEFAULT_IDLE_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=500, step=1, unit_of_measurement="W", mode="box"
                    )
                ),
                vol.Optional(
                    CONF_MIN_BOIL_DURATION,
                    default=data.get(CONF_MIN_BOIL_DURATION, DEFAULT_MIN_BOIL_DURATION),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=300, step=1, unit_of_measurement="s", mode="box"
                    )
                ),
                vol.Optional(
                    CONF_BOIL_COMPLETE_DURATION,
                    default=data.get(CONF_BOIL_COMPLETE_DURATION, DEFAULT_BOIL_COMPLETE_DURATION),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5, max=3600, step=5, unit_of_measurement="s", mode="box"
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )

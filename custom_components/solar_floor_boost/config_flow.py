"""Config flow for Solar Floor Boost."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import CONF_CLIMATES, CONF_MAX_TEMPERATURE, CONF_MIN_TEMPERATURE, DOMAIN
from .units import temperature_units


def schema(hass: HomeAssistant) -> vol.Schema:
    """Thermostats and the two safety limits, in the system's temperature unit."""
    units = temperature_units(hass)
    limit = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=units.limit_min,
            max=units.limit_max,
            step=units.delta_step,
            unit_of_measurement=units.unit,
            mode=selector.NumberSelectorMode.BOX,
        )
    )
    return vol.Schema(
        {
            vol.Required(CONF_CLIMATES): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=CLIMATE_DOMAIN, multiple=True)
            ),
            vol.Required(CONF_MAX_TEMPERATURE, default=units.max_temperature): limit,
            # Entries made before 1.7.0 have no minimum; the default fills it in.
            vol.Required(CONF_MIN_TEMPERATURE, default=units.min_temperature): limit,
        }
    )


class SolarFloorBoostConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 4

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="Solar Floor Boost", data={}, options=user_input
            )
        suggested = {CONF_CLIMATES: self.hass.states.async_entity_ids(CLIMATE_DOMAIN)}
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema(self.hass), suggested),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SolarFloorBoostOptionsFlow()


class SolarFloorBoostOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema(self.hass), self.config_entry.options
            ),
        )

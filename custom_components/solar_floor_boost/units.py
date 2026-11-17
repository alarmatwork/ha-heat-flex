"""Defaults and limits in the system's temperature unit.

Thermostats report and accept targets in the system unit (Home Assistant
converts them), so the amount, the safety limits and the rounding step all
follow it: 1 °C steps of 0.5 become 2 °F steps of 1.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant


@dataclass(frozen=True)
class TemperatureUnits:
    unit: str
    delta: float  # default amount
    delta_min: float
    delta_max: float
    delta_step: float
    temp_step: float  # rounding step when the thermostat doesn't say
    max_temperature: float  # default boost cap
    min_temperature: float  # default setback floor
    limit_min: float  # range offered for the two limits in the config flow
    limit_max: float


CELSIUS = TemperatureUnits(
    unit=UnitOfTemperature.CELSIUS,
    delta=1.0,
    delta_min=0.5,
    delta_max=5,
    delta_step=0.5,
    temp_step=0.5,
    max_temperature=28,
    min_temperature=15,
    limit_min=5,
    limit_max=35,
)

FAHRENHEIT = TemperatureUnits(
    unit=UnitOfTemperature.FAHRENHEIT,
    delta=2.0,
    delta_min=1,
    delta_max=10,
    delta_step=1,
    temp_step=1,
    max_temperature=82,
    min_temperature=59,
    limit_min=41,
    limit_max=95,
)


def temperature_units(hass: HomeAssistant) -> TemperatureUnits:
    if hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT:
        return FAHRENHEIT
    return CELSIUS


def convert_delta(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a temperature difference (no offset, unlike a temperature)."""
    if from_unit == to_unit:
        return value
    if to_unit == UnitOfTemperature.FAHRENHEIT:
        return value * 1.8
    return value / 1.8

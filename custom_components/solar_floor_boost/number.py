"""Amount and duration, shared by boost and setback, adjustable from the UI."""

from __future__ import annotations

from dataclasses import dataclass, replace

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SolarFloorBoostConfigEntry
from .boost import BoostManager
from .const import DEFAULT_DURATION
from .entity import BoostEntity
from .units import TemperatureUnits, convert_delta

TEMPERATURE_UNITS = (UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT)


@dataclass(frozen=True, kw_only=True)
class BoostNumberDescription(NumberEntityDescription):
    """``key`` is also the BoostManager attribute the value is written to."""

    default: float  # in BoostManager units
    # BoostManager value = entity value * scale (duration: hours -> minutes).
    scale: float = 1
    # Restored values in this unit are already BoostManager units (the
    # duration was in minutes up to 1.5.x).
    legacy_unit: str | None = None


DURATION = BoostNumberDescription(
    key="duration",
    icon="mdi:timer-outline",
    device_class=NumberDeviceClass.DURATION,
    # Hours, so Home Assistant displays it as "4h 45m"; 15-minute steps.
    native_min_value=0.25,
    native_max_value=12,
    native_step=0.25,
    native_unit_of_measurement=UnitOfTime.HOURS,
    mode=NumberMode.SLIDER,
    default=DEFAULT_DURATION,
    scale=60,
    legacy_unit=UnitOfTime.MINUTES,
)


def delta_description(units: TemperatureUnits) -> BoostNumberDescription:
    """The amount, in the system's temperature unit (0.5-5 °C or 1-10 °F)."""
    return BoostNumberDescription(
        key="delta",
        icon="mdi:thermometer-plus",
        native_min_value=units.delta_min,
        native_max_value=units.delta_max,
        native_step=units.delta_step,
        native_unit_of_measurement=units.unit,
        mode=NumberMode.SLIDER,
        default=units.delta,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarFloorBoostConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    async_add_entities(
        [
            BoostNumber(manager, delta_description(manager.units)),
            BoostNumber(manager, DURATION),
        ]
    )


class BoostNumber(BoostEntity, RestoreNumber):
    entity_description: BoostNumberDescription
    _platform_domain = "number"

    def __init__(
        self, manager: BoostManager, description: BoostNumberDescription
    ) -> None:
        # "delta" is named Amount; the entity ID follows the name.
        object_id = "amount" if description.key == "delta" else description.key
        super().__init__(manager, description.key, object_id)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        description = self.entity_description
        last = await self.async_get_last_number_data()
        unit = description.native_unit_of_measurement
        if last is None or last.native_value is None:
            value = description.default
        elif (
            description.legacy_unit is not None
            and last.native_unit_of_measurement == description.legacy_unit
        ):
            value = last.native_value
        elif (
            unit in TEMPERATURE_UNITS
            and last.native_unit_of_measurement in TEMPERATURE_UNITS
            and last.native_unit_of_measurement != unit
        ):
            # The system unit changed since the value was saved.
            value = self._snap(
                convert_delta(last.native_value, last.native_unit_of_measurement, unit)
            )
        else:
            value = last.native_value * description.scale
        self._manager.async_set_default(description.key, value)

    def _snap(self, value: float) -> float:
        """Round onto the slider's step and clamp to its range."""
        d = self.entity_description
        step = d.native_step or 1
        value = round(round(value / step) * step, 2)
        return min(max(value, d.native_min_value), d.native_max_value)

    @property
    def native_value(self) -> float:
        description = self.entity_description
        return getattr(self._manager, description.key) / description.scale

    async def async_set_native_value(self, value: float) -> None:
        description = self.entity_description
        self._manager.async_set_default(description.key, value * description.scale)

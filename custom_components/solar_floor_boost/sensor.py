"""Sensors showing when the current boost or setback ends."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SolarFloorBoostConfigEntry
from .boost import BoostManager
from .const import MODE_BOOST, MODE_SETBACK
from .entity import BoostEntity

# Attribute listing the thermostats; "boosted" is kept for the boost sensor.
THERMOSTATS_ATTR = {MODE_BOOST: "boosted", MODE_SETBACK: "setback"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarFloorBoostConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [EndSensor(entry.runtime_data, MODE_BOOST), EndSensor(entry.runtime_data, MODE_SETBACK)]
    )


class EndSensor(BoostEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:timer-sand"

    _platform_domain = "sensor"

    def __init__(self, manager: BoostManager, mode: str) -> None:
        super().__init__(manager, f"{mode}_end", f"{mode}_ends")
        self._mode = mode

    @property
    def _mine(self) -> bool:
        return self._manager.mode == self._mode

    @property
    def native_value(self) -> datetime | None:
        return self._manager.ends_at if self._mine else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        manager = self._manager
        return {
            "delta": manager.active_delta if self._mine else None,
            THERMOSTATS_ATTR[self._mode]: {
                entity_id: {"baseline": rec.baseline, "target": rec.target}
                for entity_id, rec in manager.boosted.items()
            }
            if self._mine
            else {},
            "pending_restore": manager.pending_restore if self._mine else [],
            **manager.start_attributes(self._mode),
        }

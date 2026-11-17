"""Switches to start/stop the boost and the setback from the UI."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SolarFloorBoostConfigEntry
from .boost import BoostManager
from .const import MODE_BOOST, MODE_SETBACK
from .entity import BoostEntity

ICONS = {MODE_BOOST: "mdi:heating-coil", MODE_SETBACK: "mdi:thermometer-low"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarFloorBoostConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [ModeSwitch(entry.runtime_data, MODE_BOOST), ModeSwitch(entry.runtime_data, MODE_SETBACK)]
    )


class ModeSwitch(BoostEntity, SwitchEntity):
    """On while the mode runs. Turning one on turns the other off."""

    def __init__(self, manager: BoostManager, mode: str) -> None:
        super().__init__(manager, mode)
        self._mode = mode
        self._attr_icon = ICONS[mode]

    @property
    def is_on(self) -> bool:
        return self._manager.is_mode_active(self._mode)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._manager.async_start(mode=self._mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._manager.async_stop(self._mode)

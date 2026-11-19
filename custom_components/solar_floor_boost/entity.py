"""Base entity for Heat Flex."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .boost import BoostManager
from .const import DOMAIN


class BoostEntity(Entity):
    _platform_domain: str  # set by each platform's subclass
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: BoostManager, key: str, object_id: str) -> None:
        self._manager = manager
        self._attr_translation_key = key
        self._attr_unique_id = f"{manager.entry.entry_id}_{key}"
        # Suggested entity ID for a new install, e.g. switch.solar_floor_boost_boost:
        # the IDs keep the domain name, as the actions do, so the documented
        # IDs are the same on every install whatever the device is called.
        # An existing entity keeps whatever ID the registry has for it.
        self.entity_id = f"{self._platform_domain}.{DOMAIN}_{object_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)},
            name=manager.entry.title,
            entry_type=DeviceEntryType.SERVICE,
            sw_version=manager.version,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._manager.async_add_listener(self.async_write_ha_state))

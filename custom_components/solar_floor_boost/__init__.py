"""Heat Flex: temporarily raise (boost) or lower (setback) thermostat targets."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .boost import BoostManager, StartInfo, source_of
from .const import (
    ATTR_AUTOMATION,
    ATTR_CLIMATE_ENTITIES,
    ATTR_DELTA,
    ATTR_DURATION,
    DOMAIN,
    LEGACY_NAME,
    MODE_BOOST,
    MODE_SETBACK,
    SOURCE_AUTOMATION,
    NAME,
    SERVICE_START,
    SERVICE_START_SETBACK,
    SERVICE_STOP,
    SERVICE_STOP_SETBACK,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_URL = f"/{DOMAIN}/solar-floor-boost-card.js"
CARD_PATH = Path(__file__).parent / "frontend" / "solar-floor-boost-card.js"

START_SCHEMA = vol.Schema(
    {
        # In the system's temperature unit: up to 10 °C or 18 °F.
        vol.Optional(ATTR_DELTA): vol.All(
            vol.Coerce(float), vol.Range(min=0.1, max=18)
        ),
        vol.Optional(ATTR_DURATION): vol.All(
            vol.Coerce(float), vol.Range(min=1, max=1440)
        ),
        vol.Optional(ATTR_CLIMATE_ENTITIES): cv.entities_domain(CLIMATE_DOMAIN),
        vol.Optional(ATTR_AUTOMATION): cv.string,
    }
)

# Start actions already warned about for being called by an automation that
# doesn't name itself (once per action per run, not on every call).
_unreported_warned: set[str] = set()

type SolarFloorBoostConfigEntry = ConfigEntry[BoostManager]


def _get_manager(hass: HomeAssistant) -> BoostManager:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="not_loaded"
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    def start(mode: str):
        async def handler(call: ServiceCall) -> None:
            await _get_manager(hass).async_start(
                delta=call.data.get(ATTR_DELTA),
                duration=call.data.get(ATTR_DURATION),
                entity_ids=call.data.get(ATTR_CLIMATE_ENTITIES),
                mode=mode,
                info=_start_info(call),
            )

        return handler

    def stop(mode: str):
        async def handler(call: ServiceCall) -> None:
            await _get_manager(hass).async_stop(mode)

        return handler

    for mode, start_service, stop_service in (
        (MODE_BOOST, SERVICE_START, SERVICE_STOP),
        (MODE_SETBACK, SERVICE_START_SETBACK, SERVICE_STOP_SETBACK),
    ):
        hass.services.async_register(
            DOMAIN, start_service, start(mode), schema=START_SCHEMA
        )
        hass.services.async_register(DOMAIN, stop_service, stop(mode))
    await _async_register_card(hass)
    return True


def _start_info(call: ServiceCall) -> StartInfo:
    """Who issued a start action and with which fields.

    An automation is expected to name itself in the ``automation`` field.
    Calls without it keep working, but that way is deprecated: the entities
    and the log can then only say "an automation".
    """
    automation = call.data.get(ATTR_AUTOMATION)
    source = source_of(call.context)
    if (
        source == SOURCE_AUTOMATION
        and not automation
        and call.service not in _unreported_warned
    ):
        _unreported_warned.add(call.service)
        _LOGGER.warning(
            "%s.%s was called by an automation without the 'automation' field. "
            "Add automation: \"{{ this.attributes.friendly_name }}\" to its data "
            "so the %s entities show which automation started them; calling "
            "without it is deprecated",
            DOMAIN,
            call.service,
            DOMAIN,
        )
    return StartInfo(
        command=f"{DOMAIN}.{call.service}",
        source=source,
        automation=automation,
        parameters={k: v for k, v in call.data.items() if k != ATTR_AUTOMATION},
    )


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the dashboard card and load it in every frontend session."""
    if hass.http is None or "frontend" not in hass.config.components:
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_PATH), cache_headers=True)]
    )
    # Version and file hash in the URL so browsers fetch the new file after
    # any update, also one that keeps the version (branch or manual install).
    version = (await async_get_integration(hass, DOMAIN)).version
    digest = await hass.async_add_executor_job(_card_digest)
    add_extra_js_url(hass, f"{CARD_URL}?v={version}-{digest}")


def _card_digest() -> str:
    return hashlib.sha256(CARD_PATH.read_bytes()).hexdigest()[:8]


async def async_setup_entry(
    hass: HomeAssistant, entry: SolarFloorBoostConfigEntry
) -> bool:
    manager = BoostManager(hass, entry)
    manager.version = str((await async_get_integration(hass, DOMAIN)).version)
    await manager.async_load()
    entry.runtime_data = manager
    entry.async_on_unload(manager.async_shutdown)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: SolarFloorBoostConfigEntry
) -> bool:
    if entry.version == 1 and entry.minor_version < 3:
        # 1.4.0 added a duration select and hid the minutes number; the
        # number is the only duration entity again (presets live in the card).
        registry = er.async_get(hass)
        unique_id = f"{entry.entry_id}_duration"
        if select := registry.async_get_entity_id(Platform.SELECT, DOMAIN, unique_id):
            registry.async_remove(select)
        if (
            number := registry.async_get_entity_id(Platform.NUMBER, DOMAIN, unique_id)
        ) and registry.async_get(number).hidden_by is er.RegistryEntryHider.INTEGRATION:
            registry.async_update_entity(number, hidden_by=None)
        hass.config_entries.async_update_entry(entry, minor_version=3)
    if entry.version == 1 and entry.minor_version < 4:
        # 1.7.0 had separate setback amount/duration numbers; the boost ones
        # are shared by both modes now.
        registry = er.async_get(hass)
        for key in ("setback_delta", "setback_duration"):
            if entity_id := registry.async_get_entity_id(
                Platform.NUMBER, DOMAIN, f"{entry.entry_id}_{key}"
            ):
                registry.async_remove(entity_id)
        hass.config_entries.async_update_entry(entry, minor_version=4)
    if entry.version == 1 and entry.minor_version < 5:
        # 2.0.0 renamed the project to Heat Flex; the device follows the
        # entry title. Entity IDs and the domain stay.
        title = NAME if entry.title == LEGACY_NAME else entry.title
        hass.config_entries.async_update_entry(entry, title=title, minor_version=5)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SolarFloorBoostConfigEntry
) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: SolarFloorBoostConfigEntry
) -> None:
    """Put thermostats back before the integration disappears."""
    manager = BoostManager(hass, entry)
    await manager.async_load(resume=False)
    await manager.async_stop()
    manager.async_shutdown()
    await manager.async_remove_storage()


async def _async_update_listener(
    hass: HomeAssistant, entry: SolarFloorBoostConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

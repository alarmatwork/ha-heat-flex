from datetime import timedelta

import voluptuous as vol

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry, async_fire_time_changed,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

DOMAIN = "solar_floor_boost"
A, B, OFF = "climate.bedroom", "climate.kitchen", "climate.garage"
AMOUNT, DURATION = "number.solar_floor_boost_amount", "number.solar_floor_boost_duration"


async def _setup(hass: HomeAssistant):
    hass.states.async_set(A, "heat", {"temperature": 22.0, "target_temp_step": 0.5, "max_temp": 35})
    hass.states.async_set(B, "heat", {"temperature": 27.5, "max_temp": 35})
    hass.states.async_set(OFF, "off", {"temperature": 20.0})
    calls = []

    async def set_temp(call: ServiceCall):
        eid = call.data["entity_id"]
        eid = eid[0] if isinstance(eid, list) else eid
        calls.append((eid, call.data["temperature"]))
        st = hass.states.get(eid)
        hass.states.async_set(eid, st.state, {**st.attributes, "temperature": call.data["temperature"]})

    entry = MockConfigEntry(domain=DOMAIN, title="Solar Floor Boost", options={"climate_entities": [A, B, OFF], "max_temperature": 28})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, "climate", {})
    hass.services.async_register("climate", "set_temperature", set_temp)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, calls


def t(hass, eid):
    return hass.states.get(eid).attributes["temperature"]


async def test_switch_boost_and_restore(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    entry, calls = await _setup(hass)
    assert hass.states.get(AMOUNT).state == "1.0"
    assert hass.states.get(DURATION).state == "2.0"
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.solar_floor_boost_boost"}, blocking=True)
    assert t(hass, A) == 23.0
    assert t(hass, B) == 28.0  # capped by max_temperature
    assert t(hass, OFF) == 21.0  # boosted even when off
    assert hass.states.get("switch.solar_floor_boost_boost").state == "on"
    sensor = hass.states.get("sensor.solar_floor_boost_boost_ends")
    assert sensor.attributes["boosted"][A] == {"baseline": 22.0, "target": 23.0}

    freezer.tick(timedelta(minutes=121))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert t(hass, A) == 22.0 and t(hass, B) == 27.5 and t(hass, OFF) == 20.0
    assert hass.states.get("switch.solar_floor_boost_boost").state == "off"


async def test_service_override_reboost_manual_change(hass: HomeAssistant, freezer):
    entry, calls = await _setup(hass)
    await hass.services.async_call(DOMAIN, "start", {"delta": 2, "duration": 30, "climate_entities": [A]}, blocking=True)
    assert t(hass, A) == 24.0 and t(hass, B) == 27.5
    # Re-boost: applied to original baseline, not stacked; timer reset.
    freezer.tick(timedelta(minutes=20))
    await hass.services.async_call(DOMAIN, "start", {"delta": 3, "duration": 30, "climate_entities": [A, B]}, blocking=True)
    assert t(hass, A) == 25.0 and t(hass, B) == 28.0
    # Someone changes B manually -> must not be restored.
    hass.states.async_set(B, "heat", {"temperature": 21.0, "max_temp": 35})
    freezer.tick(timedelta(minutes=25))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert t(hass, A) == 25.0  # still boosted, timer was reset
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert t(hass, A) == 22.0 and t(hass, B) == 21.0


async def test_unavailable_restored_later(hass: HomeAssistant):
    entry, calls = await _setup(hass)
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    hass.states.async_set(A, "unavailable", {})
    await hass.services.async_call(DOMAIN, "stop", {}, blocking=True)
    assert hass.states.get("sensor.solar_floor_boost_boost_ends").attributes["pending_restore"] == [A]
    assert t(hass, B) == 27.5
    hass.states.async_set(A, "heat", {"temperature": 23.0})
    await hass.async_block_till_done()
    assert t(hass, A) == 22.0
    assert hass.states.get("sensor.solar_floor_boost_boost_ends").attributes["pending_restore"] == []


async def test_survives_reload(hass: HomeAssistant, freezer):
    entry, calls = await _setup(hass)
    await hass.services.async_call(DOMAIN, "start", {"duration": 60}, blocking=True)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("switch.solar_floor_boost_boost").state == "on"
    freezer.tick(timedelta(minutes=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert t(hass, A) == 22.0


async def test_remove_entry_restores(hass: HomeAssistant):
    entry, calls = await _setup(hass)
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert t(hass, A) == 22.0


async def test_config_flow(hass: HomeAssistant):
    hass.states.async_set(A, "heat", {"temperature": 22.0})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "form"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"climate_entities": [A], "max_temperature": 26, "min_temperature": 16})
    assert result["type"] == "create_entry"
    assert result["options"] == {"climate_entities": [A], "max_temperature": 26, "min_temperature": 16}
    entry = result["result"]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"climate_entities": [A], "max_temperature": 25, "min_temperature": 17})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.options["max_temperature"] == 25
    assert entry.options["min_temperature"] == 17


async def test_options_flow_entry_without_minimum(hass: HomeAssistant):
    """Entries from before 1.7.0 have no minimum; the form offers the default."""
    entry, calls = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == "min_temperature")
    assert key.default() == 15.0


async def test_dashboard_card_registered(hass: HomeAssistant):
    from unittest.mock import AsyncMock, MagicMock, patch

    hass.config.components.add("frontend")
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    with patch(f"custom_components.{DOMAIN}.add_extra_js_url") as add_js:
        assert await async_setup_component(hass, DOMAIN, {})
    (paths,), _ = hass.http.async_register_static_paths.call_args
    assert paths[0].url_path == "/solar_floor_boost/solar-floor-boost-card.js"
    assert paths[0].path.endswith("frontend/solar-floor-boost-card.js")
    (_, url), _ = add_js.call_args
    assert url.startswith("/solar_floor_boost/solar-floor-boost-card.js?v=")
    # version-hash, so a changed file gets a new URL even at the same version
    import re
    assert re.fullmatch(r".*\?v=\d+\.\d+\.\d+-[0-9a-f]{8}", url), url


async def test_duration_15_minutes(hass: HomeAssistant, freezer):
    entry, calls = await _setup(hass)
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": DURATION, "value": 0.25}, blocking=True,
    )
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.solar_floor_boost_boost"}, blocking=True)
    assert t(hass, A) == 23.0
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert t(hass, A) == 22.0


async def test_upgrade_from_1_4_0(hass: HomeAssistant):
    """1.4.0 hid the minutes number and added a select; undo both."""
    from homeassistant.helpers import entity_registry as er

    entry = MockConfigEntry(
        domain=DOMAIN, title="Solar Floor Boost", minor_version=2,
        options={"climate_entities": [], "max_temperature": 28},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    number = registry.async_get_or_create(
        "number", DOMAIN, f"{entry.entry_id}_duration", config_entry=entry,
        suggested_object_id="solar_floor_boost_boost_duration",
        hidden_by=er.RegistryEntryHider.INTEGRATION,
    )
    registry.async_get_or_create("select", DOMAIN, f"{entry.entry_id}_duration", config_entry=entry)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.minor_version == 5
    assert registry.async_get_entity_id("select", DOMAIN, f"{entry.entry_id}_duration") is None
    assert registry.async_get(number.entity_id).hidden_by is None
    assert hass.states.get(number.entity_id).state == "2.0"


async def test_upgrade_keeps_user_hidden(hass: HomeAssistant):
    from homeassistant.helpers import entity_registry as er

    entry = MockConfigEntry(
        domain=DOMAIN, title="Solar Floor Boost", minor_version=2,
        options={"climate_entities": [], "max_temperature": 28},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    number = registry.async_get_or_create(
        "number", DOMAIN, f"{entry.entry_id}_duration", config_entry=entry,
        hidden_by=er.RegistryEntryHider.USER,
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(number.entity_id).hidden_by is er.RegistryEntryHider.USER


async def test_duration_number_in_hours(hass: HomeAssistant):
    from homeassistant.helpers import entity_registry as er

    await _setup(hass)
    entity_id = DURATION
    assert er.async_get(hass).async_get(entity_id).hidden_by is None
    state = hass.states.get(entity_id)
    assert (state.attributes["min"], state.attributes["max"], state.attributes["step"]) == (0.25, 12, 0.25)
    assert state.attributes["unit_of_measurement"] == "h"
    assert hass.states.get("select.solar_floor_boost_duration") is None


async def test_restore_duration_saved_in_minutes(hass: HomeAssistant, freezer):
    """Up to 1.5.x the duration was saved in minutes; it must come back as hours."""
    from homeassistant.core import State
    from pytest_homeassistant_custom_component.common import mock_restore_cache_with_extra_data

    mock_restore_cache_with_extra_data(hass, [
        (State(DURATION, "90"),
         {"native_max_value": 720, "native_min_value": 15, "native_step": 15,
          "native_unit_of_measurement": "min", "native_value": 90}),
    ])
    entry, calls = await _setup(hass)
    assert hass.states.get(DURATION).state == "1.5"
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.solar_floor_boost_boost"}, blocking=True)
    freezer.tick(timedelta(minutes=91))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert t(hass, A) == 22.0  # boost lasted 90 minutes


# --- setback ---------------------------------------------------------------

SETBACK = "switch.solar_floor_boost_setback"
BOOST = "switch.solar_floor_boost_boost"


async def test_switch_setback_and_restore(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    entry, calls = await _setup(hass)
    hass.states.async_set(A, "heat", {"temperature": 15.5, "target_temp_step": 0.5, "min_temp": 7})
    hass.states.async_set(B, "heat", {"temperature": 22.0, "min_temp": 21.5})
    await hass.services.async_call("switch", "turn_on", {"entity_id": SETBACK}, blocking=True)
    assert t(hass, A) == 15.0  # floored by min_temperature (15)
    assert t(hass, B) == 21.5  # floored by the thermostat's own min_temp
    assert t(hass, OFF) == 19.0
    assert hass.states.get(SETBACK).state == "on"
    assert hass.states.get(BOOST).state == "off"
    sensor = hass.states.get("sensor.solar_floor_boost_setback_ends")
    assert sensor.state != "unknown"
    assert sensor.attributes["delta"] == 1.0
    assert sensor.attributes["setback"][OFF] == {"baseline": 20.0, "target": 19.0}
    boost_sensor = hass.states.get("sensor.solar_floor_boost_boost_ends")
    assert boost_sensor.state == "unknown" and boost_sensor.attributes["boosted"] == {}

    freezer.tick(timedelta(minutes=121))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert t(hass, A) == 15.5 and t(hass, B) == 22.0 and t(hass, OFF) == 20.0
    assert hass.states.get(SETBACK).state == "off"


async def test_setback_skips_thermostat_at_floor(hass: HomeAssistant):
    entry, calls = await _setup(hass)
    hass.states.async_set(A, "heat", {"temperature": 15.0})
    await hass.services.async_call(DOMAIN, "start_setback", {"climate_entities": [A]}, blocking=True)
    assert t(hass, A) == 15.0
    assert hass.states.get(SETBACK).state == "off"  # nothing could be adjusted


async def test_setback_service_and_stop(hass: HomeAssistant, freezer):
    entry, calls = await _setup(hass)
    await hass.services.async_call(DOMAIN, "start_setback", {"delta": 2.5, "duration": 30, "climate_entities": [A]}, blocking=True)
    assert t(hass, A) == 19.5 and t(hass, B) == 27.5
    # stop (the boost one) must leave the setback alone
    await hass.services.async_call(DOMAIN, "stop", {}, blocking=True)
    assert t(hass, A) == 19.5 and hass.states.get(SETBACK).state == "on"
    await hass.services.async_call(DOMAIN, "stop_setback", {}, blocking=True)
    assert t(hass, A) == 22.0 and hass.states.get(SETBACK).state == "off"


async def test_modes_are_exclusive(hass: HomeAssistant, freezer):
    entry, calls = await _setup(hass)
    await hass.services.async_call("switch", "turn_on", {"entity_id": BOOST}, blocking=True)
    assert t(hass, A) == 23.0
    # Starting a setback ends the boost: A goes back to 22 and then down to 21.
    await hass.services.async_call("switch", "turn_on", {"entity_id": SETBACK}, blocking=True)
    assert t(hass, A) == 21.0 and t(hass, B) == 26.5
    assert hass.states.get(BOOST).state == "off" and hass.states.get(SETBACK).state == "on"
    assert [c for c in calls if c[0] == A][-2:] == [(A, 22.0), (A, 21.0)]
    # And back again via the boost switch.
    await hass.services.async_call("switch", "turn_on", {"entity_id": BOOST}, blocking=True)
    assert t(hass, A) == 23.0 and t(hass, B) == 28.0
    assert hass.states.get(BOOST).state == "on" and hass.states.get(SETBACK).state == "off"
    # Turning off the switch of the mode that isn't running changes nothing.
    await hass.services.async_call("switch", "turn_off", {"entity_id": SETBACK}, blocking=True)
    assert t(hass, A) == 23.0 and hass.states.get(BOOST).state == "on"
    freezer.tick(timedelta(minutes=121))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert t(hass, A) == 22.0 and t(hass, B) == 27.5


async def test_setback_survives_reload(hass: HomeAssistant, freezer):
    entry, calls = await _setup(hass)
    await hass.services.async_call(DOMAIN, "start_setback", {"duration": 60}, blocking=True)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SETBACK).state == "on" and hass.states.get(BOOST).state == "off"
    freezer.tick(timedelta(minutes=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert t(hass, A) == 22.0 and hass.states.get(SETBACK).state == "off"


async def test_storage_from_1_6_is_a_boost(hass: HomeAssistant, freezer):
    """1.6.x storage has no mode; it can only have been a boost."""
    from homeassistant.util import dt as dt_util

    hass.states.async_set(A, "heat", {"temperature": 23.0})
    entry = MockConfigEntry(domain=DOMAIN, title="Solar Floor Boost", options={"climate_entities": [A], "max_temperature": 28})
    entry.add_to_hass(hass)
    ends = (dt_util.utcnow() + timedelta(minutes=30)).isoformat()
    from homeassistant.helpers.storage import Store
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_save(
        {"ends_at": ends, "delta": 1.0, "boosted": {A: {"baseline": 22.0, "target": 23.0}}}
    )
    calls = []

    async def set_temp(call: ServiceCall):
        eid = call.data["entity_id"]
        eid = eid[0] if isinstance(eid, list) else eid
        calls.append((eid, call.data["temperature"]))
        st = hass.states.get(eid)
        hass.states.async_set(eid, st.state, {**st.attributes, "temperature": call.data["temperature"]})

    assert await async_setup_component(hass, "climate", {})
    hass.services.async_register("climate", "set_temperature", set_temp)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(BOOST).state == "on" and hass.states.get(SETBACK).state == "off"
    assert hass.states.get("sensor.solar_floor_boost_boost_ends").attributes["boosted"][A]["baseline"] == 22.0
    # Nothing is known about how a 1.6.x boost was started.
    assert hass.states.get(BOOST).attributes["started_by"] is None
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert t(hass, A) == 22.0


async def test_failed_setback_still_ends_boost(hass: HomeAssistant):
    """Starting a setback that can't adjust anything still ends the boost."""
    entry, calls = await _setup(hass)
    await hass.services.async_call("switch", "turn_on", {"entity_id": BOOST}, blocking=True)
    assert t(hass, A) == 23.0
    hass.states.async_set(OFF, "unavailable", {})
    await hass.services.async_call(DOMAIN, "start_setback", {"climate_entities": [OFF]}, blocking=True)
    assert t(hass, A) == 22.0 and t(hass, B) == 27.5
    assert hass.states.get(BOOST).state == "off" and hass.states.get(SETBACK).state == "off"
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(BOOST).state == "off"


async def test_upgrade_from_1_7_0_removes_setback_numbers(hass: HomeAssistant):
    """1.7.0 had its own setback amount/duration; both modes share one pair now."""
    from homeassistant.helpers import entity_registry as er

    entry = MockConfigEntry(
        domain=DOMAIN, title="Solar Floor Boost", minor_version=3,
        options={"climate_entities": [], "max_temperature": 28},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    for key in ("setback_delta", "setback_duration"):
        registry.async_get_or_create("number", DOMAIN, f"{entry.entry_id}_{key}", config_entry=entry)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.minor_version == 5
    for key in ("setback_delta", "setback_duration"):
        assert registry.async_get_entity_id("number", DOMAIN, f"{entry.entry_id}_{key}") is None
    assert hass.states.get(AMOUNT).state == "1.0"


async def test_shared_amount_and_duration(hass: HomeAssistant, freezer):
    entry, calls = await _setup(hass)
    await hass.services.async_call("number", "set_value", {"entity_id": AMOUNT, "value": 2}, blocking=True)
    await hass.services.async_call("number", "set_value", {"entity_id": DURATION, "value": 0.5}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {"entity_id": SETBACK}, blocking=True)
    assert t(hass, A) == 20.0
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert t(hass, A) == 22.0 and hass.states.get(SETBACK).state == "off"
    await hass.services.async_call("switch", "turn_on", {"entity_id": BOOST}, blocking=True)
    assert t(hass, A) == 24.0


# --- Fahrenheit ------------------------------------------------------------

async def _setup_f(hass: HomeAssistant, options=None):
    from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

    hass.config.units = US_CUSTOMARY_SYSTEM
    hass.states.async_set(A, "heat", {"temperature": 72.0, "target_temp_step": 1, "max_temp": 95, "min_temp": 45})
    hass.states.async_set(B, "heat", {"temperature": 81.0, "max_temp": 95, "min_temp": 45})
    calls = []

    async def set_temp(call: ServiceCall):
        eid = call.data["entity_id"]
        eid = eid[0] if isinstance(eid, list) else eid
        calls.append((eid, call.data["temperature"]))
        st = hass.states.get(eid)
        hass.states.async_set(eid, st.state, {**st.attributes, "temperature": call.data["temperature"]})

    entry = MockConfigEntry(domain=DOMAIN, title="Solar Floor Boost", options=options or {"climate_entities": [A, B]})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, "climate", {})
    hass.services.async_register("climate", "set_temperature", set_temp)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, calls


async def test_fahrenheit_defaults_and_limits(hass: HomeAssistant, freezer):
    entry, calls = await _setup_f(hass)
    amount = hass.states.get(AMOUNT)
    assert amount.state == "2.0" and amount.attributes["unit_of_measurement"] == "°F"
    assert (amount.attributes["min"], amount.attributes["max"], amount.attributes["step"]) == (1, 10, 1)
    await hass.services.async_call("switch", "turn_on", {"entity_id": BOOST}, blocking=True)
    assert t(hass, A) == 74.0
    assert t(hass, B) == 82.0  # default cap 82 °F
    await hass.services.async_call(DOMAIN, "start_setback", {"delta": 15}, blocking=True)
    assert t(hass, A) == 59.0  # default floor 59 °F
    assert t(hass, B) == 66.0
    await hass.services.async_call(DOMAIN, "stop_setback", {}, blocking=True)
    assert t(hass, A) == 72.0 and t(hass, B) == 81.0


async def test_fahrenheit_rounds_to_whole_degrees(hass: HomeAssistant):
    entry, calls = await _setup_f(hass)
    hass.states.async_set(B, "heat", {"temperature": 70.0, "max_temp": 95})  # no step attribute
    await hass.services.async_call(DOMAIN, "start", {"delta": 1.4, "climate_entities": [B]}, blocking=True)
    assert t(hass, B) == 71.0


async def test_fahrenheit_config_flow(hass: HomeAssistant):
    from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

    hass.config.units = US_CUSTOMARY_SYSTEM
    hass.states.async_set(A, "heat", {"temperature": 72.0})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    schema = result["data_schema"].schema
    defaults = {str(k): k.default() for k in schema if k.default is not vol.UNDEFINED}
    assert defaults == {"max_temperature": 82, "min_temperature": 59}
    limit = next(v for k, v in schema.items() if str(k) == "max_temperature")
    assert limit.config["unit_of_measurement"] == "°F" and limit.config["max"] == 95


async def test_amount_restored_after_unit_change(hass: HomeAssistant):
    """A 1 °C amount saved on a metric system comes back as 2 °F."""
    from homeassistant.core import State
    from pytest_homeassistant_custom_component.common import mock_restore_cache_with_extra_data

    mock_restore_cache_with_extra_data(hass, [
        (State(AMOUNT, "1.0"),
         {"native_max_value": 5, "native_min_value": 0.5, "native_step": 0.5,
          "native_unit_of_measurement": "°C", "native_value": 1.0}),
    ])
    await _setup_f(hass)
    assert hass.states.get(AMOUNT).state == "2.0"


async def test_card_version_matches_manifest_and_device(hass: HomeAssistant):
    """The card compares its own version with the device's sw_version."""
    import json, re
    from pathlib import Path
    from homeassistant.helpers import device_registry as dr

    root = Path(__file__).parent.parent / "custom_components" / DOMAIN
    manifest = json.loads((root / "manifest.json").read_text())["version"]
    card = (root / "frontend" / "solar-floor-boost-card.js").read_text()
    assert re.search(r'const CARD_VERSION = "([^"]+)"', card).group(1) == manifest
    entry, calls = await _setup(hass)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device.sw_version == manifest
    # Both ready-made cards are defined and offered in the card picker.
    for card_type in ("heat-flex-card", "heat-flex-history-card", "heat-flex-history-24h-card"):
        assert f'"{card_type}": ' in card and f'type: "{card_type}"' in card
    # Names from before the rename keep working, but are not offered twice.
    assert 'name.replace("heat-flex", "solar-floor-boost")' in card
    assert 'type: "solar-floor-boost-card"' not in card


BOOST_ENDS, SETBACK_ENDS = "sensor.solar_floor_boost_boost_ends", "sensor.solar_floor_boost_setback_ends"
EMPTY_START = {"started_at": None, "started_by": None, "automation": None, "command": None, "parameters": None}


def _clear_deprecation_warnings():
    from custom_components.solar_floor_boost import _unreported_warned

    _unreported_warned.clear()


async def test_start_records_automation_name_and_parameters(hass: HomeAssistant, caplog):
    """An automation naming itself: the entities say who started it, no warning."""
    _clear_deprecation_warnings()
    await _setup(hass)
    await hass.services.async_call(
        DOMAIN, "start_setback",
        {"delta": 2, "duration": 30, "climate_entities": [A], "automation": "Expensive energy"},
        blocking=True,
    )
    attrs = hass.states.get(SETBACK_ENDS).attributes
    assert attrs["started_by"] == "automation"
    assert attrs["automation"] == "Expensive energy"
    assert attrs["command"] == "solar_floor_boost.start_setback"
    assert attrs["parameters"] == {"delta": 2.0, "duration": 30.0, "climate_entities": [A]}
    assert attrs["started_at"] is not None
    # Same on the switch (the cards read it there), plus the amount applied;
    # nothing on the other mode.
    switch_attrs = hass.states.get(SETBACK).attributes
    assert {k: switch_attrs[k] for k in EMPTY_START} == {k: attrs[k] for k in EMPTY_START}
    assert switch_attrs["delta"] == 2.0 and hass.states.get(BOOST).attributes["delta"] is None
    assert {k: hass.states.get(BOOST).attributes[k] for k in EMPTY_START} == EMPTY_START
    assert "deprecated" not in caplog.text
    assert "started by automation 'Expensive energy' via solar_floor_boost.start_setback" in caplog.text

    await hass.services.async_call(DOMAIN, "stop_setback", {}, blocking=True)
    assert {k: hass.states.get(SETBACK).attributes[k] for k in EMPTY_START} == EMPTY_START


async def test_start_without_automation_name_is_deprecated(hass: HomeAssistant, caplog):
    """The old way keeps working; one warning per action per run."""
    _clear_deprecation_warnings()
    await _setup(hass)
    await hass.services.async_call(DOMAIN, "start", {"climate_entities": [A]}, blocking=True)
    assert t(hass, A) == 23.0
    attrs = hass.states.get(BOOST).attributes
    assert attrs["started_by"] == "automation" and attrs["automation"] is None
    assert attrs["command"] == "solar_floor_boost.start"
    assert attrs["parameters"] == {"climate_entities": [A]}
    assert caplog.text.count("solar_floor_boost.start was called by an automation without the 'automation' field") == 1

    await hass.services.async_call(DOMAIN, "start", {"climate_entities": [A]}, blocking=True)
    assert caplog.text.count("without the 'automation' field") == 1


async def test_switch_by_user_is_manual(hass: HomeAssistant, hass_admin_user, caplog):
    """A person toggling the switch: manual, no warning."""
    from homeassistant.core import Context

    _clear_deprecation_warnings()
    await _setup(hass)
    user = Context(user_id=hass_admin_user.id)
    await hass.services.async_call("switch", "turn_on", {"entity_id": BOOST}, blocking=True, context=user)
    attrs = hass.states.get(BOOST).attributes
    assert attrs["started_by"] == "manual" and attrs["automation"] is None
    assert attrs["command"] == "switch.turn_on" and attrs["parameters"] == {}
    assert hass.states.get(BOOST_ENDS).attributes["started_by"] == "manual"
    assert "started manually via switch.turn_on" in caplog.text
    assert "deprecated" not in caplog.text

    # A person using the action in developer tools is manual too, no warning.
    await hass.services.async_call(DOMAIN, "start", {"delta": 1}, blocking=True, context=user)
    assert hass.states.get(BOOST).attributes["started_by"] == "manual"
    assert "deprecated" not in caplog.text


async def test_start_info_survives_reload(hass: HomeAssistant):
    entry, _ = await _setup(hass)
    await hass.services.async_call(
        DOMAIN, "start", {"duration": 60, "automation": "Solar surplus"}, blocking=True
    )
    before = hass.states.get(BOOST).attributes
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    after = hass.states.get(BOOST).attributes
    assert {k: after[k] for k in EMPTY_START} == {k: before[k] for k in EMPTY_START}
    assert after["automation"] == "Solar surplus"


async def test_upgrade_renames_entry_to_heat_flex(hass: HomeAssistant):
    """2.0.0: an entry still titled Solar Floor Boost is renamed; a custom title is kept."""
    from homeassistant.helpers import device_registry as dr

    entry = MockConfigEntry(domain=DOMAIN, title="Solar Floor Boost", minor_version=4, options={"climate_entities": [A], "max_temperature": 28})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, "climate", {})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.minor_version == 5 and entry.title == "Heat Flex"
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device.name == "Heat Flex"
    # Entity IDs keep the domain name.
    assert hass.states.get(BOOST) is not None

    custom = MockConfigEntry(domain=DOMAIN, title="Upstairs heating", minor_version=4, options={"climate_entities": [A]})
    custom.add_to_hass(hass)
    assert await hass.config_entries.async_setup(custom.entry_id)
    await hass.async_block_till_done()
    assert custom.title == "Upstairs heating" and custom.minor_version == 5

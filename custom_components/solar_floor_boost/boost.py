"""Boost/setback manager: moves thermostat targets temporarily and restores them."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.climate.const import (
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_STEP,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CLIMATES,
    CONF_MAX_TEMPERATURE,
    CONF_MIN_TEMPERATURE,
    DEFAULT_DURATION,
    DOMAIN,
    MODE_BOOST,
    MODE_SETBACK,
    STORAGE_VERSION,
)
from .units import temperature_units

_LOGGER = logging.getLogger(__name__)

# Targets closer than this are considered equal (thermostats may round).
TEMP_TOLERANCE = 0.1
UNAVAILABLE_STATES = (STATE_UNAVAILABLE, STATE_UNKNOWN)


@dataclass
class BoostedClimate:
    """Target temperatures of one adjusted thermostat."""

    baseline: float
    target: float


def _same(a: float, b: float) -> bool:
    return abs(a - b) < TEMP_TOLERANCE


class BoostManager:
    """Owns the boost/setback state for one config entry.

    A boost raises targets, a setback lowers them; at most one of the two runs
    at a time (starting one ends the other). Every thermostat that was moved is
    remembered in ``boosted`` until it is restored. When the session ends, a
    thermostat is only put back to its baseline if its target is still the one
    we set; a manual change wins. Thermostats that are unavailable at the end
    stay in ``boosted`` and are restored as soon as they come back. State is
    persisted so a restart doesn't strand a moved setpoint.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        # Integration version, shown as the device's software version so the
        # dashboard card can tell when it is older than the integration.
        self.version: str | None = None
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        # Everything in temperature is in the system unit (°C or °F).
        self.units = temperature_units(hass)
        # Defaults used when a start request doesn't specify them; driven by
        # the number entities and shared by boost and setback.
        self.delta: float = self.units.delta
        self.duration: float = DEFAULT_DURATION
        # Current session. ``mode`` stays set after the end while thermostats
        # are still waiting to be restored, so they are reported under it.
        self.mode: str | None = None
        self.active_delta: float | None = None
        self.ends_at: datetime | None = None
        self.boosted: dict[str, BoostedClimate] = {}

        self._lock = asyncio.Lock()
        self._listeners: set[CALLBACK_TYPE] = set()
        self._unsub_timer: CALLBACK_TYPE | None = None
        self._unsub_pending: CALLBACK_TYPE | None = None
        self._unsub_started: CALLBACK_TYPE | None = None

    @property
    def climate_entities(self) -> list[str]:
        return list(self.entry.options.get(CONF_CLIMATES, []))

    @property
    def max_temperature(self) -> float:
        return float(
            self.entry.options.get(CONF_MAX_TEMPERATURE, self.units.max_temperature)
        )

    @property
    def min_temperature(self) -> float:
        return float(
            self.entry.options.get(CONF_MIN_TEMPERATURE, self.units.min_temperature)
        )

    @property
    def is_active(self) -> bool:
        """A boost or a setback is running."""
        return self.ends_at is not None

    def is_mode_active(self, mode: str) -> bool:
        return self.is_active and self.mode == mode

    @property
    def pending_restore(self) -> list[str]:
        """Thermostats whose session has ended but couldn't be restored yet."""
        return [] if self.is_active else list(self.boosted)

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> Callable[[], None]:
        self._listeners.add(update_callback)

        @callback
        def remove() -> None:
            self._listeners.discard(update_callback)

        return remove

    @callback
    def async_set_default(self, key: str, value: float) -> None:
        """Set the default ``delta`` or ``duration``; every entity showing it updates."""
        setattr(self, key, value)
        self._notify()

    @callback
    def _notify(self) -> None:
        for update_callback in list(self._listeners):
            update_callback()

    # --- lifecycle -----------------------------------------------------------

    async def async_load(self, resume: bool = True) -> None:
        data = await self._store.async_load() or {}
        ends_at = data.get("ends_at")
        self.ends_at = dt_util.parse_datetime(ends_at) if ends_at else None
        self.active_delta = data.get("delta")
        self.boosted = {
            entity_id: BoostedClimate(**rec)
            for entity_id, rec in data.get("boosted", {}).items()
        }
        # Saved by 1.6.x and older: only boosts existed.
        self.mode = data.get("mode") or (
            MODE_BOOST if (self.ends_at or self.boosted) else None
        )
        if resume and (self.ends_at or self.boosted):
            # Thermostats may not be loaded yet; wait until HA has started.
            self._unsub_started = async_at_started(self.hass, self._async_resume)

    async def _async_resume(self, _hass: HomeAssistant) -> None:
        self._unsub_started = None
        if self.ends_at and self.ends_at > dt_util.utcnow():
            self._schedule_end()
            self._notify()
        else:
            await self.async_stop()

    @callback
    def async_shutdown(self) -> None:
        """Stop timers/listeners. The session itself persists in storage."""
        for unsub in (self._unsub_timer, self._unsub_pending, self._unsub_started):
            if unsub:
                unsub()
        self._unsub_timer = self._unsub_pending = self._unsub_started = None

    async def async_remove_storage(self) -> None:
        await self._store.async_remove()

    # --- public actions ------------------------------------------------------

    async def async_start(
        self,
        delta: float | None = None,
        duration: float | None = None,
        entity_ids: list[str] | None = None,
        mode: str = MODE_BOOST,
    ) -> None:
        """Move targets by ``delta`` degrees for ``duration`` minutes.

        A boost raises them, a setback lowers them. If the same mode is already
        running, the new delta is applied to the original baselines (not
        stacked) and the end time is reset to now + duration. If the other mode
        is running, it is ended first and its thermostats restored.
        """
        delta = self.delta if delta is None else delta
        duration = self.duration if duration is None else duration
        entity_ids = entity_ids or self.climate_entities

        async with self._lock:
            if self.mode is not None and self.mode != mode:
                _LOGGER.info("Ending %s to start %s", self.mode, mode)
                await self._async_end()
            results = await asyncio.gather(
                *(
                    self._async_adjust(entity_id, delta, mode)
                    for entity_id in entity_ids
                )
            )
            if not any(results) and not self.is_active:
                _LOGGER.warning(
                    "No thermostat could be adjusted for %s: %s", mode, entity_ids
                )
                # The other mode may just have been ended above.
                await self._async_save()
                self._notify()
                return
            self.mode = mode
            self.active_delta = delta
            self.ends_at = dt_util.utcnow() + timedelta(minutes=duration)
            self._schedule_end()
            self._update_pending_tracking()
            await self._async_save()
        _LOGGER.info(
            "%s %s%s%s until %s for %s",
            mode.capitalize(),
            "-" if mode == MODE_SETBACK else "+",
            delta,
            self.units.unit,
            dt_util.as_local(self.ends_at),
            list(self.boosted),
        )
        self._notify()

    async def async_stop(self, mode: str | None = None) -> None:
        """End the running session and restore baselines.

        With ``mode``, only that mode is ended; the other keeps running.
        """
        async with self._lock:
            if mode is not None and self.mode != mode:
                return
            await self._async_end()
            await self._async_save()
        if self.boosted:
            _LOGGER.info("%s ended; waiting to restore %s", self.mode, list(self.boosted))
        self._notify()

    # --- internals -----------------------------------------------------------

    async def _async_end(self) -> None:
        """Restore what can be restored; the caller holds the lock and saves."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        self.ends_at = None
        self.active_delta = None
        await asyncio.gather(
            *(self._async_restore(entity_id) for entity_id in list(self.boosted))
        )
        if not self.boosted:
            self.mode = None
        self._update_pending_tracking()

    async def _async_adjust(self, entity_id: str, delta: float, mode: str) -> bool:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in UNAVAILABLE_STATES:
            _LOGGER.warning("Skipping %s: unavailable", entity_id)
            return False
        if (current := state.attributes.get(ATTR_TEMPERATURE)) is None:
            _LOGGER.warning("Skipping %s: no target temperature", entity_id)
            return False
        current = float(current)

        rec = self.boosted.get(entity_id)
        # Starting again: keep the original baseline unless someone changed
        # the target in the meantime.
        baseline = rec.baseline if rec and _same(current, rec.target) else current
        target = self._compute_target(state, baseline, delta, mode)
        if (target <= baseline) if mode == MODE_BOOST else (target >= baseline):
            _LOGGER.warning(
                "Skipping %s: baseline %s is already at the %s limit",
                entity_id,
                baseline,
                mode,
            )
            return False
        if not _same(current, target) and not await self._async_set_temperature(
            entity_id, target
        ):
            return False
        _LOGGER.info("%s %s: %s -> %s", mode.capitalize(), entity_id, baseline, target)
        self.boosted[entity_id] = BoostedClimate(baseline=baseline, target=target)
        return True

    async def _async_restore(self, entity_id: str) -> None:
        """Restore one thermostat; leaves it in ``boosted`` if it must retry."""
        rec = self.boosted[entity_id]
        state = self.hass.states.get(entity_id)
        if state is None or state.state in UNAVAILABLE_STATES:
            return
        current = state.attributes.get(ATTR_TEMPERATURE)
        if current is None or not _same(float(current), rec.target):
            _LOGGER.info(
                "Not restoring %s: target changed to %s since %s",
                entity_id,
                current,
                self.mode,
            )
        elif not await self._async_set_temperature(entity_id, rec.baseline):
            return
        del self.boosted[entity_id]

    def _compute_target(
        self, state: State, baseline: float, delta: float, mode: str
    ) -> float:
        """Baseline moved by ``delta``, on the thermostat's step, within limits.

        A boost is capped at the configured maximum and the thermostat's own
        ``max_temp``; a setback is floored at the configured minimum and the
        thermostat's ``min_temp``.
        """
        step = float(state.attributes.get(ATTR_TARGET_TEMP_STEP) or self.units.temp_step)
        if mode == MODE_SETBACK:
            target = round(round((baseline - delta) / step) * step, 2)
            floor = self.min_temperature
            if (device_min := state.attributes.get(ATTR_MIN_TEMP)) is not None:
                floor = max(floor, float(device_min))
            return max(target, floor)
        target = round(round((baseline + delta) / step) * step, 2)
        cap = self.max_temperature
        if (device_max := state.attributes.get(ATTR_MAX_TEMP)) is not None:
            cap = min(cap, float(device_max))
        return min(target, cap)

    async def _async_set_temperature(self, entity_id: str, temperature: float) -> bool:
        try:
            await self.hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: temperature},
                blocking=True,
            )
        except (HomeAssistantError, vol.Invalid) as err:
            _LOGGER.warning("Failed to set %s to %s: %s", entity_id, temperature, err)
            return False
        return True

    @callback
    def _schedule_end(self) -> None:
        if self._unsub_timer:
            self._unsub_timer()
        assert self.ends_at is not None
        self._unsub_timer = async_track_point_in_utc_time(
            self.hass, self._async_expired, self.ends_at
        )

    async def _async_expired(self, _now: datetime) -> None:
        self._unsub_timer = None
        await self.async_stop()

    @callback
    def _update_pending_tracking(self) -> None:
        """Watch unrestored thermostats so they're restored once available."""
        if self._unsub_pending:
            self._unsub_pending()
            self._unsub_pending = None
        if self.is_active or not self.boosted:
            return
        self._unsub_pending = async_track_state_change_event(
            self.hass, list(self.boosted), self._async_pending_changed
        )

    async def _async_pending_changed(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state is None or new_state.state in UNAVAILABLE_STATES:
            return
        entity_id = event.data["entity_id"]
        async with self._lock:
            if self.is_active or entity_id not in self.boosted:
                return
            await self._async_restore(entity_id)
            if not self.boosted:
                self.mode = None
            self._update_pending_tracking()
            await self._async_save()
        self._notify()

    async def _async_save(self) -> None:
        # Saved immediately (not delayed) so a reload right after a start
        # can't lose the baselines.
        await self._store.async_save(self._data())

    @callback
    def _data(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "delta": self.active_delta,
            "boosted": {
                entity_id: asdict(rec) for entity_id, rec in self.boosted.items()
            },
        }

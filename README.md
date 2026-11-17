# Solar Floor Boost

A Home Assistant integration that temporarily raises (**Boost**) or lowers
(**Setback**) the target temperature of selected thermostats, then puts each
one back to the target it had before.

- **Boost** when you have more energy than you need: the battery is full and
  the sun is still producing, or electricity is cheap right now. Instead of
  exporting the surplus, store it as heat in the floor by raising every
  thermostat by 1 °C for 2 hours.
- **Setback** when energy is scarce or expensive: a price peak, a low battery,
  or a grid alert. Lower every thermostat by 1 °C for 2 hours and let the floor
  coast.

Only one of the two runs at a time; starting one ends the other. Control them
from the UI, or start them from automations with your own conditions (battery
level, PV power, electricity price, outdoor temperature, ...).

![Boost card with thermostats raised by 2 °C](docs/screenshot.png)

## Installation

### Marketplace (Home Assistant 2026.11 or newer)

[![Open in the Home Assistant Marketplace](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=alarmatwork&repository=ha-solar-floor-boost&category=integration)

Settings → **Marketplace** → search for **Solar Floor Boost** (or click the
badge above). Install it, then restart Home Assistant.

### HACS (Home Assistant 2026.10 or older)

HACS → search for **Solar Floor Boost** (or click the badge above). Install
it, then restart Home Assistant.

### Manual

Copy `custom_components/solar_floor_boost` to
`<config>/custom_components/solar_floor_boost` and restart Home Assistant.

### Setup

Settings → Devices & services → **Add integration** → **Solar Floor Boost**.
Pick the thermostats, a maximum boosted target (safety cap, default 28 °C) and
a minimum setback target (safety floor, default 15 °C). You can change them
later via **Configure**.

## Entities

| Entity | Purpose |
| --- | --- |
| `switch.solar_floor_boost_boost` | On starts a boost with the values below; off stops it and restores the original targets. Turning it on during a setback ends the setback. |
| `number.solar_floor_boost_boost_amount` | Degrees to add (default 1 °C). |
| `number.solar_floor_boost_boost_duration` | Hours in 15-minute steps, shown as "4h 45m" (default 2h, max 12h). The dashboard card shows it as a preset slider: 15m, 30m, 45m, 1h, 1h 30m, 2h, 2h 30m, 3h, 3h 30m, 4h, 5h, 6h, 8h, 12h. Up to 1.5.x this entity was in minutes. |
| `sensor.solar_floor_boost_boost_ends` | When the boost ends. Attributes list each thermostat's original (`baseline`) and boosted (`target`) value. |
| `switch.solar_floor_boost_setback` | On starts a setback with the values below; off stops it and restores the original targets. Turning it on during a boost ends the boost. |
| `number.solar_floor_boost_setback_amount` | Degrees to subtract (default 1 °C). |
| `number.solar_floor_boost_setback_duration` | Same as the boost duration (default 2h, max 12h). |
| `sensor.solar_floor_boost_setback_ends` | When the setback ends. Attributes list each thermostat's original (`baseline`) and lowered (`target`) value. |

## Dashboard card

The integration ships the card in the screenshot. Edit dashboard → **Add card**
→ **By card** (or **Browse all cards**) → **Solar Floor Boost**. On Home
Assistant 2026.6+ it is also suggested under **By entity** (Community section)
when you pick any Solar Floor Boost entity. The card has a Boost section and a
Setback section; the ⓘ next to each switch explains when to use it (hover, or
tap on a phone).

```yaml
type: custom:solar-floor-boost-card
title: Floor heating   # optional
end_format: relative   # optional: relative, time, datetime, ...
```

If you prefer a plain entities card that you can customise:

```yaml
type: entities
title: Floor heating boost
show_header_toggle: false
entities:
  - type: custom:solar-floor-boost-switch-row  # toggle with an ⓘ hint
    entity: switch.solar_floor_boost_boost
    name: Boost
    hint: Use when the battery is full or electricity is cheap.
  - entity: number.solar_floor_boost_boost_amount
    name: Boost amount
  - type: custom:solar-floor-boost-duration-row  # preset slider (15m … 12h)
    entity: number.solar_floor_boost_boost_duration
    name: Boost duration
  - type: conditional
    conditions:
      - entity: switch.solar_floor_boost_boost
        state: "on"
    row:
      entity: sensor.solar_floor_boost_boost_ends
      name: Boost ends
      format: relative
  - type: divider
  - type: custom:solar-floor-boost-switch-row
    entity: switch.solar_floor_boost_setback
    name: Setback
    hint: Use when electricity is expensive or the battery is low.
  - entity: number.solar_floor_boost_setback_amount
    name: Setback amount
  - type: custom:solar-floor-boost-duration-row
    entity: number.solar_floor_boost_setback_duration
    name: Setback duration
  - type: conditional
    conditions:
      - entity: switch.solar_floor_boost_setback
        state: "on"
    row:
      entity: sensor.solar_floor_boost_setback_ends
      name: Setback ends
      format: relative
```

## Actions

```yaml
action: solar_floor_boost.start
data:
  delta: 2          # optional, defaults to Boost amount
  duration: 120     # minutes (any value), optional, defaults to Boost duration
  climate_entities: # optional, defaults to all configured thermostats
    - climate.living_room
```

```yaml
action: solar_floor_boost.stop
```

The setback actions take the same fields:

```yaml
action: solar_floor_boost.start_setback
data:
  delta: 2          # optional, defaults to Setback amount
  duration: 60      # minutes (any value), optional, defaults to Setback duration
  climate_entities: # optional, defaults to all configured thermostats
    - climate.living_room
```

```yaml
action: solar_floor_boost.stop_setback
```

Each `stop` action only ends its own mode, so an automation that stops the
boost never cuts a setback short, and vice versa. Starting one mode while the
other runs ends the other first.

## Example automation: boost with solar surplus

[examples/solar_surplus_automation.yaml](examples/solar_surplus_automation.yaml)
boosts all configured thermostats for 2 hours when all of these are true:

| Condition | Rule |
| --- | --- |
| Battery | state of charge above **90 %** |
| Sunshine left by the clock | after sunrise and at least **2 h before sunset**, so the boost ends while the sun is still up |
| Sunshine left by the forecast | more than **3 kWh** still forecast for today |
| Outside temperature | below **20 °C** |
| Not already boosting | the Boost switch is off |

It checks when the battery has been above 90 % for 5 minutes and every 10
minutes after that, so while the conditions hold a new boost starts after each
one ends. The amount comes from the **Boost amount** entity; add `delta: 2`
under `duration` to fix it in the automation instead.

### Solar forecast (optional, recommended)

The "sunshine left" check uses the
[Forecast.Solar](https://www.home-assistant.io/integrations/forecast_solar/)
integration, which estimates your panels' production from the weather
forecast. It's free and needs no account.

1. Settings → Devices & services → **Add integration** → **Forecast.Solar**.
2. Enter your panels' **latitude/longitude** (defaults to your home location),
   **declination** (tilt: 0° flat, 90° vertical), **azimuth** (180° = south),
   and **total modules power** in Wp. Add the integration once per roof
   plane if your panels face different directions.
3. Use its **Estimated energy production - remaining today** sensor (kWh) in
   the automation. The entity ID is usually
   `sensor.energy_production_today_remaining`; check
   Developer Tools → States, as it can have a suffix (for example after
   renaming the service or adding a second plane).

Without Forecast.Solar, delete that condition, or replace it with a check on
your inverter's current PV power, for example:

```yaml
  - condition: numeric_state
    entity_id: sensor.pv_power   # your inverter's PV power in W
    above: 1500
```

### Deploy the automation

1. Settings → Automations & scenes → **Create automation** →
   **Create new automation** → ⋮ → **Edit in YAML**.
2. Paste the example and replace the entity IDs with your own:
   `sensor.battery_soc` (battery state of charge, %),
   `sensor.energy_production_today_remaining` (Forecast.Solar) and
   `weather.home` (any weather entity).
3. **Save**. To test it, open the automation → ⋮ → **Run actions**: that starts
   a boost immediately, ignoring the conditions.

In the automation editor, each condition shows a live ✓ or ✕: whether it's
true right now. A ✕ is not an error, just a condition that currently blocks
the boost (for example a boost already running).

## Example automation: set back when energy is expensive

[examples/expensive_energy_setback.yaml](examples/expensive_energy_setback.yaml)
lowers all configured thermostats for 1 hour whenever the electricity price is
above a limit, re-checking every 10 minutes so the setback continues for as
long as the price stays high. Replace `sensor.electricity_price` with your
price sensor (for example from the Nord Pool, Tibber or ENTSO-e integrations)
and `0.30` with your limit in its unit. The amount comes from the **Setback
amount** entity; add `delta: 2` under `duration` to fix it in the automation.

## Behaviour

Everything below applies to a setback as well as a boost; a setback just
moves the targets down instead of up.

- **Boost and setback never run together.** Starting one while the other runs
  restores the original targets first, then applies the new mode to them.
- **Original targets are remembered** per thermostat and restored when the
  boost ends. They are saved to disk, so a restart during a boost still
  restores them (right after startup if the end time passed while Home
  Assistant was down).
- **Manual changes win.** If a thermostat's target changed during the boost
  (by you, a schedule or an app), it is left as is at the end.
- **Starting again during a boost** applies the new amount to the original
  targets instead of stacking, and restarts the timer.
- All selected thermostats are boosted, whatever their mode (heat, off, idle).
  Thermostats that are **unavailable** at start are skipped. One that
  is unavailable when the boost ends is restored as soon as it comes back
  (listed in the sensor's `pending_restore` attribute).
- The boosted target is rounded to the thermostat's temperature step and capped
  at the configured maximum and the thermostat's own `max_temp`. A setback
  target is floored at the configured minimum and the thermostat's `min_temp`.
- Removing the integration restores all thermostats.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

## Releasing

Bump `version` in `custom_components/solar_floor_boost/manifest.json` and push
to `main`. The Release workflow tags `v<version>` and publishes a GitHub
release, which the Marketplace and HACS offer as an update.

## License

MIT

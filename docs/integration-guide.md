# Heat Flex: integration guide

A self-contained reference for writing Home Assistant automations, scripts,
templates and dashboards that use the Heat Flex integration (called Solar
Floor Boost up to 1.10; the domain `solar_floor_boost` stayed). Paste it
into an LLM prompt or read it instead of the source. Entity IDs below are the
defaults; a user may have renamed them, and Home Assistant 2026.11+ may
prefix new IDs with the device's area (e.g. `switch.living_room_solar_floor_boost_boost`).

## What it does

- Temporarily moves the target temperature of configured `climate` entities
  (thermostats), then restores each one's original target.
- Two modes, mutually exclusive:
  - **boost**: raise targets by an amount for a duration (use when energy is
    plentiful or cheap: full battery with sun left, low price).
  - **setback**: lower targets by an amount for a duration (use when energy is
    scarce or expensive: price peak, low battery, grid alert).
- Starting one mode while the other runs ends the other first (its targets
  are restored), then applies the new mode.
- Starting the running mode again applies the new amount to the original
  targets (no stacking) and restarts the timer from now.
- A mode ends by itself after the duration, or earlier with its stop action.
  Manual changes win: a thermostat whose target was changed by someone else
  during the session is left as is at the end.
- One instance per Home Assistant; all entities belong to one device
  "Heat Flex".

## Entities

| Entity | State | Notes |
|---|---|---|
| `switch.solar_floor_boost_boost` | `on` while a boost runs | Turning on starts a boost with the Amount and Duration entities; turning off stops it. Attributes while on: see "Start attributes". |
| `switch.solar_floor_boost_setback` | `on` while a setback runs | Same for the setback. |
| `number.solar_floor_boost_amount` | degrees | Default amount for both modes. Celsius systems: 0.5–5 in 0.5 steps, default 1. Fahrenheit systems: 1–10 in whole degrees, default 2. Older installs: `number.solar_floor_boost_boost_amount`. |
| `number.solar_floor_boost_duration` | hours | Default duration for both modes, 0.25–12 in 0.25 steps, default 2. Older installs: `number.solar_floor_boost_boost_duration`. |
| `sensor.solar_floor_boost_boost_ends` | timestamp or `unknown` | When the running boost ends; `unknown` when no boost runs. Attributes: `delta` (amount applied), `boosted` (`{entity_id: {baseline, target}}`), `pending_restore` (list of entity IDs not yet restored because unavailable), plus the start attributes. |
| `sensor.solar_floor_boost_setback_ends` | timestamp or `unknown` | Same for the setback; the thermostat map is called `setback`. |

Units: amounts, limits and thermostat targets are in the Home Assistant
system temperature unit (°C or °F).

### Start attributes

While a mode runs, its switch and its "ends" sensor carry (they are `null`
on the mode that is not running, survive a restart and are cleared when the
session ends):

| Attribute | Values |
|---|---|
| `started_at` | ISO 8601 UTC timestamp |
| `started_by` | `manual` (a signed-in person: dashboard, more-info dialog, developer tools) or `automation` (automation or script; decided from the call context, not declared) |
| `automation` | the text given in the `automation` field of the start action, else `null` |
| `command` | `solar_floor_boost.start`, `solar_floor_boost.start_setback` or `switch.turn_on` |
| `parameters` | object with exactly the fields the caller passed (`delta`, `duration`, `climate_entities`), without defaults; `{}` for a switch |
| `delta` | the amount applied (switch attribute; the sensor has it too) |

## Actions

All fields are optional. Amount and duration default to the number entities;
thermostats default to all configured ones.

```yaml
action: solar_floor_boost.start            # start or restart a boost
data:
  delta: 1.5            # degrees in the system unit, 0.1–18 (10 °C / 18 °F max)
  duration: 90          # minutes, 1–1440
  climate_entities:     # subset of the configured thermostats
    - climate.living_room
  automation: "{{ this.attributes.friendly_name }}"   # free text: who is calling
```

```yaml
action: solar_floor_boost.start_setback    # start or restart a setback; same fields
```

```yaml
action: solar_floor_boost.stop             # end the boost now; no-op during a setback
action: solar_floor_boost.stop_setback     # end the setback now; no-op during a boost
```

Rules for callers:

- **Always pass `automation`** from automations and scripts. In an
  automation, `"{{ this.attributes.friendly_name }}"` is its own name; a
  script can use any text. Calling from an automation without it works but is
  deprecated: the attributes then say "an automation" and Home Assistant logs
  a warning once per action per run. Calls by a person (developer tools)
  never need it.
- Prefer the actions over `switch.turn_on`: the switch cannot carry
  `delta`, `duration`, `climate_entities` or `automation`.
- The temperature actually set is rounded to the thermostat's step and
  limited: a boost never goes above the configured maximum (default 28 °C /
  82 °F) or the thermostat's `max_temp`; a setback never goes below the
  configured minimum (default 15 °C / 59 °F) or the thermostat's `min_temp`.
  A thermostat already at the limit, or unavailable, is skipped. If no
  thermostat could be moved, nothing starts (the switch stays `off`).
- Actions raise an error if the integration is not set up.

## Patterns

Keep a mode running while a condition holds (ends by itself otherwise):

```yaml
alias: "Solar surplus - boost floor heating"
mode: single
triggers:
  - trigger: numeric_state
    entity_id: sensor.battery_soc
    above: 90
    for: "00:05:00"
  - trigger: time_pattern
    minutes: "/10"          # re-check so a new boost starts after the previous ended
conditions:
  - condition: state
    entity_id: switch.solar_floor_boost_boost
    state: "off"            # not already boosting
  - condition: numeric_state
    entity_id: sensor.battery_soc
    above: 90
actions:
  - action: solar_floor_boost.start
    data:
      duration: 120
      automation: "{{ this.attributes.friendly_name }}"
```

Start once, stop when the condition clears:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.electricity_price
    above: 0.30
    id: expensive
  - trigger: numeric_state
    entity_id: sensor.electricity_price
    below: 0.30
    id: cheap
actions:
  - choose:
      - conditions: "{{ trigger.id == 'expensive' }}"
        sequence:
          - action: solar_floor_boost.start_setback
            data:
              duration: 240
              automation: "{{ this.attributes.friendly_name }}"
      - conditions:
          - "{{ trigger.id == 'cheap' }}"
          # Only stop what this automation started
          - "{{ state_attr('switch.solar_floor_boost_setback', 'automation') == this.attributes.friendly_name }}"
        sequence:
          - action: solar_floor_boost.stop_setback
```

Useful templates:

```yaml
{{ is_state('switch.solar_floor_boost_boost', 'on') }}                       # boosting?
{{ state_attr('switch.solar_floor_boost_setback', 'automation') }}           # who started the setback
{{ states('sensor.solar_floor_boost_boost_ends') }}                          # ISO end time or 'unknown'
{{ (as_datetime(states('sensor.solar_floor_boost_boost_ends')) - now()).total_seconds() // 60 }}  # minutes left
{{ state_attr('sensor.solar_floor_boost_boost_ends', 'boosted') }}           # {entity_id: {baseline, target}}
```

Trigger on a session ending: a `state` trigger on the switch from `on` to
`off`. Trigger on a start by a specific automation: a `state` trigger on
the switch to `on` plus a template condition on its `automation` attribute
(a `state` condition does not render templates).

## Dashboards

Three ready-made cards (no resources to add; the integration registers them):

```yaml
type: custom:heat-flex-card                  # switches with hints, Amount, Duration presets, end times
title: Heating                               # optional
end_format: relative                         # optional
```

```yaml
type: custom:heat-flex-history-card          # sessions on a timeline, tooltip per block
title: Heating today                         # optional
span: today                                  # optional: today (calendar days) or rolling (ends now)
days: 1                                      # optional, span today, 1–14
hours: 24                                    # optional, span rolling, 1–336
```

```yaml
type: custom:heat-flex-log-card              # text log, newest first: amount, who started it, planned end, how it ended
title: Heating log                           # optional
span: today                                  # optional, as for the history card (default 2 days)
days: 2                                      # optional, span today, 1–14
hours: 24                                    # optional, span rolling, 1–336
max: 30                                      # optional, 1–200 lines
ended: true                                  # optional, false lists only the starts
```

`custom:heat-flex-history-24h-card` is the same history card preset to a
rolling 24-hour window. The `custom:solar-floor-boost-*` types from before 2.0 are
aliases of these.

Rows usable in any entities card: `custom:heat-flex-switch-row`
(`entity`, `name`, `hint`) and `custom:heat-flex-duration-row`
(`entity`, `name`).

## Configuration

Settings → Devices & services → Heat Flex → Configure: the
thermostats (`climate_entities`), the maximum boosted target
(`max_temperature`) and the minimum setback target (`min_temperature`).
There is no YAML configuration.

# Changelog

What changed in each version of Heat Flex (Solar Floor Boost up to 1.10).
Generated from the
commit history when a version is released; the same text is shown as the
release notes in Home Assistant's Marketplace and HACS.


## [2.1.1](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v2.1.1) - 2026-11-23

### Changed

- Log card: show the newest 10 lines by default; 'max' sets how many (2.1.1)

## [2.1.0](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v2.1.0) - 2026-11-23

### Added

- Add a 'Heat Flex Log' card: the sessions as a text log, newest first, with the amount, who started each one, when it was due to end and whether it was stopped early; the title opens the logbook for the two switches (2.1.0)

## [2.0.1](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v2.0.1) - 2026-11-19

### Changed

- Point the manifest, README badge, card picker entries and changelog config at the renamed repository alarmatwork/ha-heat-flex; the old address redirects (2.0.1)

## [2.0.0](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v2.0.0) - 2026-11-19

### Changed

- Rename the project to Heat Flex: shift heating in time, for any thermostat. The domain, entity IDs and action names stay solar_floor_boost, old card types keep working as aliases, and the config entry is renamed on upgrade (2.0.0)

## [1.10.0](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.10.0) - 2026-11-19

### Added

- Add a rolling-window option to the history card and a 'Solar Floor Boost History (last 24 h)' card in the picker (1.10.0)

## [1.9.2](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.9.2) - 2026-11-19

### Fixed

- Fix the history card tooltip on phones: the bar under the finger was redrawn away on every state update; a tooltip now shows while the finger rests on a bar, stays after a short tap, and a second tap or a scroll hides it (1.9.2)

## [1.9.1](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.9.1) - 2026-11-18

### Fixed

- Fix tooltips on phones: a tap on a history block or an (i) hint showed and hid the tooltip at once; hover is now for a mouse only and a tap toggles (1.9.1)

## [1.9.0](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.9.0) - 2026-11-18

### Added

- Add a History card: today's boosts and setbacks on a timeline, each block showing who started it, the amount and the times; README automations guide and docs/integration-guide.md for LLMs

## [1.8.0](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.8.0) - 2026-11-18

### Added

- Add who-started-it tracking: each boost or setback records the command, its parameters, manual or automation, and the automation's name from the new 'automation' field of the start actions (shown on the card and the entities; calling without the field still works but is deprecated)

### Documentation

- Screenshots of the card with Setback and of thermostats during a setback

## [1.7.3](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.7.3) - 2026-11-17

### Added

- Add an automatically generated changelog, shown as release notes in Home Assistant

### Maintenance

- Release workflow: notes come from the unreleased commits, heading stripped

## [1.7.2](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.7.2) - 2026-11-17

### Changed

- Card asks for a reload when the integration is newer than the loaded file

## [1.7.1](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.7.1) - 2026-11-17

### Changed

- Card URL includes the file hash so updates at the same version bust the cache
- Share Amount and Duration between Boost and Setback; follow the system temperature unit

## [1.7.0](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.7.0) - 2026-11-17

### Added

- Add Setback: temporarily lower thermostats, the opposite of Boost

### Documentation

- The integration is in the Marketplace/HACS catalog now

## [1.6.1](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.6.1) - 2026-11-16

### Added

- Add Marketplace/HACS validation workflow and document both install paths
- Add integration categories; move actions to Node 24 releases

### Documentation

- Document the solar surplus automation and Forecast.Solar setup

### Maintenance

- Sort manifest keys the way hassfest requires

## [1.6.0](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.6.0) - 2026-10-07

### Changed

- Duration in hours so Home Assistant shows "4h 45m"

## [1.5.1](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.5.1) - 2026-10-07

### Changed

- Duration presets end with 6h, 8h, 12h again

## [1.5.0](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.5.0) - 2026-10-07

### Changed

- Single duration slider: minutes on the device page, presets in the card

## [1.4.0](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.4.0) - 2026-10-07

### Changed

- Duration presets everywhere, including the device page

## [1.3.2](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.3.2) - 2026-10-07

### Fixed

- Fix card missing from the picker (custom element registry race)

## [1.3.1](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.3.1) - 2026-10-07

### Fixed

- Restore the duration number entity (fixes cards broken by 1.3.0)

## [1.3.0](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.3.0) - 2026-10-07

### Changed

- Boost duration as presets: 15m, 30m, 45m, 1h ... 12h

## [1.2.1](https://github.com/alarmatwork/ha-heat-flex/releases/tag/v1.2.1) - 2026-10-07

### Added

- Add dashboard screenshot and card example to README
- Ship a Solar Floor Boost dashboard card
- Add integration icon
- Suggest the card in the "By entity" picker

### Fixed

- Fix dashboard card stuck loading

### Changed

- Initial release of Solar Floor Boost integration
- Boost all selected thermostats, including those that are off
- Publish a GitHub release when the manifest version changes


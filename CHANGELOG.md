# Changelog

What changed in each version of Solar Floor Boost. Generated from the
commit history when a version is released; the same text is shown as the
release notes in Home Assistant's Marketplace and HACS.


## [1.7.2](https://github.com/alarmatwork/ha-solar-floor-boost/releases/tag/v1.7.2) - 2026-11-17

### Changed

- Card asks for a reload when the integration is newer than the loaded file

## [1.7.1](https://github.com/alarmatwork/ha-solar-floor-boost/releases/tag/v1.7.1) - 2026-11-17

### Changed

- Card URL includes the file hash so updates at the same version bust the cache
- Share Amount and Duration between Boost and Setback; follow the system temperature unit

## [1.7.0](https://github.com/alarmatwork/ha-solar-floor-boost/releases/tag/v1.7.0) - 2026-11-17

### Added

- Add Setback: temporarily lower thermostats, the opposite of Boost

### Documentation

- The integration is in the Marketplace/HACS catalog now

## [1.6.1](https://github.com/alarmatwork/ha-solar-floor-boost/releases/tag/v1.6.1) - 2026-11-16

### Added

- Add Marketplace/HACS validation workflow and document both install paths
- Add integration categories; move actions to Node 24 releases

### Documentation

- Document the solar surplus automation and Forecast.Solar setup

### Maintenance

- Sort manifest keys the way hassfest requires

## [1.6.0](https://github.com/alarmatwork/ha-solar-floor-boost/releases/tag/v1.6.0) - 2026-10-07

### Changed

- Duration in hours so Home Assistant shows "4h 45m"

## [1.5.1](https://github.com/alarmatwork/ha-solar-floor-boost/releases/tag/v1.5.1) - 2026-10-07

### Changed

- Duration presets end with 6h, 8h, 12h again

## [1.5.0](https://github.com/alarmatwork/ha-solar-floor-boost/releases/tag/v1.5.0) - 2026-10-07

### Changed

- Single duration slider: minutes on the device page, presets in the card

## [1.4.0](https://github.com/alarmatwork/ha-solar-floor-boost/releases/tag/v1.4.0) - 2026-10-07

### Changed

- Duration presets everywhere, including the device page

## [1.3.2](https://github.com/alarmatwork/ha-solar-floor-boost/releases/tag/v1.3.2) - 2026-10-07

### Fixed

- Fix card missing from the picker (custom element registry race)

## [1.3.1](https://github.com/alarmatwork/ha-solar-floor-boost/releases/tag/v1.3.1) - 2026-10-07

### Fixed

- Restore the duration number entity (fixes cards broken by 1.3.0)

## [1.3.0](https://github.com/alarmatwork/ha-solar-floor-boost/releases/tag/v1.3.0) - 2026-10-07

### Changed

- Boost duration as presets: 15m, 30m, 45m, 1h ... 12h

## [1.2.1](https://github.com/alarmatwork/ha-solar-floor-boost/releases/tag/v1.2.1) - 2026-10-07

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


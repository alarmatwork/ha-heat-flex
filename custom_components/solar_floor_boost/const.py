"""Constants for Solar Floor Boost."""

DOMAIN = "solar_floor_boost"

CONF_CLIMATES = "climate_entities"
CONF_MAX_TEMPERATURE = "max_temperature"
CONF_MIN_TEMPERATURE = "min_temperature"

# The two modes: a boost raises targets, a setback lowers them.
MODE_BOOST = "boost"
MODE_SETBACK = "setback"
MODES = (MODE_BOOST, MODE_SETBACK)

DEFAULT_DELTA = 1.0  # °C
DEFAULT_DURATION = 120  # minutes
DEFAULT_MAX_TEMPERATURE = 28.0  # °C, safety cap for any boosted target
DEFAULT_MIN_TEMPERATURE = 15.0  # °C, safety floor for any setback target
DEFAULT_TEMP_STEP = 0.5

ATTR_DELTA = "delta"
ATTR_DURATION = "duration"
ATTR_CLIMATE_ENTITIES = "climate_entities"

SERVICE_START = "start"
SERVICE_STOP = "stop"
SERVICE_START_SETBACK = "start_setback"
SERVICE_STOP_SETBACK = "stop_setback"

STORAGE_VERSION = 1

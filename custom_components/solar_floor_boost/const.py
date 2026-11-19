"""Constants for Heat Flex."""

# The domain keeps the original project name (Solar Floor Boost, up to
# 1.10): it is in every unique ID, entity ID, action name and storage file.
DOMAIN = "solar_floor_boost"
NAME = "Heat Flex"
LEGACY_NAME = "Solar Floor Boost"

CONF_CLIMATES = "climate_entities"
CONF_MAX_TEMPERATURE = "max_temperature"
CONF_MIN_TEMPERATURE = "min_temperature"

# The two modes: a boost raises targets, a setback lowers them.
MODE_BOOST = "boost"
MODE_SETBACK = "setback"
MODES = (MODE_BOOST, MODE_SETBACK)

DEFAULT_DURATION = 120  # minutes
# Temperature defaults live in units.py: they depend on the system unit.

ATTR_DELTA = "delta"
ATTR_DURATION = "duration"
ATTR_CLIMATE_ENTITIES = "climate_entities"
# Name of the automation (or script) starting a boost/setback, for debugging.
ATTR_AUTOMATION = "automation"

# Who started the running session: a person (UI, developer tools) or an
# automation/script. Decided from the service call's context.
SOURCE_MANUAL = "manual"
SOURCE_AUTOMATION = "automation"

SERVICE_START = "start"
SERVICE_STOP = "stop"
SERVICE_START_SETBACK = "start_setback"
SERVICE_STOP_SETBACK = "stop_setback"

STORAGE_VERSION = 1

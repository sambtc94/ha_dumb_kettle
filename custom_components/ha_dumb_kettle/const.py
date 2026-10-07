"""Constants for the Dumb Kettle integration."""
from datetime import timedelta

DOMAIN = "ha_dumb_kettle"

# Config entry keys
CONF_POWER_SENSOR = "power_sensor"
CONF_BOILING_THRESHOLD = "boiling_threshold"
CONF_IDLE_THRESHOLD = "idle_threshold"
CONF_MIN_BOIL_DURATION = "min_boil_duration"
CONF_BOIL_COMPLETE_DURATION = "boil_complete_duration"

# Default values
DEFAULT_BOILING_THRESHOLD = 1000  # Watts – power above this means kettle is boiling
DEFAULT_IDLE_THRESHOLD = 50       # Watts – power below this means kettle is idle
DEFAULT_MIN_BOIL_DURATION = 10    # Seconds – ignore boils shorter than this
DEFAULT_BOIL_COMPLETE_DURATION = 30  # Seconds – how long the boil-complete sensor stays ON

# A boil start restored after a restart is only trusted if it is this recent
MAX_RESTORED_BOIL_AGE = timedelta(minutes=15)

# State attribute that carries the boil start time across restarts
ATTR_BOIL_STARTED = "boil_started"

# Kettle states
STATE_IDLE = "idle"
STATE_BOILING = "boiling"

# Platforms
PLATFORMS = ["sensor", "binary_sensor"]

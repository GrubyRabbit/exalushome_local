"""Constants for ExalusHome Local integration."""

DOMAIN = "exalushome_local"

# Configuration keys
CONF_HOST = "host"
CONF_SERIAL = "serial"
CONF_PIN = "pin"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

# Default values
DEFAULT_PORT = 81
DEFAULT_PING_INTERVAL = 5000  # milliseconds
DEFAULT_STATE_POLLING_INTERVAL = 300  # seconds - reduce unnecessary /devices/list refreshes, websocket provides live state

# WebSocket protocol constants
WEBSOCKET_PORT = 81
WEBSOCKET_URL_FORMAT = "ws://{host}:{port}/"
WEBSOCKET_CONTROL_RESOURCE = "/devices/device/control"
WEBSOCKET_STATE_EVENT_RESOURCE = "/info/devices/device/state/changed"

# Device control features
DEVICE_CONTROL_FEATURE_BLIND = 3

# Blind control commands
BLIND_CONTROL_OPEN = 101
BLIND_CONTROL_CLOSE = 102
BLIND_CONTROL_STOP = 103

# Position mapping
# Exalus: 0 = open, 100 = closed
# Home Assistant: 0 = closed, 100 = open
# HA position = 100 - Exalus position
def exalus_to_ha_position(exalus_position: int) -> int:
    """Convert Exalus position scale to Home Assistant position scale."""
    return 100 - exalus_position


def ha_to_exalus_position(ha_position: int) -> int:
    """Convert Home Assistant position scale to Exalus position scale."""
    return 100 - ha_position


# HTTP endpoints
HTTP_CONTROLLER_INFO_ENDPOINT = "http://{host}/controller_info"
HTTP_SYSTEM_PING_ENDPOINT = "http://{host}/system/ping"

# State tracking
ATTR_DEVICE_GUID = "device_guid"
ATTR_CHANNEL = "channel"
ATTR_POSITION = "position"
ATTR_MOVING = "is_moving"
ATTR_AVAILABILITY = "available"

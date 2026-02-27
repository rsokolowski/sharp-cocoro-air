"""Constants for the Sharp COCORO Air integration."""

from homeassistant.const import Platform

DOMAIN = "sharp_cocoro_air"
PLATFORMS: list[Platform] = [Platform.FAN, Platform.SENSOR, Platform.SWITCH]

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 300

# Maps API mode key -> display name
OPERATION_MODES = {
    "auto": "Auto",
    "night": "Night",
    "pollen": "Pollen",
    "silent": "Silent",
    "medium": "Medium",
    "high": "High",
    "ai_auto": "AI Auto",
    "realize": "Realize",
}

# Reverse: display name -> API key (for decoding current mode from ECHONET data)
DISPLAY_TO_API_MODE = {v: k for k, v in OPERATION_MODES.items()}

CLEANING_MODES = {
    0x41: "Cleaning",
    0x42: "Humidifying",
    0x43: "Cleaning + Humidifying",
    0x44: "Off",
}

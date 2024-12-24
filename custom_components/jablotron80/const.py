"""Jablotron specific constants."""

import logging
import sys

LOGGER = logging.getLogger(__package__)

DOMAIN = "jablotron80"
NAME = "Jablotron 80"
MANUFACTURER = "Jablotron"
CENTRAL_UNIT_MODEL = "JA-80K"

CABLE_MODEL_JA82T = "JA_82T"
CABLE_MODEL_JA80T = "JA_80T"
CABLE_MODELS = {CABLE_MODEL_JA82T: "JA-82T", CABLE_MODEL_JA80T: "JA-80T"}
DATA_JABLOTRON = "jablotron"
DATA_OPTIONS_UPDATE_UNSUBSCRIBER = "options_update_unsubscriber"
CONFIGURATION_CENTRAL_SETTINGS = "settings"
CONFIGURATION_DEVICES = "devices"
CONFIGURATION_CODES = "codes"
CONFIGURATION_SERIAL_PORT = "serial_port"
CABLE_MODEL = "cable_model"
DEFAULT_SERIAL_PORT = "/dev/hidraw0"
DEFAULT_CABLE_MODEL = "JA-82T"
CONFIGURATION_NUMBER_OF_WIRED_DEVICES = "number_of_wired_devices"
CONFIGURATION_PASSWORD = "password"
MAX_NUMBER_OF_DEVICES = 63
MAX_NUMBER_OF_WIRED_DEVICES = 30  # maximum number wtih JA-83K and 2 expansion modules
MIN_NUMBER_OF_WIRED_DEVICES = 4  # standard for JA-82K is 4

DEVICE_CONFIGURATION_REQUIRE_CODE_TO_ARM = "device_require_code_to_arm"
DEVICE_CONFIGURATION_SYSTEM_MODE = "device_system_mode"
CONFIGURATION_REQUIRE_CODE_TO_ARM = "require_code_to_arm"
CONFIGURATION_REQUIRE_CODE_TO_DISARM = "require_code_to_disarm"
CONFIGURATION_QUIETEN_EXPECTED_WARNINGS = "quieten_expected_warnings"
CONFIGURATION_VERBOSE_CONNECTION_LOGGING = "verbose_connection_logging"
DEFAULT_CONFIGURATION_REQUIRE_CODE_TO_ARM = True
DEFAULT_CONFIGURATION_REQUIRE_CODE_TO_DISARM = True
DEFAULT_CONFIGURATION_QUIETEN_EXPECTED_WARNINGS = False
DEFAULT_CONFIGURATION_VERBOSE_CONNECTION_LOGGING = False

# Set default Log Level to Debug
# LOGGER.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
# handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
LOGGER.addHandler(handler)

DEVICE_EMPTY = "empty"
DEVICE_BUTTON = "button"
DEVICE_KEY_FOB = "key_fob"
DEVICE_KEYPAD = "keypad"
DEVICE_SIREN_OUTDOOR = "outdoor_siren"
DEVICE_SIREN_INDOOR = "indoor_siren"
DEVICE_MOTION_DETECTOR = "motion_detector"
DEVICE_WINDOW_OPENING_DETECTOR = "window_opening_detector"
DEVICE_DOOR_OPENING_DETECTOR = "door_opening_detector"
DEVICE_GLASS_BREAK_DETECTOR = "glass_break_detector"
DEVICE_SMOKE_DETECTOR = "smoke_detector"
DEVICE_FLOOD_DETECTOR = "flood_detector"
DEVICE_GAS_DETECTOR = "gas_detector"
DEVICE_OTHER = "other"

DEVICES = {
    DEVICE_KEYPAD: "Keypad",
    DEVICE_SIREN_OUTDOOR: "Outdoor siren",
    DEVICE_SIREN_INDOOR: "Indoor siren",
    DEVICE_MOTION_DETECTOR: "Motion detector",
    DEVICE_WINDOW_OPENING_DETECTOR: "Window opening detector",
    DEVICE_DOOR_OPENING_DETECTOR: "Door opening detector",
    DEVICE_GLASS_BREAK_DETECTOR: "Glass break detector",
    DEVICE_SMOKE_DETECTOR: "Smoke detector",
    DEVICE_FLOOD_DETECTOR: "Flood detector",
    DEVICE_GAS_DETECTOR: "Gas detector",
    DEVICE_KEY_FOB: "Key fob",
    DEVICE_BUTTON: "Button",
    DEVICE_OTHER: "Other",
    DEVICE_EMPTY: "Empty",
}

DEVICE_CONTROL_PANEL = "control_panel"

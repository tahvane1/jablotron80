"""Jablotron specific constants."""
import logging
import sys
LOGGER = logging.getLogger(__package__)

DOMAIN = "jablotron80"
NAME = "Jablotron 80"
MANUFACTURER = "Jablotron"
CENTRAL_UNIT_MODEL = "JA-80K"
CABLE_MODEL = "JA-82T"
DATA_JABLOTRON = "jablotron"
DATA_OPTIONS_UPDATE_UNSUBSCRIBER = "options_update_unsubscriber"
CONFIGURATION_CENTRAL_SETTINGS = "settings"
CONFIGURATION_DEVICES = "devices"
CONFIGURATION_CODES = "codes"
CONFIGURATION_SERIAL_PORT = "serial_port"
DEFAULT_SERIAL_PORT = "/dev/hidraw0"
CONFIGURATION_NUMBER_OF_DEVICES = "number_of_devices"
CONFIGURATION_PASSWORD = "password"
MAX_NUMBER_OF_DEVICES = 50

DEVICE_CONFIGURATION_REQUIRE_CODE_TO_ARM = "device_require_code_to_arm"
DEVICE_CONFIGURATION_SYSTEM_MODE = "device_system_mode"
CONFIGURATION_REQUIRE_CODE_TO_ARM = "require_code_to_arm"
CONFIGURATION_REQUIRE_CODE_TO_DISARM = "require_code_to_disarm"
DEFAULT_CONFIGURATION_REQUIRE_CODE_TO_ARM = True
DEFAULT_CONFIGURATION_REQUIRE_CODE_TO_DISARM = True


LOGGER.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

import asyncio
from homeassistant.components.alarm_control_panel import (
    DOMAIN as PLATFORM_ALARM_CONTROL_PANEL,
)
from homeassistant.components.binary_sensor import DOMAIN as PLATFORM_BINARY_SENSOR
from homeassistant.components.sensor import DOMAIN as PLATFORM_SENSOR
from homeassistant.components.button import DOMAIN as PLATFORM_BUTTON
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, config_validation as cv

# from . import hub
from .const import (
    DOMAIN,
    DATA_JABLOTRON,
    DATA_OPTIONS_UPDATE_UNSUBSCRIBER,
    NAME,
    CABLE_MODEL,
    MANUFACTURER,
    CABLE_MODELS,
)
from .jablotron import JA80CentralUnit

# List of platforms to support. There should be a matching .py file for each,
# eg <cover.py> and <sensor.py>
PLATFORMS = [
    PLATFORM_ALARM_CONTROL_PANEL,
    PLATFORM_BINARY_SENSOR,
    PLATFORM_SENSOR,
    PLATFORM_BUTTON,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict):
    # Ensure our name space for storing objects is a known type. A dict is
    # common/preferred as it allows a separate instance of your class for each
    # instance that has been created in the UI.
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Store an instance of the "connecting" class that does the work of speaking
    # with your actual devices.
    # hass.data[DOMAIN][entry.entry_id] = hub.Hub(hass, entry.data["host"])

    # This creates each HA object for each platform your device requires.
    # It's done by calling the `async_setup_entry` function in each platform module.

    cu = JA80CentralUnit(hass, entry.data, entry.options)
    await cu.initialize()

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, cu.serial_port)},
        name="Cable",
        model=CABLE_MODELS[entry.data[CABLE_MODEL]],
        manufacturer=MANUFACTURER,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_JABLOTRON: cu,
        DATA_OPTIONS_UPDATE_UNSUBSCRIBER: entry.add_update_listener(
            options_update_listener
        ),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    options_update_unsubscriber = hass.data[DOMAIN][entry.entry_id][
        DATA_OPTIONS_UPDATE_UNSUBSCRIBER
    ]
    options_update_unsubscriber()
    cu = hass.data[DOMAIN][entry.entry_id][DATA_JABLOTRON]
    cu.shutdown()
    hass.data[DOMAIN].pop(entry.entry_id)
    return True


async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    cu = hass.data[DOMAIN][entry.entry_id][DATA_JABLOTRON]
    cu.update_options(entry.options)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from .const import (
    DATA_JABLOTRON,
    DOMAIN,
    DEVICE_MOTION_DETECTOR,
    DEVICE_WINDOW_OPENING_DETECTOR,
    DEVICE_DOOR_OPENING_DETECTOR,
    DEVICE_GLASS_BREAK_DETECTOR,
    DEVICE_SMOKE_DETECTOR,
    DEVICE_FLOOD_DETECTOR,
    DEVICE_GAS_DETECTOR,
    DEVICE_KEY_FOB,
    DEVICE_KEYPAD,
    DEVICE_SIREN_INDOOR,
    DEVICE_BUTTON,
    DEVICE_CONTROL_PANEL,
)
from .jablotron import JA80CentralUnit, JablotronDevice, JablotronConstants
from .jablotronHA import JablotronEntity
from typing import Optional
import logging

LOGGER = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
    cu = hass.data[DOMAIN][config_entry.entry_id][DATA_JABLOTRON]  # type: JA80CentralUnit
    async_add_entities([JablotronDeviceSensorEntity(device, cu) for device in cu.devices], True)
    async_add_entities([JablotronDeviceSensorEntity(cu.central_device, cu)], True)
    async_add_entities([JablotronDeviceSensorEntity(led, cu) for led in cu.leds], True)
    async_add_entities([JablotronDeviceSensorEntity(code, cu) for code in cu.codes], True)
    async_add_entities([JablotronDeviceSensorEntity(cu.statustext, cu)], True)


class JablotronDeviceSensorEntity(JablotronEntity, BinarySensorEntity):
    def __init__(self, device: JablotronDevice, cu: JA80CentralUnit):
        super().__init__(cu, device)

    @property
    def is_on(self) -> bool:
        return self._object.active

    @property
    def icon(self) -> Optional[str]:
        return None

    @property
    def device_class(self) -> Optional[str]:
        if self._object._id <= 0:
            if "code" == self._object.type and self._object.reaction == JablotronConstants.REACTION_PANIC:
                return BinarySensorDeviceClass.SAFETY
            elif (
                "code" == self._object.type
                and self._object.reaction == JablotronConstants.REACTION_FIRE_ALARM
            ):
                return BinarySensorDeviceClass.SMOKE
            elif "code" == self._object.type:
                return BinarySensorDeviceClass.MOTION
            elif DEVICE_CONTROL_PANEL == self._object.type:
                return BinarySensorDeviceClass.PROBLEM
            elif "power led" == self._object.type:
                return BinarySensorDeviceClass.POWER
            elif "armed led" == self._object.type:
                return BinarySensorDeviceClass.LIGHT
        if self._object.type == DEVICE_MOTION_DETECTOR:
            return BinarySensorDeviceClass.MOTION
        if self._object.type == DEVICE_KEYPAD:
            return BinarySensorDeviceClass.PROBLEM
        if self._object.type == DEVICE_WINDOW_OPENING_DETECTOR:
            return BinarySensorDeviceClass.WINDOW

        if self._object.type == DEVICE_DOOR_OPENING_DETECTOR:
            return BinarySensorDeviceClass.DOOR

        if self._object.type == DEVICE_FLOOD_DETECTOR:
            return BinarySensorDeviceClass.MOISTURE

        if self._object.type == DEVICE_GAS_DETECTOR:
            return BinarySensorDeviceClass.GAS

        if self._object.type == DEVICE_SMOKE_DETECTOR:
            return BinarySensorDeviceClass.SMOKE

        return None

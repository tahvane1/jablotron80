from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.binary_sensor import (
	BinarySensorEntity,
	DEVICE_CLASS_CONNECTIVITY,
	DEVICE_CLASS_DOOR,
	DEVICE_CLASS_GAS,
	DEVICE_CLASS_MOISTURE,
	DEVICE_CLASS_MOTION,
	DEVICE_CLASS_PROBLEM,
	DEVICE_CLASS_SAFETY,
	DEVICE_CLASS_SMOKE,
	DEVICE_CLASS_WINDOW,
 	DEVICE_CLASS_LIGHT,
 	DEVICE_CLASS_POWER,
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
)
from .jablotron import JA80CentralUnit, JablotronDevice,JablotronConstants
from .jablotronHA import JablotronEntity
from typing import Optional
import logging
LOGGER = logging.getLogger(__package__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
	cu = hass.data[DOMAIN][config_entry.entry_id][DATA_JABLOTRON] # type: JA80CentralUnit
	async_add_entities([JablotronDeviceSensorEntity(device,cu) for device in cu.devices], True)
	async_add_entities([JablotronDeviceSensorEntity(led,cu) for led in cu.leds], True)
	async_add_entities([JablotronDeviceSensorEntity(code,cu) for code in cu.codes], True)


class JablotronDeviceSensorEntity(JablotronEntity,BinarySensorEntity):
	def __init__(self, device: JablotronDevice,cu: JA80CentralUnit):
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
				return DEVICE_CLASS_SAFETY
			elif "code" == self._object.type and self._object.reaction == JablotronConstants.REACTION_FIRE_ALARM:
				return DEVICE_CLASS_SMOKE
			elif "code" == self._object.type:
				return DEVICE_CLASS_MOTION
			elif "Control Panel" == self._object.type:
				return DEVICE_CLASS_PROBLEM
			elif "power led" == self._object.type:
				return DEVICE_CLASS_POWER
			elif "armed led" == self._object.type:
				return DEVICE_CLASS_LIGHT
		if self._object.type == DEVICE_MOTION_DETECTOR:
			return DEVICE_CLASS_MOTION
		if self._object.type == DEVICE_KEYPAD:
			return DEVICE_CLASS_PROBLEM
		if self._object.type == DEVICE_WINDOW_OPENING_DETECTOR:
			return DEVICE_CLASS_WINDOW

		if self._object.type == DEVICE_DOOR_OPENING_DETECTOR:
			return DEVICE_CLASS_DOOR

		if self._object.type == DEVICE_FLOOD_DETECTOR:
			return DEVICE_CLASS_MOISTURE

		if self._object.type == DEVICE_GAS_DETECTOR:
			return DEVICE_CLASS_GAS

		if self._object.type == DEVICE_SMOKE_DETECTOR:
			return DEVICE_CLASS_SMOKE

		return None





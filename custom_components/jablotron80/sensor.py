from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from .jablotron import JA80CentralUnit, JablotronDevice,JablotronConstants,JablotronZone,JablotronSensor
from .jablotronHA import JablotronEntity
from typing import Optional
from .const import (
	DATA_JABLOTRON,
	DOMAIN)


from homeassistant.const import (
     DEVICE_CLASS_SIGNAL_STRENGTH
)
import logging
LOGGER = logging.getLogger(__package__)
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
	cu = hass.data[DOMAIN][config_entry.entry_id][DATA_JABLOTRON] # type: JA80CentralUnit
	async_add_entities([JablotronZoneSensorEntity(zone,cu) for zone in cu.zones], True)
	async_add_entities([JablotronSignalEntity(cu.rf_level,cu)], True)
	async_add_entities([JablotronSensorEntity(cu.alert,cu)], True)

class JablotronZoneSensorEntity(JablotronEntity):
	def __init__(self, zone: JablotronZone,cu: JA80CentralUnit) -> None:
		super().__init__(cu, zone) 

	@property
	def state(self) -> str:
		"""Return the state of the sensor."""
		return self._object.status

	@property
	def icon(self) -> Optional[str]:
		return None

	@property
	def unique_id(self) -> str:
		return f"{DOMAIN}.{self._cu.serial_port}.zone.{self._object._id}"

class JablotronSensorEntity(JablotronEntity):
	def __init__(self, sensor: JablotronSensor,cu: JA80CentralUnit) -> None:
		super().__init__(cu, sensor) 

	@property
	def state(self) -> str:
		"""Return the state of the sensor."""
		return self._object.value

	@property
	def icon(self) -> Optional[str]:
		return None

	@property
	def unique_id(self) -> str:
		return f"{DOMAIN}.{self._cu.serial_port}.sensor.{self._object._id}"

class JablotronSignalEntity(JablotronSensorEntity):
	def __init__(self, sensor: JablotronSensor,cu: JA80CentralUnit) -> None:
		super().__init__(sensor, cu) 

	@property
	def unit_of_measurement(self) -> str:
		return "%"

	@property
	def device_class(self) -> str:
		return DEVICE_CLASS_SIGNAL_STRENGTH
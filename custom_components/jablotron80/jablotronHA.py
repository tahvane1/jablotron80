from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType
from typing import Any, Dict, List, Optional,Union
from .const import DATA_JABLOTRON, DOMAIN,NAME,MANUFACTURER,CENTRAL_UNIT_MODEL,DEVICES
from .jablotron import JA80CentralUnit, JablotronDevice,JablotronZone,JablotronCommon
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

class JablotronEntity(Entity):
	
	def __init__(
			self,
			cu: JA80CentralUnit,
			obj: JablotronCommon,
	) -> None:
		self._cu: JA80CentralUnit = cu
		self._object: JablotronCommon = obj


	@property
	def should_poll(self) -> bool:
		return False

	@property
	def available(self) -> bool:
		return self._cu.led_power

	@property
	def device_info(self) -> Optional[Dict[str, Any]]:
		if self._object is None:
			return {
			"identifiers": {(DOMAIN, self._cu.serial_port)},
		}
		name = CENTRAL_UNIT_MODEL
		if self._object.device_id > 0:
			name = self._object.name
		info = {"identifiers": {(DOMAIN, self._object.device_id)},
			"name": name,
			"via_device": (DOMAIN, self._cu.serial_port)}
		if hasattr(self._object,"model") and not self._object.model is None:
			info["model"] = self._object.model
		if hasattr(self._object,"manufacturer") and not self._object.manufacturer is None:
			info["manufacturer"] = self._object.manufacturer
		return info


	@property
	def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
		attr ={}
		if not self._object is None and not self._object.type is None:
			if self._object.type in DEVICES:
				attr["type"] = DEVICES[self._object.type]
			else:
				attr["type"] = self._object.type
		if not self._object is None and not self._object.zone is None:
			attr["zone"] = self._object.zone.name
			attr["zoneid"] = self._object.zone._id
		if not self._object is None and not self._object.reaction is None:
			attr["reaction"] = self._object.reaction
		if not self._object is None and hasattr(self._object,"by"):
			attr["by"] = self._object.formatted_by
		for field in ["serial_number","model","manufacturer","id","type","battery_low","tampered"]:
			if not self._object is None and hasattr(self._object,field):
				value = getattr(self._object,field)
				if not value is None:
					attr[field.replace("_"," ")] = getattr(self._object,field)
		return attr

	@property
	def name(self) -> str:
		return self._object.name

	@property
	def unique_id(self) -> str:
		return f"{DOMAIN}.{self._cu.serial_port}.{self._object.id_part}.{self._object._id}"
	
	async def async_added_to_hass(self) -> None:
		#state = await self.async_get_last_state()
		self._object.register_callback(self.async_write_ha_state)
		#if not state:
		#	return
		#self._state = state

	
	async def async_will_remove_from_hass(self) -> None:
		"""Entity being removed from hass."""
		self._object.remove_callback(self.async_write_ha_state)

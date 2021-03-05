from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType
from homeassistant.components.alarm_control_panel import (
	AlarmControlPanelEntity,
	FORMAT_NUMBER,
 	SUPPORT_ALARM_ARM_HOME,
	SUPPORT_ALARM_ARM_AWAY,
	SUPPORT_ALARM_ARM_NIGHT,
 	SUPPORT_ALARM_TRIGGER,
	ATTR_CHANGED_BY,
	ATTR_CODE_ARM_REQUIRED
)

from homeassistant.const import (
	ATTR_CODE,
	ATTR_CODE_FORMAT,
	STATE_ALARM_DISARMED,
	STATE_ALARM_ARMED_HOME,
	STATE_ALARM_ARMED_AWAY,
	STATE_ALARM_ARMED_NIGHT,
	STATE_ALARM_ARMED_CUSTOM_BYPASS,
	STATE_ALARM_PENDING,
	STATE_ALARM_ARMING,
	STATE_ALARM_DISARMING,
	STATE_ALARM_TRIGGERED,
 	STATE_UNKNOWN
)
from .const import (
	CONFIGURATION_REQUIRE_CODE_TO_ARM,
	CONFIGURATION_REQUIRE_CODE_TO_DISARM,

)

from typing import Any, Dict, List, Optional
from .const import DATA_JABLOTRON, DOMAIN,NAME, MANUFACTURER
from .jablotron import JA80CentralUnit, JablotronDevice,JablotronZone
from .jablotronHA import JablotronEntity


import logging
LOGGER = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
	cu = hass.data[DOMAIN][config_entry.entry_id][DATA_JABLOTRON]
	# how to handle split system?
	if not cu.mode == JA80CentralUnit.SYSTEM_MODE_SPLIT:
		async_add_entities([Jablotron80AlarmControl(cu,cu.zones)], True)
	else:
		async_add_entities([Jablotron80AlarmControl(cu,cu.zones,0)], True)
		async_add_entities([Jablotron80AlarmControl(cu,cu.zones,1)], True)


class Jablotron80AlarmControl(JablotronEntity,AlarmControlPanelEntity):

	def __init__(self, cu: JA80CentralUnit, zones: List[JablotronZone],main_zone:int = 0) -> None:
		self._object = zones[main_zone]
		self._main_zone = main_zone
		self._cu = cu
		self._zones = zones
		self._changed_by = "ME"

	@property
	def code_format(self) -> Optional[str]:
		if self.state == STATE_ALARM_DISARMED:
			code_required = self.code_arm_required
		else:
			code_required = self.code_disarm_required
		return FORMAT_NUMBER if code_required is True else None

	@staticmethod
	def _check_code(code: Optional[str]) -> Optional[str]:
		return None if code == "" else code


	@property
	def supported_features(self) -> int:
		if self._cu.mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT:
			return SUPPORT_ALARM_ARM_AWAY
		elif self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL:
			return SUPPORT_ALARM_ARM_AWAY|SUPPORT_ALARM_ARM_HOME|SUPPORT_ALARM_ARM_NIGHT
		elif self._cu.mode == JA80CentralUnit.SYSTEM_MODE_SPLIT:
			return SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_HOME
		return SUPPORT_ALARM_ARM_AWAY

	@property
	def code_arm_required(self) -> bool:
		if self._cu.is_code_required_for_arm():
			if CONFIGURATION_REQUIRE_CODE_TO_ARM in self._cu._options:
				return self._cu._options[CONFIGURATION_REQUIRE_CODE_TO_ARM]
			return True
		else:
			return False


	@property
	def code_disarm_required(self) -> bool:
		if CONFIGURATION_REQUIRE_CODE_TO_DISARM in self._cu._options:
			return self._cu._options[CONFIGURATION_REQUIRE_CODE_TO_DISARM]
		else:
			return True

	async def async_alarm_disarm(self, code=None) -> None:
		if not self.code_disarm_required : 
			code = self._cu._master_code
		if self._cu.mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT:
			# just one zone so input code without any "kinks"
			# todo check if you can get disarming from serial line
			self._zones[0].status =  JablotronZone.STATUS_DISARMING
			self._cu.disarm(code)
		else:
			self._cu.disarm(code)

	async def async_alarm_arm_home(self, code=None) -> None:
		if not self._cu.is_code_required_for_arm():
			code = ""
		elif not self.code_arm_required : 
			code = self._cu._master_code
		if self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL:
			self._cu.arm(code,"A")
		elif self._cu.mode == JA80CentralUnit.SYSTEM_MODE_SPLIT:
			if self.main_zone == 0:
				self._cu.arm(code,"A")
			else:
				self._cu.arm(code,"B")
	
	async def async_alarm_arm_away(self, code=None) -> None:
		if not self._cu.is_code_required_for_arm():
			code = ""
		elif not self.code_arm_required : 
			code = self._cu._master_code
		if self._cu.mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT:
			# just one zone so input code without any "kinks"
			self._cu.arm(code)
		elif self._cu.mode in [JA80CentralUnit.SYSTEM_MODE_PARTIAL,JA80CentralUnit.SYSTEM_MODE_SPLIT]:
			self._cu.arm(code,"C")

	async def async_alarm_arm_night(self, code=None) -> None:
		if not self._cu.is_code_required_for_arm():
			code = ""
		elif not self.code_arm_required : 
			code = self._cu._master_code
		if self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL:
			self._cu.arm(code,"B")

	async  def async_alarm_trigger(self, code=None) -> None:
		raise NotImplementedError()

	async  def async_alarm_arm_custom_bypass(self, code=None) -> None:
		raise NotImplementedError()


	def get_active_zone(self) -> JablotronZone:
		if self._cu.mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT and len(self._zones) == 1:
 			return self._zones[0]
		elif self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL and len(self._zones) == 3:
			zone_home = self._zones[0]
			zone_night = self._zones[1]
			zone_away  = self._zones[2]
			for zone in [zone for zone in self._zones if zone.status == JablotronZone.STATUS_ALARM]:
				return zone
			for  zone in [zone for zone in self._zones if zone.status == JablotronZone.STATUS_ENTRY_DELAY]:
				return zone
			if zone_away.status == JablotronZone.STATUS_ARMED:
				return zone_away
			elif zone_night.status == JablotronZone.STATUS_ARMED:
				return zone_night
			elif zone_home.status == JablotronZone.STATUS_ARMED:
				return zone_home
			for zone in [zone for zone in self._zones if zone.status == JablotronZone.STATUS_ARMING]:
				return zone
			for zone in [zone for zone in self._zones if zone.status == JablotronZone.STATUS_DISARMED]:
				return zone
		elif self._cu.mode == JA80CentralUnit.SYSTEM_MODE_SPLIT and len(self._zones) == 3:
			zone_home = self._zones[self._main_zone]
			zone_away  = self._zones[2]
			for zone in [zone for zone in [zone_home.status,zone_away.status] if zone.status == JablotronZone.STATUS_ALARM]:
				return zone
			for zone in [zone for zone in [zone_home.status,zone_away.status] if zone.status == JablotronZone.STATUS_ENTRY_DELAY]:
				return zone
			if zone_away.status == JablotronZone.STATUS_ARMED:
				return zone_away
			elif zone_home.status == JablotronZone.STATUS_ARMED:
				return zone_home
			for zone in [zone for zone in [zone_home.status,zone_away.status] if zone.status ==  JablotronZone.STATUS_ARMING]:
				return zone
			for zone in [zone for zone in [zone_home.status,zone_away.status] if zone.status ==  JablotronZone.STATUS_DISARMED]:
				return zone
	@property
	def state(self) -> str:
		zone = self.get_active_zone()
		if zone.status == JablotronZone.STATUS_ENTRY_DELAY:
			return STATE_ALARM_PENDING 
		elif zone.status == JablotronZone.STATUS_ARMING :
			return STATE_ALARM_ARMING 
		elif zone.status == JablotronZone.STATUS_ALARM  :
			return STATE_ALARM_TRIGGERED
			
		elif zone.status == JablotronZone.STATUS_ARMED and self._cu.mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT:
			return STATE_ALARM_ARMED_HOME
		
		elif zone.status == JablotronZone.STATUS_ARMED and self._cu.mode == JA80CentralUnit.SYSTEM_MODE_SPLIT and not zone == self._object:
			return STATE_ALARM_ARMED_AWAY
		elif zone.status == JablotronZone.STATUS_ARMED and self._cu.mode == JA80CentralUnit.SYSTEM_MODE_SPLIT and zone == self._object:
			return STATE_ALARM_ARMED_HOME
		
		elif zone.status == JablotronZone.STATUS_ARMED and self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL and zone._id == 1:
			return STATE_ALARM_ARMED_HOME
		elif zone.status == JablotronZone.STATUS_ARMED and self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL and zone._id == 2:
			return STATE_ALARM_ARMED_NIGHT
		elif zone.status == JablotronZone.STATUS_ARMED and self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL and zone._id == 3:

			return STATE_ALARM_ARMED_AWAY
		elif zone.status == JablotronZone.STATUS_DISARMED:
			return STATE_ALARM_DISARMED
		elif zone.status == JablotronZone.STATUS_DISARMING:
			return STATE_ALARM_DISARMING

		return STATE_UNKNOWN

	@property
	def should_poll(self) -> bool:
		return False

	@property
	def available(self) -> bool:
		return self._cu.led_power

	@property
	def device_info(self) -> Optional[Dict[str, Any]]:
		info = {"identifiers": {(DOMAIN, f'jablotron_panel_{self._main_zone}')},
			"name": "jablotron panel",
			"via_device": (DOMAIN, self._cu.serial_port)}
		info["model"] = "Home Assistant control panel"
		info["manufacturer"] = "Jablotron"
		return info


	@property
	def device_state_attributes(self) -> Optional[Dict[str, Any]]:
		attr = super().device_state_attributes
		return attr

	@property 
	def changed_by(self) -> str:
		zone = self.get_active_zone()
		return zone.formatted_by

	@property
	def name(self) -> str:
		if self._cu.mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT:
			return "Jablotron control panel ABC"
		elif self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL:
			return "Jablotron control panel A,AB,ABC"
		elif self._cu.mode == JA80CentralUnit.SYSTEM_MODE_SPLIT:
			if self._main_zone == 0:
				return "Jablotron control panel A,C"
			else:
				return "Jablotron control panel B,C"
		return "Jablotron control panel"

	@property
	def unique_id(self) -> str:
		return f"{DOMAIN}.{self._cu.serial_port}.{self._main_zone}"
	
	async def async_added_to_hass(self) -> None:
		for zone in self._zones:
			zone.register_callback(self.async_write_ha_state)

	async def async_will_remove_from_hass(self) -> None:
		"""Entity being removed from hass."""
		for zone in self._zones:
			zone.remove_callback(self.async_write_ha_state)
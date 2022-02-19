import logging
import asyncio
import voluptuous as vol
from collections import OrderedDict
from typing import Any, Dict, Optional,List
from homeassistant import config_entries, core, exceptions
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.core import callback
LOGGER = logging.getLogger(__name__)
from .jablotron import JA80CentralUnit,JablotronConstants,JablotronDevice,JablotronCode
from .const import (
	CONFIGURATION_SERIAL_PORT,
	CONFIGURATION_NUMBER_OF_DEVICES,
	CONFIGURATION_PASSWORD,
	CONFIGURATION_DEVICES,
	CONFIGURATION_CODES,
	CONFIGURATION_CENTRAL_SETTINGS,
    CABLE_MODELS,
    CABLE_MODEL,
    DEFAULT_CABLE_MODEL,
	DOMAIN,
	DEFAULT_SERIAL_PORT,
	MAX_NUMBER_OF_DEVICES,
 	NAME,
	DEVICES,
 	DEVICE_DOOR_OPENING_DETECTOR,
	DEVICE_KEYPAD,
	DEVICE_SMOKE_DETECTOR,
	DEVICE_CONFIGURATION_REQUIRE_CODE_TO_ARM,
 	DEVICE_CONFIGURATION_SYSTEM_MODE,
 	CONFIGURATION_REQUIRE_CODE_TO_ARM,
	CONFIGURATION_REQUIRE_CODE_TO_DISARM,
	DEFAULT_CONFIGURATION_REQUIRE_CODE_TO_ARM,
	DEFAULT_CONFIGURATION_REQUIRE_CODE_TO_DISARM,
)





class Jablotron80ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
	_config: Optional[Dict[str, Any]] = None
	_devices: Optional[List[JablotronDevice]]= None
	_codes: Optional[List[JablotronCode]]= None
	VERSION = 1
	# Pick one of the available connection classes in homeassistant/config_entries.py
	# This tells HA if it should be asking for updates, or it'll be notified of updates
	# automatically. This example uses PUSH, as the dummy hub will notify HA of
	# changes.
	CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

	@staticmethod
	@callback
	def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
		return JablotronOptionsFlow(config_entry)

	async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		"""Handle the initial step."""
		# This goes through the steps to take the user through the setup process.
		# Using this it is possible to update the UI and prompt for additional
		# information. This example provides a single form (built from `DATA_SCHEMA`),
		# and when that has some validated input, it calls `async_create_entry` to
		# actually create the HA config entry. Note the "title" value is returned by
		# `validate_input` above.
		errors = {}
		cables_by_names = {value:key for key, value in CABLE_MODELS.items()}
		if user_input is not None:
			
			#try:
			unique_id = user_input[CONFIGURATION_SERIAL_PORT]
			await self.async_set_unique_id(unique_id)
			self._abort_if_unique_id_configured()
			self._config = {
       			CABLE_MODEL: cables_by_names[user_input[CABLE_MODEL]],
				CONFIGURATION_SERIAL_PORT: user_input[CONFIGURATION_SERIAL_PORT],
				CONFIGURATION_PASSWORD: user_input[CONFIGURATION_PASSWORD],
				CONFIGURATION_NUMBER_OF_DEVICES: user_input[CONFIGURATION_NUMBER_OF_DEVICES],
		
			}
			cu = JA80CentralUnit(None, self._config, None)
			await cu.initialize()
			result = await cu.read_settings()
			self._config[CONFIGURATION_CENTRAL_SETTINGS] = {DEVICE_CONFIGURATION_REQUIRE_CODE_TO_ARM:DEFAULT_CONFIGURATION_REQUIRE_CODE_TO_ARM,
                                    DEVICE_CONFIGURATION_SYSTEM_MODE:cu.mode}
			await asyncio.sleep(5)
			cu.shutdown()
			
			

			if result:
				self._devices = cu.devices
				self._codes = cu.codes
				if result and user_input[CONFIGURATION_NUMBER_OF_DEVICES] == 0:
					if len(self._codes) == 0: 
						return self.async_create_entry(title=NAME, data=self._config)
					return await self.async_step_codes()
				else: 
					return await self.async_step_devices()
			else:
				errors["base"] = "settings_unavailable"
				LOGGER.error("Could not read settings!")
				return self.async_abort(reason="settings_unavailable")
			#except AbortFlow as ex:
			#    return self.async_abort(reason=ex.reason)
			#except Exception as ex:
			#    LOGGER.debug(format(ex))
			#    LOGGER.error("Unknown error connecting to %s at %s",NAME,user_input[CONFIGURATION_SERIAL_PORT])
			#    return self.async_abort(reason="unknown")
		# If there is no user input or there were errors, show the form again, including any errors that were found with the input.
		return self.async_show_form(
			step_id="user", data_schema=vol.Schema(
				{
        			vol.Required(CABLE_MODEL, default=DEFAULT_CABLE_MODEL): vol.In(list(CABLE_MODELS.values())),
					vol.Required(CONFIGURATION_SERIAL_PORT, default=DEFAULT_SERIAL_PORT): str,
					vol.Required(CONFIGURATION_PASSWORD): str,
					vol.Optional(CONFIGURATION_NUMBER_OF_DEVICES, default=5): vol.All(vol.Coerce(int), vol.Range(min=0, max=MAX_NUMBER_OF_DEVICES)),
				}
			),
			errors=errors,
		)

	async def async_step_devices(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		errors = {}
		devices_by_names = {value:key for key, value in DEVICES.items()}
		if user_input is not None:
			try:

				
				devices = {}
				for device in self._devices:
					devices[device.id] = {"serial_number":device.serial_number,
						"reaction":device.reaction,
						"zone": device.zone.id,
						"model":device.model,
						"manufacturer": device.manufacturer}
				for input in sorted(user_input):
					parts = input.split("_")
					if parts[0] == "device" and (parts[2] == "name" or parts[2] == "type"):
						if parts[2] == "type":
							devices[int(parts[1])][parts[2]] = devices_by_names[user_input[input]]
						else:
							devices[int(parts[1])][parts[2]] = user_input[input]

				self._config[CONFIGURATION_DEVICES] = devices
				if len(self._codes) == 0: 
					return self.async_create_entry(title=NAME, data=self._config)
				return await self.async_step_codes()

			except Exception as ex:
				LOGGER.debug(format(ex))

				return self.async_abort(reason="unknown")

		fields = OrderedDict()

		for i in range(1, self._config[CONFIGURATION_NUMBER_OF_DEVICES] + 1):
			default_device = DEVICE_DOOR_OPENING_DETECTOR
			device = self._devices[i-1]
			if device.is_control_panel: 
				default_device = DEVICES[DEVICE_KEYPAD]
			elif device.reaction == JablotronConstants.REACTION_FIRE_ALARM:
				default_device = DEVICES[DEVICE_SMOKE_DETECTOR]
			else: 
				default_device = DEVICES[DEVICE_DOOR_OPENING_DETECTOR]
			fields[vol.Required("device_{:03}_type".format(i),default=default_device)] = vol.In(list(DEVICES.values()))
			fields[vol.Required("device_{:03}_name".format(i),default=device.name)] = str

		return self.async_show_form(
			step_id="devices",
			data_schema=vol.Schema(fields),
			errors=errors,
		)
	
	async def async_step_codes(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		errors = {}
		if user_input is not None:
			try:

				codes = {}
				for code in self._codes:
					codes[code.id] = {"reaction":code.reaction,"code1":code.code1,"code2":code.code2}
				for input in sorted(user_input):
					parts = input.split("_")
					if parts[0] == "code" and parts[2] == "name":
						codes[int(parts[1])][parts[2]] = user_input[input]

				self._config[CONFIGURATION_CODES] = codes
				return self.async_create_entry(title=NAME, data=self._config)

			except Exception as ex:
				LOGGER.debug(format(ex))

				return self.async_abort(reason="unknown")

		fields = OrderedDict()

		for code in self._codes:
			default_name = f'code {code.code_id} user'
			if code.id == 0:
				default_name = "Master"
			fields[vol.Required("code_{:03}_name".format(code.id),default=default_name)] = str

		return self.async_show_form(
			step_id="codes",
			data_schema=vol.Schema(fields),
			errors=errors,
		)
class JablotronOptionsFlow(config_entries.OptionsFlow):
    
	def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
		self._config_entry: config_entries.ConfigEntry = config_entry

	async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None):
		if user_input is not None:
			return self.async_create_entry(title=NAME, data=user_input)

		return self.async_show_form(
			step_id="init",
			data_schema=vol.Schema(
				{
					vol.Optional(
						CONFIGURATION_REQUIRE_CODE_TO_DISARM,
						default=self._config_entry.options.get(CONFIGURATION_REQUIRE_CODE_TO_DISARM, DEFAULT_CONFIGURATION_REQUIRE_CODE_TO_DISARM),
					): bool,
					vol.Optional(
						CONFIGURATION_REQUIRE_CODE_TO_ARM,
						default=self._config_entry.options.get(CONFIGURATION_REQUIRE_CODE_TO_ARM, DEFAULT_CONFIGURATION_REQUIRE_CODE_TO_ARM),
					): bool,
				}
			),
		)  

import sys
import queue
import time
import datetime
from dataclasses import dataclass, field
import traceback
from typing import List,Any,Type,Optional,Union
import binascii
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import logging
import serial
import sys
LOGGER = logging.getLogger(__package__)

from typing import Any, Dict, Optional, Union,Callable
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from homeassistant.const import (
	EVENT_HOMEASSISTANT_STOP
)


if __name__ == "__main__":
	from const import (
		CONFIGURATION_SERIAL_PORT,
		CONFIGURATION_NUMBER_OF_DEVICES,
		CONFIGURATION_PASSWORD,
		CENTRAL_UNIT_MODEL,
		MANUFACTURER,
		MAX_NUMBER_OF_DEVICES,
		CONFIGURATION_DEVICES,
		CONFIGURATION_CODES,
		CABLE_MODEL,
		CABLE_MODEL_JA82T,
		CABLE_MODEL_JA80T 
	)
else:
	from .const import (
		CONFIGURATION_SERIAL_PORT,
		CONFIGURATION_NUMBER_OF_DEVICES,
		CONFIGURATION_PASSWORD,
		CENTRAL_UNIT_MODEL,
		MANUFACTURER,
		MAX_NUMBER_OF_DEVICES,
		CONFIGURATION_DEVICES,
		CONFIGURATION_CODES,
  		CABLE_MODEL,
		CABLE_MODEL_JA82T,
		CABLE_MODEL_JA80T,
		CONFIGURATION_CENTRAL_SETTINGS,
		DEVICE_CONFIGURATION_REQUIRE_CODE_TO_ARM,
		DEVICE_CONFIGURATION_SYSTEM_MODE,
	)
def log_change(func):
	def wrapper(*args, **kwargs):
		LOGGER.debug(f'{args[0].__class__.__name__} function call {func.__name__}')
		_id = "N/A"
		if hasattr(args[0],'_id'):
			_id = getattr(args[0],'_id')

		var_name = f'{func.__name__}'
		#var_name = func.__code__.co_varnames[1]
		
		prev = None
		if hasattr(args[0],f'_{var_name}'):
			prev = getattr(args[0],f'_{var_name}')
		func(*args, **kwargs)
		if hasattr(args[0],f'_{var_name}'):
			cur =  getattr(args[0],f'_{var_name}')
			if not prev == cur:
				if prev is None:
					LOGGER.info(f'{args[0].__class__.__name__}({_id}): initializing {var_name} to {cur}')
				else:
					if args[0].__class__.__name__ == "JablotronSensor" and _id == 1:
						# RF value changed frequently, only log this as debug
						LOGGER.debug(f'{args[0].__class__.__name__}({_id}): {var_name} changed from {prev} to {cur}')
					else:
						LOGGER.info(f'{args[0].__class__.__name__}({_id}): {var_name} changed from {prev} to {cur}')
				if hasattr(args[0],"publish_updates"):
					update_op = getattr(args[0], "publish_updates", None)
					if callable(update_op):
						LOGGER.debug("publishing updates")
						asyncio.get_event_loop().create_task(update_op())
	return wrapper


class JablotronSettings:
	#these are hiding sensitive output from logs
	HIDE_CODE = True
	HIDE_KEY_PRESS = True
	#sleep when no command
	SERIAL_SLEEP_NO_COMMAND = 0.2
	#sleep when command
	SERIAL_SLEEP_COMMAND = 0
	#this is just to control with zone is used in unsplit system
	ZONE_UNSPLIT = 3
 
	#these are known settings
	SETTING_ARM_WITHOUT_CODE = "Arm without code"
		
	def __init__(self) -> None:
		#these are parsed settings from central unit
		self._settings = {}
		# default values
		self._settings[JablotronSettings.SETTING_ARM_WITHOUT_CODE] = False

	def add_setting(self,name: str,value: str) -> None:
		self._settings[name] = value
	
	def get_setting(self,name) -> str:
		if name in self._settings:
			return self._settings[name]
		else: 
			return None
	
	def __str__(self) -> None:
		s = f'Setting hide_code={self.HIDE_CODE},hide_key_press={self.HIDE_KEY_PRESS}\n'
		s += 'Settings from central unit:\n'
		for key,value in self._settings.items():
			s+=f'{key}={value}\n'
		return s
	
class JablotronConstants:
	#codes and devices use reactions
	REACTION_OFF = "Off"
	REACTION_NATURAL = "Natural"
	REACTION_PANIC ="Panic"
	REACTION_FIRE_ALARM = "Fire alarm"
	REACTION_24_HOURS = "24 Hours"
	REACTION_NEXT_DELAY = "Next delay"
	REACTION_INSTANT = "Instant"
	REACTION_SET = "Set"
	REACTION_PG_CONTROL = "PG Control"
	REACTION_SET_UNSET = "Set/Unset"
	JABLOTRON_REACTION_MAPPING = {
	# 0x00 = Off (not set in my setup, instead natural is default)
	0x00: REACTION_OFF,
	# 0x01 = Natural
	0x01: REACTION_NATURAL,
	# 0x02 = Panic
	0x02: REACTION_PANIC,
	# 0x03 = fire alarm
	0x03: REACTION_FIRE_ALARM,
	# 0x04 = 24 hours
	0x04: REACTION_24_HOURS,
	# 0x05 = Next delay
	0x05: REACTION_NEXT_DELAY,
	# 0x06 = Instant
	0x06: REACTION_INSTANT,
	# 0x07 = Set
	0x07: REACTION_SET,
	# 0x08 = PG control,
	0x08: REACTION_PG_CONTROL,
	# 0x09 = Set / Unset,
	0x09: REACTION_SET_UNSET
	}
	
@dataclass
class JablotronCommon:
	_id: int = field(default=-1,init=True)
	_active: bool = field(default=False,init=False)
	_name: str = field(default=None,init=False)
	_zone: Any = field(default=None,init=False)
	_reaction: str = field(default=None,init=False)
	_type :str = field(default=None,init=False)
	_enabled: bool = field(default=False, init=False)
 

	@property
	def id_part(self):
		return f"{self.__class__.__name__}"

	@property
	def id(self):
		return self._id

	@property
	def device_id(self) -> int:
		return 0
	@property
	def enabled(self) -> bool:
		return self._enabled

	@enabled.setter
	def enabled(self, val:bool) -> None:
		self._enabled = val
  
	@property
	def type(self) -> str:
		return self._type
	
	@type.setter
	def type(self,type:str) -> None:
		self._type = type
	
	@property
	def reaction(self) -> str:
		return self._reaction
	
	@reaction.setter
	def reaction(self,reaction:str) -> None:
		self._reaction = JablotronConstants.JABLOTRON_REACTION_MAPPING[reaction]

	@property
	def name(self) -> str:
		return self._name
	
	@name.setter
	def name(self,name:str) -> None:
		self._name = name

	@property
	def active(self) -> bool:
		return self._active
	
	@property
	def zone(self) -> Any:
		return self._zone
	
	@zone.setter
	def zone(self, zone:Any) -> None:
		self._zone = zone
	
	@active.setter
	@log_change
	def active(self,active: bool) -> None:
		self._active = active
	
	def __post_init__(self):
		self._callbacks = set()
		
	def register_callback(self, callback) -> None:
		"""Register callback, called when device changes state."""
		self._callbacks.add(callback)

	def remove_callback(self, callback) -> None:
		"""Remove previously registered callback."""
		self._callbacks.discard(callback)
	
	async def publish_updates(self) -> None:
		"""Schedule call all registered callbacks."""
		for callback in self._callbacks:
			callback()
	

	

@dataclass
class JablotronCode(JablotronCommon):
	
	_code1: str = field(default=None,init=False)
	_code2: str = field(default=None,init=False)

	@property
	def code_id(self) -> int:
		return self._id

  
	@property
	def code1(self) -> str:
		return self._code1
	
	@code1.setter
	def code1(self,code:str) -> None:
		self._code1 = code
	
	@property
	def type(self):
		return "code"

	@property
	def code2(self) -> str:
		return self._code2
	
	@code2.setter
	def code2(self,code:str) -> None:
		self._code2 = code
	
	def __post_init__(self) -> None:
		super().__post_init__()
		if self._id == 0:
			self._reaction = "Admin"
		
	def __str__(self) -> str:
		s = f'code id={self.code_id},reaction={self.reaction},'
		if not self.name is None:
			s+=f'name={self.name},'
		if not self.zone is None:
			s+=f'zone={self.zone.name},'
		if not self.code1 is None:
			if JablotronSettings.HIDE_CODE:
				s +='code1=****,'
			else:
				s += f'code1={self.code1},'
		if not JablotronSettings.HIDE_CODE and not self.code2 is None:
			if JablotronSettings.HIDE_CODE:
				s +='code2=****,'
			else:
				s += f'code2={self.code2},'
		s += f'active={self.active}'
		return s
	

	

@dataclass(order=True)
class JablotronDevice(JablotronCommon):
	_model: str = field(default=None,init=False)
	_manufacturer: str = field(default=None,init=False)
	_serial_number: str = field(default=None,init=False)
	_tampered: bool = field(default=False,init=False)
	_battery_low: bool =  field(default=False,init=False)
	
	def __post_init__(self) -> None:
		super().__post_init__()
		self.enabled = True		 
	@property
	def device_id(self) -> int:
		return self._id
	
		
	@property
	def manufacturer(self) -> str:
		return self._manufacturer
	
	@manufacturer.setter
	def manufacturer(self,manufacturer:str) -> None:
		self._manufacturer = manufacturer
	
	@property
	def model(self) -> str:
		return self._model
	
	@model.setter
	def model(self,model:str) -> None:
		self._model = model
	
	
	@property	
	def battery_low(self) -> bool:
		return self._battery_low
 
	@battery_low.setter
	@log_change
	def battery_low(self,state:bool)->None:
		self._battery_low  = state


	@property	
	def name(self) -> str:
		if self._name is None:
			if not self.model is None and not self.model == "wired":
				return self.model
			elif not self.model is None:
				return f'device_{self.model}_{self.device_id}'
			else:
				return f'device_{self.device_id}'
		return self._name

	@name.setter
	def name(self,name:str) -> None:
		self._name = name
	
	@property
	def serial_number(self) -> str:
		return self._serial_number
	
	@serial_number.setter
	def serial_number(self, serial_number:str) -> None:
		self._serial_number = serial_number
	
	# can other devices have serial numbers?
	@property
	def is_control_panel(self) -> bool:
		return not self.serial_number is None
	
	@property
	def is_central_unit(self) -> bool:
		return self.device_id == 0
		
	@property
	def tampered(self) -> bool:
		return self._tampered
	
	@tampered.setter
	@log_change
	def tampered(self, tampered:bool) -> None:
		self._tampered = tampered
	
	def __str__(self) -> str:
		s = f'Device id={self.device_id},model={self.model},reaction={self.reaction},tampered={self.tampered},battery_low={self.battery_low}'
		if not self.name is None:
			s+=f'name={self.name},'
		if not self.zone is None:
			s+=f'zone={self.zone.name},'
		if not self.serial_number is None:
			s += f'serial={self.serial_number},'
		s += f'active={self._active}'
		return s


def check_active(func):
	def wrapper(*args, **kwargs):
		LOGGER.debug(f'{args[0].name} action {func.__name__}')
		prev = args[0]._status
		if not args[0].enabled:
			return
		func(*args, **kwargs)
		if not prev == args[0]._status:
			LOGGER.info(f'{args[0].name} status changed from {prev} to {args[0]._status}')
	return wrapper



@dataclass
class JablotronZone(JablotronCommon):
	_status: str = field(default="Unknown", init=False)
	_by: Union[JablotronDevice,JablotronCode] = field(default=None,init=False)
	
	STATUS_ENTRY_DELAY = 'EntryDelay'
	STATUS_ARMING = 'Arming'
	STATUS_DISARMING = 'Disarming'
	STATUS_DISARMED = 'Disarmed'
	STATUS_ALARM = 'Alarm'
	STATUS_ARMED = 'Armed'
	STATUS_SERVICE = 'Service'
	NAME_ID_MAPPING = {1: 'Zone A', 2: 'Zone B', 3: 'Zone C'}

	def __post_init__(self) -> None:
		super().__post_init__()
		self._name = JablotronZone.NAME_ID_MAPPING[self._id]
	
	@property
	def devices(self)->List[JablotronDevice]:
		return self._devices
			
	@property
	def by(self) -> Union[JablotronDevice,JablotronCode]:
		return self._by
	
	@by.setter
	@log_change
	def by(self,by: Union[JablotronDevice,JablotronCode]) -> None:
		self._by = by

	@property
	def formatted_by(self) -> str:
		if isinstance(self._by,JablotronDevice):
			return f"Device {self._by._id}, {self._by.name}"
		elif isinstance(self._by,JablotronCode):
			return f"Code {self._by._id}, {self._by.name}"

	@property
	def type(self):
		return "zone"

	@property
	def status(self) -> str:
		return self._status

	@status.setter
	@log_change
	def status(self,status: str) -> None:
		# TODO: Review is this is still needed. If it is, it needs a comment
		#if self._status == JablotronZone.STATUS_ARMED and status == JablotronZone.STATUS_ARMING:
		#	return
		self._status = status
	
		
	def __str__(self) -> str:
		s = f'Zone id={self._id},name={self.name},active={self.active},'
		if not self.status is None:
			s += f'status={self.status},'
		if not self.by is None:
			s += f'by={self.formatted_by}'
		return s
	
	@check_active     
	def device_activated(self,device: JablotronDevice ) -> None:
		if self.status == JablotronZone.STATUS_ARMED or device.reaction == JablotronConstants.REACTION_FIRE_ALARM:
			self.alarm(device)
			
	@check_active     
	def device_deactivated(self,device: JablotronDevice)-> None:
		if self.status == JablotronZone.STATUS_ALARM:
			#self.disarm()
			pass

	@check_active     
	def code_activated(self,code: JablotronCode ) -> None:
		pass
		#if self.status == JablotronZone.STATUS_ARMED or code.reaction == JablotronConstants.REACTION_FIRE_ALARM:
		#	self.alarm(code)
			
	@check_active     
	def code_deactivated(self,device: JablotronDevice)-> None:
		pass
  		#if self.status == JablotronZone.STATUS_ALARM:
		#	#self.disarm()
		#	pass

			
	@check_active      
	def tamper(self,by: Optional[JablotronDevice]  = None) -> None:
		self.alarm(by)
		
	@check_active
	def clear(self,by: Optional[JablotronCode] = None) -> None:
		self.disarm(by)
		
	@check_active
	def arming(self,by: Optional[JablotronCode] = None) -> None:
		if not by is None:
			self.by = by
		self.status = JablotronZone.STATUS_ARMING

		
	@check_active    
	def entering(self,by: Optional[JablotronDevice]) -> None:
		if not by is None:
			self.by = by
		self.status = JablotronZone.STATUS_ENTRY_DELAY
		
	@check_active
	def disarm(self,by:Optional[JablotronCode] = None) -> None:
		if not by is None:
				self.by = by
		self.status = JablotronZone.STATUS_DISARMED
		
	@check_active    
	def alarm(self,by: Optional[Union[JablotronCode,JablotronDevice]] = None) -> None:
		if not by is None:
			self.by = by
		self.status = JablotronZone.STATUS_ALARM

		
	@check_active
	def armed(self, by: Optional[JablotronCode] = None) -> None:
		if not by is None:
				self.by = by
		self.status = JablotronZone.STATUS_ARMED


@dataclass
class JablotronCommand():
	name: str = None
	code: str = None
	confirmation_required: bool = True
	confirm_prefix: str = None
	max_records: int = 10
	
	def __post_init__(self) -> None:
		if self.confirmation_required:
			self._event = threading.Event()
	
	async def wait_for_confirmation(self) -> bool:
		while not self._event.is_set():
			await asyncio.sleep(5)
		return self._confirmed
		
	def confirm(self,confirmed: bool) -> None:
		self._confirmed = confirmed
		self._event.set()
		
	
	def __str__(self) -> str:
		s = f'Command name={self.name}'
		return s
	
class JablotronConnection():

	# device is mandatory at initiation
	def __init__(self, type: str, device: str) -> None:
		LOGGER.info(f'Init JablotronConnection of type {type} with device {device}')
		self._type = type
		self._device = device
		self._cmd_q = queue.Queue()
		self._output_q = queue.Queue()
		self._stop = threading.Event()
	
	def get_record(self) -> List[bytearray]:
		if self._output_q.empty():
			return None
		record = self._output_q.get_nowait()
		if not record is None:
			self._output_q.task_done()
		return record
	
	@property
	def device(self):
		return self._device
	
	def connect(self) -> None:
		LOGGER.info(f'Connecting to JA80 via {self._type} using {self._device}...')
		if self._type == CABLE_MODEL_JA82T:
			self._connection = open(self._device, 'w+b',buffering=0)
			LOGGER.debug('Sending startup message')
			self._connection.write(b'\x00\x00\x01\x01')
			LOGGER.debug('Successfully sent startup message')
		elif self._type == CABLE_MODEL_JA80T:
			self._connection = serial.Serial(port=self._device,
                                    baudrate=9600,
                                    parity=serial.PARITY_NONE,
                                    bytesize=serial.EIGHTBITS,
                                    dsrdtr=True,# stopbits=serial.STOPBITS_ONE
                                    timeout=1)
	   
		
	def disconnect(self) -> None:
		if self.is_connected():
			LOGGER.info('Disconnecting from JA80...')
			self._connection.flush()
			self._connection.close()
			self._connection = None
		else:
			LOGGER.info('No need to disconnect; not connected')

	def shutdown(self) -> None:
		self._stop.set()
		
	def is_connected(self) -> bool:
		return self._connection is not None

		 
	def add_command(self, command: JablotronCommand) -> None:
		LOGGER.debug(f'Adding command {command}')
		self._cmd_q.put(command)

	def _get_command(self) -> Union[JablotronCommand,None]:
		# assume we have a command queue and return command if requested
		if self._cmd_q.empty():
			return None
	 
		# get one command
		cmd = self._cmd_q.get_nowait()
		if cmd.confirmation_required == False:
			# we could postpone this until command has been confirmed
			self._cmd_q.task_done()
	   
		return cmd
	
	def _forward_records(self,records: List[bytearray]) -> None:
		self._output_q.put(records)
		
	def _read_data(self, max_package_sections: int =15)->List[bytearray]:
		read_buffer = []
		ret_val = []
		for j in range(max_package_sections):
			data = self._connection.read(64)
			#UNCOMMENT THESE LINES TO SEE RAW DATA (produces a lot of logs)
			#if LOGGER.isEnabledFor(logging.DEBUG):
			#	formatted_data = " ".join(["%02x" % c for c in data])
			#	LOGGER.debug(f'Received raw data {formatted_data}')
			if self._type == CABLE_MODEL_JA82T and len(data) > 0 and data[0] == 0x82:
					size = data[1] 
					read_buffer.append(data[2:2+int(size)])
					if data[1 + int(size)] == 0xff:
						# return data received
						ret_bytes = []
						for i in b''.join(read_buffer):
							ret_bytes.append(i)
							if i == 0xff:
								ret_val.append(bytearray(ret_bytes))
								ret_bytes.clear()
						return ret_val
			elif self._type == CABLE_MODEL_JA80T:
				ret_bytes = []
				read_buffer.append(data)
				for i in b''.join(read_buffer):
					ret_bytes.append(i)
					if i == 0xff:
						ret_val.append(bytearray(ret_bytes))
						ret_bytes.clear()
				return ret_val
		return ret_val
	   
	def read_send_packet_loop(self) -> None:
		# keep reading bytes untill 0xff which indicates end of packet
		LOGGER.debug('Loop endlessly reading serial')
		while not self._stop.is_set():
			try:
				confirmed = False
				if not self.is_connected():
					LOGGER.warning('Not connected to JA80, abort')
					return []
				records = self._read_data()
				self._forward_records(records)
				send_cmd = self._get_command()
		
				if send_cmd is not None:
					# new command in queue
					if not send_cmd.code is None:
						cmd = b'\x00\x02\x01' + send_cmd.code
						
						LOGGER.debug(f'Sending new command {send_cmd}')
						self._connection.write(cmd)
						LOGGER.debug(f'Command sent {cmd}')
					if send_cmd.confirmation_required:
						# confirmation required, read until confirmation or to limit
						records_cmd = []
						for i in range(send_cmd.max_records):
							time.sleep(JablotronSettings.SERIAL_SLEEP_COMMAND)
							if confirmed:
								break 
							records_tmp = self._read_data()
							self._forward_records(records_tmp)
							for record in records_tmp:
								if record[:len(send_cmd.confirm_prefix)] == send_cmd.confirm_prefix:
									LOGGER.info(
										f"confirmation for command {send_cmd} received")
									confirmed=True
									send_cmd.confirm(True)
									
							
						if not confirmed:
							# no confirmation received
							LOGGER.info(
											f"no confirmation for command {send_cmd} received")
							send_cmd.confirm(False)       
						self._cmd_q.task_done()
						
				else:
					# no new command to send. Read status
					#self._forward_records(records)
					# sleep for a while
					time.sleep(JablotronSettings.SERIAL_SLEEP_NO_COMMAND)
				#await asyncio.sleep(0)
			except Exception as ex:
				LOGGER.error('Unexpected error: %s', traceback.format_exc())
		self.disconnect()
		
class JablotronKeyPress():
	
	_KEY_MAP = {
		"0": b'\x80',
		"1": b'\x81',
		"2": b'\x82',
		"3": b'\x83',
		"4": b'\x84',
		"5": b'\x85',
		"6": b'\x86',
		"7": b'\x87',
		"8": b'\x88',
		"9": b'\x89',
		"#": b'\x8e',
		"?": b'\x8e',
		"*": b'\x8f'
	}
	_KEYPRESS_OPTIONS = {
		0x0: {'val': '0', 'desc': 'Key 0 pressed on keypad'}, 0x1: {'val': '1', 'desc': 'Key 1 (^) pressed on keypad'}, 0x2: {'val': '2', 'desc': 'Key 2 pressed on keypad'}, 0x3: {'val': '3', 'desc': 'Key 3 pressed on keypad'}, 0x4: {'val': '4', 'desc': 'Key 4 (<) pressed on keypad'}, 0x5: {'val': '5', 'desc': 'Key 5 pressed on keypad'}, 0x6: {'val': '6', 'desc': 'Key 6 (>) pressed on keypad'}, 0x7: {'val': '7', 'desc': 'Key 7 (v) pressed on keypad'}, 0x8: {'val': '8', 'desc': 'Key 8 pressed on keypad'}, 0x9: {'val': '9', 'desc': 'Key 9 pressed on keypad'}, 0xe: {'val': '#', 'desc': 'Key # (ESC/OFF) pressed on keypad'}, 0xf: {'val': '*', 'desc': 'Key * (ON) pressed on keypad'}
	}
	
	_BEEP_OPTIONS = {
		# happens when warning appears on keypad (e.g. after alarm)
		0x0: {'val': '1s', 'desc': '1 subtle (short) beep triggered'}, 0x1: {'val': '1l', 'desc': '1 loud (long) beep triggered'}, 0x2: {'val': '2l', 'desc': '2 loud (long) beeps triggered'}, 0x3: {'val': '3l', 'desc': '3 loud (long) beeps triggered'}, 0x4: {'val': '4s', 'desc': '4 subtle (short) beeps triggered'}, 0x5: {'val': '3s', 'desc': '3 subtle (short) beeps, 1 then 2'}, 0x7: {'val': '0(1)', 'desc': 'no audible beep(1)'}, 0x8: {'val': '0(2)', 'desc': 'no audible beep(2)'}, 0xe: {'val': '?', 'desc': 'unknown beep(s) triggered'}
	}
	@staticmethod
	def get_key_command(key):
		return JablotronKeyPress._KEY_MAP[key]
	
	@staticmethod
	def get_keypress_option(code):
		return JablotronKeyPress._KEYPRESS_OPTIONS[code]
	
	@staticmethod
	def get_beep_option(code):
		return JablotronKeyPress._BEEP_OPTIONS[code]
	
class JablotronMessage():
	TYPE_STATE = 'State'
	TYPE_EVENT = 'Event'
	TYPE_EVENT_LIST = 'EventList'
	TYPE_SETTINGS = 'Settings'
	TYPE_GSM_SETTINGS = 'GSMSettings'
	TYPE_STATE_DETAIL = 'StateDetail'
	TYPE_KEYPRESS = 'KeyPress'
	TYPE_BEEP = 'Beep'
	TYPE_PING = 'Ping' # regular messages that have no clear meaning (perhaps yet)
	TYPE_PING_OR_OTHER = 'Ping or Other' # message that have no payload or otherwise the payload is a message of other type
	TYPE_SAVING = 'Saving'
	# e8,e9,e5,
	_MESSAGE_MAIN_TYPES = {
		0xed: TYPE_STATE,
		0xe3: TYPE_EVENT,
		0xe4: TYPE_EVENT_LIST,
		0xe5: TYPE_SETTINGS,
		0xe6: TYPE_SETTINGS,
  		#JA-82Y?. ef 42 00 00 00 00 00 00 00 1b ff
		0xef: TYPE_GSM_SETTINGS,
		# what is this exactly 03 fire alarm, 0D/0C codes section 0E/0C service mode
		0xe8: TYPE_STATE_DETAIL,
		0xe9: TYPE_SETTINGS,
		0x80: TYPE_KEYPRESS,
		0xa0: TYPE_BEEP,
		0xb3: TYPE_PING_OR_OTHER,
		0xb4: TYPE_PING_OR_OTHER,
		0xb7: TYPE_BEEP, # beep on set/unset (for all but setting AB)
		0xb8: TYPE_BEEP, # on setup
		0xba: TYPE_PING_OR_OTHER,
		0xc6: TYPE_PING,
		0xe7: TYPE_EVENT,
		0xec: TYPE_SAVING, # seen when saving took really long
		0xfe: TYPE_BEEP, # on setup
	}
	_LENGTHS ={ 
		0xed: 10,
		0xe3: 9,
		0xe4: 9,
		0xe5: 7,
		0xef: 10,
	  #  0xe6: 6,
		0xe8: 4,
		0xe9: 6,
		0xe7: 9,
		0xec: 10,
	}
	_RECORD_E6_LENGTHS = {
	   # 0x02:6,
		0x03:6,
		0x04:14
	}
	_RECORD_E6_02_LENGTHS ={
		0x05:6,
		0x06:6,
		0x07:6,
		0x08:6,
		0x00:6,
		0x01:6,
		0x02:6,
		0x03:6,
		0x04:6,
		0x09:7
	}
	_RECORD_E6_06_LENGTHS = {
		0x00:13,
		0x01:9,
		0x02:9,
		0x03:15,
		0x04:11,
		0x05:6,
		0x06:6,
		0x08:7,
		0x09:7
		
	}
	@staticmethod
	def get_message_type(code: bytes) -> str:
		return JablotronMessage._MESSAGE_MAIN_TYPES[code]
	
	@staticmethod
	def get_length(main_type: str,record: bytes) -> int:
		length = None
		try:
			length = JablotronMessage._LENGTHS[record[0]]
		except KeyError:
			pass
		
		if length is None:
			if main_type in [JablotronMessage.TYPE_BEEP,JablotronMessage.TYPE_KEYPRESS, JablotronMessage.TYPE_PING]:
				return 2
			else:
				#settings
				try:
					if main_type == JablotronMessage.TYPE_SETTINGS and record[0] == 0xe6:
						if not record[1] in [0x06,0x02]:
							return JablotronMessage._RECORD_E6_LENGTHS[record[1]]
						if record[1] == 0x06:
							return JablotronMessage._RECORD_E6_06_LENGTHS[record[2]]
						else:
							return JablotronMessage._RECORD_E6_02_LENGTHS[record[2]]
				except KeyError:
					return -1
		else:
			return length
		
	@staticmethod
	def validate_length(main_type: str, record:bytes ) -> bool:
		return len(record) == JablotronMessage.get_length(main_type,record)
			
	@staticmethod
	def check_crc(data: bytes) -> bool:
		#TODO algorithm not yet known
		return True
	
	@staticmethod
	def get_message_type_from_record(record,packet_data: bytes) -> str:
		message_type = None
		try:
			message_type = JablotronMessage.get_message_type(record[0])
		except Exception as ex:
			pass
		if message_type is None:
			try:
				# try again with only highest 4 bits (e.g. 0x85 > 0x80)
				message_type = JablotronMessage.get_message_type(record[0] & 0xf0)
			except Exception as ex:
				pass
		   # LOGGER.error('Error determining msg type from buffer: %s', ex)
			#  msg type is still none so next call will work
		if message_type is None:
			LOGGER.error(
					f'Unknown message type {record[0]} with data {packet_data} received')
			return None
		else:
			if message_type == JablotronMessage.TYPE_PING_OR_OTHER:
				# don't validate length for a PING_OR_OTHER as it's may contains it's own message
				return message_type
			elif JablotronMessage.validate_length(message_type,record) and JablotronMessage.check_crc(record):
				LOGGER.debug(f'Message of type {message_type} received {packet_data}')
				return message_type
			else:
				LOGGER.debug(f'Invalid message of type {message_type} received {packet_data}')
		return None
	
class JablotronState():
	#unsplit system 40->53->43->47
	# alarm without arming 44
	#partial setting A  40->51->41->45
	#partial setting AB 40->52->42->46
	#partial setting ABC 40->53->43->47
	# without 44
	#split system
	# A 60->71->61->65
	# B 60->72->62->66
	# ABC 60->73->63->67
	# without 64
	
	
	#unsplit and partial
	DISARMED = 0x40
	#split
	DISARMED_SPLIT = 0x60
	STATES_DISARMED = [DISARMED,DISARMED_SPLIT]
	#partial
	EXIT_DELAY_A = 0x51
	EXIT_DELAY_AB = 0x52
	#partial and unsplit
	EXIT_DELAY_ABC = 0x53
	
	#split
	EXIT_DELAY_SPLIT_A = 0x71
	EXIT_DELAY_SPLIT_B = 0x72
	EXIT_DELAY_SPLIT_C = 0x73
	
	STATES_EXIT_DELAY = [EXIT_DELAY_SPLIT_A,EXIT_DELAY_SPLIT_B,EXIT_DELAY_SPLIT_C,EXIT_DELAY_A,
						 EXIT_DELAY_AB, EXIT_DELAY_ABC]
	#partial
	ARMED_A = 0x41    
	ARMED_AB = 0x42
	#unsplit and partial
	ARMED_ABC = 0x43
	
	#split
	ARMED_SPLIT_A = 0x61
	ARMED_SPLIT_B = 0x62
	ARMED_SPLIT_C = 0x63
	
	STATES_ARMED = [ ARMED_SPLIT_A, ARMED_SPLIT_B, ARMED_SPLIT_C,ARMED_A, ARMED_AB, ARMED_ABC]
	ENROLLMENT = 0x01
	SERVICE = 0x00
	#SERVICE_LOADING_SETTINGS = 0x05
	#SERVICE_EXITING= 0x08
	#STATES_SERVICE = [ENROLLMENT,
	#				SERVICE, SERVICE_LOADING_SETTINGS, SERVICE_EXITING]
	MAINTENANCE = 0x20
	#BYPASS = 0x21
	#MAINTENANCE_LOADING_SETTINGS = 0x25
	#MAINTENANCE_EXITING= 0x28
	#STATES_MAINTENANCE = [MAINTENANCE,
	#					MAINTENANCE_LOADING_SETTINGS, BYPASS, MAINTENANCE_EXITING]
	
	#partial
	ALARM_A = 0x45
	ALARM_B = 0x46
	#partial and unsplit
	ALARM_C = 0x47
	#partial and unsplit
	ALARM_WITHOUT_ARMING = 0x44
	
	
	#split
	ALARM_A_SPLIT = 0x65
	ALARM_B_SPLIT = 0x66
	ALARM_C_SPLIT = 0x67
	ALARM_WITHOUT_ARMING_SPLIT = 0x64
	STATES_ALARM = [ALARM_A,ALARM_B,ALARM_C,ALARM_WITHOUT_ARMING,
					ALARM_A_SPLIT,ALARM_B_SPLIT,ALARM_C_SPLIT,ALARM_WITHOUT_ARMING_SPLIT]
	
	ARMED_ENTRY_DELAY_A = 0x49
	ARMED_ENTRY_DELAY_B = 0x4a	
	ARMED_ENTRY_DELAY_C = 0x4b

	STATES_ENTERING_DELAY = [ARMED_ENTRY_DELAY_A, ARMED_ENTRY_DELAY_B, ARMED_ENTRY_DELAY_C]
	#STATES_ELEVATED = [SERVICE,MAINTENANCE]
		
	@staticmethod
	def is_armed_state(status):
		return status in JablotronState.STATES_ARMED
	
	@staticmethod
	def is_disarmed_state(status):
		return status in JablotronState.STATES_DISARMED
	@staticmethod
	def is_elevated_state(status):
		return JablotronState.is_service_state(status) or JablotronState.is_maintenance_state(status)
		#return status in JablotronState.STATES_ELEVATED
	
	@staticmethod
	def is_exit_delay_state(status):
		return status in JablotronState.STATES_EXIT_DELAY
	
	@staticmethod
	def is_entering_delay_state(status):
		return status in JablotronState.STATES_ENTERING_DELAY
	
	@staticmethod
	def is_service_state(status):
		return not status & JablotronState.MAINTENANCE and not status & JablotronState.DISARMED
		#return status in JablotronState.STATES_SERVICE
	
	@staticmethod
	def is_maintenance_state(status):
		return status & JablotronState.MAINTENANCE and not status & JablotronState.DISARMED
		#return status in JablotronState.STATES_MAINTENANCE
	
	@staticmethod
	def is_alarm_state(status):
		return status in JablotronState.STATES_ALARM




class JablotronLed(JablotronCommon):
	pass

@dataclass
class JablotronSensor(JablotronCommon):
	_value: float = field(default=0,init=False)
	
	@property
	def value(self) -> float:
		return self._value

	@value.setter
	@log_change
	def value(self,val:float) -> None:
		self._value = val

class JA80CentralUnit(object):
	_year = datetime.datetime.now().year

   
	
	
	# Statuses
	STATUS_MAINTENANCE = 'Maintenance'
	STATUS_SERVICE = 'Service'
	STATUS_NORMAL = 'Normal'
	STATUS_ELEVATED = [STATUS_SERVICE, STATUS_MAINTENANCE]
   

	

	SYSTEM_MODE_SPLIT = "Split"
	SYSTEM_MODE_UNSPLIT = "Unsplit"
	SYSTEM_MODE_PARTIAL = "Partial"
   
	_ZONE_UNSPLIT = 1

	
	def _create_led(self,id_:int,name:str,type:str) -> JablotronLed:
		led = JablotronLed(id_)
		led.name = f'{CENTRAL_UNIT_MODEL} {name}'
		led.manufacturer = MANUFACTURER
		led.type = type
		return led



	def __init__(self, hass: HomeAssistant,  config: Dict[str, Any], options: Dict[str, Any] = None) -> None:
		self._hass: HomeAssistant.core = hass
		self._config: Dict[str, Any] = config
		self._options: Dict[str, Any] = options
		self._settings = JablotronSettings()
		self._connection = JablotronConnection(config[CABLE_MODEL],config[CONFIGURATION_SERIAL_PORT])
		device_count = config[CONFIGURATION_NUMBER_OF_DEVICES]
		if device_count == 0:
			self._max_number_of_devices = MAX_NUMBER_OF_DEVICES
		else:
			self._max_number_of_devices = config[CONFIGURATION_NUMBER_OF_DEVICES]
		self._zones = {}
		self._zones[1] = JablotronZone(1)  
		self._zones[2] = JablotronZone(2)  
		self._zones[3] = JablotronZone(3)  
		self.central_device = JablotronDevice(0)
		self.central_device.model = CENTRAL_UNIT_MODEL
		# device that receives fault alerts such as tamper alarms and communication failures
		self.central_device.name = f'{CENTRAL_UNIT_MODEL} Control Panel'
		self.central_device.manufacturer = MANUFACTURER
		self.central_device.type = "Control Panel"
		self._leds = {
      				"A":self._create_led(1,"zone A armed","armed led"),
  					"B":self._create_led(2,"zone B armed","armed led"),
	       			"C":self._create_led(3,"zone C armed","armed led"),
  					"ALARM":self._create_led(4,"alarm","alarm led"),
  					"POWER":self._create_led(5,"power","power led")}

		self._last_event_data = None
  
		self._master_code = config[CONFIGURATION_PASSWORD]
		# this is in scale 0 - 40, 0 - 100% ?
		self._rf_level = JablotronSensor(1)
		self._rf_level.name = f'{CENTRAL_UNIT_MODEL} RF level'
		self._rf_level.manufacturer = MANUFACTURER
		self._rf_level.type = "signal"
		self.last_state = None
		self.system_status = None

		self._devices = {}
		self._active_devices = {}
		self._active_codes = {}
		self._codes = {}
		self._devices = {}
		self._device_query_pending = False
		self._last_state = None
		self._mode = None
		self._connection.connect()
		self._stop = threading.Event()
		if CONFIGURATION_CENTRAL_SETTINGS in config:
			self.mode = config[CONFIGURATION_CENTRAL_SETTINGS][DEVICE_CONFIGURATION_SYSTEM_MODE]
			self._settings.add_setting(JablotronSettings.SETTING_ARM_WITHOUT_CODE, not config[CONFIGURATION_CENTRAL_SETTINGS][DEVICE_CONFIGURATION_REQUIRE_CODE_TO_ARM])
		else:
			self.mode = self.SYSTEM_MODE_UNSPLIT
		devices = {}
		if CONFIGURATION_DEVICES in config: 
			devices = config[CONFIGURATION_DEVICES]
		codes = {}
		if CONFIGURATION_CODES in config:
			codes = config[CONFIGURATION_CODES]
		for key, value in devices.items():
			device = self.get_device(int(key))
			device.name = value["name"]
			device.type = value["type"]
			device.serial_number = value["serial_number"]
			device._reaction = value["reaction"]
			device.zone = self.get_zone(value["zone"])
			device.model = value["model"]
			device.manufacturer = value["manufacturer"]
		for key,value in codes.items():
			code = self.get_code(int(key))
			code.name = value["name"]
			code._reaction = value["reaction"]
			code.code1 = value["code1"]
			code.code2 = value["code2"]
			code.enabled = True

	async def initialize(self) -> None:
		def shutdown_event(_):
			self.shutdown()
		LOGGER.info("initializing")
		if not self._hass is None:
			self._hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, shutdown_event)
		loop = asyncio.get_event_loop()
		loop.create_task(self.processing_loop())
		#loop.create_task(self.status_loop())
		io_pool_exc = ThreadPoolExecutor(max_workers=1)
		loop.run_in_executor(io_pool_exc, self._connection.read_send_packet_loop)
		LOGGER.info(f"initialization done.")


		

		
	def is_code_required_for_arm(self) -> bool:
		value = self._settings.get_setting(JablotronSettings.SETTING_ARM_WITHOUT_CODE)
		return  value is None or value == False

	@property
	def devices(self) -> List[JablotronDevice]:
		return [self.get_device(i) for i in range(1,self._max_number_of_devices+1)]

	@property
	def zones(self) -> List[JablotronZone]:
		return sorted([zone for zone in self._zones.values() if zone.enabled],key=lambda zone:zone._id)
	
	@property
	def codes(self) -> List[JablotronCode]:
		return sorted([code for code in self._codes.values() if code.enabled],key=lambda code:code._id)
	
	@property
	def leds(self) -> List[JablotronLed]:
		return self._leds.values()
	
	@property
	def serial_port(self) -> str:
		return self._connection.device
	
	@property 
	def led_a(self) -> bool:
		return self._leds["A"].active
	
	@led_a.setter
	def led_a(self,led_a: bool) -> None:
		self._leds["A"].active = led_a
		
	
	@property 
	def led_b(self) -> bool:
		return self._leds["B"].active
	
	@led_b.setter
	def led_b(self,led_b: bool) -> None:
		self._leds["B"].active  = led_b
		
		
	@property 
	def led_c(self) -> bool:
		return self._leds["C"].active
	
	@led_c.setter
	def led_c(self,led_c: bool) -> None:
		self._leds["C"].active  = led_c

	@property 
	def led_power(self) -> bool:
		return self._leds["POWER"].active
	
	@led_power.setter
	def led_power(self,led_power: bool) -> None:
		self._leds["POWER"].active  = led_power

	@property 
	def led_alarm(self) -> bool:
		return self._leds["ALARM"].active
	
	@led_alarm.setter
	def led_alarm(self,led_alarm: bool) -> None:
		self._leds["ALARM"].active  = led_alarm
	
	@property
	def rf_level(self) -> JablotronSensor:
		return self._rf_level
	
	@rf_level.setter
	def rf_level(self,rf_level: int) -> None:
		self._rf_level.value= rf_level

	@property
	def system_status(self) -> str:
		return self._system_status

	@system_status.setter
	@log_change
	def system_status(self,system_status: str) -> None:
		self._system_status = system_status
	
	def update_options(self,options: Dict[str, Any] = None) -> None:
		self._options = options
		for zone in self._zones.values():
			asyncio.get_event_loop().create_task(zone.publish_updates())
	
	@property    
	def mode(self) -> int:
		return self._mode
	
	@mode.setter
	@log_change
	def mode(self,mode:int) -> None:
		self._mode = mode
		for zone in self._zones.values():
			if not mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT or zone._id == JablotronSettings.ZONE_UNSPLIT:
				zone.enabled = True
			else:
				zone.enabled = False

	
	def _get_source(self,source:bytes ) -> Union[JablotronDevice,JablotronCode,None]:
		if source is None:
			return None
		if source < 0x40:
			# source is device
			# TODO convert bytes to int (1-50)
			return self.get_device(source)
		else:
			# source is code
			# TODO convert bytes to int (1-50)
			return self.get_code(source - 64)
	
	def get_device(self, id_: int) -> JablotronDevice:
		if id_ == 0:
			return self.central_device
		if not id_ in self._devices:
			self._devices[id_] = JablotronDevice(id_)
		return self._devices[id_]
		
	def get_code(self, id_: int ) -> JablotronCode:
		if not id_ in self._codes:
			self._codes[id_] = JablotronCode(id_)
		return self._codes[id_]
	
	def get_zone(self,id_: str) -> JablotronZone:
		if self.mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT:
			return self._zones[JablotronSettings.ZONE_UNSPLIT]
		if not id_ in self._zones:
			self._zones[id_] = JablotronZone(id_)
		return self._zones[id_]

	def _device_tampered(self,source: bytes) -> None:
		device = self.get_device(source)
		device.tampered = True
		if source == 0x00:
			#central unit tampering?
			for zone in self._zones.values():
				zone.tamper()
		else:
			zone = self._get_zone_via_object(device)
			if zone is not None:
				zone.tamper(device)
			else:
				LOGGER.info("Tampered device not configured in Home Assistant")

	def _device_battery_low(self,source: bytes) -> None:
		device = self.get_device(source)
		device.battery_low = True
	
	def notify_service(self) -> None:
		for zone in self._zones.values():
			zone.status = JablotronZone.STATUS_SERVICE
 
	def is_elevated(self) -> bool:
		for zone in self._zones.values():
			if zone.status == JablotronZone.STATUS_SERVICE:
				return True

		return False

	def _call_zones(self,source_id:bytes = None, function_name: str = None) -> None:
		for zone in self._zones.values():
			if zone is not None:
				function = getattr(zone,function_name)
				source = self._get_source(source_id)
				function(source)
   
	def _get_zone(self,zone_id:int)-> JablotronZone:
		return self._zones[zone_id]

	def _call_zone(self,zone_id: int,function_name: str = None, by: str = None)->None:
		zone = self._get_zone(zone_id)
		if zone is not None:
			function = getattr(zone,function_name)
			source = self._get_source(by)
			function(source)
		
	#devices  can be set to different zones even if system is unsplit
	def _get_zone_via_object(self,object: JablotronCommon) -> JablotronZone:
		if self.mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT:
			return self._zones[JablotronSettings.ZONE_UNSPLIT]
		else:
			return object.zone
	
	def _clear_triggers(self) -> None:
		for device in self._active_devices.values():
			#if self.system_mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT:
			#    device.deactivate()
			#else:
			device.active = False
		self._active_devices.clear()
		for code in self._active_codes.values():
    			#if self.system_mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT:
			#    device.deactivate()
			#else:
			code.active = False
		self._active_codes.clear()
 
 
	def _activate_source(self,source_id:bytes ,type=None) -> None:
		source  = self._get_source(source_id)
		if isinstance(source,JablotronDevice):
			#source is device
			
			source.active = True
			self._active_devices[source.device_id] = source
			zone = self._get_zone_via_object(source)
			if not zone is None:
				zone.device_activated(source)
		elif isinstance(source,JablotronCode):
			# source is code
			# is there need to trigger state for code?

			self._active_codes[source._id] = source
			source.active = True
			zone = self._get_zone_via_object(source)
			if not zone is None:
				zone.code_activated(source)
		else:
			LOGGER.warn(f'Unknown source type {source_id}')
	
	def _alarm_via_source(self,source_id: bytes) -> None:
		source  = self._get_source(source_id)
		self._get_zone_via_object(source).alarm(source)
			
   
	def _activate_panic_alert(self,source_id:bytes)-> None:
		self._alarm_via_source(source_id)

	
	def _process_event(self, data: bytearray, packet_data: str) -> None:
		date_time_obj = self._get_timestamp(data[1:5])
		event_type = data[5]
		event_name = "Unknown"
		warn = False
		source = data[6]
		# codes 40 master code, 41 - 50 codes 1-10

		if event_type == 0x01 or event_type == 0x02 or event_type == 0x03 or event_type == 0x04:
			event_name = "Sensor Activated"
			# alarm or doorm open?, source = device id
			# 0x01 motion?
			# 0x02 door/natural
			# 0x03 fire alarm
			# can source be also code? Now assuming it is device.
			# logic for codes and devices? devices in range hex 01 - ??, codes in 40 -
			self._activate_source(source)
		elif event_type == 0x05:
			event_name = "Tamper alarm"
			# entering service mode, source = by which id
			self._device_tampered(source)
			self._activate_source(source)
			warn = True
		elif event_type == 0x06:
			event_name = "Tampering key pad (wrong code?)"
			warn = True
			self._device_tampered(source)
			self._activate_source(source)
		elif event_type == 0x07:
			# after coming out of Service mode
			event_name = "Fault"
			warn = True
			self._activate_source(source)
		elif event_type == 0x08:
			event_name = "Setting"
			code  = self._get_source(source)
			code.active = True
			self._clear_triggers()
			self._call_zones(function_name="arming",source_id=source)
		elif event_type == 0x09:
			event_name = "Unsetting"
			# unsetting, source = by which code
			code  = self._get_source(source)
			self._call_zones(function_name="disarm",source_id=source)
			code.active = False
		elif event_type == 0x0c:
			event_name = "Completely set without code"
			# self._zones[JablotronSettings.ZONE_UNSPLIT].armed(source)
			self._call_zones(function_name="arming",source_id=source)
		elif event_type == 0x0d:
			event_name = "Partial Set A"
			code  = self._get_source(source)
			code.active = True
			self._call_zone(1,by = source,function_name="arming")
		elif event_type == 0x0e:
			event_name = "Lost communication"
			warn = True
			self._activate_source(source)
		elif event_type == 0x0f:
			event_name = "Fault, Control panel"
			warn = True
			self._activate_source(source)			
		elif event_type == 0x10:
			event_name = "Discharged battery, Control panel (1)"
			warn = True
			self._device_battery_low(source)
		elif event_type == 0x11:
			event_name = "Discharged battery"
			warn = True
			self._device_battery_low(source)
		elif event_type == 0x14:
			event_name = "Discharged battery, Control panel (2)"
			warn = True
			self._device_battery_low(source)
		elif event_type == 0x17:
			event_name = "24 hours" # for example panic alarm
			# 24 hours code=source
			code  = self._get_source(source)
			code.active = True
		elif event_type == 0x1a:
			event_name = "Setting Zone A"
			code  = self._get_source(source)
			code.active = True
			self._call_zone(1,by = source,function_name="arming")
		elif event_type == 0x1b:
			event_name = "Setting Zone B"
			code  = self._get_source(source)
			code.active = True
			self._call_zone(2,by = source,function_name="arming")

		elif event_type == 0x21:
			event_name = "Partial Set A,B"
			code  = self._get_source(source)
			code.active = True
			self._call_zone(1,by = source,function_name="arming")
			self._call_zone(2,by = source,function_name="arming")

		elif event_type == 0x41:
			event_name = "Enter Elevated Mode"

		elif event_type == 0x42:
			event_name = "Exit Elevated Mode"

		elif event_type == 0x4e:
			event_name = "Alarm Cancelled"
			# alarm cancelled / disarmed, source = by which code
			self._clear_triggers()
			#code is specific to zone or master TODO
			self._call_zones(function_name="disarm",source_id=source)

		elif event_type == 0x50:
			# received when all tamper alarms are removed (though alarm warnings may be present via status messages)
			event_name = "All tamper contacts OK"
			self._clear_tampers()
		elif event_type == 0x51:
			event_name = "No fault in system" 
			# todo: see if this message has any detail
			if source != 0x00:
				self._clear_fault(source)
			else:
				self._clear_faults()
		elif event_type == 0x52:
			event_name = "Battery OK"
			self._clear_battery()
		elif event_type == 0x5a:
			event_name = "Unconfirmed alarm"
			if source == 0x00:
				# This event occurs when an entrace delay is caused by an unconfirmed alarm
				# It looks to me like a bug in the firmware to show this as the alarm should only be triggered once
				# the second detector is triggered. But the aim of this software is to replicate the alerts of the alarm system.
				# TODO: Check the alarm logs to see what is registered. 
				event_name = event_name + ", Control panel"
			warn = True
			self._activate_source(source)

		else:
			LOGGER.error(f'Unknown timestamp event data={packet_data}')
		#crc = data[7]

		if source == 0x0:
			log = f'{event_name}, Date={date_time_obj}'
		else:
			log = f'{event_name}, {source}:{self._get_source(source).name}, Date={date_time_obj}'

		if warn:
			LOGGER.warn(log)
		else:
			LOGGER.info(log)

		self.central_device.last_event = log


	def _send_device_query(self)->None:
		if not self._device_query_pending:
			self.send_detail_command()
			
	def _confirm_device_query(self)->None:
		self._device_query_pending = False

	def _process_state(self, data: bytearray, packet_data: str) -> None:
		warn = False
		activity_name = "Unknown"
		status = data[1]
		activity = data[2]
		detail = data[3]
		leds = data[4]
		self.led_a = (leds & 0x08) == 0x08
		self.led_b = (leds & 0x04) == 0x04
		self.led_c = (leds & 0x02) == 0x02
		self.led_power  = (leds & 0x01) == 0x01
		self.led_alarm = (leds & 0x10) == 0x10
		detail_2 = data[5]
		field_2 = data[6]
		# this is probably rf strength 00 = 0%, 0A = 10%, 1E = 75%, 28 = 100%?
		self.rf_level = int(data[7]) / 40.0 * 100.0
		#crc = data[8]
		# calc = binascii.crc32(bytearray(data[0:8]))&0xff
		# LOGGER.info(f'crc received={crc},={crc:x},calculate={calc},{calc:x}')
		self._last_state = status
		if status == JablotronState.ALARM_A or status == JablotronState.ALARM_A_SPLIT:
#			detail = detail if activity == 0x10 and not detail == 0x00 else None
			self._call_zone(1,by = detail,function_name="alarm")
		elif status == JablotronState.ALARM_B or status == JablotronState.ALARM_B_SPLIT:
#			detail = detail if activity == 0x10 and not detail == 0x00 else None
			self._call_zone(2,by = detail,function_name="alarm")
		elif status == JablotronState.ALARM_C or status == JablotronState.ALARM_WITHOUT_ARMING:
#			detail = detail if activity == 0x10 and not detail == 0x00 else None
			self._call_zones(detail,function_name="alarm")
		elif status == JablotronState.ALARM_C_SPLIT:
#			detail = detail if activity == 0x10 and not detail == 0x00 else None
			self._call_zone(3,by = detail,function_name="alarm")        
		elif status in JablotronState.STATES_DISARMED:
			self.status = JA80CentralUnit.STATUS_NORMAL
			self._call_zones(function_name="disarm")
			if activity == 0x10:
				warn = True
				activity_name = 'Activity'
				# something is active
				if detail == 0x00:
					# no details... ask..
					self._send_device_query()
				else:
					# set device active
					self._confirm_device_query()
					self._activate_source(detail)
			elif activity == 0x00:
				# clear active statuses
				self._clear_triggers()
			elif activity == 0x09:
				self._device_battery_low(detail)
			elif activity == 0x07:
				#some pir activity
				#ed 40 07 06 11 00 00 00 3b ff
				self._activate_source(detail)
		elif status == JablotronState.ARMED_ABC:
			self._call_zones(function_name="armed")
		elif status == JablotronState.ARMED_A:
			self._call_zone(1,by = detail,function_name="armed")
		elif status == JablotronState.ARMED_AB:
			self._call_zone(1,by = detail,function_name="armed")
			self._call_zone(2,by = detail,function_name="armed")
		elif status == JablotronState.ARMED_SPLIT_A:
			self._call_zone(1,by = detail,function_name="armed")
		elif status == JablotronState.ARMED_SPLIT_B:
			self._call_zone(2,by = detail,function_name="armed")
		elif status == JablotronState.ARMED_SPLIT_C:
			self._call_zone(3,by = detail,function_name="armed")
		elif status == JablotronState.ARMED_ENTRY_DELAY_C: 
			# is detail 2 device id?
			#if not detail_2 == 0x00:
		#		device = self.get_device(detail_2)
		#		self._get_zone_via_object(device).entering(device)
		#		self._activate_source(detail_2)
			pass

		elif status == JablotronState.EXIT_DELAY_ABC:
			self._call_zones(function_name="arming")
		elif status == JablotronState.EXIT_DELAY_A:
			self._call_zone(1,by = detail,function_name="arming")
		elif status == JablotronState.EXIT_DELAY_AB:
			self._call_zone(1,by = detail,function_name="arming")
			self._call_zone(2,by = detail,function_name="arming")
		elif status == JablotronState.EXIT_DELAY_SPLIT_A:
			self._call_zone(1,by = detail,function_name="arming")
		elif status == JablotronState.EXIT_DELAY_SPLIT_B:
			self._call_zone(2,by = detail,function_name="arming")
		elif status == JablotronState.EXIT_DELAY_SPLIT_C:
			self._call_zone(3,by = detail,function_name="arming")
			
		if JablotronState.is_armed_state(status):
			if activity == 0x00:
				# normal state 
				#this might be needed for PIR clearing. What are effects to other sensors like doors?
				#self._clear_triggers()
				pass
			elif activity == 0x06:
				# sensor active,
				# detail = sensor id
				warn = True
				activity_name = 'Activity Confirmed (1)'
				self._activate_source(detail)
				#self._get_zone_via_device(detail).alarm(detail)
			elif activity == 0x04:
				# key pressed
				pass
			elif activity == 0x08:
				# "Fault" (on keypad), "lost communication with device" in logs
				activity_name = 'Lost communication with device'
				self._activate_source(detail)
			elif activity == 0x10:
				warn = True
				activity_name = 'Activity Confirmed (2)'
				# something is active
				if detail == 0x00:
					# no details... ask..
					self._send_device_query()
				else:
					# set device active
					self._confirm_device_query()
					self._activate_source(detail)
			elif activity == 0x0d:
				# 
				pass
			elif activity == 0x0c:
				# 
				pass
			elif activity == 0x12:
				warn = True
				activity_name = 'Activity Confirmed (3)'
				#pir movement
				#example ed 43 12 3d 0f 04 00 3c 59 ff for device 4
				self._activate_source(detail_2)
			elif activity == 0x14:
				# Unconfirmed alarm
				warn = True
				activity_name = 'Unconfirmed alarm'
				self._activate_source(detail)
			
			# the next 3 activities are some sort of status code on arming/disarming
			elif activity == 0x40:
				pass

			elif activity == 0x44:
				pass

			elif activity == 0x4c:
				pass
			else:
				LOGGER.error(f'Unknown activity received data={packet_data}')
		elif JablotronState.is_service_state(status):
			self.status = JA80CentralUnit.STATUS_SERVICE
			self.notify_service()
		elif JablotronState.is_maintenance_state(status):
			self.status = JA80CentralUnit.STATUS_MAINTENANCE
			self.notify_service()
		elif JablotronState.is_exit_delay_state(status):
			if activity == 0x0c:
				# normal state?
				#self._deactivate_source(detail)
				pass
			elif activity == 0x10:
				warn = True
				activity_name = 'Activity Confirmed'
					# something is active
				if detail == 0x00:
					# no details... ask..
					self._send_device_query()
				else:
					# set device active
					self._confirm_device_query()
					self._activate_source(detail)
			elif activity == 0x04:
				# key pressed, is this possible?
				pass
			else:
				LOGGER.error(f'Unknown activity received data={packet_data}')
		elif JablotronState.is_alarm_state(status):
			if activity == 0x00:
				# no reason yet
				pass
			elif activity == 0x06:
				# sensor causing alarm,
				# detail = sensor id
				# also something in detail_2
				self._activate_source(detail)
			elif activity == 0x04:
				# key pressed
				pass
			else:
				LOGGER.error(f'Unknown activity received data={packet_data}')
		elif JablotronState.is_entering_delay_state(status):
			# device activation?
			pass
		elif JablotronState.is_disarmed_state(status):
			pass
		else:
			LOGGER.error(
				f'Unknown status message status={status} received data={packet_data}')
		

		#if activity != 0x00:
		#	log = f'Status: {activity_name}, {detail}:{self.get_device(detail).name}'
		#	if warn:
		#		LOGGER.warn(log)
		#	else:
		#		#LOGGER.info(log)
		#		pass

		#LOGGER.info(f'Status: {hex(status)}, {format(status, "008b")}')
		#LOGGER.info(f'{self}')

	def _get_timestamp(self, data: bytearray) -> None:
		day = f'{data[0]:02x}'
		month = f'{data[1]:02x}'
		hours = f'{data[2]:02x}'
		minutes = f'{data[3]:02x}'
		date_time_str = f'{self._year}-{month}-{day} {hours}:{minutes}'
		return datetime.datetime.strptime(date_time_str, '%Y-%m-%d %H:%M')

	def _process_settings(self, data: bytearray, packet_data: str) -> None:
		setting_type_1 = data[1]
		if setting_type_1 == 0x02:
			# E6 02 05 00 4C FF 
			# selection lists
			# known index values (range 00-09)
			# 0x00 = exit delay time
			# 0x01 = entrance delay time
			# 0x02 = alarm duration time
			# 0x03 = PGX function
			# 0x04 = PGY function
			index = data[2]
			# running list index value specific to selection
			setting_value = data[3]
			crc = data[4]
			pass
		elif setting_type_1 == 0x03:
			# E6 03 00 00 21 FF 
			# some general settings
			# known index values (range 00-09)
			# 0x00 = setting(armed) without access code
			# 0x03 = exit delay beeps
			# 0x04 = exit delay beeps while partially arming
			# 0x05 = Entrance delay beeps
			# 0x06 = reset enabled
			index = data[2]
			# 0x01 = checked
			# 0x00 = unchecked
			setting_value = data[3]
			if index == 0x00:
				if setting_value == 0x01:
					self._settings.add_setting(JablotronSettings.SETTING_ARM_WITHOUT_CODE,True)
				else:
					self._settings.add_setting(JablotronSettings.SETTING_ARM_WITHOUT_CODE,False)
			# crc = data[4]
		elif setting_type_1 == 0x04:
			# some general settings
			# E6 04 02 00 01 00 01 04 01 01 02 00 1D FF
			# E6 04 02 00 01 07 01 04 01 01 02 00 07 FF
			# E6 04 02 00 02 00 01 04 01 01 02 00 1B FF
			#crc = data[12]          
			pass
		elif setting_type_1 == 0x06:
			setting_type_2 = data[2]
			if setting_type_2 == 0x00:
				# E6 06 00 00 01 0F 0F 00 00 00 00 34 FF 
				# E6 06 00 00 05 04 08 06 02 08 0D 02 FF 
				# serial numbers of devices
				device_id = int(data[3])*10 + int(data[4])
				# data 5 - 10 serial number as hex
				# 0F 0F at least for wired
				# with same logic 04 08 for JA-81F?
				# 04 08 06 02 08 0D = hex 48628D, serial 04743821 (of JA-81F)
				# crc = data[11]
				device = self.get_device(device_id)
				if not data[5:11] == b'\x0f\x0f\x00\x00\x00\x00':
					serial_hex_string = "".join(
						map(lambda x: hex(x)[2:], data[5:11]))
					serial_int_string = int(serial_hex_string, 16)
					device.serial_number = f'{serial_int_string:08d}'
					if data[5:7] == b'\x04\x08':
						# not sure if this is the logic
						device.model = 'JA-81F'
						device.manufacturer = MANUFACTURER
				else:
					device.model = "wired"
			elif setting_type_2 == 0x01:
				# E6 06 01 00 01 01 01 2B FF 
				# device reactions and associated zones
				device_id = int(data[3])*10 + int(data[4])
				# LOGGER.debug(f'Settings received data={packet_data}')
				# 0x00 = Off (not set in my setup, instead natural is default)
				# 0x01 = Natural
				# 0x02 = Panic
				# 0x03 = fire alarm
				# 0x04 = 24 hours
				# 0x05 = Next delay
				# 0x06 = Instant
				# 0x07 = Set
				# 0x08 = PG control
				# 0x09 = Set / Unset
				# crc = data[7]
				device = self.get_device(device_id)
				# NOT AVAILABLE AT THIS POINT
				# if self.system_mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT:
				#    # use only zone A if unsplit system
				#    device.zone = self.zones[1]
				#else:
				device.zone = self.get_zone([data[6]])
				device.reaction = data[5]
			elif setting_type_2 == 0x02:
				# E6 06 02 00 01 01 01 39 FF 
				# code id, reaction and associated zones
				# code id range 1 - 50
				code_id = int(data[3])*10 + int(data[4])
				code = self.get_code(code_id)
				code.reaction = data[5]
				code.zone = self.get_zone(data[6])
				# crc = data[7]
				pass
			elif setting_type_2 == 0x03:
				# E6 06 03 00 00 01 02 03 04 08 00 08 00 01 FF 
				# code id and two codes
				# code id range 0 - 50
				# code id 0, code_1 = master code, code_2 = service code
				code_id = int(data[3])*10 + int(data[4])
				code = self.get_code(code_id)
				# code_1 5-8
				code1 = "".join(map(lambda x: hex(x)[2:], data[5:9]))
				if not code1 == "ffff":
					code1 = "".join(map(lambda x: hex(x)[2:], data[5:9]))
					code.code1 = code1
					code.enabled = True
				# code_2 9-12
				code2 = "".join(map(lambda x: hex(x)[2:], data[9:13]))
				if not code2 == "ffff":
					code.code2 = code2
					code.enabled = True
				# crc = data[13]
				pass
			elif setting_type_2 == 0x04:
				# E6 06 04 00 00 00 00 00 00 43 FF 
				# timers
				# id range 0 - 9
				# timer_id = int(data[3])
				# activity = data[4]
				# hours_start = data[5]
				# minutes_start = data[6]
				# hours_end = data[7]
				# minutes_end =data[8]
				# crc = data[9]
				pass
			elif setting_type_2 == 0x05:
				# E6 06 05 00 3A FF 
				# some setting, only one field
				# setting = data[4]
				# crc = data[5]
				pass
			elif setting_type_2 == 0x06:
				# E6 06 06 00 44 FF 
				# this tells if system is unsplit, partial or split
				system_type_setting = data[3]
				if system_type_setting == 0x00:
					# unsplit
					self.mode = JA80CentralUnit.SYSTEM_MODE_UNSPLIT
				elif system_type_setting == 0x01:
					# partial
					self.mode = JA80CentralUnit.SYSTEM_MODE_PARTIAL
				elif system_type_setting == 0x02:
					# split
					self.mode = JA80CentralUnit.SYSTEM_MODE_SPLIT
				# crc = data[4]
			elif setting_type_2 == 0x08:
				# E6 06 08 00 01 41 FF 
				# some (binary?) settings
				# id range 0-7
				id_ = int(data[3])
				setting = data[4]
				crc = data[5]
				pass
			elif setting_type_2 == 0x09:
				# E6 06 09 00 00 4B FF 
				# some (binary?) settings
				# id range 0-7
				#id = int(data[3])
				#setting = data[4]
				#crc = data[5]
				pass

	def _process_state_detail(self, data: bytearray, packet_data: str) -> None:

		# if we are in elevated mode, don't process the detail
		if self.is_elevated():
			return

		detail = data[1]
		#crc = data[2]
		if detail == 0x00:
			# ???
			pass
		elif detail == 0x01:
			# panic alarm / what to do with this?
			pass
		elif detail == 0x02:
			# alarm / should this alarm all armed zoned?
			pass
		elif detail == 0x03:
			# fire alarm /should this alarm all zones?
			pass
		elif detail == 0x0e:
			# ???
			pass
		elif detail == 0x0b:
				# ???
			pass
		elif detail == 0x0d:
			# ???
			pass
		elif detail == 0x0c:
			# ???
			pass
		elif detail == 0x08:
			# comes at least when trying to enter service mode while already in service mode
			pass
		else:
			LOGGER.error(f'Unknown state detail received data={packet_data}')

	def _process_message(self, data: bytearray) -> None:
		packet_data = " ".join(["%02x" % c for c in data])
		message_type = JablotronMessage.get_message_type_from_record(data,packet_data)
		if message_type is None:
			return
		if message_type == JablotronMessage.TYPE_STATE:
			self._process_state(data, packet_data)
		elif message_type == JablotronMessage.TYPE_EVENT or message_type == JablotronMessage.TYPE_EVENT_LIST:
			# only process an event once
			if self._last_event_data != packet_data[3:21]:
				self._last_event_data = packet_data[3:21]
				LOGGER.debug(f'Last Event: {self._last_event_data}')
				self._process_event(data, packet_data)
		elif message_type == JablotronMessage.TYPE_SETTINGS:
			# service or master code needed to get these
			self._process_settings(data, packet_data)
		elif message_type == JablotronMessage.TYPE_STATE_DETAIL:
			self._process_state_detail(data, packet_data)
		elif message_type == JablotronMessage.TYPE_KEYPRESS:
			#keypress = JablotronMessage.get_keypress_option(data[0]& 0x0f)
			pass
		elif message_type == JablotronMessage.TYPE_PING_OR_OTHER:
			if len(data) != 2:
				LOGGER.debug(f"Embedded Ping: {packet_data}")
				# process message without the ping prefix
				self._process_message(data[1:])
		elif message_type == JablotronMessage.TYPE_BEEP:
			beep = JablotronKeyPress.get_beep_option(data[0]& 0x0f)
			LOGGER.info("Keypad Beep: " + hex(data[0]) + ", " + str(beep['desc']))
			#A4 incorrect?
			#A0 "received"?
			#A1 correct?
			pass
		elif message_type == JablotronMessage.TYPE_PING:
			LOGGER.debug("Ping Message: " + hex(data[0]))
			pass

	def __str__(self) -> str:
		s = f'System status={self.system_status},rf={self.rf_level.value}, system mode={self._mode}\n'
		s += f'leds: alarm={self.led_alarm}, a={self.led_a}, b={self.led_b}, c={self.led_c}, power={self.led_power}\n'
		s += f'{self._settings}'
		s += f'Zones:\n'
		for zone in self._zones.values():
			s += f'{zone}\n'
		s += "Active devices:\n"
		for device in self._active_devices.values():
			s += f'{device}\n'
		s += "Devices:\n"
		for device in self.devices:
			s += f'{device}\n'
		s += "Codes:\n"
		for code in self._codes.values():
			if code.enabled:
				s += f'{code}\n'
		return s

	def send_elevated_mode_command(self) -> None: 
		if not self._system_status in self.STATUS_ELEVATED:
			self._connection.add_command(JablotronCommand(name="Elevated mode first part",
				code=b'\x8f', confirm_prefix=b'\x8f'))
			self._connection.add_command(JablotronCommand(name="Elevated mode second part",
				code=b'\x80', confirm_prefix=b'\x80'))

	def send_return_mode_command(self) -> None:
		#if self.system_status in self.STATUS_ELEVATED:
		self._connection.add_command(JablotronCommand(name="Esc / back",
			code=b'\x8e', confirm_prefix=b'\x8e'))

	async def send_settings_command(self) -> None:
		#if self.system_status in self.STATUS_ELEVATED:
		command = JablotronCommand(name="Get settings",
				code=b'\x8a', confirm_prefix=b'\xe6\x04', max_records=300)
		self._connection.add_command(command)
		return await command.wait_for_confirmation()

	def send_detail_command(self) -> None:
		self._connection.add_command(JablotronCommand(name="Details",
			code=b'\x8e', confirm_prefix=b'\x8e'))

	def enter_elevated_mode(self, code: str) -> bool:
		# mode service/maintenance depends on pin send after this
		if JablotronState.is_elevated_state(self._last_state):
			# do nothing already on elevated mode
			pass
		elif JablotronState.is_disarmed_state(self._last_state):
			self.send_elevated_mode_command()
			self.send_key_press(code)
		elif self._last_state == JablotronState.BYPASS:
			self.send_return_mode_command()
		elif self._last_state == None:
			LOGGER.warning(
				f'Trying to enter elevated mode but not reliable status yet')
			return False
		else:
			LOGGER.error(
				f'Trying to enter elevated mode but state is {self._last_state:x}')
			return False
		return True

	def return_mode(self) -> None:
		if self._last_state == None:
			self.send_return_mode_command()
		elif not JablotronState.is_disarmed_state(self._last_state):
			self.send_return_mode_command()
		else:
			LOGGER.warning(
				f'Trying to enter normal mode but state is {self.last_state}')

	async def read_settings(self) -> bool:
		await asyncio.sleep(5)
		if self.enter_elevated_mode(self._master_code):
			result = await self.send_settings_command()
			self.send_return_mode_command()
			return result
		return False

	def send_key_press(self, key: str) -> None:
		for cmd in key:
			value = JablotronKeyPress.get_key_command(cmd)
			name = cmd
			if JablotronSettings.HIDE_KEY_PRESS:
				name = "*HIDDEN*"
			self._connection.add_command(
				JablotronCommand(name=f'keypress {name}',code=value, confirm_prefix=value))
			
	def shutdown(self) -> None:
		self._stop.set()
		self._connection.shutdown()


	def arm(self,code: str,zone:str=None) -> None:
		if zone is None:
			self.send_key_press(code)
		else:
			self.send_key_press({"A":"*2","B":"*3","C":"*1"}[zone]+code)
	
	def disarm(self,code:str,zone:str=None) -> None:
		self.send_key_press(code)
		if JablotronState.is_alarm_state(self._last_state):
			#confirm alarm
			self.send_key_press("?")
		
	async def processing_loop(self) -> None:
		previous_record = None
		while not self._stop.is_set():
			try:
				while (records := self._connection.get_record()) is not None: 
					for record in records:
						if record  != previous_record:
							previous_record = record
							self._process_message(record)
				await asyncio.sleep(1)
			except Exception as ex:
				LOGGER.error(f'Unexpected error:{record}:  {traceback.format_exc()}')
			
	# this is just for console testing
	async def status_loop(self) -> None:
		await asyncio.sleep(60)
		while not self._stop.is_set():
			LOGGER.info(f'{self}')
			await asyncio.sleep(60)
			#self.send_key_press(self._master_code)


if __name__ == "__main__":
	
	
	cu = JA80CentralUnit(None,{CONFIGURATION_SERIAL_PORT:"/dev/hidraw0",CONFIGURATION_PASSWORD :"1234"})
	loop = asyncio.get_event_loop()
	loop.create_task(cu.processing_loop())
	loop.create_task(cu.status_loop())
	loop.create_task(cu.read_settings())
   # loop.create_task(cu.status_loop())
	from concurrent.futures import ThreadPoolExecutor
	io_pool_exc = ThreadPoolExecutor(max_workers=1)
	loop.run_in_executor(io_pool_exc, cu._connection.read_send_packet_loop)
	loop.run_forever() 
  

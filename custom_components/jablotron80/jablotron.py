import queue
import time
import datetime
from dataclasses import dataclass, field
from typing import List,Any,Optional,Union
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import serial
import crccheck

from custom_components.jablotron80.const import DEVICE_CONTROL_PANEL
LOGGER = logging.getLogger(__package__)
expected_warning_level = logging.warn
verbose_connection_logging = False
_loop = None # global variable to store event loop


from typing import Any, Dict, Optional, Union,Callable
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from homeassistant.const import (
	EVENT_HOMEASSISTANT_STOP
)


if __name__ == "__main__":
	from const import (
		CONFIGURATION_SERIAL_PORT,
#		CONFIGURATION_NUMBER_OF_DEVICES,
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
		CONFIGURATION_NUMBER_OF_WIRED_DEVICES,
		CONFIGURATION_QUIETEN_EXPECTED_WARNINGS,
		CONFIGURATION_VERBOSE_CONNECTION_LOGGING,
		MIN_NUMBER_OF_WIRED_DEVICES,
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

def format_packet(data):
		return " ".join(["%02x" % c for c in data])

class JablotronSettings:
	#sleep when no command
	#SERIAL_SLEEP_NO_COMMAND = 0.2

	#these are hiding sensitive output from logs
	HIDE_CODE = True
	HIDE_KEY_PRESS = True

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
	_available: bool = field(default=True, init=False)

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
		self._battery_low = state

	@property	
	def available(self) -> bool:
		return self._available
 
	@available.setter
	@log_change
	def available(self,state:bool)->None:
		self._available = state

	@property	
	def name(self) -> str:
		if self._name is None:
			
			if self.model is None and self.serial_number is not None:
				return f'serial {self.serial_number}'
			elif self.model is not None and self.serial_number is not None:
				return f'{self.model} serial {self.serial_number}'
			elif self.model is not None:
				return f'{self.model} device {self.device_id}'
			else:

				# device 52 & 53 are visible in Bypass
				if self.device_id == 52:
					return 'Keypad'

				elif self.device_id == 53:
					return 'Communicator'
        
				elif self.device_id == 60:
					return 'PGX'

				elif self.device_id == 61:
					return 'PGY'
        
				# device 63 is when home assisant sets the alarm (with no code)
				elif self.device_id == 63:
					return 'Device on line'	
        
				return f'device {self.device_id}'
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
	
	@property
	def is_keypad(self) -> bool:
		return self.model == "JA-81F"

	@property
	def is_motion(self) -> bool:
		return self.model == "JA-80W" \
			or self.model == "JA-86P" \
			or self.model == "JA-84P"

	@property
	def is_outdoor_siren(self) -> bool:
		return self.model == "JA-80A"

	@property
	def is_indoor_siren(self) -> bool:
		return self.model == "JA-80L"

	@property
	def is_door(self) -> bool:
		return self.model == "JA-82M"

	@property
	def is_keyfob(self) -> bool:
		return self.model == "RC-86" \
			or self.model == "RC-86 (80)"

	@property
	def is_central_unit(self) -> bool:
		return self.device_id == 0 or self.device_id == 51
		
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
			s+=f',name={self.name}'
		if not self.zone is None:
			s+=f',zone={self.zone.name}'
		if not self.serial_number is None:
			s += f',serial={self.serial_number}'
		s += f',active={self._active}'
		return s


@dataclass
class JablotronControlPanel(JablotronDevice):
	_last_event: str = field(default="",init=False)


	def __post_init__(self) -> None:
		super().__post_init__()

	@property	
	def last_event(self) -> str:
		return self._last_event
 
	@last_event.setter
	@log_change
	def last_event(self,last_event:str)->None:
		self._last_event  = last_event

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
			#self.alarm(device)
			pass
			
	@check_active     
	def device_deactivated(self,device: JablotronDevice)-> None:
		if self.status == JablotronZone.STATUS_ALARM:
			#self.disarm()
			pass

	@check_active     
	def code_activated(self,code: JablotronCode ) -> None:
		if self.status == JablotronZone.STATUS_ARMED or code.reaction == JablotronConstants.REACTION_FIRE_ALARM:
			#self.alarm(code)
			pass
			
	@check_active     
	def code_deactivated(self,device: JablotronDevice)-> None:
		if self.status == JablotronZone.STATUS_ALARM:
			#self.disarm()
			pass

	
	@check_active      
	def tamper(self,by: Optional[JablotronDevice]  = None) -> None:
		#self.alarm(by)
		pass
		
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
	complete_prefix: str = None
	accepted_prefix: str = None
	max_records: int = 20
	
	def __post_init__(self) -> None:
		self._event = asyncio.Event()
	
	async def wait_for_confirmation(self) -> bool:
		await self._event.wait()
		return self._confirmed
		
	def confirm(self,confirmed: bool) -> None:
		self._confirmed = confirmed
		_loop.call_soon_threadsafe(self._event.set)
		
	def __str__(self) -> str:
		s = f'Command name={self.name}'
		return s



class JablotronConnection():

	@staticmethod
	def factory(cable_model: str, serial_port: str):
		if cable_model == CABLE_MODEL_JA82T:
			return JablotronConnectionHID(serial_port)
		else:
			return JablotronConnectionSerial(serial_port)

	# device is mandatory at initiation
	def __init__(self, device: str) -> None:
		self._device = device
		self._cmd_q = queue.Queue()
		self._output_q = queue.Queue()
		self._stop = threading.Event()
		self._connection = None
		self._messages = asyncio.Event() # are there messages to process

	def get_record(self) -> List[bytearray]:
		
		# build up multiple records from many queue entries
		# multiple records are not used in normal running as single messages are process one at a time
		records = []
		while not self._output_q.empty():
			for record in self._output_q.get_nowait():
				records.append(record)
			self._output_q.task_done()

		return records
		
	@property
	def device(self):
		return self._device
	
	def disconnect(self) -> None:
		if self.is_connected():
			LOGGER.info('Disconnecting from JA80...')
			self._connection.flush()
			self._connection.close()
			self._connection = None
		else:
			LOGGER.info('No need to disconnect; not connected')

	def reconnect(self):
		LOGGER.warning('connection failed, reconnecting')
		time.sleep(1)
		self.disconnect()
		self.connect()

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
	   
		return cmd
	
	def _forward_records(self,records: List[bytearray]) -> None:
		self._output_q.put(records)
		self._log_detail(f'Forwarding {len(records)} records')
		_loop.call_soon_threadsafe(self._messages.set)

	def _log_detail(self, log: str):

		if verbose_connection_logging:
			level = LOGGER.getEffectiveLevel()
			LOGGER.log(level, log)

	def connect(self) -> None:
		raise NotImplementedError

	def _read_data(self, max_package_sections: int =15)->List[bytearray]:
		raise NotImplementedError

	def _get_cmd(self, code: bytes) -> str:
		raise NotImplementedError

	def _confirmed(self, record, send_cmd: JablotronCommand):
		raise NotImplementedError


	def read_send_packet_loop(self) -> None:
		# keep reading bytes untill 0xff which indicates end of packet
		LOGGER.debug('Loop endlessly reading serial')
		while not self._stop.is_set() or self._cmd_q.unfinished_tasks > 0:
			try:
				if not self.is_connected():
					LOGGER.error('Not connected to JA80, abort')
					return []
				records = self._read_data()
				self._forward_records(records)
				send_cmd = self._get_command()
		
				if send_cmd is not None:
					# new command in queue

					accepted = False
					confirmed = False
					retries = 2 # 2 retries signifies 3 attempts

					while retries >= 0 and not (accepted and confirmed):
						level = logging.INFO
						for i in range(0,len(send_cmd.code)):
							if i == len(send_cmd.code)-1:
								accepted_prefix = send_cmd.accepted_prefix
							else:
								accepted_prefix =b'\xa0\xff'

							if not send_cmd.code is None:
								cmd = self._get_cmd(send_cmd.code[i].to_bytes(1,byteorder='big'))
								LOGGER.debug(f'Sending keypress, sequence:{i}')
								self._connection.write(cmd)
								LOGGER.debug(f'keypress sent, sequence:{i}')

							if self.read_until_found(accepted_prefix):
								LOGGER.debug(f'keypress accepted, sequence:{i}')
								accepted = True
							else:
								if retries == 0:
									level = logging.WARN

								LOGGER.log(level, f'no accepted message for sequence:{i} received')
								accepted = False
								break # break from for loop into retry loop, has effect of starting full command sequence from scratch

						if accepted:
							if send_cmd.complete_prefix is not None:
								# confirmation required, read until confirmation or to limit
								if self.read_until_found(send_cmd.complete_prefix, send_cmd.max_records):
									LOGGER.info(f"command {send_cmd} completed")
								else:
									if retries == 0:
										level = logging.WARN	
									LOGGER.log(level, f"no completion message found for command {send_cmd}")
									send_cmd.confirm(False)
									continue
									
							send_cmd.confirm(True)
							confirmed = True
							self._cmd_q.task_done()

						retries -=1
# No sleep needed in normal running as serial read blocks
#				else:
#					time.sleep(JablotronSettings.SERIAL_SLEEP_NO_COMMAND)

			except Exception:
				LOGGER.exception('Unexpected error: %s')
		self.disconnect()

	def read_until_found(self, prefix: str, max_records: int = 10) -> bool:

		for i in range(max_records):
			records_tmp = self._read_data()
			self._forward_records(records_tmp)
			for record in records_tmp:
				LOGGER.debug(f'record:{i}:{format_packet(record)}')
				if record[:len(prefix)] == prefix:
					return True
		
		return False


class JablotronConnectionHID(JablotronConnection):

	def connect(self) -> None:

		LOGGER.info(f'Connecting to JA80 via HID using {self._device}...')
		self._connection = open(self._device, 'w+b',buffering=0)
		LOGGER.debug('Sending startup message')
		self._connection.write(b'\x00\x00\x01\x01')
		LOGGER.debug('Successfully sent startup message')


	def _read_data(self, max_package_sections: int = 30)->List[bytearray]:
		read_buffer = []
		ret_val = []

		for j in range(max_package_sections):
			data = b''
			while data == b'':
				try:
					data = self._connection.read(64)
				except OSError:
					self.reconnect()

			self._log_detail(f'Received raw data {format_packet(data)}')
			if len(data) > 0 and data[0] == 0x82:
				size = data[1]
				if size+2 > len(data):
					size = len(data) - 2 # still process what we have, but make sure we don't overshoot buffer
					LOGGER.warning(f'Corrupt packet section: {format_packet(data)}')
				read_buffer.append(data[2:2+int(size)])
				if data[1 + int(size)] == 0xff:
					# return data received
					ret_bytes = []
					for i in b''.join(read_buffer):
						ret_bytes.append(i)
						if i == 0xff:
							record = bytearray(ret_bytes)
							self._log_detail(f'received record: {format_packet(record)}')
							ret_val.append(record)
							ret_bytes.clear()
					return ret_val
		return ret_val

	def _get_cmd(self, code: bytes) -> str:
		return b'\x00\x02\x01' + code


class JablotronConnectionSerial(JablotronConnection):

	def connect(self) -> None:

		LOGGER.info(f'Connecting to JA80 via Serial using {self._device}...')

		while self._connection is None:

			try:
				self._connection = serial.serial_for_url(url=self._device,
											baudrate=9600,
											parity=serial.PARITY_NONE,
											bytesize=serial.EIGHTBITS,
											dsrdtr=True,# stopbits=serial.STOPBITS_ONE
											timeout=1)
			except serial.SerialException as ex:
				if "timed out" in f'{ex}':
					LOGGER.info('Timeout, retrying')
				else:
					raise

	def _read_data(self, max_package_sections: int =15)->List[bytearray]:
		ret_val = []
		data = b''

		while data == b'':
			data = self._connection.read_until(b'\xff')

			if data == b'':
				self.reconnect()
				self._connection.read_until(b'\xff') # throw away first record as will be corrupt

		self._log_detail(f'received record: {format_packet(data)}')
		ret_val.append(data)
		return ret_val


	def _get_cmd(self, code: bytes) -> str:
		return code


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
		0x0: {'val': '0', 'desc': 'Key 0 pressed on keypad'}, 
		0x1: {'val': '1', 'desc': 'Key 1 (^) pressed on keypad'},
		0x2: {'val': '2', 'desc': 'Key 2 pressed on keypad'},
		0x3: {'val': '3', 'desc': 'Key 3 pressed on keypad'}, 
	 	0x4: {'val': '4', 'desc': 'Key 4 (<) pressed on keypad'}, 
		0x5: {'val': '5', 'desc': 'Key 5 pressed on keypad'}, 
		0x6: {'val': '6', 'desc': 'Key 6 (>) pressed on keypad'},
		0x7: {'val': '7', 'desc': 'Key 7 (v) pressed on keypad'},
		0x8: {'val': '8', 'desc': 'Key 8 pressed on keypad'}, 
		0x9: {'val': '9', 'desc': 'Key 9 pressed on keypad'}, 
		0xe: {'val': '#', 'desc': 'Key # (ESC/OFF) pressed on keypad'}, 
		0xf: {'val': '*', 'desc': 'Key * (ON) pressed on keypad'}
	}
	
	_BEEP_OPTIONS = {
		# happens when warning appears on keypad (e.g. after alarm)
		0x0: {'val': '1s', 'desc': '1 subtle (short) beep triggered'},
	 	0x1: {'val': '1l', 'desc': '1 loud (long) beep triggered'},
		0x2: {'val': '2l', 'desc': '2 loud (long) beeps triggered'},
		0x3: {'val': '3l', 'desc': '3 loud (long) beeps triggered'},
		0x4: {'val': '4s', 'desc': '4 subtle (short) beeps triggered'},
		0x5: {'val': '3s', 'desc': '3 subtle (short) beeps, 1 then 2'},
		0x7: {'val': '0(1)', 'desc': 'no audible beep(1)'},
		0x8: {'val': '0(2)', 'desc': 'no audible beep(2)'},
		0xe: {'val': '?', 'desc': 'unknown beep(s) triggered'}
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
	TYPE_SAVING = 'Saving'
	TYPE_CONFIRM = 'Confirm'
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
		0xb3: TYPE_PING,
		0xb4: TYPE_PING,
		0xb6: TYPE_PING,
		0xb7: TYPE_BEEP, # beep on set/unset (for all but setting AB)
		0xb8: TYPE_BEEP, # on setup
		0xba: TYPE_PING,
		0xc6: TYPE_PING,
		0xe7: TYPE_EVENT,
		0xec: TYPE_SAVING,
		0xfe: TYPE_BEEP, # on setup
		0xff: TYPE_CONFIRM # with JA-80T cable
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
		0xec: 5,
		0xff: 1
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
	def check_crc(packet: bytes) -> bool:

		length = len(packet)

		if length <= 2:
			LOGGER.debug('Short packet, no CRC to check')
			return True

		assert packet[length-1] == 0xff
		expected_checksum = packet[length-2]
		data = packet[:length-2]

		# first attempt to check CRC with one algo
		crcchecker = crccheck.crc.Crc(8, 70, initvalue=49, xor_output=0, reflect_input=False, reflect_output=False)
		checksum = crcchecker.calc(data)

		# crc is always < 0x7f, probably dropped top bit because otherwise could be seen as end of packet (0xff). However have verified it is not an CRC7 algo!
		if not checksum & 0x7f == expected_checksum:
			# second attempt to check CRC with second algo, don't know why 2 different CRC algs required..... probabyl incorrect, but will see with more data, perhaps the xor_output value is derived from somewhere else?
			crcchecker = crccheck.crc.Crc(8, 70, initvalue=49, xor_output=35, reflect_input=False, reflect_output=False)
			checksum = crcchecker.calc(data)

			if not checksum & 0x7f == expected_checksum:
				return False

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
			LOGGER.log(expected_warning_level, f'Unknown message type {hex(record[0])} with data {packet_data} received')
		else:
			if not JablotronMessage.check_crc(record):
				LOGGER.log(expected_warning_level, f'Invalid CRC for {packet_data}')
			elif JablotronMessage.validate_length(message_type,record):
				LOGGER.debug(f'Message of type {message_type} received {packet_data}')
				return message_type
			else:
				LOGGER.log(expected_warning_level, f'Invalid message of type {message_type} received {packet_data}')
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
	BYPASS = 0x21
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
	ARMED_ENTRY_DELAY_AB = 0x4a	
	ARMED_ENTRY_DELAY_ABC = 0x4b
	ARMED_ENTRY_DELAY_A_SPLIT = 0x69
	ARMED_ENTRY_DELAY_B_SPLIT = 0x6a
	ARMED_ENTRY_DELAY_C_SPLIT = 0x6b

	STATES_ENTERING_DELAY = [ARMED_ENTRY_DELAY_A, ARMED_ENTRY_DELAY_AB, ARMED_ENTRY_DELAY_ABC,
								ARMED_ENTRY_DELAY_A_SPLIT, ARMED_ENTRY_DELAY_B_SPLIT, ARMED_ENTRY_DELAY_C_SPLIT]
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


class JablotronButton(JablotronCommon):
	pass

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

@dataclass
class JablotronAlert(JablotronCommon):
	_value: str = field(default='OK',init=False)
	_message: str = field(default='',init=False)

	@property
	def value(self) -> str:
		return self._value

	@value.setter
	@log_change
	def value(self,val:str) -> None:
		self._value = val

	@property
	def message(self) -> str:
		return self._message

	@message.setter
	@log_change
	def message(self,message:str) -> None:
		self._message = message

@dataclass
class JablotronStatusText(JablotronCommon):
	_message: str = field(default='',init=False)

	@property
	def active(self) -> str:
		return self._message != '' or self._message is None

	@property
	def message(self) -> str:
		return self._message

	@message.setter
	@log_change
	def message(self,message:str) -> None:
		self._message = message

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
		self._connection = JablotronConnection.factory(config[CABLE_MODEL], config[CONFIGURATION_SERIAL_PORT])
		try:
			self._max_number_of_wired_devices = config[CONFIGURATION_NUMBER_OF_WIRED_DEVICES]
		except KeyError:
			self._max_number_of_wired_devices = MIN_NUMBER_OF_WIRED_DEVICES

		self._zones = {}
		self._zones[1] = JablotronZone(1)  
		self._zones[2] = JablotronZone(2)  
		self._zones[3] = JablotronZone(3)
		self.central_device = JablotronControlPanel(0)
		self.central_device.model = CENTRAL_UNIT_MODEL
		# device that receives fault alerts such as tamper alarms and communication failures
		self.central_device.name = f'{CENTRAL_UNIT_MODEL} Control panel'
		self.central_device.manufacturer = MANUFACTURER
		self.central_device.type = DEVICE_CONTROL_PANEL
		self._devices = {}
		self._devices[0] = self.central_device # add central device as a device so it gets an entity 
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

		self._alert = JablotronAlert(2)
		self._alert.name = f'{CENTRAL_UNIT_MODEL} Alert'
		self._alert.type = "alert"

		self._statustext = JablotronStatusText(3)
		self._statustext.name = f'{CENTRAL_UNIT_MODEL} Status Text'
		self._statustext.type = "status"

		self._query = JablotronButton(4)
		self._query.name = f'{CENTRAL_UNIT_MODEL} Query Button'
		self._query.type = "button"

		self._active_devices = {}
		self._active_codes = {}
		self._codes = {}
		self._device_query_pending = False
		self._last_state = None
		self._mode = None
		self._connection.connect()
		self._stop = threading.Event()
		self._havestate = asyncio.Event() # has the first state message been received

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

		global expected_warning_level
		try:
			if options[CONFIGURATION_QUIETEN_EXPECTED_WARNINGS]:
				expected_warning_level = logging.DEBUG
			else:
				expected_warning_level = logging.WARN
		except:
			pass

		global verbose_connection_logging
		try:
			verbose_connection_logging = options[CONFIGURATION_VERBOSE_CONNECTION_LOGGING]
		except:
			pass

	async def initialize(self) -> None:
		global _loop
		def shutdown_event(_):
			self.shutdown()
		LOGGER.info("initializing")
		if not self._hass is None:
			self._hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, shutdown_event)
		_loop = asyncio.get_event_loop()
		_loop.create_task(self.processing_loop())
		io_pool_exc = ThreadPoolExecutor(max_workers=1)
		_loop.run_in_executor(io_pool_exc, self._connection.read_send_packet_loop)
		await asyncio.wait_for(self._havestate.wait(), 20)
		LOGGER.info(f"initialization done.")

		
	def is_code_required_for_arm(self) -> bool:
		value = self._settings.get_setting(JablotronSettings.SETTING_ARM_WITHOUT_CODE)
		return  value is None or value == False

	@property
	def devices(self) -> List[JablotronDevice]:

		def registered(device: JablotronDevice):

			if (device.serial_number is not None \
				and device.reaction != JablotronConstants.REACTION_OFF) \
				or device.model == "wired":
				return True
			
			return False

		return list(filter(registered, [self.get_device(i) for i in range(1,MAX_NUMBER_OF_DEVICES)] ) )

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
#		return  "/dev/hidraw0"
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
	def alert(self) -> JablotronAlert:
		return self._alert
	
	@alert.setter
	def alert(self,alert: str) -> None:
		self._alert.value= alert

	@property
	def statustext(self) -> JablotronStatusText:
		return self._statustext
	
	@statustext.setter
	def statustext(self,statustext: str) -> None:
		self._statustext.message = statustext

	@property
	def query(self) -> JablotronButton:
		return self._query

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
	
	def _get_source_name(self, source:bytes) -> str:
		if source is None:
			return "Unknown"
		source_obj = self._get_source(source)
		if source_obj is None:
			return "Unknown"
		else:
			return source_obj.name

	def get_device(self, id_: int) -> JablotronDevice:
		if id_ == 51 or id == 0 :
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
 
	def _clear_source(self, source_id:bytes) -> None:
		source  = self._get_source(source_id)
		source.active = False

	def _clear_tampers(self) -> None:
		for device in self.devices:
			if device.tampered:
				device.tampered = False

	def _clear_battery(self) -> None:
		for device in self.devices:
			if device.battery_low:
				device.battery_low = False

	def _activate_source(self,source_id:bytes ,type=None) -> None:
		source  = self._get_source(source_id)
		if isinstance(source,JablotronDevice):
			self._activate_device(source)
		elif isinstance(source,JablotronCode):
			self._activate_code(source)
		else:
			LOGGER.warning(f'Unknown source type {source_id}')

	def _activate_code(self, code_id):
		code  = self._get_source(code_id)
		self._activate_code_object(code)

	def _clear_code(self, code_id):
		code  = self._get_source(code_id)
		if isinstance(code,JablotronCode):
			code.active = False

	def _activate_code_object(self, source):
		# is there need to trigger state for code?
		if isinstance(source,JablotronCode):
			self._active_codes[source._id] = source
			source.active = True
			zone = self._get_zone_via_object(source)
			if not zone is None:
				zone.code_activated(source)

	def _activate_device(self, source):
		if isinstance(source,JablotronDevice):
			source.active = True
			self._active_devices[source.device_id] = source
			zone = self._get_zone_via_object(source)
			if not zone is None:
				zone.device_activated(source)
	
	def _fault_source(self,source_id:bytes) -> None:
		source  = self._get_source(source_id)
		if isinstance(source,JablotronDevice):
			source.available= False
		else:
			LOGGER.error(f'Fault called for none device:{source_id}')

	def _clear_fault(self,source_id:bytes) -> None:
		source  = self._get_source(source_id)
		if isinstance(source,JablotronDevice):
			source.available = True
		else:
			LOGGER.error(f'Clear_Fault called for none device:{source_id}')

	def _clear_faults(self) -> None:
		for device in self.devices:
			if not device.available:
				device.available = True

	def _alarm_via_source(self,source_id: bytes) -> None:
		source  = self._get_source(source_id)
		self._get_zone_via_object(source).alarm(source)
			
   
	def _activate_panic_alert(self,source_id:bytes)-> None:
		self._alarm_via_source(source_id)

	
	def _process_event(self, data: bytearray, packet_data: str) -> None:
		date_time_obj = self._get_timestamp(data[1:5]) # type: datetime.datetime
		event_type = data[5]
		event_name = "Unknown" # default name to Unknown if we don't know what it is
		warn = False # by defalt we will log an info message, but for important items we will install warn
		source = data[6]
		# codes 40 master code, 41 - 50 codes 1-10
		# can source be also code? Now assuming it is device.
		# logic for codes and devices? devices in range hex 01 - ??, codes in 40 -
		if event_type == 0x01:
			event_name = "Instant zone Alarm"
			self._activate_source(source)
		elif event_type == 0x02:
			event_name = "Delay zone Alarm"
			self._activate_source(source)
		elif event_type == 0x03:
			event_name = "Fire zone Alarm"
			self._activate_source(source)
		elif event_type == 0x04:
			event_name = "Panic Alarm"
			self._activate_source(source)
		elif event_type == 0x05:
			event_name = "Tampering alarm"
			# entering service mode, source = by which id
			self._device_tampered(source)
			self._activate_source(source)
			warn = True
			#if source == 0x0:
			#	event_name += ", Control panel"
		elif event_type == 0x06:
			event_name = "Tampering key pad (wrong code?)"
			warn = True
			self._device_tampered(source)
			self._activate_source(source)
		elif event_type == 0x07:
			event_name = "Fault"
			warn = True
			self._fault_source(source)
		elif event_type == 0x08:
			event_name = "Setting"
			self._activate_code(source)
			self._clear_triggers()
			self._call_zones(function_name="arming",source_id=source)
		elif event_type == 0x09:
			event_name = "Unsetting"
			# unsetting, source = by which code
			self._clear_code(source)
			self._call_zones(function_name="disarm",source_id=source)
		elif event_type == 0x0c:
			event_name = "Completely set without code"
			# self._zones[JablotronSettings.ZONE_UNSPLIT].armed(source)
			self._call_zones(function_name="arming",source_id=source)
		elif event_type == 0x0d:
			event_name = "Partial Set A"
			self._activate_code(source)
			self._call_zone(1,by = source,function_name="arming")
		elif event_type == 0x0e:
			event_name = "Lost communication with device"
			warn = True
			self._fault_source(source)
		elif event_type == 0x0f:
			event_name = "Power fault of control panel"
			warn = True
			self._activate_source(source)			
		elif event_type == 0x10:
			event_name = "Control panel power O.K."
			self._clear_source(source)			
		elif event_type == 0x11:
			event_name = "Discharged battery"
			warn = True
			self._device_battery_low(source)
		elif event_type == 0x14:
			event_name = "Backup battery fault"
			warn = True
			self._device_battery_low(source)
			self._activate_source(source)	
		elif event_type == 0x17:
			event_name = "24 hours" # for example panic alarm
			# 24 hours code=source
			source  = self._get_source(source)
			self._activate_source(source)
		elif event_type == 0x1a:
			event_name = "Setting Zone A"
			self._activate_code(source)
			self._call_zone(1,by = source,function_name="arming")
		elif event_type == 0x1b:
			event_name = "Setting Zone B"
			self._activate_code(source)
			self._call_zone(2,by = source,function_name="arming")
		elif event_type == 0x21:
			event_name = "Partial Set A,B"
			self._activate_code(source)
			self._call_zone(1,by = source,function_name="arming")
			self._call_zone(2,by = source,function_name="arming")
		elif event_type == 0x40:
			event_name = "Control panel powering up"
		elif event_type == 0x41:
			event_name = "Enter Elevated Mode"
		elif event_type == 0x42:
			event_name = "Exit Elevated Mode"
		elif event_type == 0x44:
			event_name = "Data sent to ARC"
		elif event_type == 0x4e:
			event_name = "Alarm cancelled by a user"
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
			event_name = "All devices' power O.K."
			self._clear_battery()
		elif event_type == 0x5a:
			event_name = "Unconfirmed alarm"
			if not self._get_source(source).is_central_unit:
				self._activate_source(source)
#			else:
				# This event occurs when an entrance delay is caused by an unconfirmed alarm
				# It looks to me like a bug in the firmware to show this as the alarm should only be triggered once
				# the second detector is triggered. But the aim of this software is to replicate the alerts of the alarm system.
				# TODO: Check the alarm logs to see what is registered. 
#				event_name = event_name + ", Control panel"
			warn = True
		elif event_type == 0x5c:
			event_name = "PGX On"
		elif event_type == 0x5d:
			event_name = "PGX Off"
		elif event_type == 0x5e:
			event_name = "PGY On"
		elif event_type == 0x5f:
			event_name = "PGY Off"

		else:
			LOGGER.error(f'Unknown timestamp event data={packet_data}')
		#crc = data[7]

#		if source == 0x0:
#			log = f'{event_name}, {date_time_obj.strftime("%H:%M %a %d %b")}'
#		else:
		log = f'{event_name}, {source}:{self._get_source(source).name}, {date_time_obj.strftime("%H:%M %a %d %b")}'

		if warn:
			LOGGER.warning(log)

		self.central_device.last_event = log


	def _send_device_query(self)->None:
		if not self._device_query_pending:
			self.send_detail_command()
			
	def _confirm_device_query(self)->None:
		self._device_query_pending = False

	def _process_state(self, data: bytearray, packet_data: str) -> None:

		status = data[1]
		self._havestate.set()

		activity = data[2] & 0x3f # take lower bit below 0x40
		detail = data[3]
		leds = data[4]
		self.led_a = (leds & 0x08) == 0x08
		self.led_b = (leds & 0x04) == 0x04
		self.led_c = (leds & 0x02) == 0x02
		self.led_power  = (leds & 0x01) == 0x01 # if this is not set, power is out on control panel and power led flashes
		self.led_alarm = (leds & 0x10) == 0x10 # alert triagle may be flashing or solid
		self.led_solid_alarm = (leds & 0x20) == 0x20 # The alert triangle is solid
		
		if self.led_solid_alarm:
			self.alert = "Fault"
		elif self.led_alarm:
			self.alert = "Alarm"
		else:
			self.alert = "OK"

		detail_2 = data[5]
		field_2 = data[6]
		# this is probably rf strength 00 = 0%, 0A = 10%, 1E = 75%, 28 = 100%?
		self.rf_level = int(data[7]) / 40.0 * 100.0
		#crc = data[8]
		self._last_state = status

		by = detail if detail in [0x06, 0x12] else None

		if status == JablotronState.ALARM_A or status == JablotronState.ALARM_A_SPLIT:
			self._call_zone(1,by = by,function_name="alarm")
		elif status == JablotronState.ALARM_B or status == JablotronState.ALARM_B_SPLIT:
			self._call_zone(2,by = by,function_name="alarm")
		elif status == JablotronState.ALARM_C or status == JablotronState.ALARM_WITHOUT_ARMING:
			self._call_zones(by,function_name="alarm")
		elif status == JablotronState.ALARM_C_SPLIT:
			self._call_zone(3,by = by,function_name="alarm")        

		elif status in JablotronState.STATES_DISARMED:
			self.status = JA80CentralUnit.STATUS_NORMAL
			self._call_zones(function_name="disarm")

			if activity == 0x00 and not self.led_alarm:
				# clear active statuses
				self._clear_triggers()

		elif status == JablotronState.ARMED_ABC:
			self._call_zones(by, function_name="armed")
		elif status == JablotronState.ARMED_A:
			self._call_zone(1,by = by,function_name="armed")
		elif status == JablotronState.ARMED_AB:
			self._call_zone(1,by = by,function_name="armed")
			self._call_zone(2,by = by,function_name="armed")
		elif status == JablotronState.ARMED_SPLIT_A:
			self._call_zone(1,by = by,function_name="armed")
		elif status == JablotronState.ARMED_SPLIT_B:
			self._call_zone(2,by = by,function_name="armed")
		elif status == JablotronState.ARMED_SPLIT_C:
			self._call_zone(3,by = by,function_name="armed")


		elif status == JablotronState.ARMED_ENTRY_DELAY_ABC:
			self._call_zones(by, function_name="entering")
		elif status == JablotronState.ARMED_ENTRY_DELAY_A:
			self._call_zone(1,by = by,function_name="entering")
		elif status == JablotronState.ARMED_ENTRY_DELAY_AB:
			self._call_zone(1,by = by,function_name="entering")
			self._call_zone(2,by = by,function_name="entering")
		elif status == JablotronState.ARMED_ENTRY_DELAY_A_SPLIT:
			self._call_zone(1,by = by,function_name="entering")
		elif status == JablotronState.ARMED_ENTRY_DELAY_B_SPLIT:
			self._call_zone(2,by = by,function_name="entering")
		elif status == JablotronState.ARMED_ENTRY_DELAY_C_SPLIT:
			self._call_zone(3,by = by,function_name="entering")


		elif status == JablotronState.EXIT_DELAY_ABC:
			self._call_zones(by, function_name="arming")
		elif status == JablotronState.EXIT_DELAY_A:
			self._call_zone(1,by = by,function_name="arming")
		elif status == JablotronState.EXIT_DELAY_AB:
			self._call_zone(1,by = by,function_name="arming")
			self._call_zone(2,by = by,function_name="arming")
		elif status == JablotronState.EXIT_DELAY_SPLIT_A:
			self._call_zone(1,by = by,function_name="arming")
		elif status == JablotronState.EXIT_DELAY_SPLIT_B:
			self._call_zone(2,by = by,function_name="arming")
		elif status == JablotronState.EXIT_DELAY_SPLIT_C:
			self._call_zone(3,by = by,function_name="arming")

			
		if JablotronState.is_armed_state(status):
			state_text = ''
		elif JablotronState.is_service_state(status):
			state_text = 'Service'
			self.status = JA80CentralUnit.STATUS_SERVICE
			self.notify_service()
		elif JablotronState.is_maintenance_state(status):
			state_text = 'Maintenence'
			self.status = JA80CentralUnit.STATUS_MAINTENANCE
			self.notify_service()
		elif JablotronState.is_exit_delay_state(status):
			state_text = 'Exit delay'
		elif JablotronState.is_alarm_state(status):
			state_text = ''
		elif JablotronState.is_entering_delay_state(status):
			state_text = 'Entrance delay'
		elif JablotronState.is_disarmed_state(status):
			state_text = ''
		else:
			state_text = 'Unknown'
			LOGGER.error(
				f'Unknown status message status={hex(status)} received data={packet_data}')

		warn = False # should a warning message be logged
		log = True # should a message be logged at all

		if activity == 0x00:
			activity_name = ''

		elif activity == 0x01:
			activity_name = 'Service'

		elif activity == 0x02:
			activity_name = 'Maintenence'

		elif activity == 0x03:
			activity_name = 'Enrollment'

		elif activity == 0x04:
			activity_name = 'Complete entry'

		elif activity == 0x06:
			warn = True
			activity_name = 'Alarm'
			self._activate_source(detail)

		elif activity == 0x07:
			warn = True
			activity_name = 'Tamper alarm'
			self._activate_source(detail)

		elif activity == 0x08:
			warn = True
			activity_name = 'Fault'
			self._activate_source(detail)

		elif activity == 0x09:
			warn = True
			activity_name = 'Discharged battery'
			self._device_battery_low(detail)

		elif activity == 0x0a:
			activity_name = 'Set/Unset'

		elif activity == 0x0b:
			activity_name = 'Bypass'

		elif activity == 0x0c:
			activity_name = 'Exit delay'

		elif activity == 0x0d:
			activity_name = 'Entrance delay'

		elif activity == 0x0e:
			activity_name = 'Test OK'

		elif activity == 0x10:
			# permanent trigger during standard (unset) mode, e.g. a door open detector
			activity_name = 'Triggered detector'
			# something is active
			if detail == 0x00:
				# don't send query if we already have "triggered detector" displayed
				if activity_name not in self.statustext.message or activity_name == self.statustext.message:
					self._send_device_query()				
				else:
					log = False
			else:
				self._activate_source(detail)
				self._confirm_device_query()

		elif activity == 0x12:
			activity_name = 'Active output'
			self._activate_source(detail)

		elif activity == 0x13:
			activity_name = 'Codes'

		elif activity == 0x14:
			# Unconfirmed alarm
			warn = True
			activity_name = 'Unconfirmed alarm'
			if not self._get_source(detail).is_central_unit:
				self._activate_source(detail)

		elif activity == 0x16:
			activity_name = 'Triggered detector (multiple)'
			# multiple things are active
			if detail == 0x00:
				# no details... ask..
				self._send_device_query()				
			else:
				self._activate_source(detail)
				self._confirm_device_query()

		else:
			warn = True
			activity_name = f'Unknown Activity:{hex(activity)}'


		message = f'{activity_name}'

		if detail != 0x0:
			message = message + f', {detail}:{self._get_source_name(detail)}'

		if log:

			# This condition is complex for a couple of reasons
			# Sometime a normal message needs displaying even if there is a Fault in the system, in this case the triangle is solid
			# Also for some status' they can be alarms or normal, e.g. testing a system in maint mode isn't an alert
			if not warn or (warn and self.alert.value == "OK"):		

				# build the "non alert" message text out of the state and the activity text
				# if they are different, concatenate them so we don't lose any info
				# note that this is more verbose that the real Jablotron keypad messages and we may remove at some point
				if activity_name == state_text:
					state_text = message
				else:
					if state_text != '' and message != '':
						state_text = state_text + ", " + message 
					elif message != '':
						state_text = message

				if warn:
					LOGGER.warning(message)

			# log the message as an alert/alarm since the warning triangle is lit
			else:
				if message != self.alert.message and message != '':
					LOGGER.warning(message)
					self.alert.message = message

			if state_text != self.statustext.message:
				self.statustext.message = state_text

		else:
			LOGGER.debug('message: ' + message)

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
			# crc = data[4]
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
				if device_id >=1 and device_id <= self._max_number_of_wired_devices:
					device.model = "wired"
				elif not data[5:7] == b'\x0f\x0f':
					serial_hex_string = "".join(
						map(lambda x: hex(x)[2:], data[5:11]))
					serial_int_string = int(serial_hex_string, 16)
					device.serial_number = f'{serial_int_string:08d}'
					if data[5:7] == b'\x04\x08':
						device.model = 'JA-81F' # wireless keypad

					if data[5:7] == b'\x07\x0e':
						device.model = 'JA-80W' # motion

					if data[5:7] == b'\x06\x0e':
						device.model = 'JA-86P' # dual band motion

					if data[5:7] == b'\x05\x00':
						device.model = 'JA-80A' # external siren
						
					if data[5:7] == b'\x08\x01' \
						or data[5:7] == b'\x08\x03' \
						or data[5:7] == b'\x09\x01' \
						or data[5:7] == b'\x09\x03':
						device.model = 'RC-86' # fob

					if data[5:7] == b'\x05\x04':
						device.model = 'JA-84P' # pir camera

					if data[5:7] == b'\x01\x01':
						device.model = 'JA-80S' # smoke

					if data[5:7] == b'\x01\x04':
						device.model = 'JA-82M' # magnetic contact

					if data[5:7] == b'\x05\x08' \
						or data[5:7] == b'\x05\x09':
						device.model = 'JA-80L' # wireless intenal siren

					device.manufacturer = MANUFACTURER
				else:
					device.model = None
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
				device.zone = self.get_zone(data[6])
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
				# crc = data[5]
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
		elif detail == 0x05:
			# battery flat on backup battery
			pass
		elif detail == 0x08:
			# comes at least when trying to enter service mode while already in service mode
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

		else:
			LOGGER.error(f'Unknown state detail received data={packet_data}')

	def _process_message(self, data: bytearray) -> None:
		packet_data = format_packet(data)
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

	def send_return_mode_command(self) -> None:
		#if self.system_status in self.STATUS_ELEVATED:
		self._connection.add_command(JablotronCommand(name="Esc / back",
			code=b'\x8e', accepted_prefix=b'\xa1\xff'))

	async def send_settings_command(self) -> None:
		#if self.system_status in self.STATUS_ELEVATED:
		command = JablotronCommand(name="Get settings",
				code=b'\x8a', accepted_prefix=b'\xa1\xff', complete_prefix=b'\xe6\x04', max_records=300)
		self._connection.add_command(command)
		return await command.wait_for_confirmation()

	def send_detail_command(self) -> None:
		self._connection.add_command(JablotronCommand(name="Details",
			code=b'\x8e', accepted_prefix=b'\xa4\xff'))

	def enter_elevated_mode(self, code: str) -> bool:
		# mode service/maintenance depends on pin send after this
		if JablotronState.is_elevated_state(self._last_state):
			# do nothing already on elevated mode
			pass
		elif JablotronState.is_disarmed_state(self._last_state):
			self.send_keypress_sequence("*0" + code, b'\xa1', b'\xb8\xff')
		elif self._last_state == JablotronState.BYPASS:
			self.send_return_mode_command()
		elif self._last_state == None:
			LOGGER.warning(f'Trying to enter elevated mode but not reliable status yet')
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
			LOGGER.warning(f'Trying to enter normal mode but state is {self.last_state}')

	async def read_settings(self) -> bool:
		if self.enter_elevated_mode(self._master_code):
			result = await self.send_settings_command()
			self.send_return_mode_command()
			return result
		return False

	def send_keypress_sequence(self, key_sequence: str, accepted_prefix: bytes, complete_prefix: bytes = None) -> None:

		value = b''

		if JablotronSettings.HIDE_KEY_PRESS:
			name = "*HIDDEN*"
		else:
			name = str
		
		for i in range(0, len(key_sequence)):
			cmd = key_sequence[i] 
			value = value + JablotronKeyPress.get_key_command(cmd)

		self._connection.add_command(
			JablotronCommand(name=f'key sequence {name}',code=value, accepted_prefix=accepted_prefix + b'\xff', complete_prefix=complete_prefix))
			
	def shutdown(self) -> None:
		self._connection.shutdown()
		self._stop.set()


	def arm(self,code: str,zone:str=None) -> None:
		if zone is None:
			self.send_keypress_sequence(code, b'\xa1')
		else:
			self.send_keypress_sequence({"A":"*2","B":"*3","C":"*1"}[zone]+code, b'\xa1')
	
	def disarm(self,code:str,zone:str=None) -> None:
		self.send_keypress_sequence(code, b'\xa2')
		if JablotronState.is_alarm_state(self._last_state):
			#confirm alarm
			self.send_detail_command
		
	async def processing_loop(self) -> None:
		previous_record = None
		while not self._stop.is_set():
			await self._connection._messages.wait()
			try:
				while (records := self._connection.get_record()) != []: 
					self._connection._log_detail(f'Received {len(records)} records')
					for record in records:
						if record != previous_record:
							previous_record = record
							self._process_message(record)
							await asyncio.sleep(0) # sleep on every message processed to not block event loop
				
				self._connection._messages.clear() # once all messages are processed, clear flag
				
			except Exception:
				LOGGER.exception(f'Unexpected error processing record: {record}')
			
	# this is just for console testing
	async def status_loop(self) -> None:
		await asyncio.sleep(60)
		while not self._stop.is_set():
			LOGGER.info(f'{self}')
			await asyncio.sleep(60)
			#self.send_key_press(self._master_code, b'\xa1')

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
  

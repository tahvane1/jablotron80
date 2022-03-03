from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.button import ButtonEntity
from .jablotron import JA80CentralUnit, JablotronButton
from .jablotronHA import JablotronEntity
from typing import Optional
from .const import (
	DATA_JABLOTRON,
	DOMAIN)


import logging
LOGGER = logging.getLogger(__package__)
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
	cu = hass.data[DOMAIN][config_entry.entry_id][DATA_JABLOTRON] # type: JA80CentralUnit
	async_add_entities([JablotronQueryButtonEntity(cu.query,cu)], True)

class JablotronQueryButtonEntity(JablotronEntity, ButtonEntity):

	def __init__(self, button: JablotronButton,cu: JA80CentralUnit) -> None:
		super().__init__(cu, button) 
		
	async def async_press(self) -> None:

		self._cu._send_device_query()
		"""Handle the button press."""

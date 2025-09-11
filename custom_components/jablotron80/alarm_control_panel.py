from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
    ATTR_CHANGED_BY,
    ATTR_CODE_ARM_REQUIRED,
    AlarmControlPanelState,
)

from homeassistant.const import (
    ATTR_CODE,
    ATTR_CODE_FORMAT,
)
from .const import (
    CONFIGURATION_REQUIRE_CODE_TO_ARM,
    CONFIGURATION_REQUIRE_CODE_TO_DISARM,
)

from typing import Any, Dict, List, Optional
from .const import DATA_JABLOTRON, DOMAIN, NAME, MANUFACTURER
from .jablotron import JA80CentralUnit, JablotronDevice, JablotronZone
from .jablotronHA import JablotronEntity


import logging

LOGGER = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
    cu = hass.data[DOMAIN][config_entry.entry_id][DATA_JABLOTRON]
    # how to handle split system?
    if cu.mode != JA80CentralUnit.SYSTEM_MODE_SPLIT:
        async_add_entities([Jablotron80AlarmControl(cu, cu.zones)], True)
    else:
        async_add_entities([Jablotron80AlarmControl(cu, cu.zones, 0)], True)
        async_add_entities([Jablotron80AlarmControl(cu, cu.zones, 1)], True)


def check_zone_status(zone: JablotronZone, status: str) -> bool:
    if zone is not None and zone.status == status:
        return True
    return False


class Jablotron80AlarmControl(JablotronEntity, AlarmControlPanelEntity):

    def __init__(self, cu: JA80CentralUnit, zones: List[JablotronZone], main_zone: int = 0) -> None:
        self._object = zones[main_zone]
        self._main_zone = main_zone
        self._cu = cu
        self._zones = zones
        self._changed_by = "ME"

    @property
    def code_format(self) -> Optional[str]:
        if self.alarm_state == AlarmControlPanelState.DISARMED:
            code_required = self.code_arm_required
        else:
            code_required = self.code_disarm_required
        return CodeFormat.NUMBER if code_required is True else None

    @staticmethod
    def _check_code(code: Optional[str]) -> Optional[str]:
        return None if code == "" else code

    @property
    def supported_features(self) -> int:
        if self._cu.mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT:
            return AlarmControlPanelEntityFeature.ARM_AWAY | AlarmControlPanelEntityFeature.TRIGGER
        elif self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL:
            return (
                AlarmControlPanelEntityFeature.ARM_AWAY
                | AlarmControlPanelEntityFeature.ARM_HOME
                | AlarmControlPanelEntityFeature.ARM_NIGHT
                | AlarmControlPanelEntityFeature.TRIGGER
            )
        elif self._cu.mode == JA80CentralUnit.SYSTEM_MODE_SPLIT:
            return (
                AlarmControlPanelEntityFeature.ARM_AWAY
                | AlarmControlPanelEntityFeature.ARM_HOME
                | AlarmControlPanelEntityFeature.TRIGGER
            )
        return AlarmControlPanelEntityFeature.ARM_AWAY | AlarmControlPanelEntityFeature.TRIGGER

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
        if not self.code_disarm_required:
            code = self._cu._master_code
        if code == None:
            return
        if self._cu.mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT:
            # just one zone so input code without any "kinks"
            # todo check if you can get disarming from serial line
            self._zones[0].status = JablotronZone.STATUS_DISARMING
            await self._cu.disarm(code)
        else:
            await self._cu.disarm(code)

    async def async_alarm_arm_home(self, code=None) -> None:
        if not self._cu.is_code_required_for_arm():
            code = ""
        elif not self.code_arm_required:
            code = self._cu._master_code
        if code == None:
            return
        if self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL:
            await self._cu.arm(code, "A")
        elif self._cu.mode == JA80CentralUnit.SYSTEM_MODE_SPLIT:
            if self._main_zone == 0:
                await self._cu.arm(code, "A")
            else:
                await self._cu.arm(code, "B")

    async def async_alarm_arm_away(self, code=None) -> None:
        if not self._cu.is_code_required_for_arm():
            code = ""
        elif not self.code_arm_required:
            code = self._cu._master_code
        if code == None:
            return
        if self._cu.mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT:
            # if we have received a code use it to arm the system
            if len(code) > 0:
                await self._cu.arm(code)
            #  otherwise simulate an ABC key press (zone C means all zones)
            else:
                await self._cu.arm(code, "C")
        elif self._cu.mode in [
            JA80CentralUnit.SYSTEM_MODE_PARTIAL,
            JA80CentralUnit.SYSTEM_MODE_SPLIT,
        ]:
            await self._cu.arm(code, "C")

    async def async_alarm_arm_night(self, code=None) -> None:
        if not self._cu.is_code_required_for_arm():
            code = ""
        elif not self.code_arm_required:
            code = self._cu._master_code
        if code == None:
            return
        if self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL:
            await self._cu.arm(code, "B")

    async def async_alarm_trigger(self, code=None) -> None:
        if self.alarm_state == AlarmControlPanelState.DISARMED:
            self._cu.send_keypress_sequence("*7" + self._cu._master_code, b"\xa1")
        else:
            self._cu.send_keypress_sequence("*7" + self._cu._master_code, b"\xa2")

    async def async_alarm_arm_custom_bypass(self, code=None) -> None:
        raise NotImplementedError()

    def get_active_zone(self) -> JablotronZone:
        if self._cu.mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT and len(self._zones) == 1:
            return self._zones[0]
        elif self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL and len(self._zones) == 3:
            zone_home = self._zones[0]
            zone_night = self._zones[1]
            zone_away = self._zones[2]
            for zone in [zone for zone in self._zones if check_zone_status(zone, JablotronZone.STATUS_ALARM)]:
                return zone
            for zone in [
                zone for zone in self._zones if check_zone_status(zone, JablotronZone.STATUS_ENTRY_DELAY)
            ]:
                return zone
            if check_zone_status(zone_away, JablotronZone.STATUS_ARMED):
                return zone_away
            elif check_zone_status(zone_night, JablotronZone.STATUS_ARMED):
                return zone_night
            elif check_zone_status(zone_home, JablotronZone.STATUS_ARMED):
                return zone_home
            for zone in [
                zone for zone in self._zones if check_zone_status(zone, JablotronZone.STATUS_ARMING)
            ]:
                return zone
            for zone in [
                zone for zone in self._zones if check_zone_status(zone, JablotronZone.STATUS_DISARMED)
            ]:
                return zone
        elif self._cu.mode == JA80CentralUnit.SYSTEM_MODE_SPLIT and len(self._zones) == 3:
            zone_home = self._zones[self._main_zone]
            zone_away = self._zones[2]
            for zone in [
                zone for zone in [zone_home, zone_away] if check_zone_status(zone, JablotronZone.STATUS_ALARM)
            ]:
                return zone
            for zone in [
                zone
                for zone in [zone_home, zone_away]
                if check_zone_status(zone, JablotronZone.STATUS_ENTRY_DELAY)
            ]:
                return zone
            if check_zone_status(zone_away, JablotronZone.STATUS_ARMED):
                return zone_away
            elif check_zone_status(zone_home, JablotronZone.STATUS_ARMED):
                return zone_home
            for zone in [
                zone
                for zone in [zone_home, zone_away]
                if check_zone_status(zone, JablotronZone.STATUS_ARMING)
            ]:
                return zone
            for zone in [
                zone
                for zone in [zone_home, zone_away]
                if check_zone_status(zone, JablotronZone.STATUS_DISARMED)
            ]:
                return zone
        return self._zones[0]

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        zone = self.get_active_zone()
        if zone.status == JablotronZone.STATUS_ENTRY_DELAY:
            return AlarmControlPanelState.PENDING
        elif zone.status == JablotronZone.STATUS_ARMING:
            return AlarmControlPanelState.ARMING
        elif zone.status == JablotronZone.STATUS_ALARM:
            return AlarmControlPanelState.TRIGGERED

        elif (
            zone.status == JablotronZone.STATUS_ARMED and self._cu.mode == JA80CentralUnit.SYSTEM_MODE_UNSPLIT
        ):
            return AlarmControlPanelState.ARMED_AWAY

        elif (
            zone.status == JablotronZone.STATUS_ARMED
            and self._cu.mode == JA80CentralUnit.SYSTEM_MODE_SPLIT
            and zone != self._object
        ):
            return AlarmControlPanelState.ARMED_AWAY
        elif (
            zone.status == JablotronZone.STATUS_ARMED
            and self._cu.mode == JA80CentralUnit.SYSTEM_MODE_SPLIT
            and zone == self._object
        ):
            return AlarmControlPanelState.ARMED_HOME

        elif (
            zone.status == JablotronZone.STATUS_ARMED
            and self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL
            and zone._id == 1
        ):
            return AlarmControlPanelState.ARMED_HOME
        elif (
            zone.status == JablotronZone.STATUS_ARMED
            and self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL
            and zone._id == 2
        ):
            return AlarmControlPanelState.ARMED_NIGHT
        elif (
            zone.status == JablotronZone.STATUS_ARMED
            and self._cu.mode == JA80CentralUnit.SYSTEM_MODE_PARTIAL
            and zone._id == 3
        ):

            return AlarmControlPanelState.ARMED_AWAY
        elif zone.status == JablotronZone.STATUS_DISARMED:
            return AlarmControlPanelState.DISARMED
        elif zone.status == JablotronZone.STATUS_DISARMING:
            return AlarmControlPanelState.DISARMING

        return AlarmControlPanelState.UNKOWN

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        # return self._cu.led_power
        # when running on battery power the led in off (well flashing) and the sytem is still working see issue#85
        # we should enhance this to be based on the data flowing on the serial line
        return True

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        info = {
            "identifiers": {(DOMAIN, f"jablotron_panel_{self._main_zone}")},
            "name": "jablotron panel",
            "via_device": (DOMAIN, self._cu.serial_port),
        }
        info["model"] = "Home Assistant control panel"
        info["manufacturer"] = "Jablotron"
        return info

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        attr = super().extra_state_attributes
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

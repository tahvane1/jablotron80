import time
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType
from typing import Any, Dict, List, Optional, Union
from .const import (
    DATA_JABLOTRON,
    DOMAIN,
    NAME,
    MANUFACTURER,
    CENTRAL_UNIT_MODEL,
    DEVICES,
)
from .jablotron import JA80CentralUnit, JablotronDevice, JablotronZone, JablotronCommon, JablotronCode
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
        # return self._cu.led_power

        # #97: an entity is available only while the central unit's connection
        # is alive AND the underlying object reports itself available.
        return self._cu.connection_alive and (
            self._object.available if hasattr(self._object, "available") else True
        )

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        if self._object is None:
            return {
                "identifiers": {(DOMAIN, self._cu.serial_port)},
            }
        name = CENTRAL_UNIT_MODEL
        if self._object.device_id > 0:
            name = self._object.name
        info = {
            "identifiers": {(DOMAIN, self._object.device_id)},
            "name": name,
            "via_device": (DOMAIN, self._cu.serial_port),
        }
        if hasattr(self._object, "model") and not self._object.model is None:
            info["model"] = self._object.model
        if hasattr(self._object, "manufacturer") and not self._object.manufacturer is None:
            info["manufacturer"] = self._object.manufacturer
        return info

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        attr = {}
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
        if not self._object is None and hasattr(self._object, "by"):
            attr["by"] = self._object.formatted_by
        for field in [
            "serial_number",
            "model",
            "manufacturer",
            "id",
            "type",
            "battery_low",
            "tampered",
            "message",
            "last_event",
        ]:
            if not self._object is None and hasattr(self._object, field):
                value = getattr(self._object, field)
                if not value is None:
                    attr[field.replace("_", " ")] = getattr(self._object, field)
        # #153 follow-up: surface when the panel last reported this detector as
        # active, so the staleness behaviour is observable.
        if isinstance(self._object, JablotronDevice):
            device_id = self._object.device_id
            # `last_reported_active` is a stable wall-clock timestamp ("last active
            # at ..."); it stays visible even once the detector closes.
            last_wall = self._cu._device_last_active_wall.get(device_id)
            if last_wall is not None:
                attr["last_reported_active"] = last_wall
            # `seconds_since_reported` is a liveness metric: it only makes sense
            # while the detector is active (it climbs until the sweep clears a
            # stuck detector). On a closed detector it would freeze at a stale
            # value, so we omit it entirely when inactive.
            last_mono = self._cu._device_last_active.get(device_id)
            if last_mono is not None and self._object.active:
                attr["seconds_since_reported"] = round(time.monotonic() - last_mono)
        # #83: surface when a code was last used (arm/disarm) as a non-breaking
        # `last_used` attribute on the code entities, alongside the existing
        # active/inactive state.
        if isinstance(self._object, JablotronCode):
            last_used = self._cu._code_last_used_wall.get(self._object._id)
            if last_used is not None:
                attr["last_used"] = last_used
        return attr

    @property
    def name(self) -> str:
        return self._object.name

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}.{self._cu.serial_port}.{self._object.id_part}.{self._object._id}"

    async def async_added_to_hass(self) -> None:
        # state = await self.async_get_last_state()
        self._object.register_callback(self.async_write_ha_state)
        # if not state:
        # 	return
        # self._state = state

        # override internal configured name is it's been setup in the UI
        if self.registry_entry.name is not None:
            self._object.name = self.registry_entry.name

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._object.remove_callback(self.async_write_ha_state)

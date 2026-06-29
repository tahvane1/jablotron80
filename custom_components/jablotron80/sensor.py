from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import Entity
from .jablotron import (
    JA80CentralUnit,
    JablotronDevice,
    JablotronConstants,
    JablotronZone,
    JablotronSensor,
)
from .jablotronHA import JablotronEntity
from typing import Optional
from .const import DATA_JABLOTRON, DOMAIN

from homeassistant.components.sensor import SensorDeviceClass

import logging
import datetime

LOGGER = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities) -> None:
    cu = hass.data[DOMAIN][config_entry.entry_id][DATA_JABLOTRON]  # type: JA80CentralUnit
    async_add_entities([JablotronZoneSensorEntity(zone, cu) for zone in cu.zones], True)
    async_add_entities([JablotronSignalEntity(cu.rf_level, cu)], True)
    async_add_entities([JablotronSensorEntity(cu.alert, cu)], True)
    # #151 read-only: the panel's own clock + its drift vs HA time (event-driven).
    async_add_entities([JablotronPanelClockEntity(cu.panel_time, cu)], True)
    async_add_entities([JablotronPanelDriftEntity(cu.panel_time_drift, cu)], True)


class JablotronZoneSensorEntity(JablotronEntity):
    def __init__(self, zone: JablotronZone, cu: JA80CentralUnit) -> None:
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
    def __init__(self, sensor: JablotronSensor, cu: JA80CentralUnit) -> None:
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
    def __init__(self, sensor: JablotronSensor, cu: JA80CentralUnit) -> None:
        super().__init__(sensor, cu)

    @property
    def unit_of_measurement(self) -> str:
        return "%"

    @property
    def device_class(self) -> str:
        return SensorDeviceClass.SIGNAL_STRENGTH


class JablotronPanelClockEntity(JablotronSensorEntity):
    # #151 read-only: the panel's own clock, shown as a literal HH:MM time. None until
    # the first event provides a reading; minute resolution, year assumed by the
    # integration. Deliberately NOT a TIMESTAMP device_class: HA renders timestamp
    # sensors relative to now ("a minute ago"), which for a clock just ages
    # confusingly. The companion drift sensor carries the numeric offset vs HA time.
    @property
    def state(self):
        value = self._object.value
        return value.strftime("%H:%M") if isinstance(value, datetime.datetime) else None

    @property
    def entity_category(self) -> Optional[EntityCategory]:
        # The panel clock is diagnostic context for the drift, not a primary sensor.
        return EntityCategory.DIAGNOSTIC


class JablotronPanelDriftEntity(JablotronSensorEntity):
    # #151 read-only: drift of the panel clock vs HA time at the last event, in
    # whole seconds (signed: positive = panel ahead). Plain numeric, no device
    # class - a drift can be negative, unlike a duration.
    @property
    def unit_of_measurement(self) -> str:
        return "s"

    @property
    def entity_category(self) -> Optional[EntityCategory]:
        return EntityCategory.DIAGNOSTIC

"""Tests for the staleness diagnostic attributes on detector entities.

The staleness sweep (issue #153 follow-up) records, per device, both a
monotonic timestamp (drives the sweep) and a wall-clock timestamp. The entity
layer surfaces these so the behaviour is observable in Home Assistant:

* ``last_reported_active``   - wall-clock time the panel last reported the
  detector as active.
* ``seconds_since_reported`` - the age of that report in whole seconds; it
  climbs until the panel re-reports the detector or the sweep clears it.

These attributes only make sense for real detector devices, so they are added
only when the backing object is a ``JablotronDevice`` and a record exists.
"""

import datetime

import custom_components.jablotron80.jablotron as jablotron
from custom_components.jablotron80.jablotronHA import JablotronEntity
from custom_components.jablotron80.const import (
    CABLE_MODEL,
    CABLE_MODEL_JA82T,
    CONFIGURATION_PASSWORD,
    CONFIGURATION_SERIAL_PORT,
)

# A device id < 0x40 resolves to a JablotronDevice (>= 0x40 would be a code).
DEVICE_ID = 6


def _build_unit():
    config = {
        CABLE_MODEL: CABLE_MODEL_JA82T,
        CONFIGURATION_SERIAL_PORT: "/dev/null",
        CONFIGURATION_PASSWORD: "1234",
    }
    return jablotron.JA80CentralUnit(hass=None, config=config, options=None)


def test_device_entity_exposes_timestamp_attributes(event_loop_for_setters):
    """An active detector exposes both staleness attributes with sane values."""
    unit = _build_unit()
    unit._activate_source(DEVICE_ID)
    device = unit.get_device(DEVICE_ID)

    entity = JablotronEntity(unit, device)
    attr = entity.extra_state_attributes

    # Age attribute: present, a whole-second non-negative int.
    assert "seconds_since_reported" in attr
    assert isinstance(attr["seconds_since_reported"], int)
    assert attr["seconds_since_reported"] >= 0

    # Wall-clock attribute: present, tz-aware, and exactly the recorded value.
    assert "last_reported_active" in attr
    wall = attr["last_reported_active"]
    assert isinstance(wall, datetime.datetime)
    assert wall.tzinfo is not None
    assert wall == unit._device_last_active_wall[DEVICE_ID]


def test_device_without_record_omits_timestamp_attributes(event_loop_for_setters):
    """With no recorded timestamp, neither staleness attribute is emitted.

    The detector object still exists in the registry, but its entries in the
    last-active dicts are gone (mirrors a device that has never been reported
    active in this session). The ``.get()`` guards must then add nothing.
    """
    unit = _build_unit()
    unit._activate_source(DEVICE_ID)
    device = unit.get_device(DEVICE_ID)

    # Drop both records so the .get() lookups return None.
    unit._device_last_active.pop(DEVICE_ID, None)
    unit._device_last_active_wall.pop(DEVICE_ID, None)

    attr = JablotronEntity(unit, device).extra_state_attributes

    assert "seconds_since_reported" not in attr
    assert "last_reported_active" not in attr


def test_closed_detector_keeps_timestamp_hides_age(event_loop_for_setters):
    """A closed (inactive) detector keeps last_reported_active but drops the age.

    `seconds_since_reported` is a liveness metric. Once the detector closes it
    would otherwise freeze at a stale value, so it is omitted while inactive;
    the stable `last_reported_active` timestamp remains visible.
    """
    unit = _build_unit()
    unit._activate_source(DEVICE_ID)
    device = unit.get_device(DEVICE_ID)

    # Simulate the close: the detector goes inactive, timestamps are retained.
    device.active = False

    attr = JablotronEntity(unit, device).extra_state_attributes

    assert "last_reported_active" in attr
    assert "seconds_since_reported" not in attr

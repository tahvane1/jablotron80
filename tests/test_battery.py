"""Tests for the battery binary_sensor (issue #45).

Background
----------
Each detector's low-battery state was previously surfaced only as an
``extra_state_attributes`` field. Issue #45 exposes it as a dedicated
``binary_sensor`` with ``device_class = BATTERY`` so it shows up as a first-class
entity and triggers Home Assistant's battery-low UI.

Stub note
---------
``binary_sensor.py`` imports ``BinarySensorEntity`` and ``BinarySensorDeviceClass``
from ``homeassistant.components.binary_sensor``. The shared conftest stubs that
module with only a ``DOMAIN`` attribute, so importing the production module fails
out of the box. We therefore enrich that stub here - BEFORE importing
``binary_sensor`` - with the two symbols the module needs:

* ``BinarySensorEntity`` - a bare base class (mirrors the entity stubs already in
  conftest).
* ``BinarySensorDeviceClass`` - a tiny stand-in exposing the members the
  production code references; ``BATTERY`` is the one under test.

This lets us import the real ``JablotronBatteryBinarySensor`` and assert against
its real ``device_class`` / ``is_on`` logic without pulling in Home Assistant.
"""

import sys
import types

# conftest stubs ``jablotron.py``'s imports but NOT the extra Home Assistant
# helper modules that ``jablotronHA.py`` (pulled in by ``binary_sensor.py``)
# imports at module load. Provide just those symbols here, before importing.


def _ensure_module(name: str) -> types.ModuleType:
    mod = sys.modules.get(name)
    if mod is None:
        mod = types.ModuleType(name)
        sys.modules[name] = mod
    return mod


# homeassistant.helpers.entity.Entity
_entity = _ensure_module("homeassistant.helpers.entity")
if not hasattr(_entity, "Entity"):

    class Entity:  # noqa: D401 - dummy stand-in
        """Minimal stand-in for homeassistant.helpers.entity.Entity."""

    _entity.Entity = Entity

# homeassistant.helpers.typing.StateType
_typing = _ensure_module("homeassistant.helpers.typing")
if not hasattr(_typing, "StateType"):
    _typing.StateType = object

# homeassistant.helpers.restore_state.RestoreEntity
_restore = _ensure_module("homeassistant.helpers.restore_state")
if not hasattr(_restore, "RestoreEntity"):

    class RestoreEntity:  # noqa: D401 - dummy stand-in
        """Minimal stand-in for RestoreEntity."""

    _restore.RestoreEntity = RestoreEntity

# homeassistant.helpers.dispatcher.async_dispatcher_connect
_dispatcher = _ensure_module("homeassistant.helpers.dispatcher")
if not hasattr(_dispatcher, "async_dispatcher_connect"):
    _dispatcher.async_dispatcher_connect = lambda *a, **k: None

# Enrich the binary_sensor component stub before importing the module.
_bs_stub = sys.modules["homeassistant.components.binary_sensor"]

if not hasattr(_bs_stub, "BinarySensorEntity"):

    class BinarySensorEntity:  # noqa: D401 - dummy stand-in
        """Minimal stand-in for homeassistant ...BinarySensorEntity."""

    _bs_stub.BinarySensorEntity = BinarySensorEntity

if not hasattr(_bs_stub, "BinarySensorDeviceClass"):

    class BinarySensorDeviceClass:
        """Stand-in exposing the device-class members the integration uses.

        Values mirror Home Assistant's real ``BinarySensorDeviceClass`` enum
        string values so any assertion on the underlying value also holds.
        """

        BATTERY = "battery"
        SAFETY = "safety"
        SMOKE = "smoke"
        MOTION = "motion"
        PROBLEM = "problem"
        POWER = "power"
        LIGHT = "light"
        WINDOW = "window"
        DOOR = "door"
        MOISTURE = "moisture"
        GAS = "gas"

    _bs_stub.BinarySensorDeviceClass = BinarySensorDeviceClass


import custom_components.jablotron80.jablotron as jablotron  # noqa: E402
from custom_components.jablotron80 import binary_sensor as bs  # noqa: E402
from custom_components.jablotron80.binary_sensor import (  # noqa: E402
    JablotronBatteryBinarySensor,
)


# ---------------------------------------------------------------------------
# JablotronDevice.battery_low round-trips
# ---------------------------------------------------------------------------
def test_device_battery_low_defaults_false(event_loop_for_setters):
    """A fresh device reports a non-low battery."""
    dev = jablotron.JablotronDevice(7)
    assert dev.battery_low is False


def test_device_battery_low_round_trips(event_loop_for_setters):
    """Setting battery_low is reflected by the getter (setter runs through the
    @log_change decorator, hence the event-loop fixture)."""
    dev = jablotron.JablotronDevice(7)
    dev.battery_low = True
    assert dev.battery_low is True
    dev.battery_low = False
    assert dev.battery_low is False


# ---------------------------------------------------------------------------
# JablotronBatteryBinarySensor.device_class resolves to BATTERY
# ---------------------------------------------------------------------------
def test_battery_sensor_device_class_off_the_class():
    """The new sensor's device_class is the BATTERY device class.

    Asserting off the property descriptor avoids needing a fully wired HA
    entity. ``fget(None)`` would touch no instance state, but ``device_class``
    here ignores ``self`` entirely, so we can read the constant it returns.
    """
    # device_class is a property whose getter returns the constant unconditionally.
    resolved = JablotronBatteryBinarySensor.device_class.fget(object())
    assert resolved == bs.BinarySensorDeviceClass.BATTERY
    assert resolved == "battery"


def test_battery_sensor_is_on_reads_battery_low(event_loop_for_setters):
    """An instantiated battery sensor's ``is_on`` follows the device's
    ``battery_low`` flag.

    ``JablotronEntity.__init__`` only stores ``cu`` and ``object`` - no HA
    machinery - so the sensor can be instantiated directly with a real device
    and a ``None`` central unit (is_on never touches the cu).
    """
    dev = jablotron.JablotronDevice(7)
    sensor = JablotronBatteryBinarySensor(dev, None)

    assert sensor.is_on is False
    dev.battery_low = True
    assert sensor.is_on is True
    # device_class on the live instance also resolves to BATTERY.
    assert sensor.device_class == bs.BinarySensorDeviceClass.BATTERY

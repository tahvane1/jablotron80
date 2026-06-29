"""Tests for the per-code "last used" timestamp (issue #83).

Each code records a wall-clock timestamp whenever it is used (arm/disarm), and
the code entities surface it as a non-breaking ``last_used`` attribute alongside
the existing active/inactive state. This mirrors the detector
``last_reported_active`` pattern.

Stub note: like ``tests/test_battery.py``, importing ``jablotronHA`` pulls in
extra Home Assistant helper modules that the shared conftest does not stub, so
we provide the few needed symbols locally before importing ``JablotronEntity``.
"""

import datetime
import sys
import types

import custom_components.jablotron80.jablotron as jablotron
from custom_components.jablotron80.jablotron import JablotronCode
from custom_components.jablotron80.const import (
    CABLE_MODEL,
    CABLE_MODEL_JA82T,
    CONFIGURATION_PASSWORD,
    CONFIGURATION_SERIAL_PORT,
)


def _ensure_module(name: str) -> types.ModuleType:
    mod = sys.modules.get(name)
    if mod is None:
        mod = types.ModuleType(name)
        sys.modules[name] = mod
    return mod


_entity = _ensure_module("homeassistant.helpers.entity")
if not hasattr(_entity, "Entity"):

    class Entity:  # noqa: D401 - dummy stand-in
        """Minimal Entity stand-in."""

    _entity.Entity = Entity

_typing = _ensure_module("homeassistant.helpers.typing")
if not hasattr(_typing, "StateType"):
    _typing.StateType = object

_restore = _ensure_module("homeassistant.helpers.restore_state")
if not hasattr(_restore, "RestoreEntity"):

    class RestoreEntity:  # noqa: D401 - dummy stand-in
        """Minimal RestoreEntity stand-in."""

    _restore.RestoreEntity = RestoreEntity

_dispatcher = _ensure_module("homeassistant.helpers.dispatcher")
if not hasattr(_dispatcher, "async_dispatcher_connect"):
    _dispatcher.async_dispatcher_connect = lambda *a, **k: None

from custom_components.jablotron80.jablotronHA import JablotronEntity  # noqa: E402

# Internal code id 1 (panel source 0x41): a user code, not the admin code (id 0).
CODE_ID = 1


def _build_unit():
    config = {
        CABLE_MODEL: CABLE_MODEL_JA82T,
        CONFIGURATION_SERIAL_PORT: "/dev/null",
        CONFIGURATION_PASSWORD: "1234",
    }
    return jablotron.JA80CentralUnit(hass=None, config=config, options=None)


def test_activate_code_records_last_used(event_loop_for_setters):
    """Using a code records a recent tz-aware wall-clock timestamp."""
    unit = _build_unit()
    code = unit.get_code(CODE_ID)
    assert isinstance(code, JablotronCode)

    before = datetime.datetime.now(datetime.timezone.utc)
    unit._activate_code_object(code)
    after = datetime.datetime.now(datetime.timezone.utc)

    assert code.active is True
    assert CODE_ID in unit._code_last_used_wall
    ts = unit._code_last_used_wall[CODE_ID]
    assert isinstance(ts, datetime.datetime)
    assert ts.tzinfo is not None
    assert before <= ts <= after


def test_code_entity_exposes_last_used(event_loop_for_setters):
    """A used code exposes the last_used attribute equal to the recorded time."""
    unit = _build_unit()
    code = unit.get_code(CODE_ID)
    unit._activate_code_object(code)

    attr = JablotronEntity(unit, code).extra_state_attributes
    assert "last_used" in attr
    assert attr["last_used"] == unit._code_last_used_wall[CODE_ID]


def test_unused_code_has_no_last_used(event_loop_for_setters):
    """A code that has never been used exposes no last_used attribute."""
    unit = _build_unit()
    code = unit.get_code(CODE_ID)  # created but never activated

    attr = JablotronEntity(unit, code).extra_state_attributes
    assert "last_used" not in attr


def test_code_use_fires_logbook_event(event_loop_for_setters):
    """Using a code fires a single jablotron_code_used event for the logbook.

    The event carries the code name and unique_id (logbook.py resolves the latter
    to the code entity). It fires only on the off->on transition, so one entry
    per use - a second activation while still active fires nothing more.
    """
    fired = []

    class _Bus:
        def async_fire(self, event_type, data):
            fired.append((event_type, data))

    unit = _build_unit()
    unit._hass = type("_Hass", (), {"bus": _Bus()})()

    code = unit.get_code(CODE_ID)
    unit._activate_code_object(code)

    assert len(fired) == 1
    event_type, data = fired[0]
    assert event_type == jablotron.EVENT_CODE_USED
    assert data["code_id"] == CODE_ID
    assert data["name"] == code.name
    assert "unique_id" in data and str(CODE_ID) in data["unique_id"]
    # entity_id is carried so HA links the recorded event to the code entity.
    assert "entity_id" in data
    # generic activation (no action passed) -> renders as plain "was used"
    assert data.get("action") is None

    # Still active -> a second activation does not fire another entry.
    unit._activate_code_object(code)
    assert len(fired) == 1


def test_disarm_records_code_use_fires_event(event_loop_for_setters):
    """Disarm (the _record_code_use path) records the use and fires one event.

    The disarm handlers (0x09 Unsetting / 0x4E alarm cancelled) call
    _record_code_use directly - on disarm the code is never activated, so this is
    the only place the per-code logbook entry can originate. ``_record_code_use``
    takes the raw panel source byte (code id 1 = 0x41 = 65).
    """
    fired = []

    class _Bus:
        def async_fire(self, event_type, data):
            fired.append((event_type, data))

    unit = _build_unit()
    unit._hass = type("_Hass", (), {"bus": _Bus()})()

    code = unit.get_code(CODE_ID)
    before = datetime.datetime.now(datetime.timezone.utc)
    unit._record_code_use(CODE_ID + 64)  # raw source byte for code id 1
    after = datetime.datetime.now(datetime.timezone.utc)

    assert len(fired) == 1
    event_type, data = fired[0]
    assert event_type == jablotron.EVENT_CODE_USED
    assert data["code_id"] == CODE_ID
    assert data["name"] == code.name
    assert "unique_id" in data and str(CODE_ID) in data["unique_id"]
    # entity_id is carried so HA links the recorded event to the code entity.
    assert "entity_id" in data
    # disarm path labels the action so the logbook says "was used to disarm"
    assert data["action"] == "disarm"

    # the use is recorded for last_used; the code stays inactive (disarm clears it).
    assert CODE_ID in unit._code_last_used_wall
    ts = unit._code_last_used_wall[CODE_ID]
    assert before <= ts <= after
    assert code.active is False


def test_record_code_use_ignores_non_code(event_loop_for_setters):
    """A device source (id < 0x40) is not a code use - no event, no timestamp."""
    fired = []

    class _Bus:
        def async_fire(self, event_type, data):
            fired.append((event_type, data))

    unit = _build_unit()
    unit._hass = type("_Hass", (), {"bus": _Bus()})()

    unit._record_code_use(5)  # device id, not a code

    assert fired == []
    assert unit._code_last_used_wall == {}


def test_arm_action_labels_event(event_loop_for_setters):
    """The arm path passes action='arm' so the logbook can say 'was used to arm'.

    Mirror of the disarm test: arm routes through _activate_code(..., action='arm')
    -> _activate_code_object, which carries the action onto the fired event.
    """
    fired = []

    class _Bus:
        def async_fire(self, event_type, data):
            fired.append((event_type, data))

    unit = _build_unit()
    unit._hass = type("_Hass", (), {"bus": _Bus()})()

    code = unit.get_code(CODE_ID)
    unit._activate_code_object(code, action="arm")

    assert len(fired) == 1
    _, data = fired[0]
    assert data["action"] == "arm"

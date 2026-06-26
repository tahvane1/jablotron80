"""Test for issue #203: the alarm panel must not crash on an unmapped state.

``alarm_control_panel.py``'s ``alarm_state`` fell through to
``AlarmControlPanelState.UNKOWN`` - a typo: that enum member does not exist (and
Home Assistant's ``AlarmControlPanelState`` has no ``UNKNOWN`` either), so it
raised ``AttributeError`` whenever the panel reported a state the integration
does not map. The correct fall-through is ``None`` ("unknown" in HA).

This test reproduces the crash (red) and locks in the fix (green): for an
unmapped zone status, ``alarm_state`` must return ``None``, not raise.
"""

import sys
import types


def _ensure_module(name: str) -> types.ModuleType:
    mod = sys.modules.get(name)
    if mod is None:
        mod = types.ModuleType(name)
        sys.modules[name] = mod
    return mod


# -- HA helper stubs jablotronHA.py needs (mirrors tests/test_code_last_used.py).
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

# -- homeassistant.const extras that alarm_control_panel.py imports.
_const = _ensure_module("homeassistant.const")
for _attr in ("ATTR_CODE", "ATTR_CODE_FORMAT"):
    if not hasattr(_const, _attr):
        setattr(_const, _attr, _attr.lower())

# -- alarm_control_panel component stub. The crucial bit: AlarmControlPanelState
# mirrors HA - it has the members the code maps to, but deliberately NO `UNKOWN`,
# so the typo raises AttributeError exactly as it does on a real system.
_acp = _ensure_module("homeassistant.components.alarm_control_panel")
if not hasattr(_acp, "AlarmControlPanelEntity"):

    class AlarmControlPanelEntity:  # noqa: D401 - dummy stand-in
        """Minimal AlarmControlPanelEntity stand-in."""

    _acp.AlarmControlPanelEntity = AlarmControlPanelEntity
if not hasattr(_acp, "AlarmControlPanelEntityFeature"):

    class AlarmControlPanelEntityFeature:
        ARM_HOME = 1
        ARM_AWAY = 2
        ARM_NIGHT = 4
        TRIGGER = 8

    _acp.AlarmControlPanelEntityFeature = AlarmControlPanelEntityFeature
if not hasattr(_acp, "CodeFormat"):

    class CodeFormat:
        NUMBER = "number"
        TEXT = "text"

    _acp.CodeFormat = CodeFormat
if not hasattr(_acp, "ATTR_CHANGED_BY"):
    _acp.ATTR_CHANGED_BY = "changed_by"
if not hasattr(_acp, "ATTR_CODE_ARM_REQUIRED"):
    _acp.ATTR_CODE_ARM_REQUIRED = "code_arm_required"
if not hasattr(_acp, "AlarmControlPanelState"):

    class AlarmControlPanelState:
        # Real HA members the integration maps to - deliberately NO UNKOWN/UNKNOWN.
        DISARMED = "disarmed"
        ARMED_HOME = "armed_home"
        ARMED_AWAY = "armed_away"
        ARMED_NIGHT = "armed_night"
        PENDING = "pending"
        ARMING = "arming"
        DISARMING = "disarming"
        TRIGGERED = "triggered"

    _acp.AlarmControlPanelState = AlarmControlPanelState

from custom_components.jablotron80.alarm_control_panel import (  # noqa: E402
    Jablotron80AlarmControl,
)


def test_alarm_state_unmapped_status_returns_none():
    """For a zone status the integration does not map, alarm_state returns None.

    Reproduces #203: the previous fall-through ``AlarmControlPanelState.UNKOWN``
    raised AttributeError; the fix returns None ("unknown").
    """
    entity = Jablotron80AlarmControl.__new__(Jablotron80AlarmControl)
    # An unmapped zone status -> none of the elif branches match -> fall-through.
    unmapped_zone = types.SimpleNamespace(status="JablotronUnmappedStatus", _id=99)
    entity._cu = types.SimpleNamespace(mode="dummy-mode")
    entity._object = unmapped_zone
    entity._zones = [unmapped_zone]
    entity._main_zone = 0
    entity.get_active_zone = lambda: unmapped_zone

    assert entity.alarm_state is None

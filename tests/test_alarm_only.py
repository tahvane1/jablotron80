"""Verify quiet background operation without losing alarm state or commands."""

import pytest

from custom_components.jablotron80.const import (
    CABLE_MODEL,
    CABLE_MODEL_JA82T,
    CONFIGURATION_PASSWORD,
    CONFIGURATION_QUERY_DETECTOR_ACTIVITY,
    CONFIGURATION_SERIAL_PORT,
)
from custom_components.jablotron80.jablotron import (
    JA80CentralUnit,
    JablotronKeyPress,
    JablotronState,
    JablotronZone,
)


def make_unit(options):
    unit = JA80CentralUnit(None, {
        CABLE_MODEL: CABLE_MODEL_JA82T,
        CONFIGURATION_PASSWORD: "1234",
        CONFIGURATION_SERIAL_PORT: "/dev/null",
    }, options)
    unit.mode = JA80CentralUnit.SYSTEM_MODE_PARTIAL
    for zone in unit._zones.values():
        zone.status = JablotronZone.STATUS_DISARMED
    return unit


@pytest.mark.parametrize("activity", [0x10, 0x16])
def test_active_detectors_do_not_enqueue_background_keys(activity, event_loop_for_setters):
    unit = make_unit({CONFIGURATION_QUERY_DETECTOR_ACTIVITY: False})
    packet = bytearray([0xED, JablotronState.DISARMED, activity, 0, 1, 0, 0, 0, 0, 0xFF])
    for _ in range(5):
        event_loop_for_setters.run_until_complete(unit._process_state(packet, packet.hex()))
    assert unit._connection._cmd_q.empty()
    assert unit._last_state == JablotronState.DISARMED


@pytest.mark.parametrize("status,armed", [
    (JablotronState.DISARMED, []),
    (JablotronState.ARMED_A, [1]),
    (JablotronState.ARMED_AB, [1, 2]),
    (JablotronState.ARMED_ABC, [1, 2, 3]),
])
def test_zone_state_is_received_without_detector_queries(status, armed, event_loop_for_setters):
    unit = make_unit({CONFIGURATION_QUERY_DETECTOR_ACTIVITY: False})
    packet = bytearray([0xED, status, 0, 0, 1, 0, 0, 0, 0, 0xFF])
    event_loop_for_setters.run_until_complete(unit._process_state(packet, packet.hex()))
    for zone_id, zone in unit._zones.items():
        expected = JablotronZone.STATUS_ARMED if zone_id in armed else JablotronZone.STATUS_DISARMED
        assert zone.status == expected
    assert unit._connection._cmd_q.empty()


def test_existing_configuration_still_queries_and_option_can_change_live(event_loop_for_setters):
    unit = make_unit(None)
    loop = event_loop_for_setters
    loop.run_until_complete(unit._send_device_query())
    assert unit._connection._cmd_q.qsize() == 1
    loop.run_until_complete(unit._connection._get_command())
    unit._connection._send_cmd = None
    unit.update_options({CONFIGURATION_QUERY_DETECTOR_ACTIVITY: False})
    loop.run_until_complete(unit._send_device_query())
    assert unit._connection._cmd_q.empty()
    unit.update_options({CONFIGURATION_QUERY_DETECTOR_ACTIVITY: True})
    loop.run_until_complete(unit._send_device_query())
    assert unit._connection._cmd_q.qsize() == 1


@pytest.mark.parametrize("zone,prefix", [("A", "*2"), ("B", "*3"), ("C", "*1")])
def test_arm_commands_remain_available(zone, prefix, event_loop_for_setters):
    unit = make_unit({CONFIGURATION_QUERY_DETECTOR_ACTIVITY: False})
    loop = event_loop_for_setters
    loop.run_until_complete(unit.arm("1234", zone))
    command = loop.run_until_complete(unit._connection._get_command())
    assert command.code == b"".join(JablotronKeyPress.get_key_command(c) for c in prefix + "1234")


def test_disarm_and_explicit_query_remain_available(event_loop_for_setters):
    unit = make_unit({CONFIGURATION_QUERY_DETECTOR_ACTIVITY: False})
    unit._last_state = JablotronState.ARMED_ABC
    loop = event_loop_for_setters
    loop.run_until_complete(unit.disarm("1234"))
    command = loop.run_until_complete(unit._connection._get_command())
    assert command.code == b"".join(JablotronKeyPress.get_key_command(c) for c in "1234")
    loop.run_until_complete(unit.send_detail_command())
    command = loop.run_until_complete(unit._connection._get_command())
    assert command.name == "Details"



@pytest.mark.parametrize("pending", [False, True])
def test_manual_query_bypasses_disabled_automatic_queries(pending, event_loop_for_setters):
    unit = make_unit({CONFIGURATION_QUERY_DETECTOR_ACTIVITY: False})
    unit._device_query_pending = pending
    loop = event_loop_for_setters
    loop.run_until_complete(unit._send_device_query())
    assert unit._connection._cmd_q.empty()
    loop.run_until_complete(unit._send_device_query(manual=True))
    if pending:
        assert unit._connection._cmd_q.empty()
    else:
        command = loop.run_until_complete(unit._connection._get_command())
        assert command.name == "Details"
        assert command.code == b"\x8e"


def test_query_button_sends_details_with_automatic_queries_disabled(monkeypatch, event_loop_for_setters):
    import importlib
    import sys
    import types

    for name, attributes in {
        "homeassistant.components.button": {"ButtonEntity": type("ButtonEntity", (), {})},
        "homeassistant.helpers.entity": {"Entity": type("Entity", (), {})},
        "homeassistant.helpers.typing": {"StateType": object},
        "homeassistant.helpers.restore_state": {"RestoreEntity": type("RestoreEntity", (), {})},
        "homeassistant.helpers.dispatcher": {"async_dispatcher_connect": lambda *args, **kwargs: None},
    }.items():
        module = sys.modules.get(name)
        if module is None:
            module = types.ModuleType(name)
            monkeypatch.setitem(sys.modules, name, module)
        for attribute, value in attributes.items():
            if not hasattr(module, attribute):
                monkeypatch.setattr(module, attribute, value, raising=False)
    button_class = importlib.import_module("custom_components.jablotron80.button").JablotronQueryButtonEntity
    unit = make_unit({CONFIGURATION_QUERY_DETECTOR_ACTIVITY: False})
    button = button_class(unit.query, unit)
    loop = event_loop_for_setters
    loop.run_until_complete(button.async_press())
    command = loop.run_until_complete(unit._connection._get_command())
    assert command.name == "Details"
    assert command.code == b"\x8e"

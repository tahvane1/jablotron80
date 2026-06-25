"""Tests for the auto-reconnect / connect-failure-tolerance logic (#165, #97).

Background
----------
When the USB/serial link drops, the integration must NOT die. Previously:

* ``JablotronConnectionHID.connect()`` raised if ``open()`` failed, and
* ``read_send_packet_loop`` returned (exited) the moment ``is_connected()`` was
  False.

Together that meant nothing ever reconnected, even after the device returned.

The fix makes ``connect()`` tolerate a failed ``open()`` (leaving the connection
``None`` instead of raising) and makes ``reconnect()`` report success as a bool
so the packet loop can back off and retry. These tests exercise that contract
directly, without any real hardware and without Home Assistant ``Entity``
instances.

The async helpers are driven via the ``event_loop_for_setters`` fixture from
conftest, which installs a real current event loop for the test.
"""

import builtins

import pytest

import custom_components.jablotron80.jablotron as jablotron
from custom_components.jablotron80.const import (
    CABLE_MODEL,
    CABLE_MODEL_JA82T,
    CONFIGURATION_PASSWORD,
    CONFIGURATION_SERIAL_PORT,
)


def _build_unit():
    """Construct a JA80CentralUnit with the smallest valid (HID) config.

    The JA-82T cable model routes to the HID connection class, whose constructor
    does NOT open the serial port, so this is safe without hardware.
    """
    config = {
        CABLE_MODEL: CABLE_MODEL_JA82T,
        CONFIGURATION_SERIAL_PORT: "/dev/null",
        CONFIGURATION_PASSWORD: "1234",
    }
    return jablotron.JA80CentralUnit(hass=None, config=config, options=None)


# ---------------------------------------------------------------------------
# connect() tolerates a failed open
# ---------------------------------------------------------------------------
def test_hid_connect_nonexistent_device_does_not_raise(event_loop_for_setters):
    """Opening a device that does not exist must NOT raise; the connection is
    simply left disconnected so the reconnect loop can keep retrying."""
    conn = jablotron.JablotronConnectionHID("/nonexistent/device/path")

    # Must not raise.
    event_loop_for_setters.run_until_complete(conn.connect())

    assert conn.is_connected() is False


def test_hid_connect_tolerates_open_oserror(monkeypatch, event_loop_for_setters):
    """If ``open()`` raises OSError, connect() swallows it, leaves the connection
    None, and does not propagate the error."""
    conn = jablotron.JablotronConnectionHID("/dev/whatever")

    def _boom(*_args, **_kwargs):
        raise OSError("device gone")

    monkeypatch.setattr(builtins, "open", _boom)

    # Must not raise even though open() blows up.
    event_loop_for_setters.run_until_complete(conn.connect())

    assert conn.is_connected() is False
    assert conn._connection is None


# ---------------------------------------------------------------------------
# reconnect() reports failure as a bool and leaves consistent state
# ---------------------------------------------------------------------------
def test_reconnect_returns_false_when_device_unopenable(
    monkeypatch, event_loop_for_setters
):
    """reconnect() returns False when the device cannot be opened, and the
    connection object's state stays consistent (disconnected, no exception)."""
    conn = jablotron.JablotronConnectionHID("/dev/whatever")

    def _boom(*_args, **_kwargs):
        raise OSError("device gone")

    monkeypatch.setattr(builtins, "open", _boom)

    result = event_loop_for_setters.run_until_complete(conn.reconnect())

    assert result is False
    assert conn.is_connected() is False
    assert conn._connection is None


def test_reconnect_returns_true_when_open_succeeds(
    monkeypatch, event_loop_for_setters
):
    """reconnect() returns True once the device opens again. A fake file-like
    object stands in for the opened HID device so no real hardware is touched."""
    conn = jablotron.JablotronConnectionHID("/dev/whatever")

    class _FakeDevice:
        def write(self, _data):
            return None

        def read(self, _n):
            return b""

        def flush(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(builtins, "open", lambda *a, **k: _FakeDevice())

    result = event_loop_for_setters.run_until_complete(conn.reconnect())

    assert result is True
    assert conn.is_connected() is True


# ---------------------------------------------------------------------------
# RECONNECT_BACKOFF_SECONDS constant exists and is sane
# ---------------------------------------------------------------------------
def test_reconnect_backoff_constant_present():
    """The packet loop relies on a module-level backoff constant."""
    assert hasattr(jablotron, "RECONNECT_BACKOFF_SECONDS")
    assert jablotron.RECONNECT_BACKOFF_SECONDS > 0


# ---------------------------------------------------------------------------
# #97 Part A: rf_level is a refresh candidate
# ---------------------------------------------------------------------------
def test_rf_level_is_a_real_sensor_object(event_loop_for_setters):
    """The rf_level getter returns a JablotronSensor object (the thing the
    sensor platform builds its entity from)."""
    unit = _build_unit()
    assert unit.rf_level is not None
    assert isinstance(unit.rf_level, jablotron.JablotronSensor)
    # Same identity as the private object that _refresh_all_entities collects.
    assert unit.rf_level is unit._rf_level


def test_refresh_all_entities_includes_rf_level(event_loop_for_setters, monkeypatch):
    """The rf_level object must be among the objects _refresh_all_entities
    publishes, so its availability flips with the connection (#97 Part A).

    We capture every object publish_updates() is called on and assert the
    rf_level object's identity is present.
    """
    unit = _build_unit()

    published_ids = set()

    async def _capture(self):
        published_ids.add(id(self))

    # Patch publish_updates on the base common class so every entity-backed
    # object records that it was refreshed.
    monkeypatch.setattr(
        jablotron.JablotronCommon, "publish_updates", _capture, raising=True
    )

    event_loop_for_setters.run_until_complete(unit._refresh_all_entities())

    assert id(unit._rf_level) in published_ids

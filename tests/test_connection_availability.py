"""Tests for the stale-data / connection-watchdog logic (issue #97).

Background
----------
``JablotronConnectionHID._read_data`` blocks waiting for serial data and never
times out, so a dead link produces no exception - it just goes silent. Issue #97
adds a watchdog: the connection records ``_last_data_time`` whenever non-empty
records are forwarded, exposes ``seconds_since_last_data``, and the central unit
derives ``connection_alive`` from it. When the link goes stale the watchdog
re-publishes every entity so Home Assistant flips them to "unavailable".

These tests exercise the connection and central-unit logic directly. They do NOT
instantiate Home Assistant ``Entity`` subclasses (those need the real HA platform
classes, which are stubbed away here).

The async helpers (``_forward_records``, ``_refresh_all_entities``) are driven
via the ``event_loop_for_setters`` fixture from conftest, which installs a real
current event loop for the duration of the test.
"""

import time

import custom_components.jablotron80.jablotron as jablotron
from custom_components.jablotron80.const import (
    CABLE_MODEL,
    CABLE_MODEL_JA82T,
    CONFIGURATION_PASSWORD,
    CONFIGURATION_SERIAL_PORT,
)


def _build_unit():
    """Construct a JA80CentralUnit with the smallest valid config.

    Mirrors ``tests/test_reconciliation.py``: the JA-82T cable model routes to
    the HID connection class, whose constructor does NOT open the serial port,
    so this is safe without any hardware.
    """
    config = {
        CABLE_MODEL: CABLE_MODEL_JA82T,
        CONFIGURATION_SERIAL_PORT: "/dev/null",
        CONFIGURATION_PASSWORD: "1234",
    }
    return jablotron.JA80CentralUnit(hass=None, config=config, options=None)


# ---------------------------------------------------------------------------
# JablotronConnection.seconds_since_last_data
# ---------------------------------------------------------------------------
def test_seconds_since_last_data_starts_sane(event_loop_for_setters):
    """A freshly constructed connection has just "seen" data, so the elapsed
    time is small and non-negative."""
    unit = _build_unit()
    elapsed = unit._connection.seconds_since_last_data
    assert elapsed >= 0.0
    assert elapsed < 5.0


def test_seconds_since_last_data_grows_when_backdated(event_loop_for_setters):
    """Backdating ``_last_data_time`` increases the reported elapsed time."""
    unit = _build_unit()
    unit._connection._last_data_time = time.monotonic() - 100
    elapsed = unit._connection.seconds_since_last_data
    assert elapsed >= 100.0
    assert elapsed < 200.0  # sanity upper bound


# ---------------------------------------------------------------------------
# JA80CentralUnit.connection_alive
# ---------------------------------------------------------------------------
def test_connection_alive_true_when_recent(event_loop_for_setters):
    """With recent data the connection counts as alive."""
    unit = _build_unit()
    unit._connection._last_data_time = time.monotonic()
    assert unit.connection_alive is True


def test_connection_alive_false_when_stale(event_loop_for_setters):
    """Backdating well past the timeout makes the connection count as dead."""
    unit = _build_unit()
    unit._connection._last_data_time = time.monotonic() - 100
    assert unit.connection_alive is False


def test_connection_alive_boundary_within_timeout(event_loop_for_setters):
    """Just inside the timeout window still counts as alive."""
    unit = _build_unit()
    # Half the configured timeout ago -> still alive.
    unit._connection._last_data_time = (
        time.monotonic() - unit.CONNECTION_DATA_TIMEOUT_SECONDS / 2
    )
    assert unit.connection_alive is True


# ---------------------------------------------------------------------------
# JablotronConnection._forward_records updates _last_data_time
# ---------------------------------------------------------------------------
def test_forward_records_updates_timestamp_for_nonempty(event_loop_for_setters):
    """A non-empty record batch refreshes ``_last_data_time``."""
    unit = _build_unit()
    conn = unit._connection
    # Make the connection look stale first.
    conn._last_data_time = time.monotonic() - 100
    before = conn._last_data_time

    event_loop_for_setters.run_until_complete(
        conn._forward_records([bytearray(b"\x01\xff")])
    )

    after = conn._last_data_time
    assert after > before
    # And it is now effectively "recent".
    assert conn.seconds_since_last_data < 5.0


def test_forward_records_leaves_timestamp_for_empty(event_loop_for_setters):
    """An empty record batch must NOT refresh ``_last_data_time`` - silence on
    the wire is exactly the stale condition the watchdog detects."""
    unit = _build_unit()
    conn = unit._connection
    conn._last_data_time = time.monotonic() - 100
    before = conn._last_data_time

    event_loop_for_setters.run_until_complete(conn._forward_records([]))

    after = conn._last_data_time
    assert after == before


# ---------------------------------------------------------------------------
# _refresh_all_entities is robust and de-duplicated
# ---------------------------------------------------------------------------
def test_refresh_all_entities_runs_without_error(event_loop_for_setters):
    """Refreshing all entity-backed objects must not raise even though none of
    the test objects has callbacks registered (publish_updates is a no-op).

    The central device is de-duplicated (it is both ``central_device`` and
    ``_devices[0]``) by the set, so it is only refreshed once.
    """
    unit = _build_unit()
    event_loop_for_setters.run_until_complete(unit._refresh_all_entities())

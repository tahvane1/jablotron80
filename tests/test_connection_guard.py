"""Tests for the connection-teardown guard in _read_data (issue #165).

A concurrent disconnect/shutdown can set the connection's underlying handle to
None while the read loop is still in flight (``read_until_found`` loops
``_read_data`` without re-checking ``is_connected``). Before the guard this
raised ``AttributeError: 'NoneType' object has no attribute 'read'`` and surfaced
as "Unexpected error in packet loop". ``_read_data`` must now return ``[]``
cleanly instead.

The JA-82T cable routes to the HID connection class (``self._connection.read``);
its constructor does not open the port, so the underlying handle is already None
on a freshly built unit.
"""

import custom_components.jablotron80.jablotron as jablotron
from custom_components.jablotron80.const import (
    CABLE_MODEL,
    CABLE_MODEL_JA82T,
    CONFIGURATION_PASSWORD,
    CONFIGURATION_SERIAL_PORT,
)


def _build_unit():
    config = {
        CABLE_MODEL: CABLE_MODEL_JA82T,
        CONFIGURATION_SERIAL_PORT: "/dev/null",
        CONFIGURATION_PASSWORD: "1234",
    }
    return jablotron.JA80CentralUnit(hass=None, config=config, options=None)


def test_read_data_returns_empty_when_connection_is_none(event_loop_for_setters):
    """#165: _read_data returns [] (no crash) when the underlying handle is None."""
    unit = _build_unit()
    conn = unit._connection  # the JablotronConnection manager (HID for JA-82T)
    conn._connection = None  # connection torn down concurrently (shutdown/disconnect)

    result = event_loop_for_setters.run_until_complete(conn._read_data())

    assert result == []


def test_read_data_returns_empty_on_closed_file_valueerror(event_loop_for_setters):
    """#165: a closed underlying handle raises ValueError ("I/O operation on closed
    file") on read. The guard must bail cleanly (return []) just like for the None
    case, instead of letting it surface as "Unexpected error in packet loop"."""
    unit = _build_unit()
    conn = unit._connection

    class _ClosedHandle:
        def read(self, *args, **kwargs):
            raise ValueError("I/O operation on closed file")

    conn._connection = _ClosedHandle()  # not None, but closed -> ValueError on read

    async def _noop_reconnect():
        return False

    conn.reconnect = _noop_reconnect  # don't actually try to reopen during the test

    result = event_loop_for_setters.run_until_complete(conn._read_data())

    assert result == []

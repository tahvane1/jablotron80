"""Regression tests for serial connection lifecycle and packet-loop recovery."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
import serial

import custom_components.jablotron80.jablotron as jablotron


def _connection():
    return jablotron.JablotronConnectionSerial("/dev/unused-test-port")


@pytest.mark.parametrize("flush_fails,close_fails", [(False, False), (True, False), (False, True), (True, True)])
def test_disconnect_always_clears_handle(event_loop_for_setters, flush_fails, close_fails):
    """A failed flush must not skip close; either failure must clear the handle."""
    conn = _connection()
    handle = Mock()
    if flush_fails:
        handle.flush.side_effect = OSError("flush failed")
    if close_fails:
        handle.close.side_effect = OSError("close failed")
    conn._connection = handle

    event_loop_for_setters.run_until_complete(conn.disconnect())
    event_loop_for_setters.run_until_complete(conn.disconnect())

    handle.flush.assert_called_once_with()
    handle.close.assert_called_once_with()
    assert conn._connection is None
    assert not conn.is_connected()


def test_reconnect_recovers_after_flush_failure(event_loop_for_setters):
    conn = _connection()
    old = Mock()
    old.flush.side_effect = OSError("device disappeared")
    new = Mock()
    conn._connection = old

    async def open_new():
        conn._connection = new

    conn.connect = AsyncMock(side_effect=open_new)
    assert event_loop_for_setters.run_until_complete(conn.reconnect()) is True
    old.close.assert_called_once_with()
    conn.connect.assert_awaited_once_with()
    assert conn._connection is new


def test_concurrent_reconnects_share_one_replacement(event_loop_for_setters):
    conn = _connection()
    old, new = Mock(), Mock()
    conn._connection = old

    async def open_new():
        await asyncio.sleep(0)
        conn._connection = new

    conn.connect = AsyncMock(side_effect=open_new)

    async def drive():
        return await asyncio.wait_for(asyncio.gather(conn.reconnect(), conn.reconnect()), timeout=5)

    assert event_loop_for_setters.run_until_complete(drive()) == [True, True]
    old.close.assert_called_once_with()
    conn.connect.assert_awaited_once_with()
    new.close.assert_not_called()
    assert conn._connection is new


def test_reconnect_does_not_open_after_shutdown(event_loop_for_setters):
    conn = _connection()
    conn.connect = AsyncMock()
    conn.shutdown()

    assert event_loop_for_setters.run_until_complete(conn.reconnect()) is False
    conn.connect.assert_not_awaited()
    assert not conn.is_connected()


def test_shutdown_during_reconnect_delay_prevents_open(event_loop_for_setters):
    conn = _connection()
    conn.connect = AsyncMock()

    async def drive():
        task = asyncio.create_task(conn.reconnect())
        await asyncio.sleep(0)
        conn.shutdown()
        return await asyncio.wait_for(task, timeout=5)

    assert event_loop_for_setters.run_until_complete(drive()) is False
    conn.connect.assert_not_awaited()
    assert not conn.is_connected()


def test_shutdown_during_successful_open_closes_replacement(event_loop_for_setters):
    conn = _connection()
    new = Mock()

    async def open_new():
        conn.shutdown()
        conn._connection = new

    conn.connect = AsyncMock(side_effect=open_new)

    assert event_loop_for_setters.run_until_complete(conn.reconnect()) is False
    new.close.assert_called_once_with()
    assert not conn.is_connected()


@pytest.mark.parametrize("prior_record", [False, True])
def test_port_not_open_skips_invalid_read_iteration(event_loop_for_setters, prior_record):
    """Neither uninitialized nor previous-iteration records may be forwarded."""
    conn = _connection()
    conn._connection = Mock()
    before = [bytearray(b"\x01\xff")]
    after = [bytearray(b"\x02\xff")]
    sequence = iter(([before] if prior_record else []) + [serial.PortNotOpenError(), after])

    async def read():
        item = next(sequence)
        if isinstance(item, Exception):
            raise item
        if item is after:
            conn.shutdown()
        return item

    conn._read_data = AsyncMock(side_effect=read)
    conn.reconnect = AsyncMock(return_value=True)
    conn._forward_records = AsyncMock()
    conn._get_command = AsyncMock(return_value=None)

    event_loop_for_setters.run_until_complete(asyncio.wait_for(conn.read_send_packet_loop(), timeout=5))

    assert [call.args[0] for call in conn._forward_records.await_args_list] == (
        [before, after] if prior_record else [after]
    )
    assert conn._get_command.await_count == (2 if prior_record else 1)
    conn.reconnect.assert_awaited_once_with()

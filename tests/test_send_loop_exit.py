"""Tests for the send-loop early-exit on accept (issue #168).

A command with no ``complete_prefix`` - the background "Details" query and the
arm/disarm key sequences - used to keep re-sending its keypress(es) for every one
of the 10 retries even after the panel had already accepted it, because the loop
exit condition ``accepted and confirmed`` never became true (``confirmed`` is only
set when a ``complete_prefix`` is found). That floods the bus and, for arm/disarm,
re-enters the PIN ~11x - the root of #168 with several active sensors. The fix
marks such a command confirmed on acceptance so the loop exits after one
successful round, while leaving the full retry budget for the not-yet-accepted
case.

These tests drive ``read_send_packet_loop`` for exactly one queued command with a
mocked connection and count how many keypresses actually go out on the wire.
"""

import custom_components.jablotron80.jablotron as jablotron
from custom_components.jablotron80.jablotron import JablotronCommand
from custom_components.jablotron80.const import (
    CABLE_MODEL,
    CABLE_MODEL_JA82T,
    CONFIGURATION_PASSWORD,
    CONFIGURATION_SERIAL_PORT,
)


def _build_conn():
    config = {
        CABLE_MODEL: CABLE_MODEL_JA82T,
        CONFIGURATION_SERIAL_PORT: "/dev/null",
        CONFIGURATION_PASSWORD: "1234",
    }
    unit = jablotron.JA80CentralUnit(hass=None, config=config, options=None)
    return unit._connection  # the JablotronConnection manager (HID for JA-82T)


class _CountingHandle:
    """Stand-in for the underlying serial/HID handle: counts writes."""

    def __init__(self):
        self.writes = 0

    def write(self, data):
        self.writes += 1


def _run_one_command(loop, conn, command, accept_results):
    """Drive read_send_packet_loop for exactly one queued command.

    ``accept_results`` is consumed one entry per ``read_until_found`` call (the
    accept phase, plus the completion phase for commands with a complete_prefix);
    it falls back to the last entry once exhausted. Returns the number of keypress
    writes performed.
    """
    handle = _CountingHandle()
    conn._connection = handle  # is_connected() -> True

    calls = {"n": 0}

    async def _fake_read_until_found(prefix, max_records=10):
        i = calls["n"]
        calls["n"] += 1
        return accept_results[i] if i < len(accept_results) else accept_results[-1]

    async def _fake_read_data(*args, **kwargs):
        return []

    async def _noop():
        return None

    conn.read_until_found = _fake_read_until_found
    conn._read_data = _fake_read_data
    conn.disconnect = _noop

    async def _drive():
        conn._stop.set()  # exit the loop once the queue drains
        await conn._cmd_q.put(command)
        await conn.read_send_packet_loop()

    jablotron._loop = loop  # confirm() posts _event.set to the module-level loop
    loop.run_until_complete(_drive())
    return handle.writes


def test_no_complete_prefix_sends_once_after_accept(event_loop_for_setters):
    """#168: a Details-style command (no complete_prefix) writes its keypress ONCE
    once accepted - no more re-sending for every remaining retry (was ~11)."""
    conn = _build_conn()
    cmd = JablotronCommand(name="Details", code=b"\x8e", accepted_prefix=b"\xa4\xff")

    writes = _run_one_command(event_loop_for_setters, conn, cmd, [True])

    assert writes == 1


def test_no_complete_prefix_unaccepted_keeps_full_retry_budget(event_loop_for_setters):
    """#168 guard: when the command is never accepted, the full retry budget is
    still spent (11 attempts). The fix only short-circuits AFTER an accept."""
    conn = _build_conn()
    cmd = JablotronCommand(name="Details", code=b"\x8e", accepted_prefix=b"\xa4\xff")

    writes = _run_one_command(event_loop_for_setters, conn, cmd, [False])

    assert writes == 11  # retries 10..0 inclusive


def test_complete_prefix_command_unchanged(event_loop_for_setters):
    """A command WITH a complete_prefix still completes via its handshake and exits
    after one round - the fix leaves that path untouched."""
    conn = _build_conn()
    cmd = JablotronCommand(
        name="Get settings",
        code=b"\x8a",
        accepted_prefix=b"\xa1\xff",
        complete_prefix=b"\xe6\x04",
        max_records=300,
    )

    # call 0 = accept found, call 1 = completion found
    writes = _run_one_command(event_loop_for_setters, conn, cmd, [True, True])

    assert writes == 1

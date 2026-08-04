"""Retry budget for commands that carry the access code (#219, tamper alarm).

The panel starts a tamper (sabotage) alarm after 10 unsuccessful code entries in a
row (JA-80K installation manual). The send loop used a hard-coded ``retries = 10``
for *every* command - i.e. up to 11 attempts - with two consequences:

* a single mistyped code was re-sent 11 times, which exceeds that limit and trips
  the sabotage alarm; and
* an accepted code was re-sent as well (nothing marked it done), and since the
  master code toggles arm/disarm, that flipped the state straight back.

The budget is now per command: low by default (2 retries = 3 attempts) for anything
carrying the code, raised only for the code-less "Details" query - which is what the
generous budget was introduced for in the first place (#153).
"""

import custom_components.jablotron80.jablotron as jablotron
from custom_components.jablotron80.jablotron import JablotronCommand
from custom_components.jablotron80.const import (
    CABLE_MODEL,
    CABLE_MODEL_JA82T,
    CONFIGURATION_PASSWORD,
    CONFIGURATION_SERIAL_PORT,
)

# The prefix the panel acks every keypress with, except the last one of a sequence.
INTERMEDIATE = b"\xa0\xff"


def _build_conn():
    config = {
        CABLE_MODEL: CABLE_MODEL_JA82T,
        CONFIGURATION_SERIAL_PORT: "/dev/null",
        CONFIGURATION_PASSWORD: "1234",
    }
    unit = jablotron.JA80CentralUnit(hass=None, config=config, options=None)
    return unit._connection


class _Handle:
    """Stand-in for the serial/HID handle."""

    def write(self, data):
        pass


def _run(loop, conn, command, final_accepted: bool) -> int:
    """Drive read_send_packet_loop for exactly one command.

    The fake panel acks every intermediate keypress and answers the FINAL keypress of
    the sequence with ``final_accepted`` - so ``False`` models a code the panel
    rejects. Returns how many times the sequence reached its final keypress, which is
    exactly how many complete code entries the panel sees.
    """
    conn._connection = _Handle()
    entries = {"n": 0}

    async def _fake_read_until_found(prefix, max_records=10):
        if prefix == INTERMEDIATE:
            return True
        entries["n"] += 1
        return final_accepted

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

    jablotron._loop = loop
    loop.run_until_complete(_drive())
    return entries["n"]


def _code_command() -> JablotronCommand:
    """An arm/disarm key sequence: four code digits, no completion handshake."""
    return JablotronCommand(
        name="key sequence *HIDDEN*",
        code=b"\x81\x82\x83\x84",
        accepted_prefix=b"\xa1\xff",
    )


def test_default_budget_is_low():
    """Any command that does not opt in gets the safe, low budget."""
    assert JablotronCommand().max_retries == 2


def test_rejected_code_is_not_hammered(event_loop_for_setters):
    """A rejected code (a typo, say) must stay well under the panel's limit of 10
    unsuccessful entries in a row - otherwise it trips the sabotage alarm."""
    conn = _build_conn()

    entries = _run(event_loop_for_setters, conn, _code_command(), final_accepted=False)

    assert entries == 3  # the initial attempt plus 2 retries
    assert entries < 10  # the panel's tamper threshold


def test_accepted_code_is_sent_once(event_loop_for_setters):
    """An accepted code must not be re-sent: the master code toggles arm/disarm, so a
    second entry would flip the state straight back."""
    conn = _build_conn()

    entries = _run(event_loop_for_setters, conn, _code_command(), final_accepted=True)

    assert entries == 1


def test_detail_query_keeps_the_generous_budget(event_loop_for_setters):
    """The code-less "Details" query keeps the full budget (#153): re-sending it
    cannot trip the wrong-code tamper alarm, so raising it there is safe."""
    conn = _build_conn()
    details = JablotronCommand(
        name="Details",
        code=b"\x8e",
        accepted_prefix=b"\xa4\xff",
        max_retries=10,
    )

    entries = _run(event_loop_for_setters, conn, details, final_accepted=False)

    assert entries == 11  # the initial attempt plus 10 retries


def test_unaccepted_command_is_reported_as_failed(event_loop_for_setters):
    """A command that is never accepted must still be marked failed.

    Otherwise ``wait_for_confirmation()`` never returns - and ``read_settings()``
    awaits exactly that during startup, so it would hang for good.
    """
    conn = _build_conn()
    cmd = _code_command()

    _run(event_loop_for_setters, conn, cmd, final_accepted=False)

    assert cmd._event.is_set()
    assert cmd._confirmed is False


def _run_with_completion(loop, conn, command, completion_arrives: bool) -> int:
    """Drive the loop for one command that has a completion handshake.

    Every keypress is acked; the completion prefix answers ``completion_arrives``.
    Returns how many complete code entries the panel saw.
    """
    conn._connection = _Handle()
    entries = {"n": 0}

    async def _fake_read_until_found(prefix, max_records=10):
        if prefix == INTERMEDIATE:
            return True
        if prefix == command.complete_prefix:
            return completion_arrives
        entries["n"] += 1  # final keypress reached => one full entry went in
        return True

    async def _fake_read_data(*args, **kwargs):
        return []

    async def _noop():
        return None

    conn.read_until_found = _fake_read_until_found
    conn._read_data = _fake_read_data
    conn.disconnect = _noop

    async def _drive():
        conn._stop.set()
        await conn._cmd_q.put(command)
        await conn.read_send_packet_loop()

    jablotron._loop = loop
    loop.run_until_complete(_drive())
    return entries["n"]


def _elevated_mode_command() -> JablotronCommand:
    """Shape of ``enter_elevated_mode``: "*0" + master code, WITH a completion
    handshake. The one code-carrying command that waits for a completion prefix."""
    return JablotronCommand(
        name="key sequence *HIDDEN*",
        code=b"\x8f\x80\x81\x82\x83\x84",
        accepted_prefix=b"\xa1\xff",
        complete_prefix=b"\xb8\xff",
    )


def test_completion_never_arrives_is_bounded(event_loop_for_setters):
    """A command WITH a completion handshake must respect its budget too.

    The retry decrement used to be skipped on this path (``continue``), so a command
    whose completion never arrived re-sent its keypresses forever. Elevated mode
    carries the master code and takes exactly this path, so "forever" meant
    hammering the code into the panel without limit.
    """
    conn = _build_conn()
    cmd = _elevated_mode_command()

    entries = _run_with_completion(event_loop_for_setters, conn, cmd, completion_arrives=False)

    assert entries == 3  # bounded by the budget
    assert entries < 10  # and still under the panel's tamper threshold
    assert cmd._event.is_set()
    assert cmd._confirmed is False


def test_completion_arrives_sends_once(event_loop_for_setters):
    """The normal path is untouched: completion arrives, the command is done."""
    conn = _build_conn()
    cmd = _elevated_mode_command()

    entries = _run_with_completion(event_loop_for_setters, conn, cmd, completion_arrives=True)

    assert entries == 1
    assert cmd._confirmed is True

"""Tests for the narrowed command de-duplication (issue #153, maintainer feedback).

Background
----------
The #153 port (heifisch) added de-duplication of queued commands in
``JablotronConnection.add_command`` so that the automatic "Details" detail query
does not pile up behind itself and block a disarm.

The maintainer's concern: de-duplicating *every* command could silently drop a
legitimate repeated command sequence (e.g. a user pressing disarm twice). The
fix narrows the guard so that ONLY a "Details" command is de-duplicated;
user/functional commands are always queued.

These tests pin both halves of that contract:

* two identical "Details" commands collapse to a single queued command, and
* a non-"Details" command added twice is queued twice (never de-duplicated),

while keeping the ``_cmd_q`` / ``_cmd_list`` bookkeeping balanced so that
``_get_command``'s ``pop(0)`` stays consistent.
"""

import custom_components.jablotron80.jablotron as jablotron
from custom_components.jablotron80.jablotron import (
    JablotronCommand,
    JablotronConnectionHID,
)


def _details_command() -> JablotronCommand:
    """Build a fresh "Details" command equal to any other so-built one.

    ``JablotronCommand`` is a dataclass, so two instances built with identical
    fields compare equal - which is exactly what the de-dup guard relies on.
    """
    return JablotronCommand(name="Details", code=b"\x8e", accepted_prefix=b"\xa4\xff")


def _user_command() -> JablotronCommand:
    """Build a fresh non-"Details" (functional) command, e.g. a disarm keypress."""
    return JablotronCommand(name="Disarm", code=b"\x8f", accepted_prefix=b"\xa0\xff")


def test_repeated_details_command_is_deduplicated(event_loop_for_setters):
    """Two identical "Details" queries collapse into a single queued command."""
    loop = event_loop_for_setters
    conn = JablotronConnectionHID("/dev/null")

    loop.run_until_complete(conn.add_command(_details_command()))
    loop.run_until_complete(conn.add_command(_details_command()))

    # Only one survived: the second identical Details query was dropped.
    assert conn._cmd_q.qsize() == 1
    assert len(conn._cmd_list) == 1


def test_repeated_user_command_is_not_deduplicated(event_loop_for_setters):
    """A non-"Details" command added twice is queued twice (never de-duplicated).

    This is the maintainer's requirement: a deliberately repeated functional
    command (e.g. disarm pressed twice) must reach the panel both times.
    """
    loop = event_loop_for_setters
    conn = JablotronConnectionHID("/dev/null")

    loop.run_until_complete(conn.add_command(_user_command()))
    loop.run_until_complete(conn.add_command(_user_command()))

    # Both were queued - identical functional commands are NOT collapsed.
    assert conn._cmd_q.qsize() == 2
    assert len(conn._cmd_list) == 2


def test_get_command_keeps_cmd_list_balanced_for_user_commands(event_loop_for_setters):
    """Dequeuing pops exactly one ``_cmd_list`` entry per command, for any name.

    The narrowed guard still appends every queued command to ``_cmd_list``, so
    ``_get_command``'s ``pop(0)`` stays balanced even for non-"Details" commands.
    """
    loop = event_loop_for_setters
    conn = JablotronConnectionHID("/dev/null")

    loop.run_until_complete(conn.add_command(_user_command()))
    loop.run_until_complete(conn.add_command(_user_command()))
    assert len(conn._cmd_list) == 2

    first = loop.run_until_complete(conn._get_command())
    assert first is not None
    # One dequeued -> exactly one popped from _cmd_list, and it is now in flight.
    assert len(conn._cmd_list) == 1
    assert conn._send_cmd is first

    second = loop.run_until_complete(conn._get_command())
    assert second is not None
    assert len(conn._cmd_list) == 0
    assert conn._cmd_q.empty()

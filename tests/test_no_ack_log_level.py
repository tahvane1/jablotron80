"""Tests for the command-aware "no accepted message" log level.

The repeating background "Details" detail-query is expected NOT to be acked on
most rounds - the JA-80 panel acks roughly one keypress in six, instantly or not
at all. Reconciliation runs off the rounds that DO ack, and the staleness sweep
covers the rest, so a failed "Details" round is normal operation. Logging it at
WARN floods the Home Assistant log with ~2-3 false warnings per minute, so the
"Details" command never escalates to WARN. A real command (arm / disarm /
settings / esc) that fails to ack on its FINAL retry IS meaningful and still
warns.

The key code 0x8e is shared by both "Details" and "Esc / back", so the
distinction is made on the command NAME (its intent), not the key code: "Esc /
back" still warns. The decision is isolated in
``JablotronConnection._no_ack_log_level`` so it can be verified without driving
the full async read/send loop.
"""

import logging

import custom_components.jablotron80.jablotron as jablotron

_level = jablotron.JablotronConnection._no_ack_log_level


def test_details_never_warns_even_on_final_retry():
    # retries == 0 is the last attempt; "Details" stays out of WARN there, and of
    # course on every earlier attempt too.
    assert _level("Details", 0) == logging.INFO
    assert _level("Details", 10) == logging.INFO


def test_real_command_warns_on_final_retry_only():
    # A keypress sequence (arm/disarm) warns on the final retry...
    assert _level("key sequence *HIDDEN*", 0) == logging.WARN
    # ...but earlier attempts are still routine, no warning.
    assert _level("key sequence *HIDDEN*", 3) == logging.INFO


def test_other_real_commands_still_warn_on_final_retry():
    # "Get settings" and "Esc / back" are deliberate, non-background commands.
    assert _level("Get settings", 0) == logging.WARN
    assert _level("Esc / back", 0) == logging.WARN


def test_esc_back_shares_keycode_with_details_but_still_warns():
    # Both send b"\x8e"; the suppression keys off the command NAME, not the code,
    # so "Esc / back" must keep its final-retry warning while "Details" does not.
    assert _level("Esc / back", 0) == logging.WARN
    assert _level("Details", 0) == logging.INFO

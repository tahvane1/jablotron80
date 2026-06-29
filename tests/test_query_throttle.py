"""Tests for the detail-query send throttle (issue #168).

Each background detail ("?") query is an ESC keypress on the shared bus. Firing it
on every detector cycle (~1-2s) keeps the bus busy and cancels a keypad arm/bypass
before the user can finish. ``_send_device_query`` now enforces a minimum spacing
of ``DETAIL_QUERY_MIN_INTERVAL_SECONDS`` between queries, leaving the bus free in
between. The integration cannot see keypad input directly (it only reads its own
echoes), so a time throttle is the practical equivalent of "pause while the user
is at the keypad".
"""

import custom_components.jablotron80.jablotron as jablotron
from custom_components.jablotron80.jablotron import DETAIL_QUERY_MIN_INTERVAL_SECONDS
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


def test_detail_query_is_throttled(event_loop_for_setters):
    """A rapid second query is suppressed; once the interval elapses it goes out."""
    unit = _build_unit()
    sent = {"n": 0}

    async def _fake_send():
        sent["n"] += 1

    unit.send_detail_command = _fake_send
    loop = event_loop_for_setters

    # First query goes out.
    loop.run_until_complete(unit._send_device_query())
    assert sent["n"] == 1

    # An immediate second query is suppressed (still inside the min interval).
    loop.run_until_complete(unit._send_device_query())
    assert sent["n"] == 1

    # Once the interval has elapsed, the next query goes out again.
    unit._last_device_query -= DETAIL_QUERY_MIN_INTERVAL_SECONDS + 1
    loop.run_until_complete(unit._send_device_query())
    assert sent["n"] == 2


def test_interval_constant_is_sane():
    assert DETAIL_QUERY_MIN_INTERVAL_SECONDS >= 5

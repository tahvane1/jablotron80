"""Tests for the ack-independent staleness sweep (issue #153 follow-up).

Background
----------
On a setup with many detectors open at once, the panel's "?" detail-query
response can overflow and never get acked, so the query-ack-gated reconciliation
in ``_update_device()`` never runs. A detector the panel has STOPPED reporting
(e.g. a closed door) then stays stuck ``active=True`` in HA.

The panel's status-text reports ("Triggered detector, X:name") DO come through
reliably. ``_activate_device`` records ``time.monotonic()`` per device in
``_device_last_active`` on every such report. ``_sweep_stale_devices`` is a
time-based safety net: it deactivates any currently-active device not
re-reported within ``DEVICE_STALE_TIMEOUT_SECONDS``. It ONLY deactivates; it
never activates, and it leaves the device in ``_active_devices`` so it can
re-activate later.

Each device id used here is ``< 0x40`` so that ``_get_source`` resolves it to a
``JablotronDevice`` (ids >= 0x40 are codes, see ``JA80CentralUnit._get_source``).
"""

import datetime
import time

import custom_components.jablotron80.jablotron as jablotron
from custom_components.jablotron80.jablotron import (
    DEVICE_STALE_TIMEOUT_SECONDS,
    STALE_SWEEP_INTERVAL_SECONDS,
)
from custom_components.jablotron80.const import (
    CABLE_MODEL,
    CABLE_MODEL_JA82T,
    CONFIGURATION_PASSWORD,
    CONFIGURATION_SERIAL_PORT,
)

# Two arbitrary device ids, both < 0x40 so they resolve to devices, not codes.
DEVICE_GOES_STALE = 6
DEVICE_STAYS_FRESH = 22


def _build_unit():
    """Construct a JA80CentralUnit with a dummy hass and the smallest config.

    Mirrors ``tests/test_reconciliation.py``: the JA-82T cable model routes to
    the HID connection class, whose constructor does NOT open the serial port -
    only ``connect()`` (called from ``initialize()``, never called here) does.
    """
    config = {
        CABLE_MODEL: CABLE_MODEL_JA82T,
        CONFIGURATION_SERIAL_PORT: "/dev/null",
        CONFIGURATION_PASSWORD: "1234",
    }
    return jablotron.JA80CentralUnit(hass=None, config=config, options=None)


def test_constants_are_sane():
    """The sweep constants exist, are positive, and timeout > interval."""
    assert DEVICE_STALE_TIMEOUT_SECONDS > 0
    assert STALE_SWEEP_INTERVAL_SECONDS > 0
    assert DEVICE_STALE_TIMEOUT_SECONDS > STALE_SWEEP_INTERVAL_SECONDS


def test_activate_records_last_active(event_loop_for_setters):
    """After activating device 6, a recent timestamp is recorded and it is active."""
    unit = _build_unit()

    before = time.monotonic()
    unit._activate_source(DEVICE_GOES_STALE)
    after = time.monotonic()

    dev6 = unit.get_device(DEVICE_GOES_STALE)
    assert dev6.active is True

    # A timestamp exists for device 6 and it sits within the activation window.
    assert DEVICE_GOES_STALE in unit._device_last_active
    ts = unit._device_last_active[DEVICE_GOES_STALE]
    assert before <= ts <= after


def test_activate_records_wall_clock_timestamp(event_loop_for_setters):
    """Activation also records a tz-aware wall-clock datetime for the attribute.

    The monotonic dict drives the sweep; this parallel dict is what the entity
    surfaces as ``last_reported_active``. It must be a timezone-aware datetime
    (Home Assistant requires aware datetimes in attributes) and sit within a few
    seconds of "now".
    """
    unit = _build_unit()

    before = datetime.datetime.now(datetime.timezone.utc)
    unit._activate_source(DEVICE_GOES_STALE)
    after = datetime.datetime.now(datetime.timezone.utc)

    assert DEVICE_GOES_STALE in unit._device_last_active_wall
    wall = unit._device_last_active_wall[DEVICE_GOES_STALE]
    assert isinstance(wall, datetime.datetime)
    # Timezone-aware (not naive) so HA serialises/localises it correctly.
    assert wall.tzinfo is not None
    assert before <= wall <= after


def test_sweep_deactivates_only_the_stale_device(event_loop_for_setters):
    """A stale device turns off; a fresh one stays on; the stale one is retained.

    Devices 6 and 22 are both active. Device 6's last-active timestamp is
    back-dated beyond the timeout (stale); device 22 stays fresh. The sweep
    must return device 6, set ``dev6.active is False``, leave ``dev22.active
    is True``, and keep device 6 in ``_active_devices`` so it can re-activate.
    """
    unit = _build_unit()
    unit._last_state = jablotron.JablotronState.DISARMED

    unit._activate_source(DEVICE_GOES_STALE)
    unit._activate_source(DEVICE_STAYS_FRESH)

    dev6 = unit.get_device(DEVICE_GOES_STALE)
    dev22 = unit.get_device(DEVICE_STAYS_FRESH)
    assert dev6.active is True
    assert dev22.active is True

    # Back-date device 6 past the timeout; device 22 keeps its fresh timestamp.
    unit._device_last_active[DEVICE_GOES_STALE] = (
        time.monotonic() - (DEVICE_STALE_TIMEOUT_SECONDS + 30)
    )

    deactivated = unit._sweep_stale_devices()

    # Only the stale device is returned and deactivated.
    assert deactivated == [dev6]
    assert dev6.active is False
    # The fresh device is untouched.
    assert dev22.active is True
    # The stale device stays in the persistent registry for re-activation.
    assert DEVICE_GOES_STALE in unit._active_devices


def test_sweep_does_not_deactivate_fresh_or_untracked(event_loop_for_setters):
    """Fresh (or timestamp-absent) active devices are never swept.

    Both devices are freshly active. Additionally, the ``.get(..., now)``
    default protects a device that has no entry in ``_device_last_active`` at
    all: deleting device 22's timestamp must still leave it active after a
    sweep. The sweep returns an empty list and changes nothing.
    """
    unit = _build_unit()
    unit._last_state = jablotron.JablotronState.DISARMED

    unit._activate_source(DEVICE_GOES_STALE)
    unit._activate_source(DEVICE_STAYS_FRESH)

    dev6 = unit.get_device(DEVICE_GOES_STALE)
    dev22 = unit.get_device(DEVICE_STAYS_FRESH)

    # Remove device 22's timestamp entirely -> the default-to-now guard applies.
    del unit._device_last_active[DEVICE_STAYS_FRESH]

    deactivated = unit._sweep_stale_devices()

    assert deactivated == []
    assert dev6.active is True
    assert dev22.active is True


def test_sweep_skips_when_armed(event_loop_for_setters):
    """#208 follow-up: the sweep must never deactivate while the system is armed.

    When armed (or arming / entry-delay) the panel stops cycling the
    detail-query, so an open detector is no longer re-reported even though it is
    still open. A stale timestamp then does NOT mean "closed", so the sweep must
    do nothing; once disarmed, the same stale device is swept again.
    """
    unit = _build_unit()
    unit._activate_source(DEVICE_GOES_STALE)
    dev6 = unit.get_device(DEVICE_GOES_STALE)

    # Back-date past the timeout: this device WOULD be swept while disarmed.
    unit._device_last_active[DEVICE_GOES_STALE] = time.monotonic() - (
        DEVICE_STALE_TIMEOUT_SECONDS + 30
    )

    # Armed -> sweep is a no-op, the (still-open) detector stays active.
    unit._last_state = jablotron.JablotronState.ARMED_ABC
    assert unit._sweep_stale_devices() == []
    assert dev6.active is True

    # Disarmed -> the same stale detector is now swept off.
    unit._last_state = jablotron.JablotronState.DISARMED
    assert unit._sweep_stale_devices() == [dev6]
    assert dev6.active is False


def test_active_tracked_devices_lists_active_with_timestamp(event_loop_for_setters):
    """Variant B: only active detectors carrying a timestamp are republished.

    The sweep loop republishes this set every tick so the live staleness
    attributes refresh in the UI. A deactivated device, or one without a
    recorded timestamp, must drop out of the set.
    """
    unit = _build_unit()

    unit._activate_source(DEVICE_GOES_STALE)
    unit._activate_source(DEVICE_STAYS_FRESH)

    dev6 = unit.get_device(DEVICE_GOES_STALE)
    dev22 = unit.get_device(DEVICE_STAYS_FRESH)

    # Both active and timestamped -> both refreshed, in activation order.
    assert unit._active_tracked_devices() == [dev6, dev22]

    # A deactivated detector drops out (no point refreshing an off entity).
    dev22.active = False
    assert unit._active_tracked_devices() == [dev6]

    # An active detector without a recorded timestamp also drops out.
    del unit._device_last_active[DEVICE_GOES_STALE]
    assert unit._active_tracked_devices() == []


def test_refresh_keeps_active_detector_fresh(event_loop_for_setters):
    """#208 follow-up: refreshing active detectors prevents a false stale-clear.

    While the panel keeps reporting "triggered detector" but the keypad query is
    suppressed (the detector is already shown), a single still-open detector must
    have its last-seen time refreshed - otherwise the sweep would falsely clear
    it. ``_refresh_active_detectors_last_seen`` is what the suppressed-0x10 path
    calls; here we exercise it directly.
    """
    unit = _build_unit()
    unit._last_state = jablotron.JablotronState.DISARMED
    unit._activate_source(DEVICE_GOES_STALE)
    dev6 = unit.get_device(DEVICE_GOES_STALE)

    # Back-date past the timeout: without a refresh the sweep WOULD clear it.
    unit._device_last_active[DEVICE_GOES_STALE] = time.monotonic() - (
        DEVICE_STALE_TIMEOUT_SECONDS + 30
    )

    before = time.monotonic()
    unit._refresh_active_detectors_last_seen()
    after = time.monotonic()

    # Monotonic timestamp refreshed into the just-now window.
    ts = unit._device_last_active[DEVICE_GOES_STALE]
    assert before <= ts <= after
    # Wall-clock parallel dict refreshed too (drives last_reported_active).
    assert DEVICE_GOES_STALE in unit._device_last_active_wall
    # The detector is fresh again -> the sweep must NOT clear it.
    assert unit._sweep_stale_devices() == []
    assert dev6.active is True


def test_refresh_ignores_inactive_detectors(event_loop_for_setters):
    """Only active detectors are refreshed; an inactive one is left untouched.

    A detector still tracked in ``_active_devices`` but already turned off must
    not have its timestamp refreshed (otherwise it could never go stale/clear).
    """
    unit = _build_unit()
    unit._activate_source(DEVICE_GOES_STALE)
    dev6 = unit.get_device(DEVICE_GOES_STALE)
    dev6.active = False  # detector reported closed

    # Old timestamp; the refresh must not touch an inactive (but still tracked)
    # device.
    stale_ts = time.monotonic() - (DEVICE_STALE_TIMEOUT_SECONDS + 30)
    unit._device_last_active[DEVICE_GOES_STALE] = stale_ts

    unit._refresh_active_detectors_last_seen()

    assert unit._device_last_active[DEVICE_GOES_STALE] == stale_ts

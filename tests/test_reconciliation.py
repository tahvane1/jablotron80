"""Tests for the per-sensor-close reconciliation logic (issue #153).

This is the core protection for the ``fix/153-per-sensor-close`` branch.

Background
----------
The JA-80 central unit reports the set of currently-active (triggered) detectors
in each query round. The integration keeps two structures:

* ``_active_devices``      - a *persistent* registry of every device ever seen
                             active. It is never cleared, so it can reconcile.
* ``_active_devices_tmp``  - the set of devices seen active *in the current
                             query round*. It is rebuilt every round.

``_update_device()`` reconciles: any device in the persistent registry that is
*absent* from the current round (i.e. its detector closed) is set inactive,
independently of other detectors that are still open. That independence is the
#153 fix - a single closed detector must turn off on its own.

Each device id used here is ``< 0x40`` so that ``_get_source`` resolves it to a
``JablotronDevice`` (ids >= 0x40 are codes, see ``JA80CentralUnit._get_source``).
"""

import custom_components.jablotron80.jablotron as jablotron
from custom_components.jablotron80.const import (
    CABLE_MODEL,
    CABLE_MODEL_JA82T,
    CONFIGURATION_PASSWORD,
    CONFIGURATION_SERIAL_PORT,
)

# Two arbitrary device ids, both < 0x40 so they resolve to devices, not codes.
DEVICE_OPEN_THEN_CLOSED = 6
DEVICE_STAYS_OPEN = 22


def _build_unit():
    """Construct a JA80CentralUnit with a dummy hass and the smallest config.

    ``JA80CentralUnit.__init__`` requires only the cable model, the serial port
    and the master password; every other key is optional (the constructor
    tolerates their absence). The JA-82T cable model routes to the HID
    connection class, whose constructor does NOT open the serial port - only
    ``connect()`` (called from ``initialize()``, which we never call) does.
    """
    config = {
        CABLE_MODEL: CABLE_MODEL_JA82T,
        CONFIGURATION_SERIAL_PORT: "/dev/null",
        CONFIGURATION_PASSWORD: "1234",
    }
    return jablotron.JA80CentralUnit(hass=None, config=config, options=None)


def test_unit_constructs_with_minimal_config(event_loop_for_setters):
    """Sanity check: the smallest config constructs and starts empty."""
    unit = _build_unit()
    assert unit._active_devices == {}
    assert unit._active_devices_tmp == {}


def test_round1_two_devices_active(event_loop_for_setters):
    """Round 1: activating two devices puts both in tmp + persistent, active."""
    unit = _build_unit()

    unit._activate_source(DEVICE_OPEN_THEN_CLOSED)
    unit._activate_source(DEVICE_STAYS_OPEN)

    dev6 = unit.get_device(DEVICE_OPEN_THEN_CLOSED)
    dev22 = unit.get_device(DEVICE_STAYS_OPEN)

    # Both devices report active immediately after activation.
    assert dev6.active is True
    assert dev22.active is True

    # Both are tracked in the per-round (tmp) set and the persistent registry.
    assert DEVICE_OPEN_THEN_CLOSED in unit._active_devices_tmp
    assert DEVICE_STAYS_OPEN in unit._active_devices_tmp
    assert DEVICE_OPEN_THEN_CLOSED in unit._active_devices
    assert DEVICE_STAYS_OPEN in unit._active_devices


def test_round1_update_keeps_both_active(event_loop_for_setters):
    """Round 1 reconcile: tmp is cleared, both devices stay active.

    Because both devices were reported in this round, ``_update_device`` must
    keep both active and empty the per-round set.
    """
    unit = _build_unit()

    unit._activate_source(DEVICE_OPEN_THEN_CLOSED)
    unit._activate_source(DEVICE_STAYS_OPEN)
    unit._update_device()

    dev6 = unit.get_device(DEVICE_OPEN_THEN_CLOSED)
    dev22 = unit.get_device(DEVICE_STAYS_OPEN)

    assert unit._active_devices_tmp == {}
    assert dev6.active is True
    assert dev22.active is True


def test_per_sensor_close_closes_only_the_absent_device(event_loop_for_setters):
    """The #153 proof: a closed detector turns off independently.

    Round 1: devices 6 and 22 are both open.
    Round 2: only device 22 is reported (device 6 closed). After reconciliation,
    device 6 must be inactive while device 22 stays active.

    Contrast with the pre-fix behaviour: the old code cleared/kept triggers as a
    group, so a single still-open detector (22) could keep a closed detector (6)
    erroneously "active", or clearing one could wrongly clear the other. This
    test fails on that regression and passes on the per-sensor-close fix.
    """
    unit = _build_unit()

    # Round 1 - both detectors open.
    unit._activate_source(DEVICE_OPEN_THEN_CLOSED)
    unit._activate_source(DEVICE_STAYS_OPEN)
    unit._update_device()

    dev6 = unit.get_device(DEVICE_OPEN_THEN_CLOSED)
    dev22 = unit.get_device(DEVICE_STAYS_OPEN)
    assert dev6.active is True
    assert dev22.active is True

    # Round 2 - only device 22 is reported; device 6 has closed.
    unit._activate_source(DEVICE_STAYS_OPEN)
    unit._update_device()

    # The closed detector turns off on its own ...
    assert dev6.active is False
    # ... while the still-open detector remains active.
    assert dev22.active is True

    # Device 6 stays in the persistent registry so it can reconcile again later.
    assert DEVICE_OPEN_THEN_CLOSED in unit._active_devices
    assert DEVICE_STAYS_OPEN in unit._active_devices


def test_reopen_after_close_reactivates(event_loop_for_setters):
    """A detail check: a device can close and then re-open across rounds."""
    unit = _build_unit()
    dev6 = unit.get_device(DEVICE_OPEN_THEN_CLOSED)

    # Open, reconcile -> active.
    unit._activate_source(DEVICE_OPEN_THEN_CLOSED)
    unit._update_device()
    assert dev6.active is True

    # Absent next round -> closed.
    unit._update_device()
    assert dev6.active is False

    # Reported again -> active once more.
    unit._activate_source(DEVICE_OPEN_THEN_CLOSED)
    unit._update_device()
    assert dev6.active is True

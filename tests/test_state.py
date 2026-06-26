"""Tests for the ``JablotronState`` status-byte classification helpers.

``JablotronState`` (in jablotron.py) maps raw status bytes from the central unit
to logical states. The helpers tested here are pure static methods over the
constants defined in the same class, so they are easy to assert against without
constructing the unit.

All expected values below are taken directly from the constants in
``JablotronState`` - they are not guessed.
"""

import custom_components.jablotron80.jablotron as jablotron

JablotronState = jablotron.JablotronState


# ---------------------------------------------------------------------------
# is_armed_state  (membership in STATES_ARMED)
# ---------------------------------------------------------------------------
def test_is_armed_state_for_armed_bytes():
    # 0x43 = ARMED_ABC (unsplit/partial), 0x61 = ARMED_SPLIT_A.
    assert JablotronState.is_armed_state(JablotronState.ARMED_ABC) is True
    assert JablotronState.is_armed_state(JablotronState.ARMED_A) is True
    assert JablotronState.is_armed_state(JablotronState.ARMED_SPLIT_A) is True


def test_is_armed_state_false_for_disarmed():
    # A disarmed byte must not classify as armed.
    assert JablotronState.is_armed_state(JablotronState.DISARMED) is False


# ---------------------------------------------------------------------------
# is_disarmed_state  (membership in STATES_DISARMED)
# ---------------------------------------------------------------------------
def test_is_disarmed_state_for_disarmed_bytes():
    # 0x40 unsplit/partial disarmed, 0x60 split disarmed.
    assert JablotronState.is_disarmed_state(JablotronState.DISARMED) is True
    assert JablotronState.is_disarmed_state(JablotronState.DISARMED_SPLIT) is True


def test_is_disarmed_state_false_for_armed():
    assert JablotronState.is_disarmed_state(JablotronState.ARMED_ABC) is False


# ---------------------------------------------------------------------------
# is_alarm_state  (membership in STATES_ALARM)
# ---------------------------------------------------------------------------
def test_is_alarm_state_for_alarm_bytes():
    # 0x45 ALARM_A, 0x44 ALARM_WITHOUT_ARMING, 0x67 ALARM_C_SPLIT.
    assert JablotronState.is_alarm_state(JablotronState.ALARM_A) is True
    assert JablotronState.is_alarm_state(JablotronState.ALARM_WITHOUT_ARMING) is True
    assert JablotronState.is_alarm_state(JablotronState.ALARM_C_SPLIT) is True


def test_is_alarm_state_false_for_non_alarm():
    assert JablotronState.is_alarm_state(JablotronState.DISARMED) is False
    assert JablotronState.is_alarm_state(JablotronState.ARMED_ABC) is False


# ---------------------------------------------------------------------------
# exit-delay and entering-delay classification (membership lists)
# ---------------------------------------------------------------------------
def test_is_exit_delay_state():
    # 0x53 EXIT_DELAY_ABC, 0x71 EXIT_DELAY_SPLIT_A.
    assert JablotronState.is_exit_delay_state(JablotronState.EXIT_DELAY_ABC) is True
    assert JablotronState.is_exit_delay_state(JablotronState.EXIT_DELAY_SPLIT_A) is True
    assert JablotronState.is_exit_delay_state(JablotronState.DISARMED) is False


def test_is_entering_delay_state():
    # 0x49 ARMED_ENTRY_DELAY_A, 0x4B ARMED_ENTRY_DELAY_ABC.
    assert JablotronState.is_entering_delay_state(JablotronState.ARMED_ENTRY_DELAY_A) is True
    assert JablotronState.is_entering_delay_state(JablotronState.ARMED_ENTRY_DELAY_ABC) is True
    assert JablotronState.is_entering_delay_state(JablotronState.DISARMED) is False


# ---------------------------------------------------------------------------
# maintenance classification (bitwise: MAINTENANCE set AND DISARMED bit clear)
# ---------------------------------------------------------------------------
def test_is_maintenance_state_true_for_maintenance_byte():
    # MAINTENANCE = 0x20: 0x20 & 0x20 -> truthy, 0x20 & 0x40 -> 0 (not disarmed).
    assert bool(JablotronState.is_maintenance_state(JablotronState.MAINTENANCE)) is True


def test_is_maintenance_state_false_for_disarmed_byte():
    # DISARMED = 0x40: the DISARMED bit is set, so it is explicitly not maintenance.
    assert bool(JablotronState.is_maintenance_state(JablotronState.DISARMED)) is False

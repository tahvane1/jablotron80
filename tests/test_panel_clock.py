"""Tests for the read-only panel-clock + drift sensors (issue #151, read-only part).

The panel reports its own clock (day/month/hour/minute; no year, no seconds) only
in event records. ``_update_panel_clock`` exposes it as a tz-aware timestamp plus
the signed drift (panel - HA now) in whole seconds. Both update only on events.
"""

import datetime

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


def test_panel_clock_unset_until_first_event(event_loop_for_setters):
    """Before any event the panel-clock and drift read None (sensor 'unknown')."""
    unit = _build_unit()
    assert unit.panel_time.value is None
    assert unit.panel_time_drift.value is None


def test_update_panel_clock_sets_aware_time_and_drift(event_loop_for_setters):
    """An event timestamp becomes a tz-aware datetime; drift is signed seconds."""
    unit = _build_unit()

    # Panel reports a time ~90 s ahead of "now"; minute resolution loses the
    # sub-minute part, but the drift stays clearly positive (panel ahead).
    now = datetime.datetime.now()
    panel_naive = (now + datetime.timedelta(seconds=90)).replace(second=0, microsecond=0)

    unit._update_panel_clock(panel_naive)

    pt = unit.panel_time.value
    assert isinstance(pt, datetime.datetime)
    assert pt.tzinfo is not None  # HA requires tz-aware timestamps
    assert pt.hour == panel_naive.hour and pt.minute == panel_naive.minute

    drift = unit.panel_time_drift.value
    assert isinstance(drift, int)  # round() -> whole seconds
    assert drift > 0  # panel is ahead


def test_update_panel_clock_ignores_none(event_loop_for_setters):
    """A None timestamp leaves the sensors untouched."""
    unit = _build_unit()
    unit._update_panel_clock(None)
    assert unit.panel_time.value is None
    assert unit.panel_time_drift.value is None


# --- entity-render: the clock shows a literal HH:MM, not an aging relative time ---
import homeassistant.components.sensor as _ha_sensor  # noqa: E402

if not hasattr(_ha_sensor, "SensorDeviceClass"):

    class SensorDeviceClass:  # noqa: D401 - minimal stand-in
        TIMESTAMP = "timestamp"
        SIGNAL_STRENGTH = "signal_strength"

    _ha_sensor.SensorDeviceClass = SensorDeviceClass

from custom_components.jablotron80.sensor import JablotronPanelClockEntity  # noqa: E402


def test_panel_clock_entity_renders_hh_mm(event_loop_for_setters):
    """The clock entity shows a literal HH:MM string (no relative 'x minutes ago')."""
    unit = _build_unit()
    now = datetime.datetime.now()
    panel_naive = (now + datetime.timedelta(seconds=90)).replace(second=0, microsecond=0)
    unit._update_panel_clock(panel_naive)

    ent = JablotronPanelClockEntity(unit.panel_time, unit)
    state = ent.state
    assert state == unit.panel_time.value.strftime("%H:%M")
    assert len(state) == 5 and state[2] == ":"


def test_panel_clock_entity_none_before_event(event_loop_for_setters):
    """Before any event the entity state is None (sensor shows 'unknown')."""
    unit = _build_unit()
    ent = JablotronPanelClockEntity(unit.panel_time, unit)
    assert ent.state is None

"""Tests for the #181 arming-after-disarm guards.

Two small defensive guards prevent the "alarm re-arms / double alarm pending
right after disarming" race:
  1. a zone does not flip into entry-delay while it is being disarmed, and
  2. the alarm entity does not re-issue a disarm when it is already disarmed or
     mid-disarming (a redundant master-code keypress toggles the panel back into
     arming, since the master code toggles arm/disarm).

This covers the zone-level guard, which is plain state logic. The entity-level
guard (`async_alarm_disarm`) depends on the full Home Assistant
alarm_control_panel stack and is verified by review + live.
"""

from custom_components.jablotron80.jablotron import JablotronZone


def test_entering_skipped_while_disarming(event_loop_for_setters):
    """#181: entering() must NOT move a DISARMING zone into entry-delay."""
    zone = JablotronZone(1)
    zone.enabled = True
    zone.status = JablotronZone.STATUS_DISARMING

    zone.entering(None)

    assert zone.status == JablotronZone.STATUS_DISARMING


def test_entering_works_normally(event_loop_for_setters):
    """A zone that is not disarming still enters entry-delay as before."""
    zone = JablotronZone(2)
    zone.enabled = True
    zone.status = JablotronZone.STATUS_ARMED

    zone.entering(None)

    assert zone.status == JablotronZone.STATUS_ENTRY_DELAY

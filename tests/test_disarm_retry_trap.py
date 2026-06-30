"""Reproduces the #219 regression introduced by #216 in UNSPLIT mode.

``async_alarm_disarm`` sets ``zone[0].status = DISARMING`` optimistically *before*
sending the disarm command - but only in the ``mode == UNSPLIT`` branch. If that
first command does not take (slower/flakier bus), the zone is left at DISARMING.
The #216 guard ``if alarm_state in (DISARMED, DISARMING): return`` then drops every
follow-up disarm until the next state packet corrects the zone - which reads as
"disarming is unreliable" (issue #219).

This test drives ``async_alarm_disarm`` with a zone already in that optimistic
DISARMING state and asserts the disarm still goes out. It FAILS on the guarded
code (the bug) and PASSES once the guard no longer traps a genuine retry (e.g. the
#216 revert, or a fix that only debounces a rapid double-press).

Only UNSPLIT is affected: partial/split never set the optimistic DISARMING and
``get_active_zone`` prioritises armed zones, so ``alarm_state`` never reads
DISARMING/DISARMED while a zone is armed. (That is why a partial-mode panel does
not reproduce it.)
"""

from custom_components.jablotron80.jablotron import JablotronZone, JA80CentralUnit
from custom_components.jablotron80.alarm_control_panel import Jablotron80AlarmControl
from custom_components.jablotron80.const import CONFIGURATION_REQUIRE_CODE_TO_DISARM


class _FakeCU:
    """Minimal central-unit stand-in: UNSPLIT mode, counts disarm commands."""

    mode = JA80CentralUnit.SYSTEM_MODE_UNSPLIT
    _master_code = "1234"

    def __init__(self):
        # code not required for disarm -> the entity uses the master code itself
        self._options = {CONFIGURATION_REQUIRE_CODE_TO_DISARM: False}
        self.disarm_calls = []

    async def disarm(self, code):
        self.disarm_calls.append(code)


def test_unsplit_disarm_retry_not_trapped(event_loop_for_setters):
    """A genuine disarm retry must still issue the command in UNSPLIT mode, even
    when the zone is already in the optimistic DISARMING state from a first attempt
    that did not take."""
    cu = _FakeCU()
    zone = JablotronZone(1)
    zone.enabled = True
    zone.status = JablotronZone.STATUS_DISARMING  # optimistic state left by attempt #1

    panel = Jablotron80AlarmControl(cu, [zone], 0)
    event_loop_for_setters.run_until_complete(panel.async_alarm_disarm())

    assert cu.disarm_calls == ["1234"], (
        "disarm retry was dropped while the zone was optimistically DISARMING "
        "(#219 trap); expected the master code to be re-sent"
    )

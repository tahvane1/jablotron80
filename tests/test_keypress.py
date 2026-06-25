"""Tests for the defensive ``get_beep_option`` lookup (issue #44).

Background
----------
``JablotronKeyPress._BEEP_OPTIONS`` maps known beep codes to descriptions, but
it is sparse - several codes the panel can emit (notably 6) have no entry.
The old ``get_beep_option`` indexed the dict directly, so an unmapped code raised
``KeyError`` and broke message parsing. The fix uses ``dict.get`` with an
"Unknown" fallback.

These tests only touch ``JablotronKeyPress``, a plain class with static methods,
so no central unit or event loop is needed.
"""

import custom_components.jablotron80.jablotron as jablotron

JablotronKeyPress = jablotron.JablotronKeyPress


# ---------------------------------------------------------------------------
# Defined codes still return their mapped values
# ---------------------------------------------------------------------------
def test_defined_beep_codes_return_mapped_values():
    """Every key present in _BEEP_OPTIONS returns exactly its mapped entry."""
    for code, expected in JablotronKeyPress._BEEP_OPTIONS.items():
        assert JablotronKeyPress.get_beep_option(code) == expected


def test_specific_known_codes():
    """Spot-check a couple of known codes against their literal mappings."""
    assert JablotronKeyPress.get_beep_option(0x0) == {
        "val": "1s",
        "desc": "1 subtle (short) beep triggered",
    }
    assert JablotronKeyPress.get_beep_option(0x1) == {
        "val": "1l",
        "desc": "1 loud (long) beep triggered",
    }
    assert JablotronKeyPress.get_beep_option(0xE) == {
        "val": "?",
        "desc": "unknown beep(s) triggered",
    }


# ---------------------------------------------------------------------------
# The #44 regression: code 6 must NOT raise
# ---------------------------------------------------------------------------
def test_missing_code_6_returns_unknown_and_does_not_raise():
    """The reported crash: code 6 is absent from _BEEP_OPTIONS.

    Before the fix this raised KeyError; now it degrades to "Unknown".
    """
    # Guard the premise: 6 really is unmapped.
    assert 6 not in JablotronKeyPress._BEEP_OPTIONS
    # And the call is now safe.
    assert JablotronKeyPress.get_beep_option(6) == "Unknown"


def test_other_unmapped_codes_also_return_unknown():
    """Any unmapped code falls back to "Unknown" rather than raising."""
    for code in (0x6, 0x9, 0xA, 0xFF):
        if code in JablotronKeyPress._BEEP_OPTIONS:
            continue
        assert JablotronKeyPress.get_beep_option(code) == "Unknown"

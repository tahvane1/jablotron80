"""Shared pytest fixtures and Home Assistant stubs for the jablotron80 tests.

The integration's ``jablotron.py`` imports Home Assistant at module top:

    from homeassistant import config_entries
    from homeassistant.core import HomeAssistant
    from homeassistant.const import EVENT_HOMEASSISTANT_STOP

Home Assistant is a very heavy dependency and is NOT installed in this test
environment (by design - the task forbids installing it). Instead we insert
lightweight fake modules into ``sys.modules`` BEFORE the integration is imported,
so those imports resolve against our stubs.

We also put the repo root on ``sys.path`` so that
``import custom_components.jablotron80.jablotron`` resolves as a package.
"""

import asyncio
import os
import sys
import types

import pytest

# ---------------------------------------------------------------------------
# 1. Make the repo root importable as the parent of ``custom_components``.
# ---------------------------------------------------------------------------
# conftest.py lives in <repo>/tests/, so the repo root is one level up.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# ---------------------------------------------------------------------------
# 2. Install fake ``homeassistant`` modules into sys.modules.
# ---------------------------------------------------------------------------
def _install_homeassistant_stubs() -> None:
    """Insert minimal fake homeassistant modules so the imports succeed.

    Only the symbols actually imported by jablotron.py (and, defensively, by
    const.py / errors.py) are provided. Everything is a trivial dummy: the
    tests never drive real Home Assistant behaviour.
    """
    if "homeassistant" in sys.modules:
        return

    # Top-level package.
    ha = types.ModuleType("homeassistant")
    ha.__path__ = []  # mark as a package so submodule imports are allowed

    # homeassistant.core  ->  HomeAssistant (a dummy class is enough)
    ha_core = types.ModuleType("homeassistant.core")

    class HomeAssistant:  # noqa: D401 - dummy stand-in
        """Dummy HomeAssistant stand-in used only for type references."""

    ha_core.HomeAssistant = HomeAssistant

    # homeassistant.const  ->  EVENT_HOMEASSISTANT_STOP (a dummy string)
    ha_const = types.ModuleType("homeassistant.const")
    ha_const.EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"

    # homeassistant.config_entries  ->  empty module object is sufficient
    ha_config_entries = types.ModuleType("homeassistant.config_entries")

    # config_entries.ConfigEntry is referenced as a type hint in the package
    # __init__.py; a bare class is enough.
    class ConfigEntry:  # noqa: D401 - dummy stand-in
        """Dummy ConfigEntry stand-in used only for type references."""

    ha_config_entries.ConfigEntry = ConfigEntry

    # homeassistant.exceptions  ->  HomeAssistantError (errors.py subclasses it)
    ha_exceptions = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        """Dummy base error matching homeassistant.exceptions.HomeAssistantError."""

    ha_exceptions.HomeAssistantError = HomeAssistantError

    # -- The integration package __init__.py imports the full HA platform stack.
    # Importing `custom_components.jablotron80.jablotron` runs that __init__.py,
    # so we must stub everything it pulls in too. Each platform module only needs
    # a DOMAIN string.
    ha_components = types.ModuleType("homeassistant.components")
    ha_components.__path__ = []

    def _platform_module(name: str, domain: str) -> types.ModuleType:
        mod = types.ModuleType(f"homeassistant.components.{name}")
        mod.DOMAIN = domain
        return mod

    ha_comp_alarm = _platform_module("alarm_control_panel", "alarm_control_panel")
    ha_comp_binary = _platform_module("binary_sensor", "binary_sensor")
    ha_comp_sensor = _platform_module("sensor", "sensor")
    ha_comp_button = _platform_module("button", "button")

    # homeassistant.helpers with device_registry and config_validation.
    ha_helpers = types.ModuleType("homeassistant.helpers")
    ha_helpers.__path__ = []

    ha_dr = types.ModuleType("homeassistant.helpers.device_registry")

    def _async_get(_hass):
        return None

    ha_dr.async_get = _async_get

    ha_cv = types.ModuleType("homeassistant.helpers.config_validation")

    def _config_entry_only_config_schema(_domain):
        # The package __init__.py calls this at import time; return a no-op.
        return lambda value: value

    ha_cv.config_entry_only_config_schema = _config_entry_only_config_schema

    ha_helpers.device_registry = ha_dr
    ha_helpers.config_validation = ha_cv

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.core"] = ha_core
    sys.modules["homeassistant.const"] = ha_const
    sys.modules["homeassistant.config_entries"] = ha_config_entries
    sys.modules["homeassistant.exceptions"] = ha_exceptions
    sys.modules["homeassistant.components"] = ha_components
    sys.modules["homeassistant.components.alarm_control_panel"] = ha_comp_alarm
    sys.modules["homeassistant.components.binary_sensor"] = ha_comp_binary
    sys.modules["homeassistant.components.sensor"] = ha_comp_sensor
    sys.modules["homeassistant.components.button"] = ha_comp_button
    sys.modules["homeassistant.helpers"] = ha_helpers
    sys.modules["homeassistant.helpers.device_registry"] = ha_dr
    sys.modules["homeassistant.helpers.config_validation"] = ha_cv


_install_homeassistant_stubs()


# ---------------------------------------------------------------------------
# 3. Event-loop fixture.
# ---------------------------------------------------------------------------
# Setting a JablotronCommon ``.active`` to a *new* value runs through the
# ``@log_change`` decorator. When the value actually changes, log_change calls
#     asyncio.get_event_loop().create_task(obj.publish_updates())
# Under Python 3.12+ ``asyncio.get_event_loop()`` raises if there is no current
# event loop set for the thread and none is running. We therefore install a
# real loop as the current loop for the duration of each test so those setters
# are safe. ``publish_updates`` is a no-op coroutine when no callbacks are
# registered (the test devices have none), so the scheduled task is harmless.
@pytest.fixture
def event_loop_for_setters():
    """Provide a real current event loop so ``.active`` setters are safe."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        # log_change schedules publish_updates() coroutine tasks on this loop
        # whenever a tracked attribute changes. The loop never .run()s during a
        # test, so those tasks are still pending at teardown. Run the loop once
        # to completion to let the (no-op) coroutines finish cleanly; otherwise
        # asyncio emits "Task was destroyed but it is pending" warnings.
        try:
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        except Exception:
            pass
        loop.close()
        asyncio.set_event_loop(None)

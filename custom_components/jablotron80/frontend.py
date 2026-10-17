"""Serve only the bundled, optional dashboard module; never modify dashboards."""

import asyncio
from pathlib import Path

from homeassistant.components.http import StaticPathConfig

from .const import DOMAIN

RESOURCE_URL = "/jablotron80/frontend/jablotron-user-code-card.js"
_DATA_LOCK = "frontend_setup_lock"
_DATA_READY = "frontend_ready"


async def async_setup_frontend(hass):
    """Register once, including concurrent config-entry setup and reloads.

    Only this public JavaScript file is exposed. Credentials and key files are
    never served. Resource selection remains an explicit dashboard-owner choice.
    """
    data = hass.data.setdefault(DOMAIN, {})
    lock = data.setdefault(_DATA_LOCK, asyncio.Lock())
    async with lock:
        if data.get(_DATA_READY):
            return
        path = Path(__file__).parent / "frontend" / "jablotron-user-code-card.js"
        await hass.http.async_register_static_paths([StaticPathConfig(RESOURCE_URL, str(path), False)])
        data[_DATA_READY] = True

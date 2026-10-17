"""Check the public asset boundary and idempotent async setup."""

import asyncio
import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.jablotron80.const import DOMAIN


def test_only_bundled_asset_is_served_once_for_concurrent_entries(monkeypatch):
    http = ModuleType("homeassistant.components.http")

    @dataclass
    class StaticPathConfig:
        url_path: str
        path: str
        cache_headers: bool

    http.StaticPathConfig = StaticPathConfig
    monkeypatch.setitem(sys.modules, http.__name__, http)
    name = "custom_components.jablotron80.frontend"
    monkeypatch.delitem(sys.modules, name, raising=False)
    frontend = importlib.import_module(name)
    hass = SimpleNamespace(data={}, http=SimpleNamespace(async_register_static_paths=AsyncMock()))

    async def scenario():
        await asyncio.gather(frontend.async_setup_frontend(hass), frontend.async_setup_frontend(hass))
        await frontend.async_setup_frontend(hass)

    asyncio.run(scenario())
    hass.http.async_register_static_paths.assert_awaited_once()
    paths = hass.http.async_register_static_paths.call_args.args[0]
    assert len(paths) == 1
    asset = paths[0]
    assert asset.url_path == "/jablotron80/frontend/jablotron-user-code-card.js"
    assert Path(asset.path).is_file()
    assert Path(asset.path).parent.name == "frontend"
    assert asset.cache_headers is False
    assert hass.data[DOMAIN]["frontend_ready"] is True


def test_failed_registration_can_be_retried(monkeypatch):
    http = ModuleType("homeassistant.components.http")
    http.StaticPathConfig = lambda *args: args
    monkeypatch.setitem(sys.modules, http.__name__, http)
    name = "custom_components.jablotron80.frontend"
    monkeypatch.delitem(sys.modules, name, raising=False)
    frontend = importlib.import_module(name)
    hass = SimpleNamespace(
        data={}, http=SimpleNamespace(async_register_static_paths=AsyncMock(side_effect=[OSError(), None]))
    )

    async def scenario():
        try:
            await frontend.async_setup_frontend(hass)
        except OSError:
            pass
        assert not hass.data[DOMAIN].get("frontend_ready")
        await frontend.async_setup_frontend(hass)

    asyncio.run(scenario())
    assert hass.http.async_register_static_paths.await_count == 2

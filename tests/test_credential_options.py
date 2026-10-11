"""Exercise real options-flow migration using lightweight HA interfaces."""
import importlib
import sys
from types import SimpleNamespace, ModuleType
from copy import deepcopy
from unittest.mock import AsyncMock
import pytest

from test_user_codes import setup, run, user, ALARM
from test_user_code_api import api
from custom_components.jablotron80.credentials import BUNDLE, create_key, decoded_config
from custom_components.jablotron80.user_codes import DATA_USER_CODES
from custom_components.jablotron80.const import DOMAIN

@pytest.fixture
def flow(monkeypatch, setup, api, tmp_path):
    import homeassistant.core as core
    import homeassistant.config_entries as ce
    class ConfigFlow:
        def __init_subclass__(cls, **kwargs): pass
    class OptionsFlow:
        def async_create_entry(self, **kw): return {'type': 'create_entry', **kw}
        def async_show_form(self, **kw): return {'type': 'form', **kw}
    monkeypatch.setattr(ce, 'ConfigFlow', ConfigFlow, raising=False)
    monkeypatch.setattr(ce, 'OptionsFlow', OptionsFlow, raising=False)
    monkeypatch.setattr(ce, 'CONN_CLASS_LOCAL_PUSH', 'local_push', raising=False)
    monkeypatch.setattr(core, 'callback', lambda fn: fn, raising=False)
    data_flow = ModuleType('homeassistant.data_entry_flow')
    data_flow.AbortFlow = Exception
    monkeypatch.setitem(sys.modules, data_flow.__name__, data_flow)
    monkeypatch.delitem(sys.modules, 'custom_components.jablotron80.config_flow', raising=False)
    module = importlib.import_module('custom_components.jablotron80.config_flow')
    m, store, cu, hass = setup
    hass.data[DOMAIN][DATA_USER_CODES] = m
    hass.config = SimpleNamespace(path=lambda name: str(tmp_path / name))
    entry = SimpleNamespace(entry_id='panel1', data={'password': '4321'}, options={'code_mode': 'personal'})
    updates = []
    def update(entry, **kw):
        updates.append(deepcopy(kw))
        for name, value in kw.items(): setattr(entry, name, value)
    hass.config_entries = SimpleNamespace(async_update_entry=update)
    monkeypatch.setattr(api, 'async_setup_user_codes', AsyncMock())
    instance = module.JablotronOptionsFlow(entry)
    instance.hass = hass
    return instance, m, store, entry, updates, tmp_path


def test_ui_generates_key_and_migrates_both_stores_without_returning_pin(flow):
    f, m, store, entry, updates, tmp = flow
    path = str(tmp / 'chosen.key')
    async def scenario():
        await m.async_save(user('alice'), ALARM, '0123')
        result = await f.async_step_init({'code_mode': 'personal', 'encrypt_codes': True,
            'encryption_key_file': path, 'create_encryption_key': True})
        assert result['type'] == 'create_entry'
        assert 'create_encryption_key' not in result['data']
        assert BUNDLE in entry.data and 'password' not in entry.data
        assert decoded_config(entry.data, 'panel1')['password'] == '4321'
        assert '0123' not in str(store.data)
        assert '4321' not in str(result) + str(updates)
        assert entry.options['encrypt_codes'] is True
    run(scenario())


def test_missing_old_key_cannot_be_replaced_by_generate_checkbox(flow):
    f, m, store, entry, updates, tmp = flow
    path = str(tmp / 'chosen.key')
    async def scenario():
        first = {'code_mode': 'personal', 'encrypt_codes': True,
                 'encryption_key_file': path, 'create_encryption_key': True}
        await f.async_step_init(first)
        before = deepcopy(entry.data)
        updates.clear()
        (tmp / 'chosen.key').unlink()
        result = await f.async_step_init(first)
        assert result['type'] == 'form'
        assert result['errors'] == {'base': 'credentials_unavailable'}
        assert entry.data == before and not updates
        assert not (tmp / 'chosen.key').exists()
    run(scenario())


def test_failed_private_write_does_not_apply_config_or_options(flow):
    f, m, store, entry, updates, tmp = flow
    async def scenario():
        await m.async_save(user('alice'), ALARM, '0123')
        store.fail = True
        result = await f.async_step_init({'code_mode': 'common', 'encrypt_codes': True,
            'encryption_key_file': str(tmp / 'chosen.key'), 'create_encryption_key': True})
        assert result['type'] == 'form'
        assert entry.options == {'code_mode': 'personal'}
        assert entry.data == {'password': '4321'}
        assert not updates
    run(scenario())


def test_default_path_comes_from_ha_config_and_is_not_docker_specific(flow):
    f, _, _, _, _, tmp = flow
    form = run(f.async_step_init())
    values = form['data_schema']({})
    assert values['encryption_key_file'] == str(tmp / '.jablotron80.key')
    assert values['encrypt_codes'] is False

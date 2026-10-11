import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol

from test_user_codes import setup, user, run, ALARM
from custom_components.jablotron80.const import DOMAIN
from custom_components.jablotron80.user_codes import DATA_USER_CODES

@pytest.fixture
def api(monkeypatch):
    class View:
        @staticmethod
        def json(data, status_code=200):
            return {'status': status_code, 'body': data}
    modules = {}
    http = modules['homeassistant.components.http'] = ModuleType('http')
    http.HomeAssistantView = View
    ws = modules['homeassistant.components.websocket_api'] = ModuleType('websocket_api')
    def decorator(schema):
        def wrap(fn):
            fn.schema = vol.Schema({vol.Required('id'): int, **schema})
            return fn
        return wrap
    ws.websocket_command = decorator
    ws.async_response = lambda fn: fn
    policy = modules['homeassistant.auth.permissions.const'] = ModuleType('policy')
    policy.POLICY_CONTROL = 'control'
    storage = modules['homeassistant.helpers.storage'] = ModuleType('storage')
    storage.Store = object
    registry = modules['homeassistant.helpers.entity_registry'] = ModuleType('entity_registry')
    for name, value in modules.items():
        monkeypatch.setitem(sys.modules, name, value)
    monkeypatch.setattr(sys.modules['homeassistant.components'], 'websocket_api', ws, raising=False)
    monkeypatch.setattr(sys.modules['homeassistant.helpers'], 'entity_registry', registry, raising=False)
    name = 'custom_components.jablotron80.user_code_api'
    monkeypatch.delitem(sys.modules, name, raising=False)
    return importlib.import_module(name)

class Request:
    def __init__(self, data, caller):
        self.data = data
        self.caller = caller
    async def json(self):
        return self.data
    def __getitem__(self, key):
        assert key == 'hass_user'
        return self.caller


def prepare(setup):
    manager, store, cu, hass = setup
    alice = user('alice')
    hass.auth = SimpleNamespace(async_get_user=AsyncMock(return_value=alice))
    hass.data[DOMAIN][DATA_USER_CODES] = manager
    hass.bus = SimpleNamespace(async_fire=lambda *args, **kwargs: None)
    return manager, store, cu, hass, alice


def test_write_response_contains_no_pin_and_uses_authenticated_account(api, setup):
    m, store, cu, hass, alice = prepare(setup)
    response = run(api.UserCodeView(m).post(Request({'entity_id': ALARM, 'operation': 'save', 'code': '0123'}, alice)))
    assert response == {'status': 200, 'body': {'saved': True}}
    assert store.data['codes']['panel1'] == {'alice': '0123'}
    assert '0123' not in str(response)
    cu.disarm.assert_not_awaited()
    assert not hasattr(api.UserCodeView, 'get')

@pytest.mark.parametrize('operation', ['save', 'remove'])
def test_reject_caller_controlled_user_id(api, setup, operation):
    m, store, cu, hass, alice = prepare(setup)
    data = {'entity_id': ALARM, 'operation': operation, 'user_id': 'bob'}
    if operation == 'save':
        data['code'] = '0123'
    response = run(api.UserCodeView(m).post(Request(data, alice)))
    assert response['status'] == 400
    assert store.data is None


def test_storage_error_cannot_echo_secret(api, setup):
    m, store, cu, hass, alice = prepare(setup)
    store.async_save = AsyncMock(side_effect=OSError('secret 0123'))
    response = run(api.UserCodeView(m).post(Request({'entity_id': ALARM, 'operation': 'save', 'code': '0123'}, alice)))
    assert response['status'] == 500
    assert '0123' not in str(response)


def test_removed_user_cannot_use_existing_authenticated_connection(api, setup):
    m, store, cu, hass, alice = prepare(setup)
    hass.auth.async_get_user.return_value = None
    response = run(api.UserCodeView(m).post(Request({'entity_id': ALARM, 'operation': 'save', 'code': '0123'}, alice)))
    assert response['status'] == 400
    assert store.data is None

@pytest.mark.parametrize('handler', ['ws_status', 'ws_disarm'])
@pytest.mark.parametrize('extra', [{'user_id': 'bob'}, {'code': '0123'}])
def test_ws_schema_rejects_identity_and_secret_parameters(api, handler, extra):
    fn = getattr(api, handler)
    message = {'id': 1, 'type': 'jablotron80/user_code/' + ('status' if handler == 'ws_status' else 'disarm'), 'entity_id': ALARM, **extra}
    with pytest.raises(vol.Invalid):
        fn.schema(message)


def test_ws_disarm_audit_is_secret_free(api, setup):
    m, store, cu, hass, alice = prepare(setup)
    events, responses = [], []
    hass.bus.async_fire = lambda *args, **kw: events.append((args, kw))
    connection = SimpleNamespace(user=alice, context=lambda msg: 'alice-context',
                                 send_result=lambda *args: responses.append(args), send_error=lambda *args: pytest.fail(str(args)))
    async def scenario():
        await m.async_save(alice, ALARM, '0123')
        await api.ws_disarm(hass, connection, {'id': 1, 'entity_id': ALARM})
    run(scenario())
    assert responses == [(1, {'sent': True})]
    assert events == [(('jablotron80_saved_code_disarm_requested', {'entity_id': ALARM}), {'context': 'alice-context'})]
    assert '0123' not in str(events) + str(responses)

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.jablotron80.const import DATA_JABLOTRON, DOMAIN
from custom_components.jablotron80.user_codes import UserCodeManager, UserCodeError

ALARM = 'alarm_control_panel.oasis'

class MemoryStore:
    def __init__(self):
        self.data = None
        self.fail = False
    async def async_load(self):
        return deepcopy(self.data)
    async def async_save(self, data):
        if self.fail:
            raise OSError('write failed')
        self.data = deepcopy(data)


def user(uid, permitted=True, active=True, system=False):
    return SimpleNamespace(id=uid, is_active=active, system_generated=system,
                           permissions=SimpleNamespace(check_entity=lambda e, p: permitted))

@pytest.fixture
def setup():
    cu = SimpleNamespace(_options={"code_mode": "personal"}, connection_alive=True, zones=[SimpleNamespace(status='Armed')],
                         disarm=AsyncMock())
    entries = {ALARM: SimpleNamespace(platform=DOMAIN, config_entry_id='panel1'),
               'alarm_control_panel.second': SimpleNamespace(platform=DOMAIN, config_entry_id='panel2')}
    hass = SimpleNamespace(data={DOMAIN: {'panel1': {DATA_JABLOTRON: cu}, 'panel2': {DATA_JABLOTRON: cu}}},
                           states=SimpleNamespace(get=lambda e: SimpleNamespace(state='armed_home')))
    store = MemoryStore()
    manager = UserCodeManager(hass, store, SimpleNamespace(async_get=entries.get), 'control')
    return manager, store, cu, hass


def run(coro):
    return asyncio.run(coro)


def test_two_users_get_only_their_own_code(setup):
    m, store, cu, _ = setup
    async def scenario():
        await m.async_save(user('alice'), ALARM, '1234')
        await m.async_save(user('bob'), ALARM, '5678')
        assert m.status(user('alice'), ALARM)['saved'] is True
        assert m.status(user('eve'), ALARM)['saved'] is False
        assert await m.async_disarm(user('alice'), ALARM) == {'sent': True}
        cu.disarm.assert_awaited_once_with('1234', max_retries=0)
        m._attempts.clear()
        await m.async_disarm(user('bob'), ALARM)
        assert cu.disarm.await_args.args == ('5678',)
    run(scenario())


def test_remove_and_replace_affect_only_current_user(setup):
    m, store, _, _ = setup
    async def scenario():
        await m.async_save(user('alice'), ALARM, '0123')
        await m.async_save(user('bob'), ALARM, '5678')
        await m.async_save(user('alice'), ALARM, '0001')
        await m.async_remove(user('alice'), ALARM)
        assert m.status(user('alice'), ALARM)['saved'] is False
        assert store.data['codes']['panel1'] == {'bob': '5678'}
    run(scenario())


def test_restart_persists_account_and_panel_scopes(setup):
    m, store, cu, hass = setup
    async def scenario():
        await m.async_save(user('alice'), ALARM, '0123')
        new = UserCodeManager(hass, store, m.registry, 'control')
        await new.async_load()
        assert new.status(user('alice'), ALARM)['saved'] is True
        assert new.status(user('alice'), 'alarm_control_panel.second')['saved'] is False
        assert new.status(user('bob'), ALARM)['saved'] is False
    run(scenario())

@pytest.mark.parametrize('code', [None, 1234, '123', '12345', 'abcd', '１２３４', '1234\n'])
def test_reject_invalid_pin_without_echoing_it(setup, code):
    m, store, cu, _ = setup
    with pytest.raises(UserCodeError, match='čtyři číslice'):
        run(m.async_save(user('alice'), ALARM, code))
    assert store.data is None
    cu.disarm.assert_not_awaited()

@pytest.mark.parametrize('caller', [None, user('x', permitted=False), user('x', active=False), user('x', system=True)])
def test_permission_checks_apply_to_all_operations(setup, caller):
    m, store, cu, _ = setup
    with pytest.raises(UserCodeError):
        m.status(caller, ALARM)
    for operation in [m.async_save(caller, ALARM, '1234'), m.async_remove(caller, ALARM), m.async_disarm(caller, ALARM)]:
        with pytest.raises(UserCodeError):
            run(operation)
    assert store.data is None
    cu.disarm.assert_not_awaited()


def test_no_master_fallback_for_account_without_code(setup):
    m, store, cu, _ = setup
    cu._master_code = '9999'
    with pytest.raises(UserCodeError, match='ruční PIN'):
        run(m.async_disarm(user('alice'), ALARM))
    cu.disarm.assert_not_awaited()

@pytest.mark.parametrize('state', ['unknown', 'unavailable', 'custom_state'])
def test_unknown_state_blocks_disarming(setup, state):
    m, _, cu, hass = setup
    hass.states.get = lambda e: SimpleNamespace(state=state)
    async def scenario():
        await m.async_save(user('alice'), ALARM, '1234')
        with pytest.raises(UserCodeError):
            await m.async_disarm(user('alice'), ALARM)
    run(scenario())
    cu.disarm.assert_not_awaited()

@pytest.mark.parametrize('state', ['disarmed', 'disarming'])
def test_already_disarmed_never_sends_toggle_pin(setup, state):
    m, _, cu, hass = setup
    hass.states.get = lambda e: SimpleNamespace(state=state)
    async def scenario():
        await m.async_save(user('alice'), ALARM, '1234')
        assert await m.async_disarm(user('alice'), ALARM) == {'sent': False}
    run(scenario())
    cu.disarm.assert_not_awaited()


def test_disconnect_and_service_mode_block_disarming(setup):
    m, _, cu, _ = setup
    async def scenario():
        await m.async_save(user('alice'), ALARM, '1234')
        cu.connection_alive = False
        with pytest.raises(UserCodeError):
            await m.async_disarm(user('alice'), ALARM)
        cu.connection_alive = True
        cu.zones[0].status = 'Service'
        with pytest.raises(UserCodeError):
            await m.async_disarm(user('alice'), ALARM)
    run(scenario())
    cu.disarm.assert_not_awaited()


def test_double_click_and_multiple_users_are_throttled(setup):
    m, _, cu, _ = setup
    async def scenario():
        await m.async_save(user('alice'), ALARM, '1234')
        await m.async_save(user('bob'), ALARM, '5678')
        results = await asyncio.gather(m.async_disarm(user('alice'), ALARM), m.async_disarm(user('bob'), ALARM), return_exceptions=True)
        assert results[0] == {'sent': True}
        assert isinstance(results[1], UserCodeError)
    run(scenario())
    assert cu.disarm.await_count == 1


def test_global_attempt_budget_expires(setup, monkeypatch):
    m, _, cu, _ = setup
    import custom_components.jablotron80.user_codes as module
    now = [1000.0]
    monkeypatch.setattr(module.time, 'monotonic', lambda: now[0])
    async def scenario():
        await m.async_save(user('alice'), ALARM, '1234')
        for _ in range(3):
            await m.async_disarm(user('alice'), ALARM)
            now[0] += 16
        with pytest.raises(UserCodeError, match='Příliš mnoho'):
            await m.async_disarm(user('alice'), ALARM)
        now[0] += 301
        await m.async_disarm(user('alice'), ALARM)
    run(scenario())
    assert cu.disarm.await_count == 4


def test_failed_write_keeps_previous_code(setup):
    m, store, cu, _ = setup
    async def scenario():
        await m.async_save(user('alice'), ALARM, '1234')
        store.fail = True
        with pytest.raises(OSError):
            await m.async_save(user('alice'), ALARM, '5678')
        await m.async_disarm(user('alice'), ALARM)
        cu.disarm.assert_awaited_once_with('1234', max_retries=0)
    run(scenario())


def test_invalid_alarm_is_rejected(setup):
    m, _, cu, _ = setup
    with pytest.raises(UserCodeError):
        run(m.async_save(user('alice'), 'switch.other', '1234'))
    cu.disarm.assert_not_awaited()


def test_internal_disarmed_state_prevents_stale_ui_toggle(setup):
    m, _, cu, _ = setup
    cu.zones[0].status = 'Disarmed'
    async def scenario():
        await m.async_save(user('alice'), ALARM, '1234')
        assert await m.async_disarm(user('alice'), ALARM) == {'sent': False}
    run(scenario())
    cu.disarm.assert_not_awaited()


def test_storage_failure_blocks_saved_pin_only(setup):
    m, store, cu, _ = setup
    m.storage_available = False
    with pytest.raises(UserCodeError, match='Uložiště'):
        run(m.async_save(user('alice'), ALARM, '1234'))
    assert store.data is None
    cu.disarm.assert_not_awaited()


def test_legacy_default_is_common_and_obeys_manual_requirement(setup):
    m, _, cu, _ = setup
    cu._options = {}
    cu._master_code = '4321'
    assert m.status(user('alice'), ALARM)['mode'] == 'common'
    assert not m.status(user('alice'), ALARM)['automatic']
    with pytest.raises(UserCodeError, match='ruční'):
        run(m.async_disarm(user('alice'), ALARM))
    cu.disarm.assert_not_awaited()


def test_common_mode_uses_master_only_when_explicitly_allowed(setup):
    m, _, cu, _ = setup
    cu._options = {'code_mode': 'common', 'require_code_to_disarm': False}
    cu._master_code = '4321'
    assert m.status(user('alice'), ALARM)['automatic']
    run(m.async_disarm(user('alice'), ALARM))
    cu.disarm.assert_awaited_once_with('4321', max_retries=0)
    with pytest.raises(UserCodeError, match='zapnuté'):
        run(m.async_save(user('alice'), ALARM, '1234'))


def test_switching_modes_never_falls_back_to_master(setup):
    m, _, cu, _ = setup
    async def scenario():
        await m.async_save(user('alice'), ALARM, '0123')
        cu._options = {'code_mode': 'common', 'require_code_to_disarm': False}
        cu._master_code = '4321'
        await m.async_disarm(user('alice'), ALARM)
        assert cu.disarm.await_args.args == ('4321',)
        cu._options = {'code_mode': 'personal', 'require_code_to_disarm': False}
        m._attempts.clear()
        await m.async_disarm(user('alice'), ALARM)
        assert cu.disarm.await_args.args == ('0123',)
        m._attempts.clear()
        with pytest.raises(UserCodeError):
            await m.async_disarm(user('bob'), ALARM)
        assert cu.disarm.await_count == 2
    run(scenario())


def test_saved_code_transport_disables_automatic_retry(event_loop_for_setters):
    from custom_components.jablotron80.jablotron import JA80CentralUnit, JablotronState
    unit = JA80CentralUnit(None, {'cable_model': 'JA82T', 'password': '1234', 'serial_port': '/dev/null'}, {})
    unit._last_state = JablotronState.ARMED_ABC
    loop = event_loop_for_setters
    loop.run_until_complete(unit.disarm('0123', max_retries=0))
    command = loop.run_until_complete(unit._connection._get_command())
    assert command.max_retries == 0
    assert '0123' not in str(command)

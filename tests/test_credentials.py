"""Real cryptography tests; no real alarm commands or production credentials."""
import asyncio
import json
import os
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from custom_components.jablotron80.credentials import (
    CredentialError, BUNDLE, create_key, read_key, encode, decode,
    decoded_config, prepare_config, async_prepare_entry,
)
from test_user_codes import setup, user, run, ALARM

@pytest.fixture
def key(tmp_path):
    path = tmp_path / 'private.key'
    create_key(str(path))
    return str(path)


def options(key, enabled=True):
    return {'code_mode': 'personal', 'encrypt_codes': enabled, 'encryption_key_file': key}


def test_real_encryption_is_randomized_and_binds_owner(key):
    a = encode('0123', ['panel1', 'user', 'alice'], options(key))
    b = encode('0123', ['panel1', 'user', 'alice'], options(key))
    assert a['token'] != b['token']
    assert '"0123"' not in json.dumps(a)
    assert decode(a, ['panel1', 'user', 'alice']) == '0123'
    for context in [['panel2', 'user', 'alice'], ['panel1', 'user', 'bob'], ['panel1', 'panel']]:
        with pytest.raises(CredentialError):
            decode(a, context)


def test_wrong_missing_or_tampered_key_never_returns_plaintext(key, tmp_path):
    encrypted = encode('0123', ['panel1', 'user', 'alice'], options(key))
    original = open(key, 'rb').read()
    with open(key, 'wb') as target:
        target.write(Fernet.generate_key())
    with pytest.raises(CredentialError):
        decode(encrypted, ['panel1', 'user', 'alice'])
    with open(key, 'wb') as target:
        target.write(original)
    broken = deepcopy(encrypted)
    broken['token'] = broken['token'][:30] + ('y' if broken['token'][30] == 'x' else 'x') + broken['token'][31:]
    with pytest.raises(CredentialError):
        decode(broken, ['panel1', 'user', 'alice'])
    os.unlink(key)
    with pytest.raises(CredentialError):
        decode(encrypted, ['panel1', 'user', 'alice'])


def test_key_creation_is_exclusive_and_owner_only(key):
    original = open(key, 'rb').read()
    create_key(key)
    assert open(key, 'rb').read() == original
    assert os.stat(key).st_mode & 0o777 == 0o600
    os.chmod(key, 0o644)
    with pytest.raises(CredentialError):
        read_key(key)


def test_config_encrypts_master_and_imported_panel_codes(key):
    original = {'password': '4321', 'codes': {'1': {'name': 'Owner', 'code1': '0123', 'code2': '5678', 'reaction': 1}}, 'serial_port': '/dev/jablotron'}
    encrypted = prepare_config(original, 'panel1', options(key))
    assert 'password' not in encrypted and 'codes' not in encrypted
    assert BUNDLE in encrypted
    assert all(json.dumps(pin) not in json.dumps(encrypted) for pin in ['4321', '0123', '5678'])
    assert decoded_config(encrypted, 'panel1') == original
    assert prepare_config(encrypted, 'panel1', options(key)) == encrypted
    assert prepare_config(encrypted, 'panel1', options(key, False)) == original
    assert original['password'] == '4321'


def test_rotation_requires_old_key_and_preserves_values(key, tmp_path):
    new = str(tmp_path / 'new.key')
    create_key(new)
    encrypted = prepare_config({'password': '4321'}, 'panel1', options(key))
    rotated = prepare_config(encrypted, 'panel1', options(new))
    assert rotated[BUNDLE]['key_file'] == new
    assert decoded_config(rotated, 'panel1') == {'password': '4321'}
    os.unlink(key)
    with pytest.raises(CredentialError):
        prepare_config(encrypted, 'panel1', options(new))


def test_personal_migration_save_restart_disarm_and_disable(setup, key):
    m, store, cu, hass = setup
    async def scenario():
        await m.async_save(user('alice'), ALARM, '0123')
        await m.async_save(user('bob'), ALARM, '5678')
        await m.async_migrate('panel1', options(key))
        assert '"0123"' not in json.dumps(store.data)
        assert '"5678"' not in json.dumps(store.data)
        cu._options = options(key)
        assert m.status(user('alice'), ALARM)['encrypted']
        await m.async_load()
        await m.async_disarm(user('alice'), ALARM)
        cu.disarm.assert_awaited_once_with('0123', max_retries=0)
        await m.async_save(user('alice'), ALARM, '2345')
        assert '"2345"' not in json.dumps(store.data)
        await m.async_migrate('panel1', options(key, False))
        assert store.data['codes']['panel1'] == {'alice': '2345', 'bob': '5678'}
    run(scenario())


def test_personal_migration_failed_write_is_atomic(setup, key):
    m, store, cu, _ = setup
    async def scenario():
        await m.async_save(user('alice'), ALARM, '0123')
        before = deepcopy(store.data)
        store.fail = True
        with pytest.raises(OSError):
            await m.async_migrate('panel1', options(key))
        assert store.data == before
        assert m._codes['panel1']['alice'] == '0123'
    run(scenario())


def test_missing_personal_key_blocks_disarm_even_when_master_available(setup, key):
    m, _, cu, _ = setup
    async def scenario():
        await m.async_save(user('alice'), ALARM, '0123')
        await m.async_migrate('panel1', options(key))
        cu._options = options(key)
        cu._master_code = '4321'
        os.unlink(key)
        with pytest.raises(CredentialError):
            await m.async_disarm(user('alice'), ALARM)
    run(scenario())
    cu.disarm.assert_not_awaited()


def test_interrupted_migration_recovers_mixed_records(setup, key, tmp_path):
    m, store, _, _ = setup
    second = str(tmp_path / 'second.key')
    create_key(second)
    m._codes = {'panel1': {'alice': encode('0123', ['panel1', 'user', 'alice'], options(key)), 'bob': '5678'}}
    run(m.async_migrate('panel1', options(second)))
    os.unlink(key)
    assert decode(store.data['codes']['panel1']['alice'], ['panel1', 'user', 'alice']) == '0123'
    assert decode(store.data['codes']['panel1']['bob'], ['panel1', 'user', 'bob']) == '5678'


def test_startup_migration_returns_ciphertext_but_runtime_decrypts(setup, key):
    m, _, _, hass = setup
    entry = SimpleNamespace(entry_id='panel1', data={'password': '4321'})
    encrypted = run(async_prepare_entry(hass, entry, options(key), m))
    assert BUNDLE in encrypted and 'password' not in encrypted
    assert decoded_config(encrypted, 'panel1')['password'] == '4321'


def test_raw_logs_do_not_reveal_panel_code_table_or_keypresses(monkeypatch, caplog):
    import logging
    from custom_components.jablotron80.jablotron import JablotronSettings, JablotronMessage, format_log_packet, format_packet
    table = bytes([0xe6, 1, 2, 3, 4, 5, 6, 7, 8, 0xff])
    assert format_log_packet(table) == '<raw packet omitted>'
    monkeypatch.setattr(JablotronMessage, 'check_crc', lambda data: True)
    monkeypatch.setattr(JablotronMessage, 'validate_length', lambda kind, data: True)
    with caplog.at_level(logging.DEBUG):
        JablotronMessage.get_message_type_from_record(table, format_packet(table))
    assert format_packet(table) not in caplog.text
    assert '<raw packet omitted>' in caplog.text

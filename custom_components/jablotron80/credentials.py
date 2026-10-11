"""Authenticated, context-bound encryption. Only ciphertext and key paths persist."""

from copy import deepcopy
import base64
import json
import os
from pathlib import Path
import stat

from cryptography.fernet import Fernet, InvalidToken

from .const import (
    CONFIGURATION_PASSWORD,
    CONFIGURATION_CODES,
    CONFIGURATION_ENCRYPT_CODES,
    CONFIGURATION_ENCRYPTION_KEY_FILE,
)

BUNDLE = "encrypted_credentials"
FORMAT = "jablotron80-fernet-v1"


class CredentialError(Exception):
    """Fixed, secret-free error suitable for config flows and logs."""


def read_key(path):
    try:
        if not isinstance(path, str) or not Path(path).is_absolute():
            raise ValueError
        with open(path, "rb") as key_file:
            info = os.fstat(key_file.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise ValueError
            key = key_file.read(256).strip()
        return Fernet(key)
    except (OSError, ValueError, TypeError):
        raise CredentialError(
            "Klíč není dostupný nebo platný. Soubor musí mít oprávnění 0600 nebo 0400."
        ) from None


def create_key(path):
    """Exclusive creation; never replace a lost key with a new key silently."""
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise CredentialError("Zadej absolutní cestu k souboru klíče.")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as target:
            target.write(base64.urlsafe_b64encode(os.urandom(32)) + b"\n")
            target.flush()
            os.fsync(target.fileno())
    except FileExistsError:
        read_key(path)
    except OSError:
        raise CredentialError("Klíč nelze vytvořit. Zkontroluj cestu a oprávnění HA.") from None


def decode(value, context):
    if not isinstance(value, dict):
        return deepcopy(value)
    try:
        if set(value) != {"format", "key_file", "token"} or value["format"] != FORMAT:
            raise ValueError
        payload = json.loads(read_key(value["key_file"]).decrypt(value["token"].encode()))
        if set(payload) != {"context", "value"} or payload["context"] != context:
            raise ValueError
        return payload["value"]
    except CredentialError:
        raise
    except (InvalidToken, ValueError, TypeError, KeyError, AttributeError):
        raise CredentialError(
            "Kódy nelze dešifrovat. Ověř původní klíč; nebude použit náhradní kód."
        ) from None


def encode(value, context, options):
    if not options.get(CONFIGURATION_ENCRYPT_CODES, False):
        return deepcopy(value)
    path = options.get(CONFIGURATION_ENCRYPTION_KEY_FILE, "")
    token = read_key(path).encrypt(json.dumps({"context": context, "value": value}).encode()).decode()
    return {"format": FORMAT, "key_file": path, "token": token}


def decoded_config(data, entry_id):
    result = deepcopy(dict(data))
    if BUNDLE in result:
        bundle = decode(result.pop(BUNDLE), [entry_id, "panel"])
        if not isinstance(bundle, dict) or CONFIGURATION_PASSWORD not in bundle:
            raise CredentialError("Uložené kódy ústředny nejsou platné.")
        result.update(bundle)
    return result


def prepare_config(data, entry_id, options):
    """Decrypt old key before re-encrypting, including every imported panel PIN."""
    result = decoded_config(data, entry_id)
    if options.get(CONFIGURATION_ENCRYPT_CODES, False):
        sensitive = {
            name: result.pop(name) for name in (CONFIGURATION_PASSWORD, CONFIGURATION_CODES) if name in result
        }
        encrypted = encode(sensitive, [entry_id, "panel"], options)
        # Keep existing tokens for unchanged settings to avoid repeated disk writes.
        previous = data.get(BUNDLE)
        if (
            previous is not None
            and previous.get("key_file") == encrypted["key_file"]
            and decode(previous, [entry_id, "panel"]) == sensitive
        ):
            encrypted = previous
        result[BUNDLE] = encrypted
    return result


async def async_prepare_entry(hass, entry, options, manager):
    data = await hass.async_add_executor_job(prepare_config, entry.data, entry.entry_id, options)
    if manager.storage_available or options.get(CONFIGURATION_ENCRYPT_CODES, False) or BUNDLE in entry.data:
        await manager.async_migrate(entry.entry_id, options)
    return data

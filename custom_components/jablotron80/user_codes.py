"""Private, account-scoped PINs. Never expose a PIN as an entity or service data."""

import asyncio
from copy import deepcopy
import re
import time

from .errors import CodeOperationError
from .const import (
    DATA_JABLOTRON,
    DOMAIN,
    CONFIGURATION_CODE_MODE,
    CODE_MODE_COMMON,
    CODE_MODE_PERSONAL,
    CONFIGURATION_REQUIRE_CODE_TO_DISARM,
    CONFIGURATION_ENCRYPT_CODES,
)
from .credentials import decode, encode, read_key

DATA_USER_CODES = "user_codes"


class UserCodeError(CodeOperationError):
    """An error whose fixed message is safe to return to a client."""


class UserCodeManager:
    def __init__(self, hass, store, registry, control_policy):
        self.hass = hass
        self.store = store
        self.registry = registry
        self.control_policy = control_policy
        self._codes = {}
        self._write_lock = asyncio.Lock()
        self._panel_locks = {}
        self._attempts = {}
        self.storage_available = True

    async def async_load(self):
        data = await self.store.async_load()
        if data is not None:
            if not isinstance(data, dict) or not isinstance(data.get("codes"), dict):
                raise UserCodeError("storage_invalid")
            self._codes = data["codes"]

    def _resolve(self, user, entity_id):
        # The caller supplies an authenticated User, never a user_id from input.
        if user is None or not user.is_active or user.system_generated:
            raise UserCodeError("authentication_required")
        if not user.permissions.check_entity(entity_id, self.control_policy):
            raise UserCodeError("permission_denied")
        entry = self.registry.async_get(entity_id)
        if entry is None or entry.platform != DOMAIN or not entity_id.startswith("alarm_control_panel."):
            raise UserCodeError("invalid_entity")
        runtime = self.hass.data.get(DOMAIN, {}).get(entry.config_entry_id)
        if not isinstance(runtime, dict) or DATA_JABLOTRON not in runtime:
            raise UserCodeError("integration_unavailable")
        cu = runtime[DATA_JABLOTRON]
        if not self.storage_available and self._mode(cu) == CODE_MODE_PERSONAL:
            raise UserCodeError("storage_unavailable")
        return entry.config_entry_id, cu

    @staticmethod
    def _mode(cu):
        return (cu._options or {}).get(CONFIGURATION_CODE_MODE, CODE_MODE_COMMON)

    def status(self, user, entity_id):
        entry_id, cu = self._resolve(user, entity_id)
        mode = self._mode(cu)
        saved = user.id in self._codes.get(entry_id, {})
        automatic = (
            saved
            if mode == CODE_MODE_PERSONAL
            else not (cu._options or {}).get(CONFIGURATION_REQUIRE_CODE_TO_DISARM, True)
        )
        return {
            "saved": saved,
            "mode": mode,
            "automatic": automatic,
            "encrypted": bool((cu._options or {}).get(CONFIGURATION_ENCRYPT_CODES, False)),
        }

    async def async_save(self, user, entity_id, code):
        entry_id, cu = self._resolve(user, entity_id)
        if self._mode(cu) != CODE_MODE_PERSONAL:
            raise UserCodeError("personal_codes_disabled")
        if not isinstance(code, str) or re.fullmatch(r"[0-9]{4}", code) is None:
            raise UserCodeError("invalid_code")
        async with self._write_lock:
            updated = deepcopy(self._codes)
            updated.setdefault(entry_id, {})[user.id] = await self.hass.async_add_executor_job(
                encode, code, [entry_id, "user", user.id], cu._options or {}
            )
            await self.store.async_save({"codes": updated})
            self._codes = updated

    async def async_remove(self, user, entity_id):
        entry_id, _ = self._resolve(user, entity_id)
        async with self._write_lock:
            updated = deepcopy(self._codes)
            updated.get(entry_id, {}).pop(user.id, None)
            await self.store.async_save({"codes": updated})
            self._codes = updated

    async def async_disarm(self, user, entity_id):
        entry_id, cu = self._resolve(user, entity_id)
        async with self._panel_locks.setdefault(entry_id, asyncio.Lock()):
            # Recheck authorization and connection after waiting for the lock.
            _, cu = self._resolve(user, entity_id)
            if self._mode(cu) == CODE_MODE_PERSONAL:
                code = await self.hass.async_add_executor_job(
                    decode, self._codes.get(entry_id, {}).get(user.id), [entry_id, "user", user.id]
                )
            else:
                if (cu._options or {}).get(CONFIGURATION_REQUIRE_CODE_TO_DISARM, True):
                    raise UserCodeError("manual_code_required")
                if (cu._options or {}).get(CONFIGURATION_ENCRYPT_CODES, False):
                    from .const import CONFIGURATION_ENCRYPTION_KEY_FILE

                    await self.hass.async_add_executor_job(
                        read_key, cu._options.get(CONFIGURATION_ENCRYPTION_KEY_FILE, "")
                    )
                code = cu._master_code
            if not isinstance(code, str) or re.fullmatch(r"[0-9]{4}", code) is None:
                raise UserCodeError("code_missing")
            state = self.hass.states.get(entity_id)
            if state is None or not cu.connection_alive:
                raise UserCodeError("panel_unavailable")
            if state.state in ("disarmed", "disarming") or (
                cu.zones and all(z.status == "Disarmed" for z in cu.zones)
            ):
                return {"sent": False}
            if state.state not in (
                "armed_home",
                "armed_night",
                "armed_away",
                "arming",
                "pending",
                "triggered",
            ) or any(z.status == "Service" for z in cu.zones):
                raise UserCodeError("invalid_state")
            now = time.monotonic()
            attempts = [t for t in self._attempts.get(entry_id, []) if now - t < 300]
            if attempts and now - attempts[-1] < 15:
                raise UserCodeError("request_pending")
            if len(attempts) >= 3:
                raise UserCodeError("rate_limited")
            attempts.append(now)
            self._attempts[entry_id] = attempts
            # Call the panel directly: no PIN-bearing call_service event/trace.
            # A rejected PIN must not be automatically retried by the serial layer.
            await cu.disarm(code, max_retries=0)
            return {"sent": True}

    async def async_validate_entry(self, entry_id):
        if not self.storage_available:
            raise UserCodeError("storage_unavailable")
        for uid, value in self._codes.get(entry_id, {}).items():
            code = await self.hass.async_add_executor_job(decode, value, [entry_id, "user", uid])
            if not isinstance(code, str) or re.fullmatch(r"[0-9]{4}", code) is None:
                raise UserCodeError("stored_code_invalid")

    async def async_migrate(self, entry_id, options):
        # Per-record key paths let a restart recover from an interrupted multi-file
        # migration. Old and new records remain independently decryptable.
        async with self._write_lock:
            await self.async_validate_entry(entry_id)
            updated = deepcopy(self._codes)
            for uid, value in updated.get(entry_id, {}).items():
                context = [entry_id, "user", uid]
                code = await self.hass.async_add_executor_job(decode, value, context)
                encrypted = await self.hass.async_add_executor_job(encode, code, context, options)
                if (
                    isinstance(value, dict)
                    and isinstance(encrypted, dict)
                    and value["key_file"] == encrypted["key_file"]
                ):
                    encrypted = value
                updated[entry_id][uid] = encrypted
            if updated != self._codes:
                await self.store.async_save({"codes": updated})
                self._codes = updated

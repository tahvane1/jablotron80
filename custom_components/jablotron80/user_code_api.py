"""Authenticated APIs: PIN writes via HTTP, secret-free status/disarm via WS."""

import voluptuous as vol
import logging

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .credentials import CredentialError
from .const import DOMAIN
from .user_codes import DATA_USER_CODES, UserCodeError, UserCodeManager


class UserCodeView(HomeAssistantView):
    url = "/api/jablotron80/user_code"
    name = "api:jablotron80:user_code"
    requires_auth = True

    def __init__(self, manager):
        self.manager = manager

    async def post(self, request):
        # No caller-controlled user_id, no GET/read-back route, no body logging.
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise UserCodeError("Neplatný požadavek.")
            operation = data.get("operation")
            allowed = (
                {"entity_id", "operation", "code"} if operation == "save" else {"entity_id", "operation"}
            )
            if set(data) - allowed or not isinstance(data.get("entity_id"), str):
                raise UserCodeError("Neplatný požadavek.")
            user = await self.manager.hass.auth.async_get_user(request["hass_user"].id)
            if operation == "save":
                await self.manager.async_save(user, data["entity_id"], data.get("code"))
            elif operation == "remove":
                await self.manager.async_remove(user, data["entity_id"])
            else:
                raise UserCodeError("Neplatná operace.")
            return self.json({"saved": operation == "save"})
        except (UserCodeError, CredentialError) as err:
            return self.json({"message": str(err)}, status_code=400)
        except Exception:
            # Never format an exception containing a request body or PIN.
            return self.json({"message": "Osobní kód se nepodařilo uložit."}, status_code=500)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "jablotron80/user_code/status",
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def ws_status(hass, connection, msg):
    manager = hass.data[DOMAIN][DATA_USER_CODES]
    try:
        user = await hass.auth.async_get_user(connection.user.id)
        connection.send_result(msg["id"], manager.status(user, msg["entity_id"]))
    except (UserCodeError, CredentialError) as err:
        connection.send_error(msg["id"], "user_code_error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "jablotron80/user_code/disarm",
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def ws_disarm(hass, connection, msg):
    manager = hass.data[DOMAIN][DATA_USER_CODES]
    try:
        user = await hass.auth.async_get_user(connection.user.id)
        result = await manager.async_disarm(user, msg["entity_id"])
    except (UserCodeError, CredentialError) as err:
        connection.send_error(msg["id"], "user_code_error", str(err))
        return
    except Exception:
        connection.send_error(msg["id"], "user_code_error", "Požadavek se nepodařilo odeslat.")
        return
    if result["sent"]:
        hass.bus.async_fire(
            "jablotron80_saved_code_disarm_requested",
            {"entity_id": msg["entity_id"]},
            context=connection.context(msg),
        )
    connection.send_result(msg["id"], result)


async def async_setup_user_codes(hass):
    if DATA_USER_CODES in hass.data[DOMAIN]:
        return
    # HA's private Store uses owner-only permissions (0600); atomic writes.
    store = Store(hass, 1, "jablotron80.user_codes", private=True, atomic_writes=True)
    manager = UserCodeManager(hass, store, er.async_get(hass), POLICY_CONTROL)
    try:
        await manager.async_load()
    except Exception:
        # Keep the normal alarm integration working, but never overwrite a
        # damaged private store or print its contents in a traceback.
        manager.storage_available = False
        logging.getLogger(__name__).error("Osobní kódy nelze načíst; použijte ruční PIN.")
    hass.data[DOMAIN][DATA_USER_CODES] = manager
    hass.http.register_view(UserCodeView(manager))
    websocket_api.async_register_command(hass, ws_status)
    websocket_api.async_register_command(hass, ws_disarm)

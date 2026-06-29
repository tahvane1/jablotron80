"""Logbook descriptions for jablotron80 events.

#83/#98 follow-up: render the ``jablotron_code_used`` event as a logbook entry,
linked to the code's ``binary_sensor`` entity so each code gets its own usage
history (alongside the ``last_used`` attribute). Home Assistant's logbook
integration auto-discovers this platform and calls ``async_describe_events``.
"""

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, EVENT_CODE_USED


@callback
def async_describe_events(hass: HomeAssistant, async_describe_event) -> None:
    """Describe jablotron80 logbook events."""

    @callback
    def async_describe_code_used(event):
        data = event.data
        # Prefer the entity_id carried on the event: the integration sets it so HA
        # links the recorded event to the code's binary_sensor (the entity-scoped
        # "Activity" filters on it). Fall back to resolving it from the unique_id.
        entity_id = data.get("entity_id")
        if not entity_id:
            unique_id = data.get("unique_id")
            if unique_id:
                entity_id = er.async_get(hass).async_get_entity_id("binary_sensor", DOMAIN, unique_id)
        # #83 follow-up: distinguish what the code was used for, when the integration
        # knows it. arm/disarm come from different event paths; other code uses
        # (e.g. panic/tamper) carry no action and stay the plain "was used".
        action = data.get("action")
        if action == "arm":
            message = "was used to arm"
        elif action == "disarm":
            message = "was used to disarm"
        else:
            message = "was used"
        return {
            LOGBOOK_ENTRY_NAME: data.get("name") or "Code",
            LOGBOOK_ENTRY_MESSAGE: message,
            LOGBOOK_ENTRY_ENTITY_ID: entity_id,
        }

    async_describe_event(DOMAIN, EVENT_CODE_USED, async_describe_code_used)

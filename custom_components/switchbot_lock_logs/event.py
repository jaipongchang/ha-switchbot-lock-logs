"""Event platform for SwitchBot Lock Logs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.event import EventEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Event

from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, CONF_MAC_ADDRESS, SWITCHBOT_DOMAIN
from .models import EVENT_TYPES

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SwitchBotLockLogsConfigEntry
    from .lock_log_manager import SwitchBotLockLogManager


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SwitchBotLockLogsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the lock log event entity."""
    log_manager = entry.runtime_data.log_manager
    device_id = entry.data[CONF_DEVICE_ID]
    device_name = entry.data[CONF_DEVICE_NAME]
    mac_address = entry.data[CONF_MAC_ADDRESS]

    async_add_entities(
        [SwitchBotLockLogEventEntity(log_manager, device_id, device_name, mac_address)]
    )


class SwitchBotLockLogEventEntity(EventEntity):
    """Fires one event per lock log entry batch (newest shown)."""

    _attr_has_entity_name = True
    _attr_translation_key = "lock_log"

    def __init__(
        self,
        log_manager: SwitchBotLockLogManager,
        device_id: str,  # noqa: ARG002
        device_name: str,  # noqa: ARG002
        mac_address: str,
    ) -> None:
        """Initialize the event entity."""
        self._log_manager = log_manager
        self._attr_unique_id = f"{mac_address}-lock_log"
        self._attr_event_types = EVENT_TYPES
        self._attr_device_info = DeviceInfo(
            identifiers={(SWITCHBOT_DOMAIN, mac_address)},
        )

    async def async_added_to_hass(self) -> None:
        """Register for log updates."""
        self.async_on_remove(
            self._log_manager.async_add_listener(self._handle_log_update)
        )

    @callback
    def _handle_log_update(self) -> None:
        """Handle log update notification."""
        if not (latest := self._log_manager.latest_log):
            return
        action_name: str = latest.get("action_name", "unknown")
        self._attr_event = Event(
            event_type=action_name if action_name in EVENT_TYPES else "unknown",
            data={
                k: latest.get(k)
                for k in (
                    "user_id",
                    "user_name",
                    "action_code",
                    "action_name",
                    "source_code",
                    "source_name",
                    "payload",
                    "timestamp",
                    "raw_timestamp",
                )
            },
        )
        self.async_write_ha_state()

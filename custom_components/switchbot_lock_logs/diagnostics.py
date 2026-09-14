"""Diagnostics for SwitchBot Lock Logs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import CONF_MAC_ADDRESS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import SwitchBotLockLogsConfigEntry

TO_REDACT = {CONF_MAC_ADDRESS, "mac", "user_name"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SwitchBotLockLogsConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    manager = entry.runtime_data.log_manager
    data: dict[str, Any] = {
        "entry": {"data": dict(entry.data), "options": dict(entry.options)},
        "model": manager.model,
        "clock_offset": manager.effective_clock_offset,
        "history_size": len(manager.history_entries),
        "latest_log": async_redact_data(manager.latest_log or {}, TO_REDACT),
    }
    return async_redact_data(data, TO_REDACT)

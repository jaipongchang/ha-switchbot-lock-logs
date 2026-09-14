"""Lock log fetching and enrichment for SwitchBot locks."""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import Enum
from typing import Any

from homeassistant.core import HomeAssistant, callback
from switchbot import SwitchbotLock

try:
    from switchbot.const import LockLogAction, LockLogSource
except ImportError:

    class LockLogSource(Enum):
        """Compatibility fallback for pySwitchbot versions without LockLogSource."""

        APP = 0
        KEYPAD = 1
        MANUAL = 2
        AUTO_LOCK = 3
        NFC = 4
        REMOTE = 5
        FINGERPRINT = 6

    class LockLogAction(Enum):
        """Compatibility fallback for pySwitchbot versions without LockLogAction."""

        LOCKED = 0
        UNLOCKED = 1
        JAMMED = 2
        UNLOCK_FAILED = 3
        LOCK_FAILED = 4

from .const import EVENT_LOCK_LOG_ENTRY, LOGGER
from .history import CalibrationStore, HistoryStore
from .models import enrich_log
from .storage import SwitchBotLockUserStore

COMMAND_LOCK_LOG_BASE_TIME = "57001401"
COMMAND_READ_LOCK_LOG = "57001405"
COMMAND_RESULT_EXPECTED_VALUES = {1, 6}


async def _compat_get_logs(
    lock_device: SwitchbotLock,
    base_time: int = 0,
    max_entries: int = 20,
) -> list[dict[str, Any]] | None:
    """Read lock logs on pySwitchbot versions without get_logs()."""
    timestamp_bytes = base_time.to_bytes(4, "big").hex()
    base_cmd = COMMAND_LOCK_LOG_BASE_TIME + timestamp_bytes

    result = await lock_device._send_command(base_cmd)

    if (
        not result
        or not lock_device._check_command_result(
            result,
            0,
            COMMAND_RESULT_EXPECTED_VALUES,
        )
    ):
        LOGGER.warning("Failed to set lock log base time")
        return None

    logs: list[dict[str, Any]] = []

    for index in range(max_entries):
        result = await lock_device._send_command(COMMAND_READ_LOCK_LOG)

        if (
            not result
            or not lock_device._check_command_result(
                result,
                0,
                COMMAND_RESULT_EXPECTED_VALUES,
            )
        ):
            LOGGER.debug("Failed to read lock log entry %d", index)
            break

        data = result[1:]

        if not data:
            break
        if not any(byte != 0 for byte in data):
            break
        if len(data) < 8:
            LOGGER.warning("Lock log entry too short: %s", data.hex())
            continue

        logs.append(
            {
                "timestamp": int.from_bytes(data[0:4], "big"),
                "index": data[4],
                "source": data[5],
                "action": data[6],
                "value": data[7],
                "payload": data[8:].hex() if len(data) > 8 else "",
            }
        )

    return logs


class SwitchBotLockLogManager:
    """Manage lock logs for a single lock device."""

    def __init__(  # noqa: PLR0913
        self,
        hass: HomeAssistant,
        lock_device: SwitchbotLock,
        mac: str,
        user_store: SwitchBotLockUserStore,
        *,
        model: str = "lock",
        history_store: HistoryStore,
        calibration_store: CalibrationStore,
        history_cap: int = 500,
        manual_clock_offset: int | None = None,
    ) -> None:
        """Initialize the log manager."""
        self._hass = hass
        self._lock_device = lock_device
        self._mac = mac
        self._user_store = user_store
        self._model = model
        self._history_store = history_store
        self._history_buffer = (
            history_store.get_buffer(mac, history_cap) if history_cap > 0 else None
        )
        self._calibration_store = calibration_store
        self._tracker = calibration_store.get_tracker(mac)
        self._manual_clock_offset = manual_clock_offset
        self._latest_logs: list[dict[str, Any]] = []
        self._listeners: list[Callable[[], None]] = []

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """
        Add a listener to be notified of log updates.

        Returns a function to remove the listener.
        """
        self._listeners.append(listener)

        def remove_listener() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove_listener

    @callback
    def _notify_listeners(self) -> None:
        """Notify all listeners of log update."""
        for listener in self._listeners:
            listener()

    async def async_fetch_logs(
        self,
        base_time: int = 0,
        max_entries: int = 10,
        *,
        trigger: str = "manual",
    ) -> list[dict[str, Any]]:
        """
        Fetch logs from device and enrich with user names.

        Returns all logs without filtering. Filtering for sensor updates
        is handled by the sensor itself.

        This method handles BLE errors gracefully and returns cached logs
        if the fetch fails.
        """
        LOGGER.debug("Fetching logs for %s", self._mac)

        try:
            native_get_logs = getattr(self._lock_device, "get_logs", None)
            if callable(native_get_logs):
                logs = await native_get_logs(base_time, max_entries)
            else:
                logs = await _compat_get_logs(
                    self._lock_device, base_time, max_entries
                )
        except Exception as err:
            LOGGER.warning(
                "Failed to fetch logs for %s: %s. Returning cached logs.",
                self._mac,
                err,
            )
            return self._latest_logs.copy()

        if not logs:
            LOGGER.debug("No logs retrieved for %s", self._mac)
            return []

        LOGGER.debug("Retrieved %d logs for %s", len(logs), self._mac)

        enriched_logs = await self._enrich_logs(logs)

        if (
            trigger == "state_change"
            and enriched_logs
            and self._tracker.add_sample(
                time.time(), enriched_logs[0]["raw_timestamp"]
            )
        ):
            await self._calibration_store.async_set_tracker(self._mac, self._tracker)

        new_entries: list[dict[str, Any]] = []
        if self._history_buffer is not None:
            new_entries = self._history_buffer.append(enriched_logs)
            await self._history_store.async_save(self._mac)
        else:
            new_entries = enriched_logs

        for entry in new_entries:
            self._hass.bus.async_fire(
                EVENT_LOCK_LOG_ENTRY,
                {
                    **entry,
                    "mac": self._mac,
                    "device_name": self._lock_device.name,
                },
            )

        self._latest_logs = enriched_logs
        self._notify_listeners()

        return enriched_logs

    async def _enrich_logs(self, logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Enrich raw logs with decoding, user names, corrected timestamps."""
        users = await self._user_store.async_get_users(self._mac)
        return [
            enrich_log(
                log,
                model=self._model,
                users=users,
                clock_offset=self.effective_clock_offset,
            )
            for log in logs
        ]

    @property
    def effective_clock_offset(self) -> int | None:
        """Manual override wins over learned offset."""
        return (
            self._manual_clock_offset
            if self._manual_clock_offset is not None
            else self._tracker.offset()
        )

    @property
    def model(self) -> str:
        """Get the lock model."""
        return self._model

    @property
    def history_entries(self) -> list[dict[str, Any]]:
        """Get all history-buffer entries."""
        return self._history_buffer.entries if self._history_buffer else []

    @property
    def latest_log(self) -> dict[str, Any] | None:
        """Get the most recent log entry."""
        return self._latest_logs[0] if self._latest_logs else None

    @property
    def latest_logs(self) -> list[dict[str, Any]]:
        """Get all cached logs."""
        return self._latest_logs.copy()

    @property
    def mac(self) -> str:
        """Get the MAC address."""
        return self._mac

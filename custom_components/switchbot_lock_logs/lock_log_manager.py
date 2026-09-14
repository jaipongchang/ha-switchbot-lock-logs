"""Lock log fetching and enrichment for SwitchBot locks."""

from __future__ import annotations

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

from .const import LOGGER
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

    def __init__(
        self,
        hass: HomeAssistant,
        lock_device: SwitchbotLock,
        mac: str,
        user_store: SwitchBotLockUserStore,
    ) -> None:
        """Initialize the log manager."""
        self._hass = hass
        self._lock_device = lock_device
        self._mac = mac
        self._user_store = user_store
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
        self, base_time: int = 0, max_entries: int = 10
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
        self._latest_logs = enriched_logs
        self._notify_listeners()

        return enriched_logs

    async def _enrich_logs(self, logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Add user names and human-readable fields to logs."""
        users = await self._user_store.async_get_users(self._mac)

        enriched = []
        for log in logs:
            user_id = self._extract_user_id(log.get("payload", ""))

            if user_id is not None and str(user_id) in users:
                user_name = users[str(user_id)]
            else:
                user_name = None

            try:
                source_name = LockLogSource(log["source"]).name
                source_display = source_name.replace("_", " ").title()
            except (ValueError, KeyError):
                source_display = f"Unknown (Source {log.get('source', '?')})"

            try:
                action_name = LockLogAction(log["action"]).name.lower()
            except (ValueError, KeyError):
                action_name = f"unknown_{log.get('action', '?')}"

            enriched_log = {
                **log,
                "user_id": user_id,
                "user_name": user_name,
                "source_display": source_display,
                "action_name": action_name,
            }
            enriched.append(enriched_log)

        return enriched

    @staticmethod
    def _extract_user_id(payload: str) -> int | None:
        """
        Extract user ID from log payload.

        Payload formats:
        - 59 03 XX YY 00 00 (hex string) - Type 3 pattern
        - 59 01 XX YY 00 00 (hex string) - Type 1 pattern
        Where XX (byte 2) is the user ID.
        """
        if not payload or len(payload) < 6:
            return None

        try:
            if payload[0:2] == "59" and payload[2:4] in ("01", "03"):
                user_id = int(payload[4:6], 16)
                return user_id if user_id > 0 else None
            # SwitchBot Lock Ultra: first byte varies per device (seen: 2b, 31),
            # method at byte 1 (01/03/06), user id at byte 2. GH issue #3.
            if payload[0:2] != "59" and payload[2:4] in ("01", "03", "06"):
                user_id = int(payload[4:6], 16)
                return user_id if user_id > 0 else None
        except (ValueError, IndexError):
            pass

        return None

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

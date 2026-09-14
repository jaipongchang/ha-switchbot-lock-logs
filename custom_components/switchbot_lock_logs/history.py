"""Persistent per-lock log history and clock calibration stores."""

from __future__ import annotations

from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .clock import ClockOffsetTracker

STORAGE_KEY_HISTORY: Final = "switchbot_lock_logs_history"
STORAGE_KEY_CALIBRATION: Final = "switchbot_lock_logs_calibration"
STORAGE_VERSION: Final = 1

def _key(entry: dict[str, Any]) -> tuple[int, int, str]:
    return (int(entry.get("timestamp", 0)), int(entry.get("action", 0)), str(entry.get("payload", "")))

class HistoryBuffer:
    """Newest-first ring buffer with (timestamp, action, payload) dedup. Pure."""

    def __init__(self, cap: int, initial: list[dict[str, Any]] | None = None) -> None:
        self._cap = cap
        self._entries: list[dict[str, Any]] = []
        self._seen: set[tuple[int, int, str]] = set()
        for entry in sorted(initial or [], key=lambda e: e.get("timestamp", 0), reverse=True):
            self._insert(entry)

    def _insert(self, entry: dict[str, Any]) -> None:
        k = _key(entry)
        if k in self._seen:
            return
        self._seen.add(k)
        self._entries.insert(0, dict(entry))
        if len(self._entries) > self._cap:
            dropped = self._entries.pop()
            self._seen.discard(_key(dropped))

    def append(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Insert newest-first batch; return only entries not seen before."""
        new = [e for e in entries if _key(e) not in self._seen]
        for entry in sorted(new, key=lambda e: e.get("timestamp", 0)):
            self._insert(entry)
        return [e for e in self._entries if _key(e) in {_key(n) for n in new}]

    @property
    def entries(self) -> list[dict[str, Any]]:
        return [dict(e) for e in self._entries]

    def __len__(self) -> int:
        return len(self._entries)

class HistoryStore:
    """Persists per-MAC HistoryBuffers in HA storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY_HISTORY)
        self._data: dict[str, list[dict[str, Any]]] = {}
        self._buffers: dict[str, HistoryBuffer] = {}

    async def async_load(self) -> None:
        self._data = await self._store.async_load() or {}

    def get_buffer(self, mac: str, cap: int) -> HistoryBuffer:
        if mac not in self._buffers:
            self._buffers[mac] = HistoryBuffer(cap, self._data.get(mac, []))
        return self._buffers[mac]

    async def async_save(self, mac: str) -> None:
        self._data[mac] = self._buffers[mac].entries
        await self._store.async_save(self._data)

class CalibrationStore:
    """Persists clock offset samples and manual overrides per MAC."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY_CALIBRATION)
        self._data: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> None:
        self._data = await self._store.async_load() or {}

    def get_tracker(self, mac: str) -> ClockOffsetTracker:
        return ClockOffsetTracker(self._data.get(mac, {}).get("samples", []))

    def get_manual_offset(self, mac: str) -> int | None:
        return self._data.get(mac, {}).get("manual_offset")

    async def async_set_tracker(self, mac: str, tracker: ClockOffsetTracker) -> None:
        self._data.setdefault(mac, {})["samples"] = tracker.samples
        await self._store.async_save(self._data)

    async def async_set_manual_offset(self, mac: str, seconds: int | None) -> None:
        self._data.setdefault(mac, {})["manual_offset"] = seconds
        await self._store.async_save(self._data)

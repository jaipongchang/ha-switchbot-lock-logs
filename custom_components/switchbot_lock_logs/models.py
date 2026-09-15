"""Model-aware decoding and enrichment for SwitchBot lock logs (pure logic)."""

from __future__ import annotations

from typing import Any, Final

MODEL_ULTRA: Final = "lock_ultra"
CLASSIC_MODELS: Final = {"lock", "lock_pro", "lock_lite"}

# Lock Ultra action codes (observed 2026-09-14 on live device + GH issue #3).
# Lock Ultra action codes — calibrated 2026-09-14 on live Lock Ultra 1CC5.
# Note: failed keypad attempts are NOT written to the device's BLE log history.
ULTRA_ACTION_MAP: Final[dict[int, str]] = {
    0: "auto_lock",
    15: "unlock",
    18: "lock",
    22: "lock",
    128: "lock",
}
# Lock Ultra source codes — raw ints observed; labels unreliable pre-calibration.
# Lock Ultra source codes — calibrated: 1=manual thumbturn, 2=keypad/biometric,
# 3=system (auto-lock).
ULTRA_SOURCE_MAP: Final[dict[int, str]] = {
    1: "manual",
    2: "keypad",
    3: "system",
}

_CLASSIC_CACHE: dict[str, dict[int, str]] = {}
_MIN_PAYLOAD_LEN: Final = 6


def _classic_enums(domain: str) -> dict[int, str]:
    """Map classic-model enum values to lowercase names (lazy optional import)."""
    if domain not in _CLASSIC_CACHE:
        try:
            if domain == "action":
                # lazy optional pySwitchbot import
                from switchbot.const import LockLogAction as ActionEnum  # noqa: PLC0415
            else:
                # lazy optional pySwitchbot import
                from switchbot.const import LockLogSource as SourceEnum  # noqa: PLC0415
            chosen = ActionEnum if domain == "action" else SourceEnum
            _CLASSIC_CACHE[domain] = {int(e.value): e.name.lower() for e in chosen}
        except Exception:  # noqa: BLE001  (pySwitchbot may lack these enums entirely)
            _CLASSIC_CACHE[domain] = {}
    return _CLASSIC_CACHE[domain]


def extract_user_id(payload: str) -> int | None:
    """User id at payload byte 2; method byte 1 (01/03/06); byte 0 varies on Ultra."""
    if not payload or len(payload) < _MIN_PAYLOAD_LEN:
        return None
    try:
        if payload[0:2] == "59" and payload[2:4] in ("01", "03"):
            user_id = int(payload[4:6], 16)
            return user_id if user_id > 0 else None
        if payload[0:2] != "59" and payload[2:4] in ("01", "03", "06"):
            user_id = int(payload[4:6], 16)
            return user_id if user_id > 0 else None
    except (ValueError, IndexError):
        pass
    return None


def decode_action(model: str, code: int) -> str:
    """Return a stable event name for an action code, per model family."""
    if model == MODEL_ULTRA:
        return ULTRA_ACTION_MAP.get(code, f"unknown_{code}")
    return _classic_enums("action").get(code, f"unknown_{code}")


def decode_source(model: str, code: int) -> str:
    """Return a stable source name for a source code, per model family."""
    if model == MODEL_ULTRA:
        return ULTRA_SOURCE_MAP.get(code, f"unknown_{code}")
    return _classic_enums("source").get(code, f"unknown_{code}")


def enrich_log(
    log: dict[str, Any],
    *,
    model: str,
    users: dict[str, str],
    clock_offset: int | None,
    source_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a copy of log with decoded names, codes, corrected timestamp."""
    raw_ts = int(log.get("timestamp", 0))
    user_id = extract_user_id(log.get("payload", ""))
    action_code = int(log.get("action", 0))
    source_code = int(log.get("source", 0))
    overrides = source_overrides or {}
    source_name = overrides.get(str(source_code)) or decode_source(model, source_code)
    return {
        **log,
        "timestamp": raw_ts + clock_offset if clock_offset else raw_ts,
        "raw_timestamp": raw_ts,
        "user_id": user_id,
        "user_name": users.get(str(user_id)) if user_id is not None else None,
        "action_code": action_code,
        "action_name": decode_action(model, action_code),
        "source_code": source_code,
        "source_name": source_name,
        "source_display": source_name.replace("_", " ").title(),
        "payload": log.get("payload", ""),
    }


EVENT_TYPES: Final[list[str]] = sorted(
    {
        "auto_lock",
        "lock",
        "unlock",
        # failed_attempt reserved: not written to device BLE log (see README/issue)
        "failed_attempt",
        "unknown",
    }
    | set(ULTRA_ACTION_MAP.values())
)

"""tests/test_models.py"""

from switchbot_lock_logs.models import (
    EVENT_TYPES,
    MODEL_ULTRA,
    ULTRA_ACTION_MAP,
    decode_action,
    decode_source,
    enrich_log,
    extract_user_id,
)

PAYLOADS = {  # captured from live Lock Ultra + GH issue #3 + classic
    "ultra_user_10": "31030a000000",
    "ultra_user_11": "31010b010000",
    "ultra_nouser": "310000000000",
    "ultra_issue3_a": "2b010b010000",
    "ultra_issue3_b": "2b030a000000",
    "ultra_issue3_fp": "2b0600000000",
    "system_zero": "000000000000",
    "classic": "59031f0000",
}


def test_extract_user_id_known_payloads():
    assert extract_user_id(PAYLOADS["ultra_user_10"]) == 10
    assert extract_user_id(PAYLOADS["ultra_user_11"]) == 11
    assert extract_user_id(PAYLOADS["ultra_issue3_a"]) == 11
    assert extract_user_id(PAYLOADS["ultra_issue3_b"]) == 10
    assert extract_user_id(PAYLOADS["classic"]) == 31


def test_extract_user_id_none_cases():
    for key in ("ultra_nouser", "ultra_issue3_fp", "system_zero"):
        assert extract_user_id(PAYLOADS[key]) is None
    assert extract_user_id("") is None
    assert extract_user_id("3103") is None


def test_decode_action_ultra_and_fallback():
    assert decode_action(MODEL_ULTRA, 15) == "unlock"
    assert decode_action(MODEL_ULTRA, 999) == "unknown_999"
    assert decode_action("lock", 999) == "unknown_999"


def test_decode_source_fallback():
    assert decode_source(MODEL_ULTRA, 999) == "unknown_999"


def test_enrich_log_full_shape():
    log = {
        "timestamp": 1789383726,
        "action": 15,
        "source": 2,
        "payload": PAYLOADS["ultra_user_10"],
    }
    out = enrich_log(log, model=MODEL_ULTRA, users={"10": "Alice"}, clock_offset=195)
    assert out["user_id"] == 10 and out["user_name"] == "Alice"
    assert out["action_code"] == 15 and out["action_name"] == "unlock"
    assert out["source_code"] == 2 and isinstance(out["source_name"], str)
    assert out["raw_timestamp"] == 1789383726 and out["timestamp"] == 1789383921
    assert out["payload"] == PAYLOADS["ultra_user_10"]


def test_enrich_log_no_offset_no_user():
    log = {"timestamp": 5, "action": 0, "source": 0, "payload": PAYLOADS["system_zero"]}
    out = enrich_log(log, model=MODEL_ULTRA, users={}, clock_offset=None)
    assert out["timestamp"] == 5 and out["user_name"] is None


def test_event_types_covered():
    assert "unlock" in EVENT_TYPES
    assert "unknown" in EVENT_TYPES
    assert "failed_attempt" in EVENT_TYPES
    assert set(ULTRA_ACTION_MAP.values()) <= set(EVENT_TYPES)

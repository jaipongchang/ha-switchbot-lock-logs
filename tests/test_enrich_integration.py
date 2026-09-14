"""tests/test_enrich_integration.py — pure composition used by the manager."""

from switchbot_lock_logs.clock import ClockOffsetTracker
from switchbot_lock_logs.history import HistoryBuffer
from switchbot_lock_logs.models import MODEL_ULTRA, enrich_log

RAW = [
    {"timestamp": 1789383726, "action": 15, "source": 2, "payload": "31030a000000"},
    {"timestamp": 1789383717, "action": 15, "source": 1, "payload": "310000000000"},
]


def simulate_fetch(raw_logs, users, tracker, buf):
    offset = tracker.offset()
    enriched = [
        enrich_log(entry, model=MODEL_ULTRA, users=users, clock_offset=offset)
        for entry in raw_logs
    ]
    return buf.append(enriched), enriched


def test_first_fetch_all_new_second_fetch_dedup():
    buf = HistoryBuffer(cap=100)
    tracker = ClockOffsetTracker()
    new1, enriched1 = simulate_fetch(RAW, {"10": "Alice"}, tracker, buf)
    assert len(new1) == 2 and enriched1[0]["user_name"] == "Alice"
    new2, _ = simulate_fetch(RAW, {"10": "Alice"}, tracker, buf)
    assert new2 == []


def test_offset_applied_once_learned():
    buf = HistoryBuffer(cap=100)
    tracker = ClockOffsetTracker([195])  # pre-learned offset
    _new, enriched = simulate_fetch(RAW[:1], {}, tracker, buf)
    assert enriched[0]["raw_timestamp"] == 1789383726
    assert enriched[0]["timestamp"] == 1789383726 + 195

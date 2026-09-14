"""tests/test_history.py"""
from switchbot_lock_logs.history import HistoryBuffer

ENTRY_A = {"timestamp": 100, "action": 15, "payload": "31030a000000"}
ENTRY_B = {"timestamp": 200, "action": 128, "payload": "000000000000"}
ENTRY_C = {"timestamp": 300, "action": 15, "payload": "31010b010000"}

def test_append_returns_only_new():
    buf = HistoryBuffer(cap=10)
    assert buf.append([ENTRY_B, ENTRY_A]) == [ENTRY_B, ENTRY_A]
    assert buf.append([ENTRY_A, ENTRY_C]) == [ENTRY_C]
    assert len(buf) == 3

def test_newest_first():
    buf = HistoryBuffer(cap=10)
    buf.append([ENTRY_A, ENTRY_B])
    assert [e["timestamp"] for e in buf.entries] == [200, 100]

def test_ring_cap():
    buf = HistoryBuffer(cap=2)
    for e in (ENTRY_A, ENTRY_B, ENTRY_C):
        buf.append([e])
    assert len(buf) == 2
    assert [e["timestamp"] for e in buf.entries] == [300, 200]

def test_dedup_after_restore():
    buf = HistoryBuffer(cap=10, initial=[ENTRY_A])
    assert buf.append([ENTRY_A]) == []

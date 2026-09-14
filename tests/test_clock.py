"""tests/test_clock.py"""

from switchbot_lock_logs.clock import ClockOffsetTracker


def test_rejects_impossible_samples():
    t = ClockOffsetTracker()
    assert t.add_sample(1000.0, 1005.0) is False  # log from the future
    assert t.add_sample(4000.0, 0.0) is False  # stale (4e3 s old, > MAX_VALID)
    assert t.offset() is None


def test_median_of_samples():
    t = ClockOffsetTracker()
    for fetch, log in [(100.0, 0.0), (200.0, 0.0), (300.0, 0.0)]:
        t.add_sample(fetch, log)  # samples 100, 200, 300
    assert t.offset() == 200


def test_ring_of_five():
    t = ClockOffsetTracker([10, 20, 30, 40, 50])
    t.add_sample(1000.0, 900.0)  # sample 100 evicts 10
    assert t.samples[-1] == 100 and len(t.samples) == 5
    assert t.offset() == 40  # median of 20,30,40,50,100


def test_offset_empty():
    assert ClockOffsetTracker().offset() is None

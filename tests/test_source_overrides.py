"""Tests for per-lock source overrides."""

from switchbot_lock_logs.models import enrich_log

BASE = {"timestamp": 100, "action": 18, "source": 3, "payload": "000000000000"}


def test_override_wins_over_global_map():
    out = enrich_log(
        BASE,
        model="lock_ultra",
        users={},
        clock_offset=None,
        source_overrides={"3": "Manual"},
    )
    assert out["source_name"] == "Manual"
    assert out["source_display"] == "Manual"


def test_no_override_falls_back():
    out = enrich_log(BASE, model="lock_ultra", users={}, clock_offset=None)
    assert out["source_name"] == "system"
    assert out["source_display"] == "System"

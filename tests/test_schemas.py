"""Tests for voluptuous service schemas in const.py (HA-free)."""

import pytest
import voluptuous as vol
from switchbot_lock_logs.const import (
    DELETE_LOCK_USER_NAME_SCHEMA,
    GET_LOCK_LOGS_SCHEMA,
    SET_LOCK_USER_NAME_SCHEMA,
)


def test_get_lock_logs_valid_and_defaults():
    out = GET_LOCK_LOGS_SCHEMA({"device_id": "abc"})
    assert out["max_entries"] == 20
    assert out["base_time"] == 0
    assert out["include_history"] is False


def test_get_lock_logs_rejects():
    with pytest.raises(vol.Invalid):
        GET_LOCK_LOGS_SCHEMA({"device_id": 123})  # non-str id
    with pytest.raises(vol.Invalid):
        GET_LOCK_LOGS_SCHEMA({"device_id": "a", "max_entries": 0})  # below min
    with pytest.raises(vol.Invalid):
        GET_LOCK_LOGS_SCHEMA({"device_id": "a", "max_entries": 101})  # above max
    with pytest.raises(vol.Invalid):
        GET_LOCK_LOGS_SCHEMA({"device_id": "a", "base_time": -1})  # negative
    with pytest.raises(vol.Invalid):
        GET_LOCK_LOGS_SCHEMA({"device_id": "a", "base_time": 2**32})  # uint32 overflow
    with pytest.raises(vol.Invalid):
        GET_LOCK_LOGS_SCHEMA({})  # missing device_id


def test_include_history_rejects_strings():
    # vol.Boolean() rejects user-supplied strings like "yes"/"true".
    with pytest.raises(vol.Invalid):
        GET_LOCK_LOGS_SCHEMA({"device_id": "a", "include_history": "yes"})
    with pytest.raises(vol.Invalid):
        GET_LOCK_LOGS_SCHEMA({"device_id": "a", "include_history": "true"})


def test_set_user_name():
    out = SET_LOCK_USER_NAME_SCHEMA(
        {"device_id": "a", "user_id": 10, "name": "  Alice "}
    )
    assert out["name"] == "Alice"
    for bad in [
        {"device_id": "a", "user_id": 256, "name": "x"},  # >255
        {"device_id": "a", "user_id": -1, "name": "x"},  # <0
        {"device_id": "a", "user_id": 10, "name": "   "},  # blank
        {"device_id": "a", "user_id": 10, "name": "x" * 65},  # too long
    ]:
        with pytest.raises(vol.Invalid):
            SET_LOCK_USER_NAME_SCHEMA(bad)


def test_delete_user_name():
    out = DELETE_LOCK_USER_NAME_SCHEMA({"device_id": "a", "user_id": 0})
    assert out["user_id"] == 0

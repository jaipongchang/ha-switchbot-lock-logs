"""Constants for the SwitchBot Lock Logs integration."""

from __future__ import annotations

import logging
from typing import Final

import voluptuous as vol

DOMAIN: Final = "switchbot_lock_logs"
LOGGER = logging.getLogger(__package__)

# Core SwitchBot integration domain
SWITCHBOT_DOMAIN: Final = "switchbot"

# Config entry data keys
CONF_DEVICE_ID: Final = "device_id"
CONF_DEVICE_NAME: Final = "device_name"
CONF_MAC_ADDRESS: Final = "mac_address"

# Lock Log Defaults
DEFAULT_LOCK_LOG_MAX_ENTRIES: Final = 20

# Services
SERVICE_GET_LOCK_LOGS: Final = "get_lock_logs"
SERVICE_SET_LOCK_USER_NAME: Final = "set_lock_user_name"
SERVICE_DELETE_LOCK_USER_NAME: Final = "delete_lock_user_name"

GET_LOCK_LOGS_SCHEMA: Final = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Optional("max_entries", default=DEFAULT_LOCK_LOG_MAX_ENTRIES): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Optional("base_time", default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=4294967295)
        ),
        vol.Optional("include_history", default=False): bool,
    }
)

SET_LOCK_USER_NAME_SCHEMA: Final = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("user_id"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        vol.Required("name"): vol.All(
            str, lambda s: s.strip(), vol.Length(min=1, max=64)
        ),
    }
)

DELETE_LOCK_USER_NAME_SCHEMA: Final = vol.Schema(
    {
        vol.Required("device_id"): str,
        vol.Required("user_id"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
    }
)

# Events
EVENT_LOCK_LOG_ENTRY: Final = "switchbot_lock_logs_new_entry"

# Storage
STORAGE_KEY_LOCK_USERS: Final = "switchbot_lock_logs_users"
STORAGE_VERSION_LOCK_USERS: Final = 1

# Lock model types (from core switchbot const.py)
LOCK_MODELS: Final = {"lock", "lock_pro", "lock_lite", "lock_ultra"}

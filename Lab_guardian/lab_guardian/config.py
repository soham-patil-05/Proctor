"""Configuration defaults — overridden by env vars.

LAB_LIST is duplicated in frontend constants and must remain identical.
"""

import os
from urllib.parse import urlparse

# Backend server URL
API_BASE_URL = os.environ.get("LAB_GUARDIAN_API_URL", "https://proctor-0luy.onrender.com")
_parsed_api = urlparse(API_BASE_URL)
BACKEND_HOST = os.environ.get("LAB_GUARDIAN_BACKEND_HOST", _parsed_api.hostname or "localhost")
BACKEND_PORT = int(os.environ.get("LAB_GUARDIAN_BACKEND_PORT", str(_parsed_api.port or (443 if _parsed_api.scheme == "https" else 80))))

# Shared lab identifiers. Keep identical to frontend/src/constants/labs.js
LAB_LIST = [
    "A3-301", "A3-302", "A3-303", "A3-304", "A3-305",
    "A3-306", "A3-307", "A3-308", "A3-309", "A3-310", "A3-311",
    "A3-401", "A3-402", "A3-403", "A3-404", "A3-405",
    "A3-406", "A3-407", "A3-408", "A3-409", "A3-410", "A3-411",
]

# Monitor intervals (seconds)
SNAPSHOT_INTERVAL = int(os.environ.get("LG_SNAPSHOT_INTERVAL", "30"))
DELTA_INTERVAL = int(os.environ.get("LG_DELTA_INTERVAL", "3"))
DEVICE_POLL_INTERVAL = int(os.environ.get("LG_DEVICE_POLL_INTERVAL", "2"))
NETWORK_POLL_INTERVAL = int(os.environ.get("LG_NETWORK_POLL_INTERVAL", "5"))
NETWORK_SS_INTERVAL = int(os.environ.get("LG_NETWORK_SS_INTERVAL", "2"))
AUDITD_LOG_PATH = os.environ.get("LG_AUDITD_LOG_PATH", "/var/log/audit/audit.log")
HEARTBEAT_INTERVAL = int(os.environ.get("LG_HEARTBEAT_INTERVAL", "5"))

# Reconnect backoff
RECONNECT_BASE = 1
RECONNECT_MAX = 60

# Change thresholds for process_update
CPU_CHANGE_THRESHOLD = 5.0   # percent
MEM_CHANGE_THRESHOLD = 1.0   # MB

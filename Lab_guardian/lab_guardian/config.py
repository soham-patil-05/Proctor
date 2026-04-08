"""Configuration defaults — overridden by env vars or CLI args."""

import os

# Backend server URLs
API_BASE_URL = os.environ.get("LAB_GUARDIAN_API_URL", "http://localhost:8000")
WS_BASE_URL = os.environ.get("LAB_GUARDIAN_WS_URL", "ws://localhost:8001")

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

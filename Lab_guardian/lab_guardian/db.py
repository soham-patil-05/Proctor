"""Local SQLite persistence for Lab Guardian.

Export payload contract used by GUI -> backend ingest:
{
  sessionId,
  rollNo,
  labNo,
  name,
  recordedAt,
  processes: [...],
  devices: { usb: [...], external: [...] },
  network: {...} | null,
  domainActivity: [...],
  terminalEvents: [...],
  browserHistory: [...]
}
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any
from typing import Optional

_DB_LOCK = threading.Lock()
_DB_PATH = os.environ.get("LG_LOCAL_DB_PATH", os.path.abspath("labguardian_local.db"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    global _DB_PATH
    if db_path:
        _DB_PATH = db_path

    with _DB_LOCK:
        conn = _connect()
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                name TEXT,
                lab_no TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                synced INTEGER DEFAULT 0
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS processes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                lab_no TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                synced INTEGER DEFAULT 0
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                lab_no TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                synced INTEGER DEFAULT 0
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS network_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                lab_no TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                synced INTEGER DEFAULT 0
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS domain_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                lab_no TEXT NOT NULL,
                payload TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                synced INTEGER DEFAULT 0
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS terminal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                lab_no TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                synced INTEGER DEFAULT 0
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS browser_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                lab_no TEXT NOT NULL,
                payload TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                synced INTEGER DEFAULT 0
            )
            """
        )

        conn.commit()
        conn.close()


def start_session(session_id: str, roll_no: str, name: str, lab_no: str) -> None:
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO sessions (session_id, roll_no, name, lab_no, started_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, roll_no, name, lab_no, _now_iso()),
        )
        conn.commit()
        conn.close()


def end_session(session_id: str, roll_no: str) -> None:
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            UPDATE sessions
            SET ended_at = ?
            WHERE session_id = ? AND roll_no = ? AND ended_at IS NULL
            """,
            (_now_iso(), session_id, roll_no),
        )
        conn.commit()
        conn.close()


def _insert_generic(
    table: str,
    session_id: str,
    roll_no: str,
    lab_no: str,
    payload: Any,
    event_type: Optional[str] = None,
    recorded_at: Optional[str] = None,
) -> None:
    recorded_at = recorded_at or _now_iso()
    payload_text = json.dumps(payload, ensure_ascii=True)

    with _DB_LOCK:
        conn = _connect()
        if event_type is None:
            conn.execute(
                f"INSERT INTO {table} (session_id, roll_no, lab_no, payload, recorded_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, roll_no, lab_no, payload_text, recorded_at),
            )
        else:
            conn.execute(
                f"INSERT INTO {table} (session_id, roll_no, lab_no, event_type, payload, recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, roll_no, lab_no, event_type, payload_text, recorded_at),
            )
        conn.commit()
        conn.close()


def insert_processes(session_id: str, roll_no: str, lab_no: str, event_type: str, data: Any, recorded_at: Optional[str] = None) -> None:
    _insert_generic("processes", session_id, roll_no, lab_no, data, event_type=event_type, recorded_at=recorded_at)


def insert_devices(session_id: str, roll_no: str, lab_no: str, event_type: str, data: Any, recorded_at: Optional[str] = None) -> None:
    _insert_generic("devices", session_id, roll_no, lab_no, data, event_type=event_type, recorded_at=recorded_at)


def insert_network(session_id: str, roll_no: str, lab_no: str, event_type: str, data: Any, recorded_at: Optional[str] = None) -> None:
    _insert_generic("network_snapshots", session_id, roll_no, lab_no, data, event_type=event_type, recorded_at=recorded_at)


def insert_domain_activity(session_id: str, roll_no: str, lab_no: str, data: Any, recorded_at: Optional[str] = None) -> None:
    _insert_generic("domain_activity", session_id, roll_no, lab_no, data, event_type=None, recorded_at=recorded_at)


def insert_terminal_event(session_id: str, roll_no: str, lab_no: str, event_type: str, data: Any, recorded_at: Optional[str] = None) -> None:
    _insert_generic("terminal_events", session_id, roll_no, lab_no, data, event_type=event_type, recorded_at=recorded_at)


def insert_browser_history(session_id: str, roll_no: str, lab_no: str, data: Any, recorded_at: Optional[str] = None) -> None:
    _insert_generic("browser_history", session_id, roll_no, lab_no, data, event_type=None, recorded_at=recorded_at)


def insert_event(session_id: str, roll_no: str, lab_no: str, event: dict) -> None:
    event_type = event.get("type")
    data = event.get("data")
    ts = event.get("ts")
    recorded_at = None
    if ts:
        try:
            recorded_at = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
        except Exception:
            recorded_at = _now_iso()

    if event_type in {"process_snapshot", "process_new", "process_update", "process_end"}:
        insert_processes(session_id, roll_no, lab_no, event_type, data, recorded_at)
    elif event_type in {"devices_snapshot", "device_connected", "device_disconnected"}:
        insert_devices(session_id, roll_no, lab_no, event_type, data, recorded_at)
    elif event_type in {"network_snapshot", "network_update"}:
        insert_network(session_id, roll_no, lab_no, event_type, data, recorded_at)
    elif event_type == "domain_activity":
        insert_domain_activity(session_id, roll_no, lab_no, data, recorded_at)
    elif event_type in {"terminal_request", "terminal_command"}:
        payload = dict(data or {})
        meta = event.get("meta") or {}
        if "risk_level" in meta and "risk_level" not in payload:
            payload["risk_level"] = meta.get("risk_level")
        if "message" in meta and "message" not in payload:
            payload["message"] = meta.get("message")
        insert_terminal_event(session_id, roll_no, lab_no, event_type, payload, recorded_at)
    elif event_type == "browser_history":
        insert_browser_history(session_id, roll_no, lab_no, data, recorded_at)


def _fetch_rows(table: str, session_id: str, roll_no: str, unsynced_only: bool) -> list[dict]:
    where_synced = "AND synced = 0" if unsynced_only else ""
    with _DB_LOCK:
        conn = _connect()
        rows = conn.execute(
            f"""
            SELECT id, event_type, payload, recorded_at, lab_no
            FROM {table}
            WHERE session_id = ? AND roll_no = ? {where_synced}
            ORDER BY recorded_at ASC
            """,
            (session_id, roll_no),
        ).fetchall()
        conn.close()

    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "eventType": r["event_type"] if "event_type" in r.keys() else None,
                "data": json.loads(r["payload"]),
                "recordedAt": r["recorded_at"],
                "labNo": r["lab_no"],
            }
        )
    return out


def query_unsynced_records(session_id: str, roll_no: str) -> dict:
    processes = _fetch_rows("processes", session_id, roll_no, unsynced_only=True)
    devices = _fetch_rows("devices", session_id, roll_no, unsynced_only=True)
    network = _fetch_rows("network_snapshots", session_id, roll_no, unsynced_only=True)

    with _DB_LOCK:
        conn = _connect()
        domains_raw = conn.execute(
            """
            SELECT id, payload, recorded_at, lab_no
            FROM domain_activity
            WHERE session_id = ? AND roll_no = ? AND synced = 0
            ORDER BY recorded_at ASC
            """,
            (session_id, roll_no),
        ).fetchall()
        terminal_raw = conn.execute(
            """
            SELECT id, event_type, payload, recorded_at, lab_no
            FROM terminal_events
            WHERE session_id = ? AND roll_no = ? AND synced = 0
            ORDER BY recorded_at ASC
            """,
            (session_id, roll_no),
        ).fetchall()
        browser_raw = conn.execute(
            """
            SELECT id, payload, recorded_at, lab_no
            FROM browser_history
            WHERE session_id = ? AND roll_no = ? AND synced = 0
            ORDER BY recorded_at ASC
            """,
            (session_id, roll_no),
        ).fetchall()
        session_row = conn.execute(
            """
            SELECT name, lab_no
            FROM sessions
            WHERE session_id = ? AND roll_no = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_id, roll_no),
        ).fetchone()
        conn.close()

    domains = [
        {"id": r["id"], "data": json.loads(r["payload"]), "recordedAt": r["recorded_at"], "labNo": r["lab_no"]}
        for r in domains_raw
    ]
    terminal = [
        {
            "id": r["id"],
            "eventType": r["event_type"],
            "data": json.loads(r["payload"]),
            "recordedAt": r["recorded_at"],
            "labNo": r["lab_no"],
        }
        for r in terminal_raw
    ]
    browser = [
        {"id": r["id"], "data": json.loads(r["payload"]), "recordedAt": r["recorded_at"], "labNo": r["lab_no"]}
        for r in browser_raw
    ]

    lab_no = session_row["lab_no"] if session_row else ""
    name = session_row["name"] if session_row else ""

    return {
        "sessionId": session_id,
        "rollNo": roll_no,
        "labNo": lab_no,
        "name": name,
        "recordedAt": _now_iso(),
        "processes": processes,
        "devices": devices,
        "network": network,
        "domainActivity": domains,
        "terminalEvents": terminal,
        "browserHistory": browser,
    }


def mark_synced(id_map: dict[str, list[int]]) -> None:
    table_map = {
        "processes": "processes",
        "devices": "devices",
        "network": "network_snapshots",
        "domainActivity": "domain_activity",
        "terminalEvents": "terminal_events",
        "browserHistory": "browser_history",
    }

    with _DB_LOCK:
        conn = _connect()
        for key, ids in id_map.items():
            table = table_map.get(key)
            if not table or not ids:
                continue
            placeholders = ",".join(["?"] * len(ids))
            conn.execute(f"UPDATE {table} SET synced = 1 WHERE id IN ({placeholders})", ids)
        conn.commit()
        conn.close()


def _collapse_events_for_payload(records: dict) -> dict:
    def _latest_by_type(rows: list[dict], target_type: str):
        filtered = [r for r in rows if r.get("eventType") == target_type]
        return filtered[-1]["data"] if filtered else None

    process_rows = records.get("processes", [])
    latest_snapshot = _latest_by_type(process_rows, "process_snapshot")
    if latest_snapshot is None:
        latest_snapshot = []

    device_rows = records.get("devices", [])
    latest_devices = _latest_by_type(device_rows, "devices_snapshot")
    if latest_devices is None:
        latest_devices = {"usb": [], "external": []}

    network_rows = records.get("network", [])
    latest_network = None
    for row in reversed(network_rows):
        if row.get("eventType") in {"network_update", "network_snapshot"}:
            latest_network = row["data"]
            break

    domain_activity = []
    for row in records.get("domainActivity", []):
        data = row.get("data")
        if isinstance(data, list):
            domain_activity.extend(data)

    terminal_events = []
    for row in records.get("terminalEvents", []):
        data = dict(row.get("data") or {})
        data["eventType"] = row.get("eventType")
        terminal_events.append(data)

    browser_history = []
    for row in records.get("browserHistory", []):
        data = row.get("data")
        if isinstance(data, list):
            browser_history.extend(data)

    return {
        "sessionId": records.get("sessionId"),
        "rollNo": records.get("rollNo"),
        "labNo": records.get("labNo"),
        "name": records.get("name", ""),
        "recordedAt": records.get("recordedAt"),
        "processes": latest_snapshot,
        "devices": latest_devices,
        "network": latest_network,
        "domainActivity": domain_activity,
        "terminalEvents": terminal_events,
        "browserHistory": browser_history,
    }


def get_unsynced_export_payload(session_id: str, roll_no: str) -> tuple[dict, dict[str, list[int]]]:
    records = query_unsynced_records(session_id, roll_no)
    id_map = {
        "processes": [x["id"] for x in records.get("processes", [])],
        "devices": [x["id"] for x in records.get("devices", [])],
        "network": [x["id"] for x in records.get("network", [])],
        "domainActivity": [x["id"] for x in records.get("domainActivity", [])],
        "terminalEvents": [x["id"] for x in records.get("terminalEvents", [])],
        "browserHistory": [x["id"] for x in records.get("browserHistory", [])],
    }
    payload = _collapse_events_for_payload(records)
    return payload, id_map


def get_latest_session_payload(session_id: str, roll_no: str) -> dict:
    records = {
        "sessionId": session_id,
        "rollNo": roll_no,
        "recordedAt": _now_iso(),
        "processes": _fetch_rows("processes", session_id, roll_no, unsynced_only=False),
        "devices": _fetch_rows("devices", session_id, roll_no, unsynced_only=False),
        "network": _fetch_rows("network_snapshots", session_id, roll_no, unsynced_only=False),
        "domainActivity": [],
        "terminalEvents": [],
        "browserHistory": [],
    }

    with _DB_LOCK:
        conn = _connect()
        session_row = conn.execute(
            """
            SELECT name, lab_no
            FROM sessions
            WHERE session_id = ? AND roll_no = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_id, roll_no),
        ).fetchone()

        domains_raw = conn.execute(
            """
            SELECT id, payload, recorded_at, lab_no
            FROM domain_activity
            WHERE session_id = ? AND roll_no = ?
            ORDER BY recorded_at ASC
            """,
            (session_id, roll_no),
        ).fetchall()
        terminal_raw = conn.execute(
            """
            SELECT id, event_type, payload, recorded_at, lab_no
            FROM terminal_events
            WHERE session_id = ? AND roll_no = ?
            ORDER BY recorded_at ASC
            """,
            (session_id, roll_no),
        ).fetchall()
        browser_raw = conn.execute(
            """
            SELECT id, payload, recorded_at, lab_no
            FROM browser_history
            WHERE session_id = ? AND roll_no = ?
            ORDER BY recorded_at ASC
            """,
            (session_id, roll_no),
        ).fetchall()
        conn.close()

    records["name"] = session_row["name"] if session_row else ""
    records["labNo"] = session_row["lab_no"] if session_row else ""
    records["domainActivity"] = [
        {"id": r["id"], "data": json.loads(r["payload"]), "recordedAt": r["recorded_at"], "labNo": r["lab_no"]}
        for r in domains_raw
    ]
    records["terminalEvents"] = [
        {
            "id": r["id"],
            "eventType": r["event_type"],
            "data": json.loads(r["payload"]),
            "recordedAt": r["recorded_at"],
            "labNo": r["lab_no"],
        }
        for r in terminal_raw
    ]
    records["browserHistory"] = [
        {"id": r["id"], "data": json.loads(r["payload"]), "recordedAt": r["recorded_at"], "labNo": r["lab_no"]}
        for r in browser_raw
    ]

    return _collapse_events_for_payload(records)

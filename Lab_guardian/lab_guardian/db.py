"""Local SQLite persistence for Lab Guardian.

EXPORT_PAYLOAD_SCHEMA:
{
  "sessionId": string,
  "rollNo": string,
  "labNo": string,
  "name": string,
  "processes": [ { pid, process_name, cpu_percent, memory_mb, status, risk_level, category } ],
  "devices": [ { device_id, device_name, device_type, connected_at, disconnected_at, readable_name, risk_level, message } ],
  "network": { ip_address, gateway, dns, active_connections: [...] } | null,
  "domainActivity": [ { domain, request_count, risk_level, last_accessed } ],
  "terminalEvents": [ { event_type, tool, remote_ip, remote_host, remote_port, pid, full_command, risk_level, message, detected_at } ],
  "browserHistory": [ { url, title, visit_count, last_visit } ]
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


def _to_recorded_at(ts: Optional[float]) -> str:
    if ts is None:
        return _now_iso()
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except Exception:
        return _now_iso()


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
                ended_at TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS live_processes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                lab_no TEXT NOT NULL,
                pid INTEGER NOT NULL,
                process_name TEXT,
                cpu_percent REAL,
                memory_mb REAL,
                status TEXT,
                risk_level TEXT,
                category TEXT,
                recorded_at TEXT NOT NULL,
                synced INTEGER DEFAULT 0,
                UNIQUE(session_id, roll_no, pid)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS connected_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                lab_no TEXT NOT NULL,
                device_id TEXT NOT NULL,
                device_name TEXT,
                device_type TEXT,
                connected_at TEXT,
                disconnected_at TEXT,
                readable_name TEXT,
                risk_level TEXT,
                message TEXT,
                recorded_at TEXT NOT NULL,
                synced INTEGER DEFAULT 0,
                UNIQUE(session_id, roll_no, device_id)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS network_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                lab_no TEXT NOT NULL,
                ip_address TEXT,
                gateway TEXT,
                dns TEXT,
                active_connections TEXT,
                recorded_at TEXT NOT NULL,
                synced INTEGER DEFAULT 0,
                UNIQUE(session_id, roll_no)
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
                domain TEXT NOT NULL,
                request_count INTEGER DEFAULT 0,
                risk_level TEXT,
                last_accessed TEXT,
                synced INTEGER DEFAULT 0,
                UNIQUE(session_id, roll_no, domain)
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
                event_type TEXT,
                tool TEXT,
                remote_ip TEXT,
                remote_host TEXT,
                remote_port INTEGER,
                pid INTEGER,
                full_command TEXT,
                risk_level TEXT,
                message TEXT,
                detected_at TEXT,
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
                url TEXT,
                title TEXT,
                visit_count INTEGER DEFAULT 1,
                last_visit TEXT,
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


def insert_processes(session_id: str, roll_no: str, lab_no: str, event_type: str, data: Any, ts: Optional[float] = None) -> None:
    recorded_at = _to_recorded_at(ts)
    with _DB_LOCK:
        conn = _connect()

        if event_type == "process_snapshot":
            conn.execute(
                """
                UPDATE live_processes
                SET status = 'ended', recorded_at = ?, synced = 0
                WHERE session_id = ? AND roll_no = ?
                """,
                (recorded_at, session_id, roll_no),
            )

            for proc in data or []:
                conn.execute(
                    """
                    INSERT INTO live_processes
                    (session_id, roll_no, lab_no, pid, process_name, cpu_percent, memory_mb, status, risk_level, category, recorded_at, synced)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    ON CONFLICT(session_id, roll_no, pid)
                    DO UPDATE SET
                        process_name = excluded.process_name,
                        cpu_percent = excluded.cpu_percent,
                        memory_mb = excluded.memory_mb,
                        status = excluded.status,
                        risk_level = excluded.risk_level,
                        category = excluded.category,
                        recorded_at = excluded.recorded_at,
                        synced = 0,
                        lab_no = excluded.lab_no
                    """,
                    (
                        session_id,
                        roll_no,
                        lab_no,
                        proc.get("pid"),
                        proc.get("name") or proc.get("process_name"),
                        proc.get("cpu") if proc.get("cpu") is not None else proc.get("cpu_percent"),
                        proc.get("memory") if proc.get("memory") is not None else proc.get("memory_mb"),
                        proc.get("status") or "running",
                        proc.get("risk_level"),
                        proc.get("category"),
                        recorded_at,
                    ),
                )

        elif event_type in {"process_new", "process_update"} and isinstance(data, dict):
            conn.execute(
                """
                INSERT INTO live_processes
                (session_id, roll_no, lab_no, pid, process_name, cpu_percent, memory_mb, status, risk_level, category, recorded_at, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(session_id, roll_no, pid)
                DO UPDATE SET
                    process_name = excluded.process_name,
                    cpu_percent = excluded.cpu_percent,
                    memory_mb = excluded.memory_mb,
                    status = excluded.status,
                    risk_level = excluded.risk_level,
                    category = excluded.category,
                    recorded_at = excluded.recorded_at,
                    synced = 0,
                    lab_no = excluded.lab_no
                """,
                (
                    session_id,
                    roll_no,
                    lab_no,
                    data.get("pid"),
                    data.get("name") or data.get("process_name"),
                    data.get("cpu") if data.get("cpu") is not None else data.get("cpu_percent"),
                    data.get("memory") if data.get("memory") is not None else data.get("memory_mb"),
                    data.get("status") or "running",
                    data.get("risk_level"),
                    data.get("category"),
                    recorded_at,
                ),
            )

        elif event_type == "process_end" and isinstance(data, dict):
            conn.execute(
                """
                UPDATE live_processes
                SET status = 'ended', recorded_at = ?, synced = 0
                WHERE session_id = ? AND roll_no = ? AND pid = ?
                """,
                (recorded_at, session_id, roll_no, data.get("pid")),
            )

        conn.commit()
        conn.close()


def insert_devices(session_id: str, roll_no: str, lab_no: str, event_type: str, data: Any, ts: Optional[float] = None) -> None:
    recorded_at = _to_recorded_at(ts)
    with _DB_LOCK:
        conn = _connect()

        if event_type == "devices_snapshot" and isinstance(data, dict):
            snapshot_ids: set[str] = set()
            for device_type in ("usb", "external"):
                for d in data.get(device_type, []) or []:
                    device_id = str(d.get("id") or d.get("device_id") or "")
                    if not device_id:
                        continue
                    snapshot_ids.add(device_id)
                    conn.execute(
                        """
                        INSERT INTO connected_devices
                        (session_id, roll_no, lab_no, device_id, device_name, device_type, connected_at, disconnected_at, readable_name, risk_level, message, recorded_at, synced)
                        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, 0)
                        ON CONFLICT(session_id, roll_no, device_id)
                        DO UPDATE SET
                            device_name = excluded.device_name,
                            device_type = excluded.device_type,
                            connected_at = COALESCE(connected_devices.connected_at, excluded.connected_at),
                            disconnected_at = NULL,
                            readable_name = excluded.readable_name,
                            risk_level = excluded.risk_level,
                            message = excluded.message,
                            recorded_at = excluded.recorded_at,
                            synced = 0,
                            lab_no = excluded.lab_no
                        """,
                        (
                            session_id,
                            roll_no,
                            lab_no,
                            device_id,
                            d.get("name") or d.get("device_name"),
                            device_type,
                            recorded_at,
                            d.get("readable_name"),
                            d.get("risk_level"),
                            d.get("message"),
                            recorded_at,
                        ),
                    )

            if snapshot_ids:
                placeholders = ",".join(["?"] * len(snapshot_ids))
                conn.execute(
                    f"""
                    UPDATE connected_devices
                    SET disconnected_at = ?, recorded_at = ?, synced = 0
                    WHERE session_id = ? AND roll_no = ? AND device_id NOT IN ({placeholders})
                    """,
                    (recorded_at, recorded_at, session_id, roll_no, *list(snapshot_ids)),
                )

        elif event_type == "device_connected" and isinstance(data, dict):
            device_id = str(data.get("id") or data.get("device_id") or "")
            if device_id:
                device_type = data.get("type") or data.get("device_type") or "usb"
                conn.execute(
                    """
                    INSERT INTO connected_devices
                    (session_id, roll_no, lab_no, device_id, device_name, device_type, connected_at, disconnected_at, readable_name, risk_level, message, recorded_at, synced)
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, 0)
                    ON CONFLICT(session_id, roll_no, device_id)
                    DO UPDATE SET
                        device_name = excluded.device_name,
                        device_type = excluded.device_type,
                        connected_at = COALESCE(connected_devices.connected_at, excluded.connected_at),
                        disconnected_at = NULL,
                        readable_name = excluded.readable_name,
                        risk_level = excluded.risk_level,
                        message = excluded.message,
                        recorded_at = excluded.recorded_at,
                        synced = 0,
                        lab_no = excluded.lab_no
                    """,
                    (
                        session_id,
                        roll_no,
                        lab_no,
                        device_id,
                        data.get("name") or data.get("device_name"),
                        device_type,
                        recorded_at,
                        data.get("readable_name"),
                        data.get("risk_level"),
                        data.get("message"),
                        recorded_at,
                    ),
                )

        elif event_type == "device_disconnected" and isinstance(data, dict):
            device_id = str(data.get("id") or data.get("device_id") or "")
            if device_id:
                conn.execute(
                    """
                    UPDATE connected_devices
                    SET disconnected_at = ?, recorded_at = ?, synced = 0
                    WHERE session_id = ? AND roll_no = ? AND device_id = ?
                    """,
                    (recorded_at, recorded_at, session_id, roll_no, device_id),
                )

        conn.commit()
        conn.close()


def insert_network(session_id: str, roll_no: str, lab_no: str, event_type: str, data: Any, ts: Optional[float] = None) -> None:
    if event_type not in {"network_snapshot", "network_update"} or not isinstance(data, dict):
        return

    recorded_at = _to_recorded_at(ts)
    active_connections = data.get("active_connections")
    if active_connections is None:
        active_connections = data.get("activeConnections")
    if active_connections is None:
        active_connections = []

    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO network_info
            (session_id, roll_no, lab_no, ip_address, gateway, dns, active_connections, recorded_at, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(session_id, roll_no)
            DO UPDATE SET
                ip_address = excluded.ip_address,
                gateway = excluded.gateway,
                dns = excluded.dns,
                active_connections = excluded.active_connections,
                recorded_at = excluded.recorded_at,
                synced = 0,
                lab_no = excluded.lab_no
            """,
            (
                session_id,
                roll_no,
                lab_no,
                data.get("ip") or data.get("ip_address"),
                data.get("gateway"),
                json.dumps(data.get("dns") or [], ensure_ascii=True),
                json.dumps(active_connections, ensure_ascii=True),
                recorded_at,
            ),
        )
        conn.commit()
        conn.close()


def insert_domain_activity(session_id: str, roll_no: str, lab_no: str, data: Any, ts: Optional[float] = None) -> None:
    recorded_at = _to_recorded_at(ts)
    rows = data if isinstance(data, list) else []

    with _DB_LOCK:
        conn = _connect()
        for item in rows:
            domain = item.get("domain")
            if not domain:
                continue
            count = item.get("count") if item.get("count") is not None else item.get("request_count")
            count = int(count or 1)
            conn.execute(
                """
                INSERT INTO domain_activity
                (session_id, roll_no, lab_no, domain, request_count, risk_level, last_accessed, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(session_id, roll_no, domain)
                DO UPDATE SET
                    request_count = domain_activity.request_count + excluded.request_count,
                    risk_level = COALESCE(excluded.risk_level, domain_activity.risk_level),
                    last_accessed = excluded.last_accessed,
                    synced = 0,
                    lab_no = excluded.lab_no
                """,
                (
                    session_id,
                    roll_no,
                    lab_no,
                    domain,
                    count,
                    item.get("risk_level"),
                    recorded_at,
                ),
            )
        conn.commit()
        conn.close()


def insert_terminal_event(session_id: str, roll_no: str, lab_no: str, event_type: str, data: Any, ts: Optional[float] = None) -> None:
    if not isinstance(data, dict):
        return
    detected_at = _to_recorded_at(ts)

    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO terminal_events
            (session_id, roll_no, lab_no, event_type, tool, remote_ip, remote_host, remote_port, pid, full_command, risk_level, message, detected_at, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                session_id,
                roll_no,
                lab_no,
                event_type,
                data.get("tool"),
                data.get("remote_ip"),
                data.get("remote_host"),
                data.get("remote_port"),
                data.get("pid"),
                data.get("full_command"),
                data.get("risk_level"),
                data.get("message"),
                detected_at,
            ),
        )
        conn.commit()
        conn.close()


def insert_browser_history(session_id: str, roll_no: str, lab_no: str, data: Any, ts: Optional[float] = None) -> None:
    rows = data if isinstance(data, list) else []
    default_time = _to_recorded_at(ts)

    with _DB_LOCK:
        conn = _connect()
        for item in rows:
            if not isinstance(item, dict):
                continue
            conn.execute(
                """
                INSERT INTO browser_history
                (session_id, roll_no, lab_no, url, title, visit_count, last_visit, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    session_id,
                    roll_no,
                    lab_no,
                    item.get("url"),
                    item.get("title"),
                    int(item.get("visit_count") or 1),
                    item.get("last_visit") or default_time,
                ),
            )
        conn.commit()
        conn.close()


def _load_processes(conn: sqlite3.Connection, session_id: str, roll_no: str, unsynced_only: bool) -> list[dict]:
    where_synced = "AND synced = 0" if unsynced_only else ""
    rows = conn.execute(
        f"""
        SELECT pid, process_name, cpu_percent, memory_mb, status, risk_level, category
        FROM live_processes
        WHERE session_id = ? AND roll_no = ? {where_synced}
        ORDER BY recorded_at DESC
        """,
        (session_id, roll_no),
    ).fetchall()
    return [dict(r) for r in rows]


def _load_devices(conn: sqlite3.Connection, session_id: str, roll_no: str, unsynced_only: bool) -> list[dict]:
    where_synced = "AND synced = 0" if unsynced_only else ""
    rows = conn.execute(
        f"""
        SELECT device_id, device_name, device_type, connected_at, disconnected_at, readable_name, risk_level, message
        FROM connected_devices
        WHERE session_id = ? AND roll_no = ? {where_synced}
        ORDER BY connected_at DESC
        """,
        (session_id, roll_no),
    ).fetchall()
    return [dict(r) for r in rows]


def _load_network(conn: sqlite3.Connection, session_id: str, roll_no: str, unsynced_only: bool) -> Optional[dict]:
    where_synced = "AND synced = 0" if unsynced_only else ""
    row = conn.execute(
        f"""
        SELECT ip_address, gateway, dns, active_connections
        FROM network_info
        WHERE session_id = ? AND roll_no = ? {where_synced}
        ORDER BY recorded_at DESC
        LIMIT 1
        """,
        (session_id, roll_no),
    ).fetchone()
    if not row:
        return None

    out = dict(row)
    try:
        out["dns"] = json.loads(out.get("dns") or "[]")
    except Exception:
        out["dns"] = []

    try:
        out["active_connections"] = json.loads(out.get("active_connections") or "[]")
    except Exception:
        out["active_connections"] = []

    return out


def _load_domain_activity(conn: sqlite3.Connection, session_id: str, roll_no: str, unsynced_only: bool) -> list[dict]:
    where_synced = "AND synced = 0" if unsynced_only else ""
    rows = conn.execute(
        f"""
        SELECT domain, request_count, risk_level, last_accessed
        FROM domain_activity
        WHERE session_id = ? AND roll_no = ? {where_synced}
        ORDER BY request_count DESC
        """,
        (session_id, roll_no),
    ).fetchall()
    return [dict(r) for r in rows]


def _load_terminal_events(conn: sqlite3.Connection, session_id: str, roll_no: str, unsynced_only: bool) -> list[dict]:
    where_synced = "AND synced = 0" if unsynced_only else ""
    rows = conn.execute(
        f"""
        SELECT event_type, tool, remote_ip, remote_host, remote_port, pid, full_command, risk_level, message, detected_at
        FROM terminal_events
        WHERE session_id = ? AND roll_no = ? {where_synced}
        ORDER BY detected_at DESC
        """,
        (session_id, roll_no),
    ).fetchall()
    return [dict(r) for r in rows]


def _load_browser_history(conn: sqlite3.Connection, session_id: str, roll_no: str, unsynced_only: bool) -> list[dict]:
    where_synced = "AND synced = 0" if unsynced_only else ""
    rows = conn.execute(
        f"""
        SELECT url, title, visit_count, last_visit
        FROM browser_history
        WHERE session_id = ? AND roll_no = ? {where_synced}
        ORDER BY last_visit DESC
        """,
        (session_id, roll_no),
    ).fetchall()
    return [dict(r) for r in rows]


def _session_info(conn: sqlite3.Connection, session_id: str, roll_no: str) -> tuple[str, str]:
    row = conn.execute(
        """
        SELECT name, lab_no
        FROM sessions
        WHERE session_id = ? AND roll_no = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (session_id, roll_no),
    ).fetchone()
    if not row:
        return "", ""
    return row["name"] or "", row["lab_no"] or ""


def get_unsynced_export_payload(session_id: str, roll_no: str) -> tuple[dict, dict[str, list[int]]]:
    with _DB_LOCK:
        conn = _connect()

        name, lab_no = _session_info(conn, session_id, roll_no)
        payload = {
            "sessionId": session_id,
            "rollNo": roll_no,
            "labNo": lab_no,
            "name": name,
            "processes": _load_processes(conn, session_id, roll_no, unsynced_only=True),
            "devices": _load_devices(conn, session_id, roll_no, unsynced_only=True),
            "network": _load_network(conn, session_id, roll_no, unsynced_only=True),
            "domainActivity": _load_domain_activity(conn, session_id, roll_no, unsynced_only=True),
            "terminalEvents": _load_terminal_events(conn, session_id, roll_no, unsynced_only=True),
            "browserHistory": _load_browser_history(conn, session_id, roll_no, unsynced_only=True),
        }

        id_map = {
            "processes": [r["id"] for r in conn.execute("SELECT id FROM live_processes WHERE session_id = ? AND roll_no = ? AND synced = 0", (session_id, roll_no)).fetchall()],
            "devices": [r["id"] for r in conn.execute("SELECT id FROM connected_devices WHERE session_id = ? AND roll_no = ? AND synced = 0", (session_id, roll_no)).fetchall()],
            "network": [r["id"] for r in conn.execute("SELECT id FROM network_info WHERE session_id = ? AND roll_no = ? AND synced = 0", (session_id, roll_no)).fetchall()],
            "domainActivity": [r["id"] for r in conn.execute("SELECT id FROM domain_activity WHERE session_id = ? AND roll_no = ? AND synced = 0", (session_id, roll_no)).fetchall()],
            "terminalEvents": [r["id"] for r in conn.execute("SELECT id FROM terminal_events WHERE session_id = ? AND roll_no = ? AND synced = 0", (session_id, roll_no)).fetchall()],
            "browserHistory": [r["id"] for r in conn.execute("SELECT id FROM browser_history WHERE session_id = ? AND roll_no = ? AND synced = 0", (session_id, roll_no)).fetchall()],
        }

        conn.close()
        return payload, id_map


def mark_synced(id_map: dict[str, list[int]]) -> None:
    table_map = {
        "processes": "live_processes",
        "devices": "connected_devices",
        "network": "network_info",
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


def get_latest_session_payload(session_id: str, roll_no: str) -> dict:
    with _DB_LOCK:
        conn = _connect()
        name, lab_no = _session_info(conn, session_id, roll_no)
        out = {
            "sessionId": session_id,
            "rollNo": roll_no,
            "labNo": lab_no,
            "name": name,
            "processes": _load_processes(conn, session_id, roll_no, unsynced_only=False),
            "devices": _load_devices(conn, session_id, roll_no, unsynced_only=False),
            "network": _load_network(conn, session_id, roll_no, unsynced_only=False),
            "domainActivity": _load_domain_activity(conn, session_id, roll_no, unsynced_only=False),
            "terminalEvents": _load_terminal_events(conn, session_id, roll_no, unsynced_only=False),
            "browserHistory": _load_browser_history(conn, session_id, roll_no, unsynced_only=False),
        }
        conn.close()
        return out

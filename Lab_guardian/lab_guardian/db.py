"""Local SQLite persistence for Lab Guardian canonical telemetry contract."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Optional

_DB_LOCK = threading.Lock()
_DB_PATH = os.environ.get("LG_LOCAL_DB_PATH", os.path.abspath("labguardian_local.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=True)


def _normalize_risk(value: Any) -> str:
    risk = str(value or "normal").strip().lower()
    if risk not in {"high", "medium", "low", "normal"}:
        return "normal"
    return risk


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def init_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Initialize local SQLite schema and return a connection."""
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
                lab_no TEXT,
                started_at TEXT DEFAULT (datetime('now')),
                ended_at TEXT
            )
            """
        )

        # Remove non-canonical local tables if they exist.
        cur.execute("DROP TABLE IF EXISTS network_info")
        cur.execute("DROP TABLE IF EXISTS domain_activity")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS usb_devices (
                session_id    TEXT NOT NULL,
                roll_no       TEXT NOT NULL,
                id            TEXT NOT NULL,
                readable_name TEXT,
                message       TEXT,
                risk_level    TEXT,
                metadata      TEXT,
                device_type   TEXT,
                synced        INTEGER DEFAULT 0,
                PRIMARY KEY (session_id, roll_no, id)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS browser_history (
                session_id   TEXT NOT NULL,
                roll_no      TEXT NOT NULL,
                url          TEXT NOT NULL,
                title        TEXT,
                visit_count  INTEGER DEFAULT 1,
                last_visited REAL,
                browser      TEXT,
                synced       INTEGER DEFAULT 0,
                PRIMARY KEY (session_id, roll_no, url)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS processes (
                session_id TEXT NOT NULL,
                roll_no    TEXT NOT NULL,
                pid        INTEGER NOT NULL,
                name       TEXT,
                label      TEXT,
                cpu        REAL,
                memory     REAL,
                status     TEXT,
                risk_level TEXT,
                synced     INTEGER DEFAULT 0,
                PRIMARY KEY (session_id, roll_no, pid)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS terminal_events (
                session_id   TEXT NOT NULL,
                roll_no      TEXT NOT NULL,
                id           TEXT,
                event_type   TEXT,
                tool         TEXT,
                detected_at  TEXT,
                pid          INTEGER,
                full_command TEXT,
                remote_ip    TEXT,
                remote_port  TEXT,
                remote_host  TEXT,
                message      TEXT,
                risk_level   TEXT,
                synced       INTEGER DEFAULT 0
            )
            """
        )

        conn.commit()
        return conn


def start_session(session_id: str, roll_no: str, name: str, lab_no: str) -> None:
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO sessions (session_id, roll_no, name, lab_no)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, roll_no, name, lab_no),
        )
        conn.commit()
        conn.close()


def end_session(session_id: str, roll_no: str) -> None:
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            UPDATE sessions
            SET ended_at = datetime('now')
            WHERE session_id = ? AND roll_no = ? AND ended_at IS NULL
            """,
            (session_id, roll_no),
        )
        conn.commit()
        conn.close()


def replace_devices(session_id: str, roll_no: str, device_list: list[dict]) -> None:
    with _DB_LOCK:
        conn = _connect()
        conn.execute("DELETE FROM usb_devices WHERE session_id = ? AND roll_no = ?", (session_id, roll_no))
        for device in device_list or []:
            if not isinstance(device, dict):
                continue
            device_id = str(device.get("id") or "").strip()
            if not device_id:
                continue
            metadata = device.get("metadata") if isinstance(device.get("metadata"), dict) else {}
            conn.execute(
                """
                INSERT INTO usb_devices (session_id, roll_no, id, readable_name, message, risk_level, metadata, device_type, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'usb', 0)
                """,
                (
                    session_id,
                    roll_no,
                    device_id,
                    device.get("readable_name"),
                    device.get("message"),
                    _normalize_risk(device.get("risk_level")),
                    _json_dumps(metadata),
                ),
            )
        conn.commit()
        conn.close()


def upsert_device(session_id: str, roll_no: str, device: dict) -> None:
    if not isinstance(device, dict):
        return
    device_id = str(device.get("id") or "").strip()
    if not device_id:
        return
    metadata = device.get("metadata") if isinstance(device.get("metadata"), dict) else {}
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO usb_devices (session_id, roll_no, id, readable_name, message, risk_level, metadata, device_type, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'usb', 0)
            ON CONFLICT(session_id, roll_no, id)
            DO UPDATE SET
                readable_name = excluded.readable_name,
                message = excluded.message,
                risk_level = excluded.risk_level,
                metadata = excluded.metadata,
                device_type = 'usb',
                synced = 0
            """,
            (
                session_id,
                roll_no,
                device_id,
                device.get("readable_name"),
                device.get("message"),
                _normalize_risk(device.get("risk_level")),
                _json_dumps(metadata),
            ),
        )
        conn.commit()
        conn.close()


def remove_device(session_id: str, roll_no: str, device_id: str) -> None:
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            "DELETE FROM usb_devices WHERE session_id = ? AND roll_no = ? AND id = ?",
            (session_id, roll_no, str(device_id or "")),
        )
        conn.commit()
        conn.close()


def upsert_browser_history(session_id: str, roll_no: str, entry: dict) -> None:
    if not isinstance(entry, dict):
        return
    url = str(entry.get("url") or "").strip()
    if not url:
        return

    visit_count = _safe_int(entry.get("visit_count")) or 1
    last_visited = _safe_float(entry.get("last_visited"))
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO browser_history (session_id, roll_no, url, title, visit_count, last_visited, browser, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(session_id, roll_no, url)
            DO UPDATE SET
                title = COALESCE(excluded.title, browser_history.title),
                visit_count = MAX(browser_history.visit_count, excluded.visit_count),
                last_visited = MAX(COALESCE(browser_history.last_visited, 0), COALESCE(excluded.last_visited, 0)),
                browser = COALESCE(excluded.browser, browser_history.browser),
                synced = 0
            """,
            (session_id, roll_no, url, entry.get("title"), visit_count, last_visited, entry.get("browser")),
        )
        conn.commit()
        conn.close()


def replace_processes(session_id: str, roll_no: str, process_list: list[dict]) -> None:
    with _DB_LOCK:
        conn = _connect()
        conn.execute("DELETE FROM processes WHERE session_id = ? AND roll_no = ?", (session_id, roll_no))
        for process in process_list or []:
            if not isinstance(process, dict):
                continue
            risk = str(process.get("risk_level") or "").lower()
            status = str(process.get("status") or "running").lower()
            if risk not in {"high", "medium"} or status == "ended":
                continue
            conn.execute(
                """
                INSERT INTO processes (session_id, roll_no, pid, name, label, cpu, memory, status, risk_level, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    session_id,
                    roll_no,
                    _safe_int(process.get("pid")),
                    process.get("name"),
                    process.get("label"),
                    _safe_float(process.get("cpu")) or 0.0,
                    _safe_float(process.get("memory")) or 0.0,
                    process.get("status") or "running",
                    risk,
                ),
            )
        conn.commit()
        conn.close()


def upsert_process(session_id: str, roll_no: str, process: dict) -> None:
    if not isinstance(process, dict):
        return
    risk = str(process.get("risk_level") or "").lower()
    status = str(process.get("status") or "running").lower()
    if risk not in {"high", "medium"} or status == "ended":
        return

    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO processes (session_id, roll_no, pid, name, label, cpu, memory, status, risk_level, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(session_id, roll_no, pid)
            DO UPDATE SET
                name = excluded.name,
                label = excluded.label,
                cpu = excluded.cpu,
                memory = excluded.memory,
                status = excluded.status,
                risk_level = excluded.risk_level,
                synced = 0
            """,
            (
                session_id,
                roll_no,
                _safe_int(process.get("pid")),
                process.get("name"),
                process.get("label"),
                _safe_float(process.get("cpu")) or 0.0,
                _safe_float(process.get("memory")) or 0.0,
                process.get("status") or "running",
                risk,
            ),
        )
        conn.commit()
        conn.close()


def update_process(session_id: str, roll_no: str, process: dict) -> None:
    if not isinstance(process, dict):
        return
    pid = _safe_int(process.get("pid"))
    if pid is None:
        return

    incoming_risk = str(process.get("risk_level") or "").lower()
    with _DB_LOCK:
        conn = _connect()
        existing = conn.execute(
            "SELECT risk_level FROM processes WHERE session_id = ? AND roll_no = ? AND pid = ?",
            (session_id, roll_no, pid),
        ).fetchone()

        existing_risk = str(existing["risk_level"] or "").lower() if existing else ""
        if incoming_risk not in {"high", "medium"} and existing_risk not in {"high", "medium"}:
            conn.close()
            return

        if str(process.get("status") or "").lower() == "ended":
            conn.execute(
                "DELETE FROM processes WHERE session_id = ? AND roll_no = ? AND pid = ?",
                (session_id, roll_no, pid),
            )
            conn.commit()
            conn.close()
            return

        allowed_fields = ["name", "label", "cpu", "memory", "status", "risk_level"]
        updates = []
        params: list[Any] = []

        for field in allowed_fields:
            if field not in process or process.get(field) is None:
                continue
            value = process.get(field)
            if field in {"cpu", "memory"}:
                value = _safe_float(value)
            if field == "risk_level":
                value = str(value).lower()
            updates.append(f"{field} = ?")
            params.append(value)

        if not updates:
            conn.close()
            return

        updates.append("synced = 0")
        sql = f"UPDATE processes SET {', '.join(updates)} WHERE session_id = ? AND roll_no = ? AND pid = ?"
        params.extend([session_id, roll_no, pid])
        conn.execute(sql, tuple(params))
        conn.commit()
        conn.close()


def delete_process(session_id: str, roll_no: str, pid: int) -> None:
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            "DELETE FROM processes WHERE session_id = ? AND roll_no = ? AND pid = ?",
            (session_id, roll_no, _safe_int(pid)),
        )
        conn.commit()
        conn.close()


def insert_terminal_event(session_id: str, roll_no: str, event: dict) -> None:
    if not isinstance(event, dict):
        return
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO terminal_events (
                session_id, roll_no, id, event_type, tool, detected_at, pid,
                full_command, remote_ip, remote_port, remote_host, message, risk_level, synced
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                session_id,
                roll_no,
                event.get("id"),
                event.get("event_type"),
                event.get("tool"),
                event.get("detected_at"),
                _safe_int(event.get("pid")),
                event.get("full_command"),
                event.get("remote_ip"),
                str(event.get("remote_port")) if event.get("remote_port") is not None else None,
                event.get("remote_host"),
                event.get("message"),
                _normalize_risk(event.get("risk_level")),
            ),
        )
        conn.commit()
        conn.close()


def replace_terminal_events(session_id: str, roll_no: str, event_list: list[dict]) -> None:
    with _DB_LOCK:
        conn = _connect()
        conn.execute("DELETE FROM terminal_events WHERE session_id = ? AND roll_no = ?", (session_id, roll_no))
        for event in event_list or []:
            if not isinstance(event, dict):
                continue
            conn.execute(
                """
                INSERT INTO terminal_events (
                    session_id, roll_no, id, event_type, tool, detected_at, pid,
                    full_command, remote_ip, remote_port, remote_host, message, risk_level, synced
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    session_id,
                    roll_no,
                    event.get("id"),
                    event.get("event_type"),
                    event.get("tool"),
                    event.get("detected_at"),
                    _safe_int(event.get("pid")),
                    event.get("full_command"),
                    event.get("remote_ip"),
                    str(event.get("remote_port")) if event.get("remote_port") is not None else None,
                    event.get("remote_host"),
                    event.get("message"),
                    _normalize_risk(event.get("risk_level")),
                ),
            )
        conn.commit()
        conn.close()


def _parse_device_metadata(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _load_devices(conn: sqlite3.Connection, session_id: str, roll_no: str, unsynced_only: bool) -> tuple[list[dict], list[int]]:
    where_synced = " AND synced = 0" if unsynced_only else ""
    rows = conn.execute(
        f"""
        SELECT rowid, id, readable_name, message, risk_level, metadata, device_type
        FROM usb_devices
        WHERE session_id = ? AND roll_no = ?{where_synced}
        ORDER BY rowid DESC
        """,
        (session_id, roll_no),
    ).fetchall()

    out = []
    ids = []
    for row in rows:
        item = dict(row)
        ids.append(int(item.pop("rowid")))
        item["metadata"] = _parse_device_metadata(item.get("metadata"))
        out.append(item)
    return out, ids


def _load_browser_history(conn: sqlite3.Connection, session_id: str, roll_no: str, unsynced_only: bool) -> tuple[list[dict], list[int]]:
    where_synced = " AND synced = 0" if unsynced_only else ""
    rows = conn.execute(
        f"""
        SELECT rowid, url, title, visit_count, last_visited, browser
        FROM browser_history
        WHERE session_id = ? AND roll_no = ?{where_synced}
        ORDER BY COALESCE(last_visited, 0) DESC
        """,
        (session_id, roll_no),
    ).fetchall()
    out = []
    ids = []
    for row in rows:
        item = dict(row)
        ids.append(int(item.pop("rowid")))
        out.append(item)
    return out, ids


def _load_processes(conn: sqlite3.Connection, session_id: str, roll_no: str, unsynced_only: bool) -> tuple[list[dict], list[int]]:
    where_synced = " AND synced = 0" if unsynced_only else ""
    rows = conn.execute(
        f"""
        SELECT rowid, pid, name, label, cpu, memory, status, risk_level
        FROM processes
        WHERE session_id = ? AND roll_no = ?{where_synced}
        ORDER BY rowid DESC
        """,
        (session_id, roll_no),
    ).fetchall()
    out = []
    ids = []
    for row in rows:
        item = dict(row)
        ids.append(int(item.pop("rowid")))
        out.append(item)
    return out, ids


def _load_terminal_events(conn: sqlite3.Connection, session_id: str, roll_no: str, unsynced_only: bool) -> tuple[list[dict], list[int]]:
    where_synced = " AND synced = 0" if unsynced_only else ""
    rows = conn.execute(
        f"""
        SELECT rowid, id, event_type, tool, detected_at, pid, full_command,
               remote_ip, remote_port, remote_host, message, risk_level
        FROM terminal_events
        WHERE session_id = ? AND roll_no = ?{where_synced}
        ORDER BY detected_at DESC
        """,
        (session_id, roll_no),
    ).fetchall()
    out = []
    ids = []
    for row in rows:
        item = dict(row)
        ids.append(int(item.pop("rowid")))
        out.append(item)
    return out, ids


def get_all_for_session(session_id: str, roll_no: str) -> dict:
    with _DB_LOCK:
        conn = _connect()
        devices, _ = _load_devices(conn, session_id, roll_no, unsynced_only=False)
        browser_history, _ = _load_browser_history(conn, session_id, roll_no, unsynced_only=False)
        processes, _ = _load_processes(conn, session_id, roll_no, unsynced_only=False)
        terminal_events, _ = _load_terminal_events(conn, session_id, roll_no, unsynced_only=False)
        conn.close()

    return {
        "devices": devices,
        "browserHistory": browser_history,
        "processes": processes,
        "terminalEvents": terminal_events,
    }


def get_unsynced(session_id: str, roll_no: str) -> tuple[dict, dict[str, list[int]]]:
    with _DB_LOCK:
        conn = _connect()
        devices, device_ids = _load_devices(conn, session_id, roll_no, unsynced_only=True)
        browser_history, browser_ids = _load_browser_history(conn, session_id, roll_no, unsynced_only=True)
        processes, process_ids = _load_processes(conn, session_id, roll_no, unsynced_only=True)
        terminal_events, terminal_ids = _load_terminal_events(conn, session_id, roll_no, unsynced_only=True)
        conn.close()

    return (
        {
            "devices": devices,
            "browserHistory": browser_history,
            "processes": processes,
            "terminalEvents": terminal_events,
        },
        {
            "devices": device_ids,
            "browserHistory": browser_ids,
            "processes": process_ids,
            "terminalEvents": terminal_ids,
        },
    )


def mark_synced(session_id: str, roll_no: str) -> None:
    with _DB_LOCK:
        conn = _connect()
        conn.execute("UPDATE usb_devices SET synced = 1 WHERE session_id = ? AND roll_no = ?", (session_id, roll_no))
        conn.execute("UPDATE browser_history SET synced = 1 WHERE session_id = ? AND roll_no = ?", (session_id, roll_no))
        conn.execute("UPDATE processes SET synced = 1 WHERE session_id = ? AND roll_no = ?", (session_id, roll_no))
        conn.execute("UPDATE terminal_events SET synced = 1 WHERE session_id = ? AND roll_no = ?", (session_id, roll_no))
        conn.commit()
        conn.close()


def get_session_info(session_id: str, roll_no: str) -> tuple[str, str]:
    with _DB_LOCK:
        conn = _connect()
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
        conn.close()
    if not row:
        return "", ""
    return row["name"] or "", row["lab_no"] or ""

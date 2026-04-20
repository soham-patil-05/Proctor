"""Local SQLite persistence for Lab Guardian telemetry."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Optional

_DB_LOCK = threading.Lock()
_DB_PATH = os.environ.get("LG_LOCAL_DB_PATH", os.path.abspath("labguardian_local.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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


def _normalize_risk(value: Any) -> str:
    risk = str(value or "normal").strip().lower()
    if risk not in {"high", "medium", "low", "normal", "safe"}:
        return "normal"
    return risk


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _ensure_synced_column(cur: sqlite3.Cursor, table_name: str) -> None:
    try:
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN synced INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        # Safe for existing DBs where the column already exists.
        pass


def _ensure_optional_column(cur: sqlite3.Cursor, table_name: str, column_sql: str) -> None:
    try:
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")
    except sqlite3.OperationalError:
        pass


def init_db(db_path: Optional[str] = None) -> sqlite3.Connection:
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

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS processes (
                session_id TEXT NOT NULL,
                roll_no    TEXT NOT NULL,
                pid        INTEGER,
                name       TEXT,
                label      TEXT,
                cpu        REAL,
                memory     REAL,
                status     TEXT,
                risk_level TEXT,
                category   TEXT,
                detected_at TEXT,
                synced     INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS usb_devices (
                session_id    TEXT NOT NULL,
                roll_no       TEXT NOT NULL,
                id            TEXT,
                readable_name TEXT,
                message       TEXT,
                risk_level    TEXT,
                metadata      TEXT,
                device_type   TEXT,
                detected_at   TEXT,
                synced        INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS browser_history (
                session_id   TEXT NOT NULL,
                roll_no      TEXT NOT NULL,
                url          TEXT,
                title        TEXT,
                visit_count  INTEGER,
                last_visited REAL,
                browser      TEXT,
                synced       INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS terminal_events (
                session_id   TEXT NOT NULL,
                roll_no      TEXT NOT NULL,
                event_type   TEXT,
                tool         TEXT,
                remote_ip    TEXT,
                remote_host  TEXT,
                remote_port  TEXT,
                pid          INTEGER,
                full_command TEXT,
                risk_level   TEXT,
                message      TEXT,
                detected_at  TEXT,
                synced       INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        for table in ("processes", "usb_devices", "browser_history", "terminal_events"):
            _ensure_synced_column(cur, table)

        _ensure_optional_column(cur, "processes", "category TEXT")
        _ensure_optional_column(cur, "processes", "detected_at TEXT")
        _ensure_optional_column(cur, "usb_devices", "detected_at TEXT")

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


def replace_processes(session_id: str, roll_no: str, process_list: list[dict]) -> None:
    with _DB_LOCK:
        conn = _connect()
        for process in process_list or []:
            if not isinstance(process, dict):
                continue
            conn.execute(
                """
                INSERT INTO processes (session_id, roll_no, pid, name, label, cpu, memory, status, risk_level, category, detected_at, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    session_id,
                    roll_no,
                    _safe_int(process.get("pid")),
                    process.get("name"),
                    process.get("label"),
                    _safe_float(process.get("cpu")),
                    _safe_float(process.get("memory")),
                    process.get("status") or "running",
                    _normalize_risk(process.get("risk_level")),
                    process.get("category"),
                    process.get("detected_at") or _now_iso(),
                ),
            )
        conn.commit()
        conn.close()


def upsert_process(session_id: str, roll_no: str, process: dict) -> None:
    if not isinstance(process, dict):
        return
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO processes (session_id, roll_no, pid, name, label, cpu, memory, status, risk_level, category, detected_at, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                session_id,
                roll_no,
                _safe_int(process.get("pid")),
                process.get("name"),
                process.get("label"),
                _safe_float(process.get("cpu")),
                _safe_float(process.get("memory")),
                process.get("status") or "running",
                _normalize_risk(process.get("risk_level")),
                process.get("category"),
                process.get("detected_at") or _now_iso(),
            ),
        )
        conn.commit()
        conn.close()


def update_process(session_id: str, roll_no: str, process: dict) -> None:
    # Append-only semantics: updates become new rows.
    upsert_process(session_id, roll_no, process)


def delete_process(session_id: str, roll_no: str, pid: int) -> None:
    # Append-only semantics: process_end is persisted as status=ended event row.
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO processes (session_id, roll_no, pid, name, label, cpu, memory, status, risk_level, category, detected_at, synced)
            VALUES (?, ?, ?, NULL, NULL, NULL, NULL, 'ended', NULL, NULL, ?, 0)
            """,
            (session_id, roll_no, _safe_int(pid), _now_iso()),
        )
        conn.commit()
        conn.close()


def replace_devices(session_id: str, roll_no: str, device_list: list[dict]) -> None:
    with _DB_LOCK:
        conn = _connect()
        for device in device_list or []:
            if not isinstance(device, dict):
                continue
            metadata = device.get("metadata") if isinstance(device.get("metadata"), dict) else {}
            conn.execute(
                """
                INSERT INTO usb_devices (session_id, roll_no, id, readable_name, message, risk_level, metadata, device_type, detected_at, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    session_id,
                    roll_no,
                    str(device.get("id") or "").strip() or None,
                    device.get("readable_name"),
                    device.get("message"),
                    _normalize_risk(device.get("risk_level")),
                    json.dumps(metadata, ensure_ascii=True),
                    device.get("device_type") or "usb",
                    device.get("detected_at") or _now_iso(),
                ),
            )
        conn.commit()
        conn.close()


def upsert_device(session_id: str, roll_no: str, device: dict) -> None:
    if not isinstance(device, dict):
        return
    with _DB_LOCK:
        conn = _connect()
        metadata = device.get("metadata") if isinstance(device.get("metadata"), dict) else {}
        conn.execute(
            """
            INSERT INTO usb_devices (session_id, roll_no, id, readable_name, message, risk_level, metadata, device_type, detected_at, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                session_id,
                roll_no,
                str(device.get("id") or "").strip() or None,
                device.get("readable_name"),
                device.get("message"),
                _normalize_risk(device.get("risk_level")),
                json.dumps(metadata, ensure_ascii=True),
                device.get("device_type") or "usb",
                device.get("detected_at") or _now_iso(),
            ),
        )
        conn.commit()
        conn.close()


def remove_device(session_id: str, roll_no: str, device_id: str) -> None:
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO usb_devices (session_id, roll_no, id, readable_name, message, risk_level, metadata, device_type, detected_at, synced)
            VALUES (?, ?, ?, NULL, 'Device disconnected', 'low', '{}', 'usb', ?, 0)
            """,
            (session_id, roll_no, str(device_id or "").strip() or None, _now_iso()),
        )
        conn.commit()
        conn.close()


def upsert_browser_history(session_id: str, roll_no: str, entry: dict) -> None:
    if not isinstance(entry, dict):
        return
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO browser_history (session_id, roll_no, url, title, visit_count, last_visited, browser, synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                session_id,
                roll_no,
                entry.get("url"),
                entry.get("title"),
                _safe_int(entry.get("visit_count")) or 1,
                _safe_float(entry.get("last_visited")),
                entry.get("browser"),
            ),
        )
        conn.commit()
        conn.close()


def save_terminal_event(session_id: str, roll_no: str, event: dict) -> None:
    if not isinstance(event, dict):
        return
    with _DB_LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO terminal_events (
                session_id, roll_no, event_type, tool, remote_ip, remote_host, remote_port,
                pid, full_command, risk_level, message, detected_at, synced
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                session_id,
                roll_no,
                event.get("event_type"),
                event.get("tool"),
                event.get("remote_ip"),
                event.get("remote_host"),
                str(event.get("remote_port")) if event.get("remote_port") is not None else None,
                _safe_int(event.get("pid")),
                event.get("full_command"),
                _normalize_risk(event.get("risk_level")),
                event.get("message"),
                event.get("detected_at") or _now_iso(),
            ),
        )
        conn.commit()
        conn.close()


def insert_terminal_event(session_id: str, roll_no: str, event: dict) -> None:
    # Backward-compatible alias.
    save_terminal_event(session_id, roll_no, event)


def replace_terminal_events(session_id: str, roll_no: str, event_list: list[dict]) -> None:
    with _DB_LOCK:
        conn = _connect()
        for event in event_list or []:
            if not isinstance(event, dict):
                continue
            conn.execute(
                """
                INSERT INTO terminal_events (
                    session_id, roll_no, event_type, tool, remote_ip, remote_host, remote_port,
                    pid, full_command, risk_level, message, detected_at, synced
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    session_id,
                    roll_no,
                    event.get("event_type"),
                    event.get("tool"),
                    event.get("remote_ip"),
                    event.get("remote_host"),
                    str(event.get("remote_port")) if event.get("remote_port") is not None else None,
                    _safe_int(event.get("pid")),
                    event.get("full_command"),
                    _normalize_risk(event.get("risk_level")),
                    event.get("message"),
                    event.get("detected_at") or _now_iso(),
                ),
            )
        conn.commit()
        conn.close()


def _parse_metadata(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def get_all_for_session(session_id: str, roll_no: str) -> dict:
    with _DB_LOCK:
        conn = _connect()

        device_rows = conn.execute(
            """
            SELECT rowid AS _rowid, id, readable_name, message, risk_level, metadata, device_type, detected_at
            FROM usb_devices
            WHERE session_id = ? AND roll_no = ?
            ORDER BY COALESCE(detected_at, ''), rowid ASC
            """,
            (session_id, roll_no),
        ).fetchall()

        browser_rows = conn.execute(
            """
            SELECT rowid AS _rowid, url, title, visit_count, last_visited, browser
            FROM browser_history
            WHERE session_id = ? AND roll_no = ?
            ORDER BY COALESCE(last_visited, 0) ASC, rowid ASC
            """,
            (session_id, roll_no),
        ).fetchall()

        process_rows = conn.execute(
            """
            SELECT rowid AS _rowid, pid, name, label, cpu, memory, status, risk_level, category, detected_at
            FROM processes
            WHERE session_id = ? AND roll_no = ?
            ORDER BY COALESCE(detected_at, ''), rowid ASC
            """,
            (session_id, roll_no),
        ).fetchall()

        terminal_rows = conn.execute(
            """
            SELECT rowid AS _rowid, event_type, tool, remote_ip, remote_host, remote_port, pid,
                   full_command, risk_level, message, detected_at
            FROM terminal_events
            WHERE session_id = ? AND roll_no = ?
            ORDER BY COALESCE(detected_at, ''), rowid ASC
            """,
            (session_id, roll_no),
        ).fetchall()

        conn.close()

    devices = []
    for row in device_rows:
        item = dict(row)
        item["metadata"] = _parse_metadata(item.get("metadata"))
        devices.append(item)

    return {
        "devices": devices,
        "browserHistory": [dict(row) for row in browser_rows],
        "processes": [dict(row) for row in process_rows],
        "terminalEvents": [dict(row) for row in terminal_rows],
    }


def get_unsynced(session_id: str, roll_no: str) -> dict:
    with _DB_LOCK:
        conn = _connect()

        device_rows = conn.execute(
            """
            SELECT rowid AS _rowid, id, readable_name, message, risk_level, metadata, device_type, detected_at
            FROM usb_devices
            WHERE session_id = ? AND roll_no = ? AND synced = 0
            ORDER BY COALESCE(detected_at, ''), rowid ASC
            """,
            (session_id, roll_no),
        ).fetchall()

        browser_rows = conn.execute(
            """
            SELECT rowid AS _rowid, url, title, visit_count, last_visited, browser
            FROM browser_history
            WHERE session_id = ? AND roll_no = ? AND synced = 0
            ORDER BY COALESCE(last_visited, 0) ASC, rowid ASC
            """,
            (session_id, roll_no),
        ).fetchall()

        process_rows = conn.execute(
            """
            SELECT rowid AS _rowid, pid, name, label, cpu, memory, status, risk_level, category, detected_at
            FROM processes
            WHERE session_id = ? AND roll_no = ? AND synced = 0
            ORDER BY COALESCE(detected_at, ''), rowid ASC
            """,
            (session_id, roll_no),
        ).fetchall()

        terminal_rows = conn.execute(
            """
            SELECT rowid AS _rowid, event_type, tool, remote_ip, remote_host, remote_port, pid,
                   full_command, risk_level, message, detected_at
            FROM terminal_events
            WHERE session_id = ? AND roll_no = ? AND synced = 0
            ORDER BY COALESCE(detected_at, ''), rowid ASC
            """,
            (session_id, roll_no),
        ).fetchall()

        conn.close()

    devices = []
    for row in device_rows:
        item = dict(row)
        item["metadata"] = _parse_metadata(item.get("metadata"))
        devices.append(item)

    return {
        "processes": [dict(row) for row in process_rows],
        "devices": devices,
        "browserHistory": [dict(row) for row in browser_rows],
        "terminalEvents": [dict(row) for row in terminal_rows],
    }


def mark_synced(session_id: str, roll_no: str) -> None:
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute("BEGIN")
            conn.execute(
                "UPDATE processes SET synced = 1 WHERE session_id = ? AND roll_no = ? AND synced = 0",
                (session_id, roll_no),
            )
            conn.execute(
                "UPDATE usb_devices SET synced = 1 WHERE session_id = ? AND roll_no = ? AND synced = 0",
                (session_id, roll_no),
            )
            conn.execute(
                "UPDATE browser_history SET synced = 1 WHERE session_id = ? AND roll_no = ? AND synced = 0",
                (session_id, roll_no),
            )
            conn.execute(
                "UPDATE terminal_events SET synced = 1 WHERE session_id = ? AND roll_no = ? AND synced = 0",
                (session_id, roll_no),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
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

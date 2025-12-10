from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import current_app, g

SCHEMA_VERSION = 3
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"


def init_app(app) -> None:
    """Configure database lifecycle and ensure schema exists."""

    app.teardown_appcontext(_close_connection)

    with app.app_context():
        _ensure_schema()


def _get_connection() -> sqlite3.Connection:
    if "db_conn" not in g:
        db_path = Path(current_app.config["APP_SETTINGS"].db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        g.db_conn = conn
    return g.db_conn


def _close_connection(_=None) -> None:
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    for column in columns:
        name = column["name"] if isinstance(column, sqlite3.Row) else column[1]
        if name == column_name:
            return True
    return False


def _create_base_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sid TEXT UNIQUE,
            direction TEXT NOT NULL CHECK(direction IN ('inbound', 'outbound')),
            to_number TEXT,
            from_number TEXT,
            body TEXT NOT NULL,
            status TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_messages_sid ON messages(sid);
        CREATE INDEX IF NOT EXISTS idx_messages_created_at
            ON messages(created_at);
        CREATE INDEX IF NOT EXISTS idx_messages_direction_created_at
            ON messages(direction, created_at);

        CREATE TABLE IF NOT EXISTS auto_reply_config (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            enabled INTEGER NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '',
            enabled_since TEXT
        );
        INSERT OR IGNORE INTO auto_reply_config (id, enabled, message, enabled_since)
             VALUES (1, 0, '', NULL);

        CREATE TABLE IF NOT EXISTS scheduled_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            to_number TEXT NOT NULL,
            body TEXT NOT NULL,
            interval_seconds INTEGER NOT NULL CHECK(interval_seconds >= 60),
            enabled INTEGER NOT NULL DEFAULT 1,
            last_sent_at TEXT,
            next_run_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_scheduled_enabled_next_run
            ON scheduled_messages(enabled, next_run_at);
        """
    )


def _migration_add_auto_reply_enabled_since(conn: sqlite3.Connection) -> None:
    if not _column_exists(conn, "auto_reply_config", "enabled_since"):
        conn.execute("ALTER TABLE auto_reply_config ADD COLUMN enabled_since TEXT")
        conn.execute(
            "UPDATE auto_reply_config SET enabled_since = NULL WHERE enabled_since IS NULL"
        )


def _migration_add_message_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_direction_created_at ON messages(direction, created_at)"
    )


def _ensure_schema() -> None:
    db_path = Path(current_app.config["APP_SETTINGS"].db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        current_version_row = conn.execute("PRAGMA user_version").fetchone()
        current_version = int(current_version_row[0]) if current_version_row else 0

        has_messages_table = _table_exists(conn, "messages")

        if current_version == 0 and not has_messages_table:
            _create_base_schema(conn)
            current_version = SCHEMA_VERSION
        else:
            if current_version == 0:
                current_version = 1

            if current_version < 2:
                _migration_add_auto_reply_enabled_since(conn)
                current_version = 2

            if current_version < 3:
                _migration_add_message_indexes(conn)
                current_version = 3

        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()


def _utc_timestamp() -> str:
    return datetime.utcnow().strftime(_TIMESTAMP_FORMAT)


def _utc_after(seconds: int) -> str:
    return (datetime.utcnow() + timedelta(seconds=seconds)).strftime(_TIMESTAMP_FORMAT)


def _safe_fromiso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def upsert_message(
    *,
    sid: Optional[str],
    direction: str,
    to_number: Optional[str],
    from_number: Optional[str],
    body: str,
    status: Optional[str],
    error: Optional[str],
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
) -> int:
    conn = _get_connection()
    now = _utc_timestamp()
    created_value = created_at or now
    updated_value = updated_at or now

    def _update_record(record_id: int, *, set_sid: bool) -> int:
        if set_sid:
            query = """
                UPDATE messages
                   SET sid = ?,
                       direction = ?,
                       to_number = ?,
                       from_number = ?,
                       body = ?,
                       status = ?,
                       error = ?,
                       created_at = ?,
                       updated_at = ?
                 WHERE id = ?
                """
            params = (
                sid,
                direction,
                to_number,
                from_number,
                body,
                status,
                error,
                created_value,
                updated_value,
                record_id,
            )
        else:
            query = """
                UPDATE messages
                   SET direction = ?,
                       to_number = ?,
                       from_number = ?,
                       body = ?,
                       status = ?,
                       error = ?,
                       created_at = ?,
                       updated_at = ?
                 WHERE id = ?
                """
            params = (
                direction,
                to_number,
                from_number,
                body,
                status,
                error,
                created_value,
                updated_value,
                record_id,
            )

        conn.execute(query, params)
        conn.commit()
        return record_id

    if sid:
        placeholder = conn.execute(
            """
            SELECT id, created_at
              FROM messages
             WHERE sid IS NULL
               AND direction = ?
               AND ((from_number = ?) OR (from_number IS NULL AND ? IS NULL))
               AND ((to_number = ?) OR (to_number IS NULL AND ? IS NULL))
          ORDER BY datetime(created_at) DESC, id DESC
             LIMIT 1
            """,
            (direction, from_number, from_number, to_number, to_number),
        ).fetchone()

        if placeholder:
            placeholder_dt = _safe_fromiso(placeholder["created_at"])
            desired_dt = _safe_fromiso(created_value)
            use_placeholder = True
            if placeholder_dt and desired_dt:
                use_placeholder = abs((desired_dt - placeholder_dt).total_seconds()) <= 600
            if use_placeholder:
                return _update_record(int(placeholder["id"]), set_sid=True)

        try:
            cursor = conn.execute(
                """
                INSERT INTO messages (
                    sid,
                    direction,
                    to_number,
                    from_number,
                    body,
                    status,
                    error,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sid, direction, to_number, from_number, body, status, error, created_value, updated_value),
            )
            conn.commit()
            return int(cursor.lastrowid)
        except sqlite3.IntegrityError:
            existing = conn.execute(
                "SELECT id FROM messages WHERE sid = ?",
                (sid,),
            ).fetchone()
            if existing:
                return _update_record(int(existing["id"]), set_sid=False)
            raise

    cursor = conn.execute(
        """
        INSERT INTO messages (
            sid,
            direction,
            to_number,
            from_number,
            body,
            status,
            error,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (sid, direction, to_number, from_number, body, status, error, created_value, updated_value),
    )
    conn.commit()
    return int(cursor.lastrowid)


def insert_message(
    *,
    direction: str,
    body: str,
    sid: Optional[str] = None,
    to_number: Optional[str] = None,
    from_number: Optional[str] = None,
    status: Optional[str] = None,
    error: Optional[str] = None,
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
) -> int:
    conn = _get_connection()
    now = _utc_timestamp()
    created_value = created_at or now
    updated_value = updated_at or now
    cursor = conn.execute(
        """
        INSERT INTO messages (
            sid,
            direction,
            to_number,
            from_number,
            body,
            status,
            error,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (sid, direction, to_number, from_number, body, status, error, created_value, updated_value),
    )
    conn.commit()
    return int(cursor.lastrowid)


def update_message_status_by_sid(
    *, sid: str, status: Optional[str], error: Optional[str] = None
) -> bool:
    conn = _get_connection()
    now = _utc_timestamp()
    cursor = conn.execute(
        """
        UPDATE messages
           SET status = ?,
               error = CASE WHEN ? IS NOT NULL THEN ? ELSE error END,
               updated_at = ?
         WHERE sid = ?
        """,
        (status, error, error, now, sid),
    )
    conn.commit()
    return cursor.rowcount > 0


def list_messages(
    limit: int = 50,
    direction: Optional[str] = None,
    participant: Optional[str] = None,
    ascending: bool = False,
) -> List[Dict[str, Any]]:
    conn = _get_connection()
    query = (
        "SELECT id, sid, direction, to_number, from_number, body, status, error, created_at, updated_at "
        "FROM messages"
    )
    params: List[Any] = []
    clauses = []

    if direction in {"inbound", "outbound"}:
        clauses.append("direction = ?")
        params.append(direction)

    if participant:
        clauses.append("(to_number = ? OR from_number = ?)")
        params.extend([participant, participant])

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    order = "ASC" if ascending else "DESC"
    query += f" ORDER BY datetime(created_at) {order}, id {order} LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_conversations(limit: int = 30) -> List[Dict[str, Any]]:
    """Return distinct participants with latest message metadata."""

    conn = _get_connection()
    query = (
        """
        WITH normalized AS (
            SELECT
                id,
                CASE WHEN direction = 'inbound' THEN from_number ELSE to_number END AS participant,
                direction,
                body,
                status,
                error,
                created_at,
                updated_at
            FROM messages
        ),
        filtered AS (
            SELECT * FROM normalized
             WHERE participant IS NOT NULL AND TRIM(participant) <> ''
        ),
        ranked AS (
            SELECT
                *,
                ROW_NUMBER() OVER (PARTITION BY participant ORDER BY datetime(created_at) DESC, id DESC) AS rownum,
                COUNT(*) OVER (PARTITION BY participant) AS total_messages
            FROM filtered
        )
        SELECT
            participant,
            body AS last_body,
            direction AS last_direction,
            status AS last_status,
            error AS last_error,
            created_at AS last_created_at,
            updated_at AS last_updated_at,
            total_messages
        FROM ranked
        WHERE rownum = 1
        ORDER BY datetime(last_created_at) DESC, participant
        LIMIT ?
        """
    )

    rows = conn.execute(query, (limit,)).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_last_inbound_id() -> int:
    conn = _get_connection()
    row = conn.execute(
        "SELECT MAX(id) AS max_id FROM messages WHERE direction = 'inbound'"
    ).fetchone()
    return int(row["max_id"]) if row and row["max_id"] is not None else 0


def list_inbound_after(last_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    conn = _get_connection()
    rows = conn.execute(
        """
        SELECT id, sid, direction, to_number, from_number, body, status, error, created_at, updated_at
          FROM messages
         WHERE direction = 'inbound' AND id > ?
      ORDER BY id ASC
         LIMIT ?
        """,
        (last_id, limit),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_auto_reply_config() -> Dict[str, Any]:
    conn = _get_connection()
    row = conn.execute(
        "SELECT id, enabled, message, enabled_since FROM auto_reply_config WHERE id = 1"
    ).fetchone()
    if row is None:
        # Fallback to defaults if somehow missing
        conn.execute(
            "INSERT OR IGNORE INTO auto_reply_config (id, enabled, message, enabled_since) VALUES (1, 0, '', NULL)"
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, enabled, message, enabled_since FROM auto_reply_config WHERE id = 1"
        ).fetchone()
        if row is None:
            return {"enabled": False, "message": "", "enabled_since": None}

    return {
        "enabled": bool(row["enabled"]),
        "message": row["message"] or "",
        "enabled_since": row["enabled_since"],
    }


def set_auto_reply_config(*, enabled: bool, message: str) -> None:
    conn = _get_connection()
    current_cfg = get_auto_reply_config()
    now = _utc_timestamp()
    if enabled:
        if current_cfg.get("enabled"):
            enabled_since = current_cfg.get("enabled_since") or now
        else:
            enabled_since = now
    else:
        enabled_since = None

    conn.execute(
        "UPDATE auto_reply_config SET enabled = ?, message = ?, enabled_since = ? WHERE id = 1",
        (1 if enabled else 0, message or "", enabled_since),
    )
    conn.commit()


def get_message_stats() -> Dict[str, Any]:
    conn = _get_connection()

    counts = conn.execute(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN direction = 'inbound' THEN 1 ELSE 0 END) as inbound,
            SUM(CASE WHEN direction = 'outbound' THEN 1 ELSE 0 END) as outbound
        FROM messages
        """
    ).fetchone()

    latest = conn.execute(
        """
        SELECT id, sid, direction, to_number, from_number, body, status, error, created_at
          FROM messages
      ORDER BY created_at DESC
         LIMIT 1
        """
    ).fetchone()

    total = int(counts["total"]) if counts and counts["total"] is not None else 0
    inbound = int(counts["inbound"]) if counts and counts["inbound"] is not None else 0
    outbound = int(counts["outbound"]) if counts and counts["outbound"] is not None else 0

    return {
        "total": total,
        "inbound": inbound,
        "outbound": outbound,
        "latest": _row_to_dict(latest) if latest else None,
    }


def _row_to_dict(row: Optional[sqlite3.Row]) -> Dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def delete_message_by_sid(sid: str) -> bool:
    conn = _get_connection()
    cursor = conn.execute("DELETE FROM messages WHERE sid = ?", (sid,))
    conn.commit()
    return cursor.rowcount > 0


# Scheduled messages (reminders)


def list_scheduled_messages() -> List[Dict[str, Any]]:
    conn = _get_connection()
    rows = conn.execute(
        """
        SELECT id, to_number, body, interval_seconds, enabled, last_sent_at, next_run_at, created_at, updated_at
          FROM scheduled_messages
      ORDER BY datetime(created_at) DESC, id DESC
        """
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def create_scheduled_message(*, to_number: str, body: str, interval_seconds: int, enabled: bool = True) -> int:
    conn = _get_connection()
    now = _utc_timestamp()
    next_run = _utc_after(interval_seconds)
    cursor = conn.execute(
        """
        INSERT INTO scheduled_messages (to_number, body, interval_seconds, enabled, last_sent_at, next_run_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, NULL, ?, ?, ?)
        """,
        (to_number, body, interval_seconds, 1 if enabled else 0, next_run, now, now),
    )
    conn.commit()
    return int(cursor.lastrowid)


def update_scheduled_message(
    *,
    sched_id: int,
    to_number: Optional[str] = None,
    body: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    enabled: Optional[bool] = None,
) -> bool:
    conn = _get_connection()
    fields = []
    params: List[Any] = []

    if to_number is not None:
        fields.append("to_number = ?")
        params.append(to_number)
    if body is not None:
        fields.append("body = ?")
        params.append(body)
    if interval_seconds is not None:
        fields.append("interval_seconds = ?")
        params.append(interval_seconds)
    if enabled is not None:
        fields.append("enabled = ?")
        params.append(1 if enabled else 0)

    if not fields:
        return False

    fields.append("updated_at = ?")
    params.append(_utc_timestamp())
    params.append(sched_id)

    cursor = conn.execute(
        f"UPDATE scheduled_messages SET {', '.join(fields)} WHERE id = ?",
        params,
    )
    conn.commit()
    return cursor.rowcount > 0


def delete_scheduled_message(sched_id: int) -> bool:
    conn = _get_connection()
    cursor = conn.execute("DELETE FROM scheduled_messages WHERE id = ?", (sched_id,))
    conn.commit()
    return cursor.rowcount > 0


def mark_scheduled_sent(sched_id: int, interval_seconds: int) -> None:
    conn = _get_connection()
    now = _utc_timestamp()
    next_run = _utc_after(interval_seconds)
    conn.execute(
        """
        UPDATE scheduled_messages
           SET last_sent_at = ?,
               next_run_at = ?,
               updated_at = ?
         WHERE id = ?
        """,
        (now, next_run, now, sched_id),
    )
    conn.commit()


def list_due_scheduled_messages(limit: int = 20) -> List[Dict[str, Any]]:
    conn = _get_connection()
    now = _utc_timestamp()
    rows = conn.execute(
        """
        SELECT id, to_number, body, interval_seconds, enabled, last_sent_at, next_run_at, created_at, updated_at
          FROM scheduled_messages
         WHERE enabled = 1
           AND next_run_at IS NOT NULL
           AND datetime(next_run_at) <= datetime(?)
      ORDER BY datetime(next_run_at) ASC, id ASC
         LIMIT ?
        """,
        (now, limit),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import current_app, g


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


def _ensure_schema() -> None:
    db_path = Path(current_app.config["APP_SETTINGS"].db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sid TEXT,
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
            CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_sid_unique
                ON messages(sid)
             WHERE sid IS NOT NULL;

            CREATE TABLE IF NOT EXISTS auto_reply_config (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                enabled INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT ''
            );
            INSERT OR IGNORE INTO auto_reply_config (id, enabled, message)
                 VALUES (1, 0, '');
            """
        )
        conn.commit()
    finally:
        conn.close()


def _utc_timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


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

    if sid:
        existing = conn.execute(
            "SELECT id FROM messages WHERE sid = ?",
            (sid,),
        ).fetchone()
        if existing:
            record_id = int(existing["id"])
            conn.execute(
                """
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
                """,
                (
                    direction,
                    to_number,
                    from_number,
                    body,
                    status,
                    error,
                    created_value,
                    updated_value,
                    record_id,
                ),
            )
            conn.commit()
            return record_id

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
) -> int:
    conn = _get_connection()
    now = _utc_timestamp()
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
        (sid, direction, to_number, from_number, body, status, error, now, now),
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
        "SELECT id, enabled, message FROM auto_reply_config WHERE id = 1"
    ).fetchone()
    if row is None:
        # Fallback to defaults if somehow missing
        conn.execute(
            "INSERT OR IGNORE INTO auto_reply_config (id, enabled, message) VALUES (1, 0, '')"
        )
        conn.commit()
        return {"enabled": False, "message": ""}

    return {
        "enabled": bool(row["enabled"]),
        "message": row["message"] or "",
    }


def set_auto_reply_config(*, enabled: bool, message: str) -> None:
    conn = _get_connection()
    conn.execute(
        "UPDATE auto_reply_config SET enabled = ?, message = ? WHERE id = 1",
        (1 if enabled else 0, message or ""),
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

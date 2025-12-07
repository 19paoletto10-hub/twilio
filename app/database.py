from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import current_app, g


# Shared schema SQL so we can create schema for file-backed or in-memory DBs
SCHEMA_SQL = """
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


def init_app(app) -> None:
    """Configure database lifecycle and ensure schema exists."""

    app.teardown_appcontext(_close_connection)

    with app.app_context():
        try:
            _ensure_schema()
        except RuntimeError as exc:
            # If the configured DB path is not writable (common with Docker mounts),
            # attempt a fallback to a writable path under /tmp. If that also fails,
            # create an in-memory DB so the app can continue running in degraded
            # mode (data will not persist across restarts).
            current_app.logger.warning(
                "Database not writable at %s: %s. Attempting fallback to /tmp.",
                app.config["APP_SETTINGS"].db_path,
                exc,
            )

            fallback = Path("/tmp/twilio_app.db")
            try:
                fallback.parent.mkdir(parents=True, exist_ok=True)
                # Mutate AppSettings.db_path to point to fallback file
                app.config["APP_SETTINGS"].db_path = str(fallback)
                _ensure_schema()
                app.config["DB_FALLBACK_PATH"] = str(fallback)
                current_app.logger.info("Initialized fallback SQLite DB at %s", fallback)
            except Exception as exc2:  # noqa: BLE001
                current_app.logger.exception("Fallback DB initialization failed: %s", exc2)
                # As a last resort, allow an in-memory DB (non-persistent). This
                # keeps the app available for demos/tests but data will be ephemeral.
                app.config["DB_DISABLED"] = False
                conn = sqlite3.connect(":memory:")
                conn.row_factory = sqlite3.Row
                # Create schema in-memory
                conn.executescript(SCHEMA_SQL)
                conn.commit()
                g.db_conn = conn
                app.config["DB_IN_MEMORY"] = True


def _get_connection() -> sqlite3.Connection:
    if "db_conn" not in g:
        # If previously initialized in-memory connection exists on the app, reuse it
        if current_app.config.get("DB_IN_MEMORY"):
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            g.db_conn = conn
            return g.db_conn

        db_path = Path(current_app.config["APP_SETTINGS"].db_path)
        _assert_db_writable(db_path)
        # Use a slightly higher timeout to avoid busy errors under load
        conn = sqlite3.connect(str(db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        g.db_conn = conn
    return g.db_conn


def _close_connection(_=None) -> None:
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()


def _ensure_schema() -> None:
    db_path = Path(current_app.config["APP_SETTINGS"].db_path)
    _assert_db_writable(db_path)

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
    except sqlite3.OperationalError as exc:  # noqa: BLE001
        _raise_readonly_hint(db_path, exc)
    finally:
        conn.close()


def _assert_db_writable(db_path: Path) -> None:
    """Ensure that the SQLite file (or its directory) can be written to."""

    parent = db_path.parent
    parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists() and not os.access(db_path, os.W_OK):
        _raise_readonly_hint(db_path, OSError("database file is read-only"))

    test_file = parent / f".db-write-test-{os.getpid()}"
    try:
        with open(test_file, "wb") as handle:
            handle.write(b"ok")
    except OSError as exc:  # noqa: BLE001
        _raise_readonly_hint(db_path, exc)
    finally:
        try:
            test_file.unlink()
        except OSError:
            pass


def _raise_readonly_hint(db_path: Path, exc: Exception) -> None:
    message = (
        f"Cannot write to SQLite database at {db_path} ({exc}). "
        "If you are running inside Docker, ensure the mounted volume is writable (e.g. '-v $(pwd)/data:/app/data') "
        "or set DB_PATH to a writable location."
    )
    current_app.logger.error(message)
    raise RuntimeError(message) from exc


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

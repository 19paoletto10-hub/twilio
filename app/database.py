from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from flask import current_app, g

SCHEMA_VERSION = 8
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"
_NORMALIZE_PREFIXES = ("whatsapp:", "sms:", "mms:", "client:", "sip:")
_NORMALIZE_STRIP_CHARS = (" ", "-", "(", ")", ".", "_")


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


def normalize_contact(value: Optional[str]) -> str:
    if not value:
        return ""
    cleaned = value.strip()
    lowered = cleaned.lower()
    for prefix in _NORMALIZE_PREFIXES:
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            lowered = lowered[len(prefix) :]
            break

    normalized = cleaned.strip()
    for ch in _NORMALIZE_STRIP_CHARS:
        normalized = normalized.replace(ch, "")

    normalized = normalized.strip()
    if not normalized:
        return ""

    lowered_norm = normalized.lower()
    if lowered_norm.startswith("+00") and len(normalized) > 3:
        normalized = "+" + normalized[3:]
    elif lowered_norm.startswith("00") and len(normalized) > 2:
        normalized = "+" + normalized[2:]

    digits_only = normalized.lstrip("+")
    if digits_only.isdigit():
        if not digits_only:
            return ""
        return "+" + digits_only

    return normalized.lower()


def _normalized_sql(column: str) -> str:
    expr = f"LOWER({column})"
    for prefix in _NORMALIZE_PREFIXES:
        expr = f"REPLACE({expr}, '{prefix}', '')"
    for ch in _NORMALIZE_STRIP_CHARS:
        expr = f"REPLACE({expr}, '{ch}', '')"
    return expr


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

        CREATE TABLE IF NOT EXISTS ai_config (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            enabled INTEGER NOT NULL DEFAULT 0,
            api_key TEXT,
            system_prompt TEXT,
            target_number TEXT,
            target_number_normalized TEXT,
            model TEXT NOT NULL DEFAULT 'gpt-4o-mini',
            temperature REAL NOT NULL DEFAULT 0.7,
            enabled_source TEXT NOT NULL DEFAULT 'db',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        INSERT OR IGNORE INTO ai_config (id, enabled, model, temperature, enabled_source, updated_at, target_number_normalized)
             VALUES (1, 0, 'gpt-4o-mini', 0.7, 'db', '', '');

        CREATE TABLE IF NOT EXISTS multi_sms_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            body TEXT NOT NULL,
            sender_identity TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            error TEXT,
            total_recipients INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            invalid_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            scheduled_at TEXT,
            started_at TEXT,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS multi_sms_recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL REFERENCES multi_sms_batches(id) ON DELETE CASCADE,
            number_raw TEXT,
            number_normalized TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            sid TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            sent_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_multi_sms_batch_status
            ON multi_sms_batches(status, datetime(scheduled_at));
        CREATE INDEX IF NOT EXISTS idx_multi_sms_recipient_batch
            ON multi_sms_recipients(batch_id);
        CREATE INDEX IF NOT EXISTS idx_multi_sms_recipient_status
            ON multi_sms_recipients(batch_id, status);
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


def _migration_add_ai_config(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ai_config (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            enabled INTEGER NOT NULL DEFAULT 0,
            api_key TEXT,
            system_prompt TEXT,
            target_number TEXT,
            target_number_normalized TEXT,
            model TEXT NOT NULL DEFAULT 'gpt-4o-mini',
            temperature REAL NOT NULL DEFAULT 0.7,
            enabled_source TEXT NOT NULL DEFAULT 'db',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        INSERT OR IGNORE INTO ai_config (id, enabled, model, temperature, enabled_source, updated_at, target_number_normalized)
             VALUES (1, 0, 'gpt-4o-mini', 0.7, 'db', '', '');
        """
    )


def _migration_add_ai_normalized_target(conn: sqlite3.Connection) -> None:
    if _column_exists(conn, "ai_config", "target_number_normalized"):
        return

    conn.execute("ALTER TABLE ai_config ADD COLUMN target_number_normalized TEXT")
    row = conn.execute("SELECT target_number FROM ai_config WHERE id = 1").fetchone()
    normalized = normalize_contact(row["target_number"]) if row else ""
    conn.execute(
        "UPDATE ai_config SET target_number_normalized = ? WHERE id = 1",
        (normalized,),
    )


def _migration_add_ai_enabled_source(conn: sqlite3.Connection) -> None:
    if _column_exists(conn, "ai_config", "enabled_source"):
        return

    conn.execute("ALTER TABLE ai_config ADD COLUMN enabled_source TEXT NOT NULL DEFAULT 'db'")
    conn.execute(
        "UPDATE ai_config SET enabled_source = 'db' WHERE enabled_source IS NULL OR enabled_source = ''"
    )


def _migration_add_multi_sms_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS multi_sms_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            body TEXT NOT NULL,
            sender_identity TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            error TEXT,
            total_recipients INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            invalid_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            scheduled_at TEXT,
            started_at TEXT,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS multi_sms_recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL REFERENCES multi_sms_batches(id) ON DELETE CASCADE,
            number_raw TEXT,
            number_normalized TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            sid TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            sent_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_multi_sms_batch_status
            ON multi_sms_batches(status, datetime(scheduled_at));
        CREATE INDEX IF NOT EXISTS idx_multi_sms_recipient_batch
            ON multi_sms_recipients(batch_id);
        CREATE INDEX IF NOT EXISTS idx_multi_sms_recipient_status
            ON multi_sms_recipients(batch_id, status);
        """
    )


def _migration_add_app_settings(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'db',
            updated_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS settings_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            action TEXT NOT NULL,
            source TEXT NOT NULL,
            user_ip TEXT,
            created_at TEXT NOT NULL DEFAULT ''
        );
        """
    )


def _ensure_app_settings_table(conn: sqlite3.Connection) -> None:
    """Ensure app_settings/settings_audit tables exist (idempotent)."""
    if not _table_exists(conn, "app_settings") or not _table_exists(conn, "settings_audit"):
        _migration_add_app_settings(conn)


def _ensure_multi_sms_tables(conn: sqlite3.Connection) -> None:
    has_batches = _table_exists(conn, "multi_sms_batches")
    has_recipients = _table_exists(conn, "multi_sms_recipients")

    if has_batches and has_recipients:
        return

    _migration_add_multi_sms_tables(conn)


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

            if current_version < 4:
                _migration_add_ai_config(conn)
                current_version = 4

            if current_version < 5:
                _migration_add_ai_normalized_target(conn)
                current_version = 5

            if current_version < 6:
                _migration_add_ai_enabled_source(conn)
                current_version = 6

            if current_version < 7:
                _migration_add_multi_sms_tables(conn)
                current_version = 7

            if current_version < 8:
                _migration_add_app_settings(conn)
                current_version = 8

        _ensure_multi_sms_tables(conn)

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
    participant_normalized: Optional[str] = None,
    ascending: bool = False,
) -> List[Dict[str, Any]]:
    if participant and participant_normalized:
        raise ValueError("Provide either participant or participant_normalized, not both")

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
    elif participant_normalized:
        normalized_value = normalize_contact(participant_normalized)
        if not normalized_value:
            return []
        normalized_to = _normalized_sql("to_number")
        normalized_from = _normalized_sql("from_number")
        clauses.append(f"(({normalized_to}) = ? OR ({normalized_from}) = ?)")
        params.extend([normalized_value, normalized_value])

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY datetime(created_at) DESC, id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    items = [_row_to_dict(row) for row in rows]
    if ascending:
        items.reverse()
    return items


def _conversation_filter_clause(
    participant: Optional[str],
    participant_normalized: Optional[str],
) -> Tuple[str, List[Any]]:
    if participant_normalized:
        normalized_value = normalize_contact(participant_normalized)
        if normalized_value:
            normalized_to = _normalized_sql("to_number")
            normalized_from = _normalized_sql("from_number")
            clause = f"(({normalized_to}) = ? OR ({normalized_from}) = ?)"
            return clause, [normalized_value, normalized_value]

    if participant:
        trimmed = participant.strip()
        if trimmed:
            clause = "(to_number = ? OR from_number = ?)"
            return clause, [trimmed, trimmed]

    raise ValueError("Participant filter is required")


def list_conversation_message_refs(
    *,
    participant: str,
    participant_normalized: Optional[str] = None,
) -> List[Dict[str, Any]]:
    clause, params = _conversation_filter_clause(participant, participant_normalized)
    conn = _get_connection()
    query = f"SELECT id, sid FROM messages WHERE {clause} ORDER BY datetime(created_at) ASC, id ASC"
    rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def delete_conversation_messages(
    *,
    participant: str,
    participant_normalized: Optional[str] = None,
) -> int:
    clause, params = _conversation_filter_clause(participant, participant_normalized)
    conn = _get_connection()
    cursor = conn.execute(f"DELETE FROM messages WHERE {clause}", params)
    conn.commit()
    return cursor.rowcount


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


def get_ai_config() -> Dict[str, Any]:
    conn = _get_connection()
    row = conn.execute(
        """
        SELECT id,
               enabled,
               api_key,
               system_prompt,
               target_number,
               target_number_normalized,
               model,
               temperature,
             enabled_source,
               updated_at
          FROM ai_config
         WHERE id = 1
        """
    ).fetchone()

    if row is None:
        conn.execute(
            "INSERT OR IGNORE INTO ai_config (id, enabled, model, temperature, updated_at, target_number_normalized) VALUES (1, 0, 'gpt-4o-mini', 0.7, '', '')"
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, enabled, api_key, system_prompt, target_number, target_number_normalized, model, temperature, enabled_source, updated_at FROM ai_config WHERE id = 1"
        ).fetchone()

    target_raw = row["target_number"] or ""
    normalized_source = row["target_number_normalized"] or target_raw
    normalized = normalize_contact(normalized_source) or normalize_contact(target_raw)
    return {
        "enabled": bool(row["enabled"]),
        "api_key": row["api_key"],
        "system_prompt": row["system_prompt"] or "",
        "target_number": row["target_number"] or "",
        "target_number_normalized": normalized or "",
        "model": row["model"] or "gpt-4o-mini",
        "temperature": float(row["temperature"] or 0.7),
        "enabled_source": row["enabled_source"] or "db",
        "updated_at": row["updated_at"] or "",
    }


def set_ai_config(
    *,
    enabled: bool,
    api_key: Optional[str],
    system_prompt: Optional[str],
    target_number: Optional[str],
    model: Optional[str],
    temperature: Optional[float],
    enabled_source: Optional[str] = None,
) -> Dict[str, Any]:
    conn = _get_connection()
    current = get_ai_config()
    resolved_api_key = api_key if api_key is not None else current.get("api_key")
    resolved_prompt = system_prompt if system_prompt is not None else current.get("system_prompt", "")
    resolved_target = target_number if target_number is not None else current.get("target_number", "")
    resolved_target_normalized = normalize_contact(resolved_target)
    resolved_model = model if model is not None else current.get("model", "gpt-4o-mini")
    resolved_temperature = (
        float(temperature)
        if temperature is not None
        else float(current.get("temperature", 0.7) or 0.7)
    )
    current_source = current.get("enabled_source") or "db"
    resolved_enabled_source = enabled_source if enabled_source is not None else current_source

    conn.execute(
        """
        UPDATE ai_config
           SET enabled = ?,
               api_key = ?,
               system_prompt = ?,
               target_number = ?,
               target_number_normalized = ?,
               model = ?,
               temperature = ?,
               enabled_source = ?,
               updated_at = ?
         WHERE id = 1
        """,
        (
            1 if enabled else 0,
            resolved_api_key,
            resolved_prompt or "",
            resolved_target or "",
            resolved_target_normalized,
            resolved_model or "gpt-4o-mini",
            resolved_temperature,
            resolved_enabled_source,
            _utc_timestamp(),
        ),
    )
    conn.commit()
    return get_ai_config()


# ---------------------------------------------------------------------------
# App settings (non-secret)
# ---------------------------------------------------------------------------


def _insert_settings_audit(
    *,
    setting_key: str,
    old_value: Optional[str],
    new_value: Optional[str],
    action: str,
    source: str,
    user_ip: Optional[str] = None,
) -> None:
    conn = _get_connection()
    conn.execute(
        """
        INSERT INTO settings_audit (setting_key, old_value, new_value, action, source, user_ip, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (setting_key, old_value, new_value, action, source, user_ip, _utc_timestamp()),
    )
    conn.commit()


def get_app_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = _get_connection()
    _ensure_app_settings_table(conn)
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return default
    return row["value"]


def list_app_settings(keys: Optional[Sequence[str]] = None) -> Dict[str, str]:
    conn = _get_connection()
    _ensure_app_settings_table(conn)
    if keys:
        placeholders = ",".join(["?"] * len(keys))
        rows = conn.execute(
            f"SELECT key, value FROM app_settings WHERE key IN ({placeholders})",
            tuple(keys),
        ).fetchall()
    else:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def set_app_setting(
    *,
    key: str,
    value: str,
    source: str = "db",
    user_ip: Optional[str] = None,
) -> Dict[str, str]:
    conn = _get_connection()
    _ensure_app_settings_table(conn)
    existing = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    old_value = existing["value"] if existing else None

    conn.execute(
        """
        INSERT INTO app_settings (key, value, source, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value,
                      source = excluded.source,
                      updated_at = excluded.updated_at
        """,
        (key, value, source or "db", _utc_timestamp()),
    )
    conn.commit()

    _insert_settings_audit(
        setting_key=key,
        old_value=old_value,
        new_value=value,
        action="update" if existing else "create",
        source=source or "db",
        user_ip=user_ip,
    )

    return {"key": key, "value": value, "source": source or "db"}


def delete_app_setting(*, key: str, source: str = "db", user_ip: Optional[str] = None) -> bool:
    conn = _get_connection()
    _ensure_app_settings_table(conn)
    existing = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    if not existing:
        return False

    conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
    conn.commit()

    _insert_settings_audit(
        setting_key=key,
        old_value=existing["value"],
        new_value=None,
        action="delete",
        source=source or "db",
        user_ip=user_ip,
    )
    return True


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


# Multi-SMS batches & recipients


def _serialize_multi_sms_batch(row: Optional[sqlite3.Row]) -> Dict[str, Any]:
    if row is None:
        return {}

    total = int(row["total_recipients"] or 0)
    success = int(row["success_count"] or 0)
    failure = int(row["failure_count"] or 0)
    invalid = int(row["invalid_count"] or 0)
    pending = max(total - success - failure - invalid, 0)

    return {
        "id": int(row["id"]),
        "body": row["body"],
        "sender_identity": row["sender_identity"],
        "status": row["status"],
        "error": row["error"],
        "total_recipients": total,
        "success_count": success,
        "failure_count": failure,
        "invalid_count": invalid,
        "pending_count": pending,
        "created_at": row["created_at"],
        "scheduled_at": row["scheduled_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
    }


def _serialize_multi_sms_recipient(row: Optional[sqlite3.Row]) -> Dict[str, Any]:
    if row is None:
        return {}

    return {
        "id": int(row["id"]),
        "batch_id": int(row["batch_id"]),
        "number_raw": row["number_raw"],
        "number_normalized": row["number_normalized"],
        "status": row["status"],
        "sid": row["sid"],
        "error": row["error"],
        "created_at": row["created_at"],
        "sent_at": row["sent_at"],
    }


def create_multi_sms_batch(
    *,
    body: str,
    recipients: Sequence[str],
    sender_identity: Optional[str] = None,
    scheduled_at: Optional[str] = None,
) -> Dict[str, Any]:
    cleaned: List[Tuple[str, Optional[str]]] = []
    seen: Set[str] = set()
    for value in recipients:
        raw = (str(value or "").strip())
        if not raw:
            continue
        normalized = normalize_contact(raw)
        key = (normalized or raw).lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append((raw, normalized))

    if not cleaned:
        raise ValueError("Provide at least one valid recipient number.")

    conn = _get_connection()
    now = _utc_timestamp()
    scheduled_value = scheduled_at or now

    invalid_count = sum(1 for _, normalized in cleaned if not normalized)

    cursor = conn.execute(
        """
        INSERT INTO multi_sms_batches (
            body,
            sender_identity,
            status,
            error,
            total_recipients,
            success_count,
            failure_count,
            invalid_count,
            created_at,
            scheduled_at
        ) VALUES (?, ?, 'pending', NULL, ?, 0, 0, ?, ?, ?)
        """,
        (body, sender_identity, len(cleaned), invalid_count, now, scheduled_value),
    )
    batch_id = int(cursor.lastrowid)

    for raw, normalized in cleaned:
        status = 'pending' if normalized else 'invalid'
        error = None if normalized else 'Nie udało się znormalizować numeru.'
        conn.execute(
            """
            INSERT INTO multi_sms_recipients (
                batch_id,
                number_raw,
                number_normalized,
                status,
                sid,
                error,
                created_at,
                sent_at
            ) VALUES (?, ?, ?, ?, NULL, ?, ?, NULL)
            """,
            (batch_id, raw, normalized, status, error, now),
        )

    conn.commit()
    return get_multi_sms_batch(batch_id)


def get_multi_sms_batch(batch_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    row = conn.execute(
        "SELECT * FROM multi_sms_batches WHERE id = ?",
        (batch_id,),
    ).fetchone()
    return _serialize_multi_sms_batch(row) if row else None


def list_multi_sms_batches(limit: int = 20) -> List[Dict[str, Any]]:
    conn = _get_connection()
    rows = conn.execute(
        """
        SELECT *
          FROM multi_sms_batches
      ORDER BY datetime(created_at) DESC, id DESC
         LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_serialize_multi_sms_batch(row) for row in rows]


def list_multi_sms_recipients(
    batch_id: int,
    *,
    statuses: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    conn = _get_connection()
    query = "SELECT * FROM multi_sms_recipients WHERE batch_id = ?"
    params: List[Any] = [batch_id]

    if statuses:
        filtered = [status.strip() for status in statuses if status and status.strip()]
        if filtered:
            placeholders = ",".join(["?"] * len(filtered))
            query += f" AND status IN ({placeholders})"
            params.extend(filtered)

    query += " ORDER BY id ASC"
    rows = conn.execute(query, params).fetchall()
    return [_serialize_multi_sms_recipient(row) for row in rows]


def reserve_next_multi_sms_batch() -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    now = _utc_timestamp()
    row = conn.execute(
        """
        SELECT id
          FROM multi_sms_batches
         WHERE status = 'pending'
           AND (scheduled_at IS NULL OR datetime(scheduled_at) <= datetime(?))
           AND EXISTS (
                SELECT 1 FROM multi_sms_recipients r
                 WHERE r.batch_id = multi_sms_batches.id
                   AND r.status = 'pending'
            )
      ORDER BY datetime(created_at) ASC, id ASC
         LIMIT 1
        """,
        (now,),
    ).fetchone()

    if not row:
        return None

    batch_id = int(row["id"])
    cursor = conn.execute(
        """
        UPDATE multi_sms_batches
           SET status = 'processing',
               started_at = COALESCE(started_at, ?)
         WHERE id = ? AND status = 'pending'
        """,
        (now, batch_id),
    )
    conn.commit()

    if cursor.rowcount == 0:
        return None
    return get_multi_sms_batch(batch_id)


def update_multi_sms_batch_status(
    batch_id: int,
    *,
    status: str,
    error: Optional[str] = None,
    completed: bool = False,
) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    fields = ["status = ?"]
    params: List[Any] = [status]

    if error is not None:
        fields.append("error = ?")
        params.append(error or None)

    if completed:
        fields.append("completed_at = ?")
        params.append(_utc_timestamp())

    params.append(batch_id)
    conn.execute(f"UPDATE multi_sms_batches SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    return get_multi_sms_batch(batch_id)


def update_multi_sms_recipient(
    recipient_id: int,
    *,
    status: str,
    sid: Optional[str] = None,
    error: Optional[str] = None,
    sent_at: Optional[str] = None,
) -> None:
    conn = _get_connection()
    conn.execute(
        """
        UPDATE multi_sms_recipients
           SET status = ?,
               sid = ?,
               error = ?,
               sent_at = CASE WHEN ? IS NOT NULL THEN ? ELSE sent_at END
         WHERE id = ?
        """,
        (status, sid, error, sent_at, sent_at, recipient_id),
    )
    conn.commit()


def recalc_multi_sms_counters(batch_id: int) -> Dict[str, int]:
    conn = _get_connection()
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) AS success,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
            SUM(CASE WHEN status = 'invalid' THEN 1 ELSE 0 END) AS invalid
          FROM multi_sms_recipients
         WHERE batch_id = ?
        """,
        (batch_id,),
    ).fetchone()

    total = int(row["total"] or 0)
    success = int(row["success"] or 0)
    failed = int(row["failed"] or 0)
    invalid = int(row["invalid"] or 0)

    conn.execute(
        """
        UPDATE multi_sms_batches
           SET total_recipients = ?,
               success_count = ?,
               failure_count = ?,
               invalid_count = ?
         WHERE id = ?
        """,
        (total, success, failed, invalid, batch_id),
    )
    conn.commit()
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "invalid": invalid,
    }


def _env_bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    lowered = value.strip().lower()
    if not lowered:
        return None
    if lowered in {"1", "true", "t", "yes", "y"}:
        return True
    if lowered in {"0", "false", "f", "no", "n"}:
        return False
    return None


def _env_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _env_str(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def apply_ai_env_defaults(app) -> None:
    """Override AI config using environment variables when provided."""

    env_api_key = _env_str("OPENAI_API_KEY")
    env_model = _env_str("OPENAI_MODEL")
    env_temp = _env_float(os.getenv("OPENAI_TEMPERATURE"))
    env_target = _env_str("AI_TARGET_NUMBER")
    env_prompt = _env_str("AI_SYSTEM_PROMPT")
    env_enabled = _env_bool(os.getenv("AI_ENABLED"))

    if not any([
        env_api_key,
        env_model,
        env_temp is not None,
        env_target,
        env_prompt,
        env_enabled is not None,
    ]):
        return

    with app.app_context():
        current = get_ai_config()
        current_enabled = bool(current.get("enabled", False))
        current_source = current.get("enabled_source") or "db"
        resolved_enabled = current_enabled
        resolved_source = current_source

        if env_enabled is not None:
            env_bool = bool(env_enabled)
            if current_source == "ui" and env_bool != current_enabled:
                app.logger.info(
                    "Skipping AI_ENABLED env override (managed in UI, current=%s, env=%s)",
                    current_enabled,
                    env_bool,
                )
            elif current_source == "ui" and env_bool == current_enabled:
                resolved_enabled = current_enabled
                resolved_source = current_source
            else:
                resolved_enabled = env_bool
                resolved_source = "env"

        updated_cfg = set_ai_config(
            enabled=bool(resolved_enabled),
            api_key=env_api_key,
            system_prompt=env_prompt,
            target_number=env_target,
            model=env_model,
            temperature=env_temp,
            enabled_source=resolved_source,
        )

        if updated_cfg.get("enabled"):
            auto_cfg = get_auto_reply_config()
            if auto_cfg.get("enabled"):
                app.logger.info("Disabling auto-reply because AI is enabled via environment")
                set_auto_reply_config(enabled=False, message=auto_cfg.get("message", ""))

        if updated_cfg == current:
            app.logger.debug("AI env defaults matched current config; no changes applied")
        else:
            app.logger.info(
                "AI config bootstrapped from env (enabled=%s, model=%s, target=%s)",
                updated_cfg.get("enabled"),
                updated_cfg.get("model"),
                updated_cfg.get("target_number"),
            )

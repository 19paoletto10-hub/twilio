from __future__ import annotations

import io
import json
import os
import re
import shutil
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
from urllib.parse import unquote

from flask import Blueprint, current_app, request, Response, jsonify, send_file
from twilio.request_validator import RequestValidator
from openai import OpenAI, OpenAIError

from .chat_logic import build_chat_engine
from .ai_service import AIResponder, AIReplyError, send_ai_generated_sms
from .twilio_client import TwilioService
from .auto_reply import enqueue_auto_reply
from .database import (
    get_auto_reply_config,
    set_auto_reply_config,
    get_ai_config,
    set_ai_config,
    normalize_contact,
    apply_ai_env_defaults,
    get_app_setting,
    set_app_setting,
    get_listeners_config,
    get_listener_by_command,
    update_listener_config,
    has_outbound_reply_for_inbound,
)
from .database import (
    list_scheduled_messages,
    create_scheduled_message,
    update_scheduled_message,
    delete_scheduled_message,
)
from .database import (
    insert_message,
    list_messages,
    update_message_status_by_sid,
    get_message_stats,
    upsert_message,
    delete_message_by_sid,
    list_conversations,
    list_conversation_message_refs,
    delete_conversation_messages,
)
from .database import (
    create_multi_sms_batch,
    get_multi_sms_batch,
    list_multi_sms_batches,
    list_multi_sms_recipients,
)
from .scraper_service import ScraperService, SCRAPED_DIR, DATA_DIR
from .secrets_manager import SecretsManager, SecretStatus
from .config import reload_runtime_settings
from .faiss_service import (
    FAISS_INDEX_PATH,
    DOCS_JSONL_PATH,
    DOCS_JSON_PATH,
    ARTICLES_JSONL_PATH,
)
from .validators import E164_PATTERN as E164_RE

NEWS_CONFIG_PATH = os.path.join(DATA_DIR, "news_config.json")
MAX_FAISS_BACKUP_BYTES = 250 * 1024 * 1024  # 250 MB safety limit


DEFAULT_NEWS_PROMPT = "Wygeneruj krótkie podsumowanie najważniejszych newsów."
ALL_CATEGORIES_PROMPT = (
    "Przygotuj profesjonalne, polskie streszczenie wszystkich kategorii newsów. "
    "Każdą kategorię analizuj oddzielnie. Dla KAŻDEJ kategorii wypisz nagłówek oraz 2-3 zdania z najważniejszymi faktami (bez wypunktowań). "
    "Uwzględniaj konkrety (liczby, decyzje, konsekwencje). Jeśli brak danych, napisz 'brak danych'."
)
DEFAULT_PER_CATEGORY_K = 2


FAISS_BACKUP_FILES = [
    {"name": "index.faiss", "path": os.path.join(FAISS_INDEX_PATH, "index.faiss"), "required": True, "purge": True},
    {"name": "index.pkl", "path": os.path.join(FAISS_INDEX_PATH, "index.pkl"), "required": True, "purge": True},
    {"name": "documents.jsonl", "path": DOCS_JSONL_PATH, "required": False, "purge": True},
    {"name": "documents.json", "path": DOCS_JSON_PATH, "required": False, "purge": True},
    {"name": "articles.jsonl", "path": ARTICLES_JSONL_PATH, "required": False, "purge": True},
    {"name": "news_config.json", "path": NEWS_CONFIG_PATH, "required": False, "purge": False},
]


webhooks_bp = Blueprint("webhooks", __name__)


CHAT_HISTORY_LIMIT = 50

# Deduplikacja teraz odbywa się przez sprawdzanie bazy danych
# Funkcja has_outbound_reply_for_inbound() sprawdza czy wysłaliśmy odpowiedź


def _datetime_to_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def _parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _persist_twilio_message(message) -> None:
    direction = (
        "inbound"
        if (getattr(message, "direction", "") or "").startswith("inbound")
        else "outbound"
    )
    error_details = message.error_message or (
        f"Error code: {message.error_code}" if getattr(message, "error_code", None) else None
    )

    upsert_message(
        sid=message.sid,
        direction=direction,
        to_number=getattr(message, "to", None),
        from_number=getattr(message, "from_", None),
        body=getattr(message, "body", "") or "",
        status=getattr(message, "status", None),
        error=error_details,
        created_at=_datetime_to_iso(getattr(message, "date_created", None)),
        updated_at=_datetime_to_iso(getattr(message, "date_updated", None)),
    )


def send_ai_message_to_configured_target(
    *,
    latest_user_message: Optional[str] = None,
    history_limit: int = 20,
    api_key_override: Optional[str] = None,
    reply_text_override: Optional[str] = None,
    origin_number: Optional[str] = None,
    participant_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate an AI reply and send it to the configured AI target number."""

    cfg = get_ai_config()
    api_key = (api_key_override or cfg.get("api_key") or "").strip()
    if not api_key:
        raise AIReplyError(
            "Brak klucza OpenAI. Uzupełnij konfigurację AI lub przekaż api_key.",
            status_code=400,
        )

    target_number = (participant_override or cfg.get("target_number") or "").strip()
    normalized_target = normalize_contact(target_number)
    if not normalized_target:
        raise AIReplyError("Brak skonfigurowanego numeru AI.", status_code=400)

    try:
        resolved_history_limit = max(1, min(int(history_limit), 200))
    except (TypeError, ValueError):
        resolved_history_limit = 20

    responder = AIResponder(
        api_key=api_key,
        model=(cfg.get("model") or "gpt-4o-mini").strip(),
        system_prompt=cfg.get("system_prompt") or "",
        temperature=float(cfg.get("temperature", 0.7) or 0.7),
        history_limit=resolved_history_limit,
    )

    if reply_text_override is None:
        try:
            reply_text = responder.build_reply(
                participant=target_number,
                latest_user_message=latest_user_message or None,
            )
        except Exception as exc:  # noqa: BLE001
            current_app.logger.exception(
                "send_ai_message_to_configured_target: OpenAI error: %s", exc
            )
            raise AIReplyError(
                f"Generowanie odpowiedzi nie powiodło się: {exc}",
                status_code=502,
            ) from exc
    else:
        reply_text = reply_text_override

    reply_text = (reply_text or "").strip()
    if not reply_text:
        raise AIReplyError("OpenAI nie zwróciło treści odpowiedzi.", status_code=502)

    twilio_client: TwilioService = current_app.config["TWILIO_CLIENT"]

    dispatch_result = send_ai_generated_sms(
        responder=responder,
        twilio_client=twilio_client,
        participant_number=target_number,
        latest_user_message=latest_user_message,
        reply_text_override=reply_text_override,
        origin_number=origin_number,
        logger=current_app.logger,
    )

    _persist_twilio_message(dispatch_result.twilio_message)

    return {
        "to": dispatch_result.to_number,
        "to_normalized": dispatch_result.normalized_to,
        "body": dispatch_result.reply_text,
        "sid": dispatch_result.sid,
        "status": dispatch_result.status,
        "model": responder.model,
        "temperature": responder.temperature,
        "history_limit": responder.history_limit,
        "origin_number": dispatch_result.origin_number,
    }


def _validate_twilio_signature(req) -> bool:
    # Allow disabling validation for local testing (e.g., ngrok) via env flag
    if os.getenv("TWILIO_VALIDATE_SIGNATURE", "true").lower() in {"0", "false", "no", "off"}:
        current_app.logger.warning("Skipping Twilio signature validation (TWILIO_VALIDATE_SIGNATURE disabled)")
        return True

    settings = current_app.config.get("TWILIO_SETTINGS")
    if not settings or not settings.auth_token:
        current_app.logger.error("Missing Twilio auth token; cannot validate signature")
        return False

    signature = req.headers.get("X-Twilio-Signature", "")
    validator = RequestValidator(settings.auth_token)

    # Flask preserves the raw URL including query string; Twilio expects exactly that
    url = req.url
    params = req.form.to_dict(flat=False) or req.form.to_dict() or {}

    is_valid = validator.validate(url, params, signature)
    if not is_valid:
        current_app.logger.warning(
            "Invalid Twilio signature for %s (sig=%s, url=%s, params=%s)",
            req.path,
            signature,
            url,
            params,
        )
    else:
        current_app.logger.debug("Twilio signature validated for %s", req.path)
    return is_valid


def _handle_news_listener_sync(from_number: str, to_number: str, body: str, sid: Optional[str]) -> None:
    """Synchronicznie obsłuż komendę /news - odpytaj FAISS i wyślij SMS."""
    from .faiss_service import FAISSService

    # DEDUPLIKACJA: Sprawdź w bazie czy już wysłaliśmy odpowiedź do tego nadawcy
    if sid and from_number:
        if has_outbound_reply_for_inbound(sid, from_number):
            current_app.logger.debug("/news: SID %s already replied to %s, skipping", sid, from_number)
            return

    twilio_client: TwilioService = current_app.config["TWILIO_CLIENT"]

    # Wyciągnij zapytanie po /news
    query = body.strip()[5:].strip()  # Usuń "/news" z początku
    if not query:
        query = "Jakie są najnowsze wiadomości?"

    current_app.logger.info("/news listener processing query: %s", query[:100])

    try:
        faiss_svc = FAISSService()
        response = faiss_svc.answer_query(query, top_k=5)

        if response.get("answer"):
            reply_text = f"📰 News:\n\n{response['answer']}"
        else:
            reply_text = "❌ Nie znaleziono odpowiedzi w bazie newsów."

        # Wyślij odpowiedź SMS
        origin_number = to_number or twilio_client.settings.default_from
        if not origin_number:
            current_app.logger.error("/news: No origin number configured")
            return

        message = twilio_client.send_reply_to_inbound(
            inbound_from=from_number,
            inbound_to=origin_number,
            body=reply_text,
        )
        _persist_twilio_message(message)
        current_app.logger.info(
            "/news reply sent to %s (SID: %s, query: %s)",
            from_number, message.sid, query[:50]
        )
    except Exception as exc:
        current_app.logger.exception("/news listener error: %s", exc)
        insert_message(
            direction="outbound",
            sid=None,
            to_number=from_number,
            from_number=to_number,
            body="",
            status="failed",
            error=str(exc),
        )


def _maybe_enqueue_auto_reply_for_message(message) -> None:
    """Queue reactive replies (AI, auto-reply or listeners) when enabled and inbound.
    
    Wszystko jest przetwarzane ASYNCHRONICZNIE przez worker w tle.
    """

    # Pobierz dane wiadomości
    body = getattr(message, "body", "") or ""
    direction = getattr(message, "direction", "") or ""
    
    if not direction.startswith("inbound"):
        return

    from_number = (getattr(message, "from_", "") or "").strip()
    to_number = (getattr(message, "to", "") or "").strip()
    sid = getattr(message, "sid", None)

    # DEDUPLIKACJA: Sprawdź w bazie czy już wysłaliśmy odpowiedź do tego nadawcy
    if sid and from_number:
        if has_outbound_reply_for_inbound(sid, from_number):
            current_app.logger.debug(
                "Skipping message SID=%s - already replied to %s", sid, from_number
            )
            return

    auto_cfg = get_auto_reply_config()
    ai_cfg = get_ai_config()

    ai_enabled = bool(ai_cfg.get("enabled"))
    auto_enabled = bool(auto_cfg.get("enabled"))

    # Sprawdź listener * dla auto-reply (AI działa niezależnie od listenera *)
    default_listener = get_listener_by_command("*")
    default_listener_enabled = default_listener and default_listener.get("enabled")
    
    # Dla wszystkich wiadomości - sprawdź czy AI lub auto-reply jest włączone
    if not ai_enabled and (not auto_enabled or not default_listener_enabled):
        current_app.logger.debug(
            "No active response for polling: ai=%s, auto=%s, listener*=%s",
            ai_enabled, auto_enabled, default_listener_enabled
        )
        return

    # ─────────────────────────────────────────────────────────
    # ENQUEUE do workera w tle - asynchroniczne przetwarzanie
    # Worker obsłuży: AI reply, /news listener, auto-reply
    # ─────────────────────────────────────────────────────────
    received_at_iso = None
    for attr in ("date_created", "date_sent", "date_updated"):
        dt_value = getattr(message, attr, None)
        if dt_value:
            received_at_iso = _datetime_to_iso(dt_value)
            if received_at_iso:
                break
    if not received_at_iso:
        received_at_iso = _datetime_to_iso(datetime.utcnow())

    enqueue_auto_reply(
        current_app,
        sid=sid,
        from_number=from_number,
        to_number=to_number,
        body=body,
        received_at=received_at_iso,
    )


def _mask_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    trimmed = value.strip()
    if len(trimmed) <= 4:
        return "•" * len(trimmed)
    return "•" * (len(trimmed) - 4) + trimmed[-4:]


def _serialize_secret(status: SecretStatus) -> Dict[str, Any]:
    return {
        "key": status.key,
        "exists": status.exists,
        "masked": status.masked,
        "source": status.source,
    }


def _resolve_rag_chat_model() -> str:
    stored = get_app_setting("rag_chat_model")
    if stored:
        return stored
    return os.getenv("SECOND_MODEL", os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")).strip()


def _select_openai_key() -> Optional[str]:
    # Priority: dedicated RAG key, primary key in env, ai_config db value
    for env_key in ("SECOND_OPENAI", "OPENAI_API_KEY"):
        candidate = (os.getenv(env_key, "") or "").strip()
        if candidate:
            return candidate

    cfg = get_ai_config()
    api_key = (cfg.get("api_key") or "").strip()
    return api_key or None


def _available_openai_models() -> List[str]:
    key = _select_openai_key()
    if not key:
        return []
    try:
        return _list_openai_chat_models(key)
    except ValueError as exc:
        current_app.logger.warning("Listing OpenAI models failed: %s", exc)
        return []


def _list_openai_chat_models(api_key: str) -> List[str]:
    client = OpenAI(api_key=api_key)
    try:
        response = client.models.list()
    except OpenAIError as exc:
        raise ValueError(f"Pobieranie listy modeli nie powiodło się: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Nieoczekiwany błąd podczas listowania modeli: {exc}") from exc

    model_ids = [getattr(item, "id", "") for item in getattr(response, "data", []) if getattr(item, "id", None)]
    chat_like = [mid for mid in model_ids if "embedding" not in mid.lower() and not mid.lower().startswith("whisper")]
    return sorted(set(chat_like))


def _split_multi_sms_numbers(raw_value: str) -> List[str]:
    normalized = raw_value.replace("\r", "\n")
    parts = re.split(r"[,;\n]+", normalized)
    return [part.strip() for part in parts if part and part.strip()]


def _extract_multi_sms_recipients(payload: Dict[str, Any]) -> List[str]:
    raw = payload.get("recipients")
    if isinstance(raw, str):
        numbers = _split_multi_sms_numbers(raw)
    elif isinstance(raw, (list, tuple)):
        numbers = [str(item).strip() for item in raw if str(item).strip()]
    else:
        merged = (
            payload.get("numbers")
            or payload.get("targets")
            or payload.get("numbers_text")
            or payload.get("recipients_text")
            or ""
        )
        numbers = _split_multi_sms_numbers(str(merged)) if merged else []

    return numbers


def _sender_identity_label() -> str:
    settings = current_app.config["TWILIO_SETTINGS"]
    if settings.messaging_service_sid:
        return f"Messaging Service {settings.messaging_service_sid}"
    if settings.default_from:
        return settings.default_from
    return ""


# ---------------------------------------------------------------------------
# News helpers
# ---------------------------------------------------------------------------
def _default_news_config() -> Dict[str, Any]:
    return {
        "enabled": True,
        "recipients": [],  # Lista odbiorców: [{id, phone, prompt, time, enabled, created_at}]
        "updated_at": "",
        "last_build_at": "",
        "active_index": "faiss_openai_index",
    }


def _load_news_config() -> Dict[str, Any]:
    base = _default_news_config()
    try:
        if os.path.exists(NEWS_CONFIG_PATH):
            with open(NEWS_CONFIG_PATH, "r", encoding="utf-8") as f:
                stored = json.load(f)
                if isinstance(stored, dict):
                    base.update(stored)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning("News config load failed: %s", exc)
    normalized_recipients: List[Dict[str, Any]] = []
    for recipient in base.get("recipients", []):
        if not isinstance(recipient, dict):
            continue
        recipient.setdefault("use_all_categories", True)
        prompt_value = (recipient.get("prompt") or "").strip()
        if recipient["use_all_categories"]:
            recipient["prompt"] = prompt_value or ALL_CATEGORIES_PROMPT
        else:
            recipient["prompt"] = prompt_value or DEFAULT_NEWS_PROMPT
        normalized_recipients.append(recipient)
    base["recipients"] = normalized_recipients
    return base


def _save_news_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    data = _default_news_config()
    data.update(cfg)
    data["updated_at"] = datetime.utcnow().isoformat() + "Z"
    os.makedirs(os.path.dirname(NEWS_CONFIG_PATH), exist_ok=True)
    with open(NEWS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def _serialize_news_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "recipients": cfg.get("recipients", []),
        "updated_at": cfg.get("updated_at", ""),
        "last_build_at": cfg.get("last_build_at", ""),
        "active_index": cfg.get("active_index", "faiss_openai_index"),
    }


def _list_scraped_files() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not os.path.isdir(SCRAPED_DIR):
        return items

    for fn in sorted(os.listdir(SCRAPED_DIR)):
        if not (fn.endswith(".txt") or fn.endswith(".json")):
            continue

        path = os.path.join(SCRAPED_DIR, fn)
        try:
            stat = os.stat(path)
            name, ext = os.path.splitext(fn)
            items.append(
                {
                    "name": fn,
                    "category": name.replace("_", " ").title(),
                    "size_bytes": stat.st_size,
                    "updated_at": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
                    "format": ext.lstrip("."),
                }
            )
        except OSError as exc:  # noqa: BLE001
            current_app.logger.warning("Cannot stat %s: %s", path, exc)
            continue
    return items


def _read_scraped_file_content(filename: str) -> Dict[str, Any]:
    safe_name = os.path.basename(filename)
    path = os.path.join(SCRAPED_DIR, safe_name)

    if not os.path.exists(path):
        # try alternate extension
        base, _ = os.path.splitext(safe_name)
        alt_txt = os.path.join(SCRAPED_DIR, base + ".txt")
        alt_json = os.path.join(SCRAPED_DIR, base + ".json")
        if os.path.exists(alt_txt):
            path = alt_txt
            safe_name = os.path.basename(alt_txt)
        elif os.path.exists(alt_json):
            path = alt_json
            safe_name = os.path.basename(alt_json)
        else:
            return {"error": "Plik nie istnieje."}

    try:
        stat = os.stat(path)
        _, ext = os.path.splitext(path)
        content = ""
        if ext.lower() == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                parts = []
                for idx, item in enumerate(data, 1):
                    title = (item.get("title") or "Bez tytułu").strip()
                    url = item.get("url") or ""
                    text = item.get("text") or ""
                    parts.append(f"[{idx}] {title}\n{url}\n\n{text}".strip())
                content = "\n\n" + ("-" * 40) + "\n\n".join(parts)
            else:
                content = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

        return {
            "name": safe_name,
            "content": content,
            "size_bytes": stat.st_size,
            "updated_at": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
        }
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Error reading scraped file %s: %s", path, exc)
        return {"error": f"Nie udało się odczytać pliku: {exc}"}


def _faiss_indices_payload() -> Dict[str, Any]:
    os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
    index_file = os.path.join(FAISS_INDEX_PATH, "index.faiss")
    docs_file = os.path.join(FAISS_INDEX_PATH, "docs.json")
    npz_file = os.path.join(FAISS_INDEX_PATH, "index.npz")

    def _stat(path: str) -> Optional[float]:
        try:
            return os.path.getmtime(path)
        except OSError:
            return None

    mtimes = [t for t in (_stat(index_file), _stat(docs_file), _stat(npz_file)) if t]
    updated_at = None
    if mtimes:
        updated_at = datetime.utcfromtimestamp(max(mtimes)).isoformat() + "Z"

    size_total = 0
    for path in (index_file, docs_file, npz_file):
        try:
            size_total += os.path.getsize(path)
        except OSError:
            continue

    exists = any(os.path.exists(p) for p in (index_file, npz_file, docs_file))

    return {
        "items": [
            {
                "name": "faiss_openai_index",
                "status": "aktywny" if exists else "brak danych",
                "active": True,
                "size": size_total if size_total else None,
                "created_at": updated_at or "",
                "exists": exists,
            }
        ],
        "updated_at": updated_at,
    }


def _faiss_index_files(name: str) -> Dict[str, str]:
    base = FAISS_INDEX_PATH  # single index directory; extendable for future multi-index
    safe_name = os.path.basename(name)
    return {
        "index": os.path.join(base, "index.faiss"),
        "docs": os.path.join(base, "docs.json"),
        "npz": os.path.join(base, "index.npz"),
        "base": base,
        "name": safe_name,
    }


def _faiss_backup_manifest() -> List[Dict[str, Any]]:
    manifest: List[Dict[str, Any]] = []
    for item in FAISS_BACKUP_FILES:
        manifest.append({**item, "exists": os.path.exists(item["path"])})
    return manifest


def _delete_faiss_index(name: str) -> Dict[str, Any]:
    paths = _faiss_index_files(name)
    removed: List[str] = []
    missing: List[str] = []
    failed: List[Dict[str, str]] = []

    artifact_paths = set()
    for key in ("index", "docs", "npz"):
        artifact_paths.add(paths[key])

    for item in FAISS_BACKUP_FILES:
        if not item.get("purge", True):
            continue
        artifact_paths.add(item["path"])

    for target in sorted(artifact_paths):
        if not target:
            continue
        try:
            if os.path.isdir(target):
                # Directory cleanup is handled separately once files are removed.
                continue
            if os.path.exists(target):
                os.remove(target)
                removed.append(os.path.basename(target) or target)
            else:
                missing.append(os.path.basename(target) or target)
        except OSError as exc:  # noqa: BLE001
            current_app.logger.warning("Cannot delete %s: %s", target, exc)
            failed.append({"path": target, "error": str(exc)})

    base_dir = paths["base"]
    base_removed = False
    if os.path.isdir(base_dir):
        try:
            if not os.listdir(base_dir):
                os.rmdir(base_dir)
                base_removed = True
                removed.append(os.path.basename(base_dir) or base_dir)
        except OSError as exc:  # noqa: BLE001
            current_app.logger.warning("Cannot remove directory %s: %s", base_dir, exc)
            failed.append({"path": base_dir, "error": str(exc)})

    return {
        "name": paths["name"],
        "removed": removed,
        "missing": missing,
        "failed": failed,
        "base_removed": base_removed,
    }


def _send_ai_reply_message(*, inbound_from: str, inbound_to: str, reply_text: str):
    """Send AI-generated reply back to the original sender via Twilio."""

    twilio_client: TwilioService = current_app.config["TWILIO_CLIENT"]
    message = twilio_client.send_reply_to_inbound(
        inbound_from=inbound_from,
        inbound_to=inbound_to,
        body=reply_text,
    )
    _persist_twilio_message(message)
    return message
def _serialize_ai_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "enabled": bool(cfg.get("enabled")),
        "system_prompt": cfg.get("system_prompt", ""),
        "target_number": cfg.get("target_number", ""),
        "target_number_normalized": cfg.get("target_number_normalized", ""),
        "model": cfg.get("model", "gpt-4o-mini"),
        "temperature": float(cfg.get("temperature", 0.7) or 0.7),
        "updated_at": cfg.get("updated_at") or "",
        "has_api_key": bool((cfg.get("api_key") or "").strip()),
        "api_key_preview": _mask_secret(cfg.get("api_key")),
    }


def _twilio_message_to_dict(message) -> Dict[str, Any]:
    return {
        "sid": message.sid,
        "status": getattr(message, "status", None),
        "direction": getattr(message, "direction", None),
        "from": getattr(message, "from_", None),
        "to": getattr(message, "to", None),
        "body": getattr(message, "body", None),
        "num_media": getattr(message, "num_media", None),
        "num_segments": getattr(message, "num_segments", None),
        "error_code": getattr(message, "error_code", None),
        "error_message": getattr(message, "error_message", None),
        "messaging_service_sid": getattr(message, "messaging_service_sid", None),
        "price": getattr(message, "price", None),
        "price_unit": getattr(message, "price_unit", None),
        "date_created": _datetime_to_iso(getattr(message, "date_created", None)),
        "date_updated": _datetime_to_iso(getattr(message, "date_updated", None)),
        "date_sent": _datetime_to_iso(getattr(message, "date_sent", None)),
    }


def _coerce_media_urls(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else None
    if isinstance(value, list | tuple):
        cleaned_list = [str(item) for item in value if str(item).strip()]
        return cleaned_list or None
    return None


def _encode_content_variables(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value)
    except TypeError:
        return None


def _parse_datetime_arg(raw_value: Optional[str]) -> Optional[datetime]:
    if not raw_value:
        return None
    try:
        # datetime.fromisoformat supports timezone-aware inputs as well
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


def _maybe_sync_messages(limit: int = 50) -> None:
    cache = current_app.config.setdefault("TWILIO_SYNC_CACHE", {"last_sync": 0.0})
    now = time.time()
    if now - cache.get("last_sync", 0.0) < 10:
        return

    twilio_client: TwilioService = current_app.config["TWILIO_CLIENT"]
    try:
        remote_messages = twilio_client.client.messages.list(limit=limit)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning("Unable to sync messages from Twilio: %s", exc)
        cache["last_sync"] = now
        return

    first_inbound_enqueued = False
    for message in remote_messages:
        _persist_twilio_message(message)
        if not first_inbound_enqueued and (getattr(message, "direction", "") or "").startswith("inbound"):
            _maybe_enqueue_auto_reply_for_message(message)
            first_inbound_enqueued = True

    cache["last_sync"] = now


@webhooks_bp.post("/twilio/inbound")
def inbound_message():
    app = current_app
    app.logger.info("Inbound webhook hit: %s", request.path)

    if not _validate_twilio_signature(request):
        return Response("Forbidden", status=403)

    app.logger.info("Received inbound hook: %s", request.form.to_dict())

    # Extract and validate webhook parameters
    from_number = (request.form.get("From") or "").strip()
    to_number = (request.form.get("To") or "").strip()
    body = (request.form.get("Body") or "").strip()
    message_sid = (request.form.get("MessageSid") or "").strip() or None
    message_status = (request.form.get("SmsStatus") or "").strip() or None

    # Validate required parameters
    if not from_number or not to_number:
        app.logger.warning("Missing required webhook parameters: From=%s, To=%s", from_number, to_number)
        return Response("<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response></Response>", mimetype="application/xml")

    received_at_iso = _datetime_to_iso(datetime.utcnow())

    # Store the incoming message
    try:
        if message_sid:
            upsert_message(
                sid=message_sid,
                direction="inbound",
                to_number=to_number,
                from_number=from_number,
                body=body,
                status=message_status,
                error=None,
                created_at=None,
                updated_at=None,
            )
        else:
            insert_message(
                direction="inbound",
                sid=None,
                to_number=to_number,
                from_number=from_number,
                body=body,
                status=message_status,
            )
        app.logger.info(
            "Stored inbound message from %s to %s (SID: %s)", 
            from_number, to_number, message_sid or "N/A"
        )
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Failed to store inbound message: %s", exc)

    # DEDUPLIKACJA: Sprawdź w bazie czy już wysłaliśmy odpowiedź do tego nadawcy
    if message_sid and from_number:
        if has_outbound_reply_for_inbound(message_sid, from_number):
            app.logger.debug(
                "Skipping inbound SID=%s - already replied to %s", message_sid, from_number
            )
            return Response("OK", mimetype="text/plain")

    twilio_client: TwilioService = app.config["TWILIO_CLIENT"]

    ai_cfg = get_ai_config()
    auto_cfg = get_auto_reply_config()

    ai_enabled = bool(ai_cfg.get("enabled"))
    auto_enabled = bool(auto_cfg.get("enabled"))

    # Sprawdź czy wiadomość jest komendą listenera /news
    if body.lower().startswith("/news"):
        news_listener = get_listener_by_command("/news")
        if news_listener and news_listener.get("enabled"):
            # Wyciągnij zapytanie po komendzie /news
            query = body[5:].strip()  # Usuń "/news" z początku
            if query:
                try:
                    from .faiss_service import FAISSService
                    faiss_svc = FAISSService()
                    answer_result = faiss_svc.answer_query(query)
                    # answer_query returns Dict with 'answer' key
                    answer_text = answer_result.get("answer") if isinstance(answer_result, dict) else str(answer_result)
                    if answer_text:
                        # Wyślij odpowiedź SMS
                        message = twilio_client.send_reply_to_inbound(
                            inbound_from=from_number,
                            inbound_to=to_number,
                            body=str(answer_text),
                        )
                        _persist_twilio_message(message)
                        app.logger.info("Sent /news reply to %s (SID: %s)", from_number, message.sid)
                    else:
                        # Brak odpowiedzi z FAISS
                        no_answer = "Nie znaleziono informacji na temat: " + query[:50]
                        message = twilio_client.send_reply_to_inbound(
                            inbound_from=from_number,
                            inbound_to=to_number,
                            body=no_answer,
                        )
                        _persist_twilio_message(message)
                        app.logger.info("Sent /news no-answer reply to %s", from_number)
                except Exception as exc:
                    app.logger.exception("Failed to process /news query: %s", exc)
            else:
                # Brak zapytania po /news
                help_msg = "Użycie: /news <Twoje pytanie>\nPrzykład: /news co nowego w gospodarce?"
                try:
                    message = twilio_client.send_reply_to_inbound(
                        inbound_from=from_number,
                        inbound_to=to_number,
                        body=help_msg,
                    )
                    _persist_twilio_message(message)
                except Exception as exc:
                    app.logger.exception("Failed to send /news help: %s", exc)
            # Listener /news obsłużył komendę
            return Response("OK", mimetype="text/plain")

    # Dla wszystkich innych wiadomości (nie /news) - sprawdź AI i auto-reply
    # Listener * kontroluje tylko auto-reply, AI działa niezależnie gdy włączone
    default_listener = get_listener_by_command("*")
    default_listener_enabled = default_listener and default_listener.get("enabled")
    
    app.logger.info(
        "Processing message: ai_enabled=%s, auto_enabled=%s, default_listener=%s",
        ai_enabled, auto_enabled, default_listener_enabled
    )

    # Handle AI reply synchronously gdy AI włączone (niezależnie od listenera *)
    if ai_enabled:
        try:
            api_key = (ai_cfg.get("api_key") or "").strip()
            if api_key:
                app.logger.info("Processing AI reply synchronously for %s", from_number)
                responder = AIResponder(
                    api_key=api_key,
                    model=(ai_cfg.get("model") or "gpt-4o-mini").strip(),
                    system_prompt=ai_cfg.get("system_prompt") or "",
                    temperature=float(ai_cfg.get("temperature", 0.7) or 0.7),
                )
                
                result = send_ai_generated_sms(
                    responder=responder,
                    twilio_client=twilio_client,
                    participant_number=from_number,
                    latest_user_message=body,
                    # Wymuszamy nadawcę z TWILIO_DEFAULT_FROM (nie numer przychodzący)
                    origin_number=twilio_client.settings.default_from,
                    logger=app.logger,
                )
                
                insert_message(
                    direction="outbound",
                    sid=result.sid,
                    to_number=result.to_number,
                    from_number=result.origin_number or to_number or twilio_client.settings.default_from,
                    body=result.reply_text,
                    status=result.status or "ai-auto-reply",
                )
                
                # Odpowiedź zapisana do bazy - deduplikacja zadziała automatycznie
                app.logger.info("AI reply sent to %s with SID=%s", from_number, result.sid or "unknown")
                return Response("OK", mimetype="text/plain")
            else:
                app.logger.error("AI enabled but no API key configured")
        except Exception as exc:
            app.logger.exception("Synchronous AI reply failed: %s", exc)
            insert_message(
                direction="outbound",
                sid=None,
                to_number=from_number,
                from_number=to_number or twilio_client.settings.default_from,
                body="",
                status="failed",
                error=str(exc),
            )

    # Fallback to async auto-reply gdy listener * włączony i auto_enabled
    # Auto-reply wymaga włączonego listenera * (w przeciwieństwie do AI)
    if default_listener_enabled and auto_enabled:
        enqueue_auto_reply(
            app,
            sid=message_sid,
            from_number=from_number,
            to_number=to_number,
            body=body,
            received_at=received_at_iso,
        )
        return Response("OK", mimetype="text/plain")

    # Jeśli brak AI i brak auto-reply (lub listener * wyłączony dla auto-reply) - zwróć OK bez odpowiedzi
    if not ai_enabled and (not default_listener_enabled or not auto_enabled):
        app.logger.info("No active response mechanism for message from %s (ai=%s, auto=%s, listener=%s)", 
                       from_number, ai_enabled, auto_enabled, default_listener_enabled)
        return Response("OK", mimetype="text/plain")

    # Generate auto-reply using chat engine when both AI and auto-reply are disabled

    # Otherwise, fall back to chat-engine based reply (synchronous send)
    reply_text = None
    try:
        chat_engine = build_chat_engine()
        reply_text = chat_engine.build_reply(from_number, body)
        if reply_text:
            app.logger.info(
                "Generated auto-reply to %s: %s",
                from_number,
                reply_text[:50] + ("..." if len(reply_text) > 50 else ""),
            )
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Failed to generate auto-reply: %s", exc)
        reply_text = None

    if reply_text:
        try:
            message = twilio_client.send_reply_to_inbound(
                inbound_from=from_number,
                inbound_to=to_number,
                body=reply_text,
            )
            _persist_twilio_message(message)
            app.logger.info("Sent auto-reply via API to %s (SID: %s)", from_number, message.sid)
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Failed to send auto-reply via API: %s", exc)
            insert_message(
                direction="outbound",
                sid=None,
                to_number=from_number,
                from_number=to_number,
                body=reply_text,
                status="failed",
                error=str(exc),
            )

    return Response("OK", mimetype="text/plain")


@webhooks_bp.get("/api/auto-reply/config")
def api_get_auto_reply_config():
    """Expose current auto-reply configuration."""

    cfg = get_auto_reply_config()
    return jsonify({"enabled": bool(cfg.get("enabled")), "message": cfg.get("message", "")})


@webhooks_bp.post("/api/auto-reply/config")
def api_update_auto_reply_config():
    """Update auto-reply toggle and message template."""

    payload = request.get_json(force=True, silent=True) or {}
    enabled = bool(payload.get("enabled", False))
    message = (payload.get("message") or "").strip()

    if enabled and not message:
        return jsonify({"error": "Treść auto-odpowiedzi jest wymagana gdy funkcja jest włączona."}), 400

    if len(message) > 640:
        return jsonify({"error": "Treść auto-odpowiedzi nie może przekraczać 640 znaków."}), 400

    if enabled:
        ai_cfg = get_ai_config()
        if ai_cfg.get("enabled"):
            current_app.logger.info("Auto-reply enabling forces AI mode off")
            set_ai_config(
                enabled=False,
                api_key=None,
                system_prompt=None,
                target_number=None,
                model=None,
                temperature=None,
            )

    set_auto_reply_config(enabled=enabled, message=message)
    cfg = get_auto_reply_config()
    return jsonify({"enabled": bool(cfg.get("enabled")), "message": cfg.get("message", "")})


@webhooks_bp.get("/api/ai/config")
def api_get_ai_config():
    cfg = get_ai_config()
    return jsonify(_serialize_ai_config(cfg))


@webhooks_bp.post("/api/ai/config")
def api_update_ai_config():
    payload = request.get_json(force=True, silent=True) or {}
    enabled = bool(payload.get("enabled", False))
    target_number = (payload.get("target_number") or "").strip()
    system_prompt = payload.get("system_prompt")
    model = (payload.get("model") or "gpt-4o-mini").strip()
    temperature_raw = payload.get("temperature")

    if temperature_raw is None:
        temperature = None
    else:
        try:
            temperature = float(temperature_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "Temperatura musi być liczbą."}), 400
        if temperature < 0 or temperature > 2:
            return jsonify({"error": "Temperatura musi być w zakresie 0-2."}), 400

    normalized_target = normalize_contact(target_number)
    if enabled and not normalized_target:
        return jsonify({"error": "Podaj numer uczestnika rozmowy."}), 400

    api_key_provided = "api_key" in payload
    api_key_value = payload.get("api_key") if api_key_provided else None
    if api_key_provided:
        api_key_value = (api_key_value or "").strip()

    current_cfg = get_ai_config()
    if enabled:
        has_api_key = bool((current_cfg.get("api_key") or "").strip())
        will_have_key = bool((api_key_value or "").strip()) or has_api_key
        if not will_have_key:
            return jsonify({"error": "Podaj klucz API, aby włączyć integrację AI."}), 400

    updated_cfg = set_ai_config(
        enabled=enabled,
        api_key=api_key_value if api_key_provided else None,
        system_prompt=system_prompt,
        target_number=target_number,
        model=model or None,
        temperature=temperature,
        enabled_source="ui",
    )

    if enabled:
        auto_cfg = get_auto_reply_config()
        if auto_cfg.get("enabled"):
            current_app.logger.info("Disabling auto-reply because AI mode has been enabled")
            set_auto_reply_config(enabled=False, message=auto_cfg.get("message", ""))

    return jsonify(_serialize_ai_config(updated_cfg))


@webhooks_bp.get("/api/secrets")
def api_list_secrets():
    mgr = SecretsManager()
    statuses = mgr.list_statuses()
    return jsonify({key: _serialize_secret(status) for key, status in statuses.items()})


@webhooks_bp.post("/api/secrets/<key_name>")
def api_set_secret(key_name: str):
    payload = request.get_json(force=True, silent=True) or {}
    value = (payload.get("value") or "").strip()
    persist_env = bool(payload.get("persist_env", False))
    run_test = bool(payload.get("test", False))

    mgr = SecretsManager()
    try:
        status = mgr.set(key_name, value, persist_env=persist_env)
        test_result = mgr.test(key_name, value) if run_test else None
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # Keep runtime config in sync after secret updates
    if key_name in {"OPENAI_API_KEY", "SECOND_OPENAI"}:
        try:
            apply_ai_env_defaults(current_app)
            reload_runtime_settings(current_app)
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning("OpenAI runtime reload after secret update failed: %s", exc)

    if key_name in {"TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_DEFAULT_FROM", "TWILIO_MESSAGING_SERVICE_SID"}:
        try:
            reload_runtime_settings(current_app)
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning("Twilio runtime reload after secret update failed: %s", exc)

    response: Dict[str, Any] = {"status": _serialize_secret(status)}
    if test_result is not None:
        response["test"] = test_result
    return jsonify(response)


@webhooks_bp.post("/api/secrets/<key_name>/test")
def api_test_secret(key_name: str):
    payload = request.get_json(force=True, silent=True) or {}
    value = (payload.get("value") or "").strip()
    mgr = SecretsManager()
    try:
        result = mgr.test(key_name, value or None)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@webhooks_bp.get("/api/models")
def api_get_models():
    ai_cfg = get_ai_config()
    return jsonify(
        {
            "chat_model": ai_cfg.get("model", "gpt-4o-mini"),
            "rag_chat_model": _resolve_rag_chat_model(),
            "available_models": _available_openai_models(),
        }
    )


@webhooks_bp.post("/api/models")
def api_update_models():
    payload = request.get_json(force=True, silent=True) or {}
    chat_model = (payload.get("chat_model") or "").strip()
    rag_model = (payload.get("rag_chat_model") or "").strip()

    if not chat_model and not rag_model:
        return jsonify({"error": "Brak pól do aktualizacji."}), 400

    updates: Dict[str, Any] = {}
    if chat_model:
        current_cfg = get_ai_config()
        updated = set_ai_config(
            enabled=current_cfg.get("enabled", False),
            api_key=None,
            system_prompt=None,
            target_number=None,
            model=chat_model,
            temperature=None,
            enabled_source=current_cfg.get("enabled_source", "ui"),
        )
        updates["chat_model"] = updated.get("model")

    if rag_model:
        set_app_setting(
            key="rag_chat_model",
            value=rag_model,
            source="ui",
            user_ip=request.remote_addr,
        )
        updates["rag_chat_model"] = rag_model

    updates["available_models"] = _available_openai_models()
    return jsonify(updates)


@webhooks_bp.post("/api/settings/reload")
def api_reload_settings():
    try:
        summary = reload_runtime_settings(current_app)
        apply_ai_env_defaults(current_app)
        return jsonify({"ok": True, "summary": summary})
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Reload settings failed: %s", exc)
        return jsonify({"error": f"Nie udało się przeładować konfiguracji: {exc}"}), 500


@webhooks_bp.post("/api/ai/test")
def api_test_ai_connection():
    payload = request.get_json(force=True, silent=True) or {}
    participant_override = (payload.get("participant") or "").strip()
    message = (payload.get("message") or "").strip()
    api_key_override = (payload.get("api_key") or "").strip()
    history_limit_raw = payload.get("history_limit")
    use_latest_message = payload.get("use_latest_message", True)

    # Safely parse history_limit with explicit None check
    history_limit = 20  # default
    if history_limit_raw is not None:
        try:
            history_limit = max(1, min(int(history_limit_raw), 200))
        except (TypeError, ValueError):
            pass  # Keep default

    cfg = get_ai_config()
    api_key = api_key_override or (cfg.get("api_key") or "").strip()
    if not api_key:
        return jsonify({"error": "Brak klucza OpenAI. Wklej go w formularzu lub zapisz w konfiguracji."}), 400

    target_number = participant_override or (cfg.get("target_number") or "").strip()
    normalized_target = normalize_contact(target_number)
    if not normalized_target:
        return jsonify({"error": "Podaj numer rozmówcy w konfiguracji AI lub w polu 'participant'."}), 400

    latest_message = None
    if use_latest_message and not message:
        candidates = list_messages(
            limit=10,
            direction="inbound",
            participant_normalized=normalized_target,
        )
        for item in candidates:
            body = (item.get("body") or "").strip()
            if body:
                latest_message = item
                break

    prompt_text = message or (latest_message.get("body") if latest_message else "")
    fallback_prompt = "To jest test połączenia z OpenAI. Potwierdź, że wszystko działa."
    used_latest_message = bool(latest_message and not message)
    if not prompt_text:
        prompt_text = fallback_prompt
        used_latest_message = False

    responder = AIResponder(
        api_key=api_key,
        model=(cfg.get("model") or "gpt-4o-mini").strip(),
        system_prompt=cfg.get("system_prompt") or "",
        temperature=float(cfg.get("temperature", 0.7) or 0.7),
        history_limit=history_limit,
    )

    try:
        reply = responder.build_reply(participant=target_number, latest_user_message=prompt_text)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("AI test request failed: %s", exc)
        return jsonify({"error": f"Żądanie OpenAI nie powiodło się: {exc}"}), 502

    reply = (reply or "").strip()
    if not reply:
        return jsonify({"error": "OpenAI nie zwróciło treści odpowiedzi."}), 502

    return jsonify(
        {
            "participant": target_number,
            "participant_normalized": normalize_contact(target_number),
            "input": prompt_text,
            "reply": reply,
            "model": responder.model,
            "temperature": responder.temperature,
            "history_limit": responder.history_limit,
            "used_latest_message": used_latest_message,
            "latest_message": latest_message,
            "fallback_used": not message and not latest_message,
        }
    )


@webhooks_bp.post("/api/ai/send")
def api_ai_send_message():
    """Generate an AI reply and send it via Twilio to a selected number.

        Body JSON:
            - participant: target phone number (optional; defaults to configured AI target)
            - latest: optional latest user message to include
            - history_limit: optional int, default 20
            - api_key: optional override for OpenAI key (if not stored)
    """

    payload = request.get_json(force=True, silent=True) or {}
    participant = (payload.get("participant") or "").strip()
    latest = (payload.get("latest") or "").strip()
    api_key_override = (payload.get("api_key") or "").strip()
    history_limit_raw = payload.get("history_limit", 20)
    
    # Safely parse history_limit with explicit None check
    history_limit = 20  # default
    if history_limit_raw is not None:
        try:
            history_limit = max(1, min(int(history_limit_raw), 200))
        except (TypeError, ValueError):
            pass  # Keep default

    try:
        result = send_ai_message_to_configured_target(
            latest_user_message=latest or None,
            history_limit=history_limit,
            api_key_override=api_key_override or None,
            participant_override=participant or None,
        )
    except AIReplyError as exc:
        if exc.reply_text:
            cfg = get_ai_config()
            target_number = participant or (cfg.get("target_number") or "")
            insert_message(
                direction="outbound",
                sid=None,
                to_number=target_number,
                from_number=current_app.config["TWILIO_SETTINGS"].default_from,
                body=exc.reply_text,
                status="failed",
                error=str(exc),
            )
        return jsonify({"error": str(exc)}), exc.status_code

    return jsonify(result), 201


@webhooks_bp.post("/api/ai/reply")
def api_ai_reply_to_inbound():
    payload = request.get_json(force=True, silent=True) or {}
    # Numer telefonu nie jest już wymagany – ten endpoint testuje tylko łączność HTTP
    _ = (payload.get("target_number") or "").strip()  # zachowaj zgodność z istniejącym UI

    svc = ScraperService()
    sample_url = next(iter(svc.news_sites.values()))
    started = time.monotonic()
    html = svc._get(sample_url)  # best-effort ping
    latency_ms = int((time.monotonic() - started) * 1000)

    if not html:
        return jsonify({"success": False, "error": "Brak odpowiedzi z serwisem news."}), 502

    cfg = _load_news_config()
    cfg["last_test_at"] = datetime.utcnow().isoformat() + "Z"
    cfg = _save_news_config(cfg)
    return jsonify(
        {
            "success": True,
            "details": f"Połączenie OK ({latency_ms} ms)",
            "latency_ms": latency_ms,
            "source": sample_url,
            "tested_at": cfg["last_test_at"],
        }
    )

    cfg = get_ai_config()
    api_key = api_key_override or (cfg.get("api_key") or "").strip()
    if not api_key:
        return jsonify({"error": "Brak klucza OpenAI. Uzupełnij konfigurację lub podaj api_key w żądaniu."}), 400

    responder = AIResponder(
        api_key=api_key,
        model=(cfg.get("model") or "gpt-4o-mini").strip(),
        system_prompt=cfg.get("system_prompt") or "",
        temperature=float(cfg.get("temperature", 0.7) or 0.7),
        history_limit=history_limit,
    )

    try:
        reply_text = responder.build_reply(participant=inbound_from, latest_user_message=latest or None)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("AI reply generation failed: %s", exc)
        return jsonify({"error": f"Generowanie odpowiedzi nie powiodło się: {exc}"}), 502

    reply_text = (reply_text or "").strip()
    if not reply_text:
        return jsonify({"error": "OpenAI nie zwróciło treści odpowiedzi."}), 502

    try:
        message = _send_ai_reply_message(inbound_from=inbound_from, inbound_to=inbound_to, reply_text=reply_text)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Twilio send failed: %s", exc)
        insert_message(
            direction="outbound",
            sid=None,
            to_number=inbound_from,
            from_number=inbound_to,
            body=reply_text,
            status="failed",
            error=str(exc),
        )
        return jsonify({"error": f"Wysyłka SMS nie powiodła się: {exc}"}), 502

    return jsonify(
        {
            "to": inbound_from,
            "from": inbound_to,
            "body": reply_text,
            "sid": getattr(message, "sid", None),
            "status": getattr(message, "status", None),
            "model": responder.model,
            "temperature": responder.temperature,
            "history_limit": responder.history_limit,
        }
    ), 201


@webhooks_bp.get("/api/ai/conversation")
def api_get_ai_conversation():
    participant = (request.args.get("participant") or "").strip()
    limit_raw = request.args.get("limit", "50")
    try:
        limit = max(1, min(200, int(limit_raw)))
    except ValueError:
        limit = 50

    normalized = ""
    if not participant:
        cfg = get_ai_config()
        participant = (cfg.get("target_number") or "").strip()
        normalized = cfg.get("target_number_normalized") or normalize_contact(participant)
    else:
        normalized = normalize_contact(participant)

    if not normalized:
        return jsonify({"participant": "", "items": []})

    messages = list_messages(
        limit=limit,
        participant_normalized=normalized,
        ascending=True,
    )
    return jsonify({"participant": participant, "items": messages})


@webhooks_bp.get("/api/reminders")
def api_list_reminders():
    items = list_scheduled_messages()
    return jsonify({"items": items, "count": len(items)})


@webhooks_bp.post("/api/reminders")
def api_create_reminder():
    payload = request.get_json(force=True, silent=True) or {}
    to_number = (payload.get("to") or "").strip()
    body = (payload.get("body") or "").strip()
    interval_minutes_raw = payload.get("interval_minutes")

    # Safely parse interval_minutes with explicit None check
    interval_minutes = 0
    if interval_minutes_raw is not None:
        try:
            interval_minutes = int(interval_minutes_raw)
        except (TypeError, ValueError):
            pass  # Keep default (0, will fail validation below)

    if not to_number:
        return jsonify({"error": "Pole 'to' jest wymagane."}), 400
    if not body:
        return jsonify({"error": "Pole 'body' jest wymagane."}), 400
    if interval_minutes < 1:
        return jsonify({"error": "Interwał musi być co najmniej 1 minuta."}), 400

    interval_seconds = interval_minutes * 60

    sched_id = create_scheduled_message(
        to_number=to_number,
        body=body,
        interval_seconds=interval_seconds,
        enabled=True,
    )
    items = list_scheduled_messages()
    return jsonify({"id": sched_id, "items": items, "count": len(items)}), 201


@webhooks_bp.post("/api/reminders/<int:sched_id>/toggle")
def api_toggle_reminder(sched_id: int):
    payload = request.get_json(force=True, silent=True) or {}
    enabled = bool(payload.get("enabled", False))
    updated = update_scheduled_message(sched_id=sched_id, enabled=enabled)
    if not updated:
        return jsonify({"error": "Nie znaleziono rekordu."}), 404
    items = list_scheduled_messages()
    return jsonify({"items": items, "count": len(items)})


@webhooks_bp.delete("/api/reminders/<int:sched_id>")
def api_delete_reminder(sched_id: int):
    deleted = delete_scheduled_message(sched_id)
    if not deleted:
        return jsonify({"error": "Nie znaleziono rekordu."}), 404
    items = list_scheduled_messages()
    return jsonify({"items": items, "count": len(items)})


@webhooks_bp.get("/api/news/config")
def api_get_news_config():
    cfg = _load_news_config()
    return jsonify(_serialize_news_config(cfg))


@webhooks_bp.post("/api/news/config")
def api_update_news_config():
    """Deprecated - use /api/news/recipients instead"""
    return jsonify({"error": "Use /api/news/recipients to manage notification recipients"}), 400


@webhooks_bp.get("/api/news/recipients")
def api_get_news_recipients():
    """Get list of all news notification recipients"""
    cfg = _load_news_config()
    recipients = cfg.get("recipients", [])
    return jsonify({"recipients": recipients, "count": len(recipients)})


@webhooks_bp.post("/api/news/recipients")
def api_add_news_recipient():
    """Add new news notification recipient"""
    payload = request.get_json(force=True, silent=True) or {}
    phone = (payload.get("phone") or "").strip()
    prompt = (payload.get("prompt") or "").strip()
    time_str = (payload.get("time") or "08:00").strip()
    use_all_categories = bool(payload.get("use_all_categories", True))
    
    if not phone:
        return jsonify({"error": "Podaj numer telefonu."}), 400
    
    if use_all_categories:
        prompt = ALL_CATEGORIES_PROMPT
    elif not prompt:
        prompt = DEFAULT_NEWS_PROMPT
    
    # Walidacja formatu czasu (HH:MM, 24h)
    import re
    if not re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", time_str):
        return jsonify({"error": "Nieprawidłowy format czasu. Użyj HH:MM (24h)."}), 400

    # Normalizuj i waliduj numer telefonu (E.164)
    normalized = normalize_contact(phone)
    if not normalized or not E164_RE.match(normalized):
        return jsonify({"error": "Podaj numer w formacie E.164, np. +48123456789."}), 400
    
    cfg = _load_news_config()
    recipients = cfg.get("recipients", [])

    # Zapobiegaj duplikatom (ten sam numer i godzina)
    for existing in recipients:
        if (
            existing.get("phone_normalized") == normalized
            and existing.get("time") == time_str
        ):
            return jsonify({"error": "Taki odbiorca (numer + godzina) już istnieje."}), 400

    # Wygeneruj ID (max ID + 1)
    max_id = max([r.get("id", 0) for r in recipients], default=0)
    new_id = max_id + 1
    
    # Utwórz nowego odbiorce
    new_recipient = {
        "id": new_id,
        "phone": phone,
        "phone_normalized": normalized,
        "prompt": prompt,
        "time": time_str,
        "enabled": True,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "last_sent_at": None,
        "use_all_categories": use_all_categories,
    }
    
    recipients.append(new_recipient)
    cfg["recipients"] = recipients
    saved = _save_news_config(cfg)
    
    return jsonify({
        "success": True,
        "recipient": new_recipient,
        "recipients": saved.get("recipients", [])
    })


@webhooks_bp.delete("/api/news/recipients/<int:recipient_id>")
def api_delete_news_recipient(recipient_id: int):
    """Delete news notification recipient"""
    cfg = _load_news_config()
    recipients = cfg.get("recipients", [])
    
    # Znajdź i usuń odbiorce
    new_recipients = [r for r in recipients if r.get("id") != recipient_id]
    
    if len(new_recipients) == len(recipients):
        return jsonify({"error": "Nie znaleziono odbiorcy"}), 404
    
    cfg["recipients"] = new_recipients
    saved = _save_news_config(cfg)
    
    return jsonify({
        "success": True,
        "recipients": saved.get("recipients", [])
    })


@webhooks_bp.post("/api/news/recipients/<int:recipient_id>/toggle")
def api_toggle_news_recipient(recipient_id: int):
    """Enable/disable news notification recipient"""
    cfg = _load_news_config()
    recipients = cfg.get("recipients", [])
    
    found = False
    for recipient in recipients:
        if recipient.get("id") == recipient_id:
            recipient["enabled"] = not recipient.get("enabled", True)
            found = True
            break
    
    if not found:
        return jsonify({"error": "Nie znaleziono odbiorcy"}), 404
    
    cfg["recipients"] = recipients
    saved = _save_news_config(cfg)
    
    return jsonify({
        "success": True,
        "recipients": saved.get("recipients", [])
    })


@webhooks_bp.post("/api/news/recipients/<int:recipient_id>/test")
def api_test_news_recipient(recipient_id: int):
    """Test notification generation for recipient (without sending SMS)"""
    cfg = _load_news_config()
    recipients = cfg.get("recipients", [])
    
    recipient = next((r for r in recipients if r.get("id") == recipient_id), None)
    if not recipient:
        return jsonify({"error": "Nie znaleziono odbiorcy"}), 404
    
    try:
        from app.faiss_service import FAISSService

        try:
            faiss_service = FAISSService()
        except RuntimeError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        loaded = faiss_service.load_index()
        
        if not loaded:
            return jsonify({
                "success": False,
                "error": "Brak indeksu FAISS. Najpierw wykonaj scraping."
            }), 404
        
        use_all_categories = bool(recipient.get("use_all_categories", True))
        prompt = (recipient.get("prompt") or "").strip() or (
            ALL_CATEGORIES_PROMPT if use_all_categories else DEFAULT_NEWS_PROMPT
        )
        if use_all_categories:
            response = faiss_service.answer_query_all_categories(prompt, per_category_k=DEFAULT_PER_CATEGORY_K)
        else:
            response = faiss_service.answer_query(prompt, top_k=5)
        
        if response.get("success") and response.get("answer"):
            message = f"📰 News Test:\n\n{response['answer']}"
            return jsonify({
                "success": True,
                "recipient_id": recipient_id,
                "phone": recipient.get("phone"),
                "message": message,
                "llm_used": response.get("llm_used", False),
                "mode": "all_categories" if use_all_categories else "standard",
            })
        else:
            return jsonify({
                "success": False,
                "error": response.get("error", "Nie udało się wygenerować odpowiedzi")
            }), 500
            
    except Exception as exc:
        current_app.logger.exception("Test recipient failed: %s", exc)
        return jsonify({
            "success": False,
            "error": f"Błąd: {exc}"
        }), 500


@webhooks_bp.post("/api/news/recipients/<int:recipient_id>/send")
def api_send_news_recipient(recipient_id: int):
    """Force send notification to specific recipient"""
    cfg = _load_news_config()
    recipients = cfg.get("recipients", [])
    
    recipient = next((r for r in recipients if r.get("id") == recipient_id), None)
    if not recipient:
        return jsonify({"error": "Nie znaleziono odbiorcy"}), 404
    
    if not recipient.get("enabled"):
        return jsonify({"error": "Odbiorca jest wyłączony"}), 400
    
    try:
        from app.faiss_service import FAISSService
        from app.twilio_client import TwilioService

        # Walidacja numeru odbiorcy
        phone = recipient.get("phone_normalized") or recipient.get("phone")
        if not phone or not E164_RE.match(phone):
            return jsonify({
                "success": False,
                "error": "Nieprawidłowy numer telefonu odbiorcy (wymagany format E.164).",
            }), 400

        try:
            faiss_service = FAISSService()
        except RuntimeError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        faiss_service.load_index()

        use_all_categories = bool(recipient.get("use_all_categories", True))
        prompt = (recipient.get("prompt") or "").strip() or (
            ALL_CATEGORIES_PROMPT if use_all_categories else DEFAULT_NEWS_PROMPT
        )
        if use_all_categories:
            response = faiss_service.answer_query_all_categories(prompt, per_category_k=DEFAULT_PER_CATEGORY_K)
        else:
            response = faiss_service.answer_query(prompt, top_k=5)

        if not response.get("success") or not response.get("answer"):
            return jsonify({
                "success": False,
                "error": "Nie udało się wygenerować wiadomości",
            }), 500

        message = f"📰 News:\n\n{response['answer']}"

        # Wyślij SMS
        twilio_client: TwilioService = current_app.config["TWILIO_CLIENT"]
        origin = twilio_client.settings.default_from

        if not origin:
            return jsonify({
                "success": False,
                "error": "Brak skonfigurowanego nadawcy Twilio",
            }), 500

        result = twilio_client.send_chunked_sms(
            from_=origin,
            to=phone,
            body=message,
        )

        if result.get("success"):
            # Aktualizuj last_sent_at
            for r in recipients:
                if r.get("id") == recipient_id:
                    r["last_sent_at"] = datetime.utcnow().isoformat() + "Z"
                    break

            cfg["recipients"] = recipients
            _save_news_config(cfg)

            return jsonify({
                "success": True,
                "recipient_id": recipient_id,
                "phone": phone,
                "message_sid": result.get("sid"),
                "parts": result.get("parts", 1),
                "mode": "all_categories" if use_all_categories else "standard",
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get("error", "Nie udało się wysłać SMS"),
            }), 500

    except Exception as exc:
        current_app.logger.exception("Send to recipient failed: %s", exc)
        return jsonify({
            "success": False,
            "error": f"Błąd: {exc}"
        }), 500


@webhooks_bp.post("/api/news/test")
def api_test_news():
    payload = request.get_json(force=True, silent=True) or {}
    # Numer telefonu nie jest już wymagany – ten endpoint testuje tylko łączność HTTP
    _ = (payload.get("target_number") or "").strip()  # zachowaj zgodność z istniejącym UI

    svc = ScraperService()
    sample_url = next(iter(svc.news_sites.values()))
    started = time.monotonic()
    html = svc._get(sample_url)  # best-effort ping
    latency_ms = int((time.monotonic() - started) * 1000)

    if not html:
        return jsonify({"success": False, "error": "Brak odpowiedzi z serwisu news."}), 502

    cfg = _load_news_config()
    cfg["last_test_at"] = datetime.utcnow().isoformat() + "Z"
    _save_news_config(cfg)
    return jsonify(
        {
            "success": True,
            "details": f"Połączenie OK ({latency_ms} ms)",
            "latency_ms": latency_ms,
            "source": sample_url,
            "tested_at": cfg["last_test_at"],
        }
    )


@webhooks_bp.post("/api/news/scrape")
def api_news_scrape():
    cfg = _load_news_config()
    svc = ScraperService()
    started_at = datetime.utcnow().isoformat() + "Z"
    try:
        results = svc.fetch_all_categories(build_faiss=True)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("News scrape failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 502

    completed_at = datetime.utcnow().isoformat() + "Z"
    cfg["last_build_at"] = completed_at
    saved_cfg = _save_news_config(cfg)

    items = []
    for category, content in results.items():
        ok = bool(content) and not str(content).startswith("❌")
        items.append({"category": category, "success": ok, "preview": (content or "")[:200]})

    files = _list_scraped_files()
    return jsonify(
        {
            "success": True,
            "started_at": started_at,
            "completed_at": completed_at,
            "items": items,
            "files": files,
            "config": _serialize_news_config(saved_cfg),
        }
    )


@webhooks_bp.get("/api/news/scrape/stream")
def api_news_scrape_stream():
    """SSE endpoint for streaming scrape progress per category."""

    def generate():
        cfg = _load_news_config()
        svc = ScraperService()
        started_at = datetime.utcnow().isoformat() + "Z"

        # Send initial event with categories list
        categories = list(svc.news_sites.keys())
        yield f"data: {json.dumps({'type': 'start', 'categories': categories, 'started_at': started_at})}\n\n"

        results: Dict[str, str] = {}
        all_articles: list = []

        for idx, (category, url) in enumerate(svc.news_sites.items()):
            # Send "processing" event
            yield f"data: {json.dumps({'type': 'processing', 'category': category, 'index': idx, 'total': len(categories)})}\n\n"

            try:
                articles = svc.scrape_category(category, url)
                if not articles:
                    msg = f"❌ Brak artykułów dla kategorii {category}"
                    results[category] = msg
                    yield f"data: {json.dumps({'type': 'done', 'category': category, 'success': False, 'message': msg})}\n\n"
                    svc._sleep()
                    continue

                combined_text = "\n\n".join(a.text for a in articles).strip()
                if not combined_text:
                    msg = f"❌ Pusta treść po czyszczeniu dla {category}"
                    results[category] = msg
                    yield f"data: {json.dumps({'type': 'done', 'category': category, 'success': False, 'message': msg})}\n\n"
                    svc._sleep()
                    continue

                svc._save_category(category, articles)
                svc.scraped_cache[category] = combined_text
                results[category] = combined_text
                all_articles.extend(articles)

                yield f"data: {json.dumps({'type': 'done', 'category': category, 'success': True, 'articles_count': len(articles)})}\n\n"

            except Exception as exc:  # noqa: BLE001
                msg = f"❌ Błąd podczas pobierania: {exc}"
                results[category] = msg
                yield f"data: {json.dumps({'type': 'done', 'category': category, 'success': False, 'message': str(exc)})}\n\n"
            finally:
                svc._sleep()

        # Save articles store
        if all_articles:
            svc._upsert_articles_store(all_articles)

        # Build FAISS
        yield f"data: {json.dumps({'type': 'building_faiss'})}\n\n"
        svc._build_faiss_from_results(results)

        completed_at = datetime.utcnow().isoformat() + "Z"
        cfg["last_build_at"] = completed_at
        _save_news_config(cfg)

        # Final summary
        items = []
        for category, content in results.items():
            ok = bool(content) and not str(content).startswith("❌")
            items.append({"category": category, "success": ok})

        files = _list_scraped_files()
        yield f"data: {json.dumps({'type': 'complete', 'completed_at': completed_at, 'items': items, 'files_count': len(files)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@webhooks_bp.get("/api/news/files")
def api_news_files():
    items = _list_scraped_files()
    return jsonify({"items": items, "count": len(items)})


@webhooks_bp.get("/api/news/files/<path:filename>")
def api_news_file_content(filename: str):
    data = _read_scraped_file_content(filename)
    if data.get("error"):
        return jsonify(data), 404
    return jsonify(data)


@webhooks_bp.delete("/api/news/files/<path:filename>")
def api_news_file_delete(filename: str):
    safe_name = os.path.basename(filename)
    path = os.path.join(SCRAPED_DIR, safe_name)

    if not os.path.exists(path):
        return jsonify({"error": "Plik nie istnieje."}), 404

    try:
        os.remove(path)
        return jsonify({"success": True, "removed": safe_name})
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Cannot delete scraped file %s: %s", path, exc)
        return jsonify({"error": f"Nie udało się usunąć pliku: {exc}"}), 500


@webhooks_bp.delete("/api/news/files")
def api_news_files_delete_all():
    """Delete all scraped files."""
    try:
        files = _list_scraped_files()
        deleted = []
        errors = []

        for file_info in files:
            safe_name = os.path.basename(file_info.get("name", ""))
            if not safe_name:
                continue
            path = os.path.join(SCRAPED_DIR, safe_name)
            try:
                if os.path.exists(path):
                    os.remove(path)
                    deleted.append(safe_name)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{safe_name}: {exc}")

        return jsonify({
            "success": len(errors) == 0,
            "deleted": deleted,
            "deleted_count": len(deleted),
            "errors": errors,
        })
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Cannot delete all scraped files: %s", exc)
        return jsonify({"error": f"Nie udało się usunąć plików: {exc}"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Listeners API
# ─────────────────────────────────────────────────────────────────────────────
# Listeners are command-based triggers that respond to incoming SMS messages
# starting with specific prefixes (e.g., /news). This API provides management
# endpoints for configuring and testing listeners.
# ─────────────────────────────────────────────────────────────────────────────


@webhooks_bp.get("/api/listeners")
def api_get_listeners():
    """Get all listener configurations.
    
    Returns:
        JSON with list of all configured listeners including:
        - id: Unique identifier
        - command: Command prefix (e.g., '/news')
        - enabled: Whether the listener is active
        - description: Human-readable description
        - created_at, updated_at: Timestamps
    """
    try:
        listeners = get_listeners_config()
        return jsonify({"success": True, "listeners": listeners})
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Failed to get listeners: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@webhooks_bp.post("/api/listeners/<int:listener_id>")
def api_update_listener(listener_id: int):
    """Update listener configuration.
    
    Args:
        listener_id: ID of the listener to update
        
    Request body:
        - enabled (bool, optional): Enable or disable the listener
        - description (str, optional): Update the description
        
    Returns:
        Updated listener configuration
    """
    payload = request.get_json(force=True, silent=True) or {}
    
    enabled = payload.get("enabled")
    description = payload.get("description")
    
    try:
        result = update_listener_config(
            listener_id,
            enabled=enabled if enabled is not None else None,
            description=description,
        )
        current_app.logger.info(
            "Listener %d updated: enabled=%s",
            listener_id,
            enabled
        )
        return jsonify({"success": True, "listener": result})
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Failed to update listener: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@webhooks_bp.post("/api/listeners/test")
def api_test_listener():
    """Test /news listener with a sample query.
    
    Request body:
        - query (str): Test query, optionally starting with /news
        
    Returns:
        - success: Whether the test succeeded
        - query: The processed query (without /news prefix)
        - answer: The generated answer from FAISS
        - llm_used: Whether an LLM was used for generation
    """
    payload = request.get_json(force=True, silent=True) or {}
    query = (payload.get("query") or "").strip()
    
    if not query:
        return jsonify({"success": False, "error": "Podaj zapytanie testowe"}), 400
    
    try:
        from .faiss_service import FAISSService
        faiss_service = FAISSService()
        
        # Remove /news prefix if present
        clean_query = query
        if clean_query.lower().startswith("/news"):
            clean_query = clean_query[5:].strip()
        
        if not clean_query:
            clean_query = "Jakie są najnowsze wiadomości?"
        
        response = faiss_service.answer_query(clean_query, top_k=5)
        
        if response.get("success") and response.get("answer"):
            current_app.logger.info("Listener test successful for query: %s", clean_query[:50])
            return jsonify({
                "success": True,
                "query": clean_query,
                "answer": response["answer"],
                "llm_used": response.get("llm_used", False),
            })
        else:
            return jsonify({
                "success": False,
                "error": response.get("error", "Brak odpowiedzi z FAISS"),
            }), 500
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Listener test failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@webhooks_bp.get("/api/news/faiss/export")
def api_news_faiss_export():
    manifest = _faiss_backup_manifest()
    available = [item for item in manifest if item["exists"]]

    if not available:
        return jsonify({"error": "Brak plików FAISS do zapisania."}), 404

    generated_at = datetime.utcnow().isoformat() + "Z"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        files_meta: List[Dict[str, Any]] = []
        for item in available:
            try:
                zf.write(item["path"], arcname=item["name"])
                size_bytes = os.path.getsize(item["path"])
            except Exception as exc:  # noqa: BLE001
                current_app.logger.warning("Cannot add %s to FAISS export: %s", item["path"], exc)
                continue
            files_meta.append(
                {
                    "name": item["name"],
                    "required": item["required"],
                    "size_bytes": size_bytes,
                }
            )

        zf.writestr(
            "manifest.json",
            json.dumps({"generated_at": generated_at, "files": files_meta}, ensure_ascii=False, indent=2),
        )

    buffer.seek(0)
    filename = f"faiss_backup_{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.zip"
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


@webhooks_bp.post("/api/news/faiss/import")
def api_news_faiss_import():
    uploaded = request.files.get("archive")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Wybierz plik ZIP z backupem FAISS."}), 400

    if not uploaded.filename.lower().endswith(".zip"):
        return jsonify({"error": "Obsługiwane są tylko archiwa .zip."}), 400

    content_length = request.content_length or uploaded.content_length
    if content_length and content_length > MAX_FAISS_BACKUP_BYTES:
        return jsonify({"error": "Plik backupu jest zbyt duży (limit 250 MB)."}), 413

    restored: List[str] = []

    try:
        with tempfile.TemporaryDirectory(prefix="faiss_import_") as tmpdir:
            archive_path = os.path.join(tmpdir, "upload.zip")
            uploaded.save(archive_path)

            with zipfile.ZipFile(archive_path, "r") as zf:
                members = {
                    os.path.basename(name): name
                    for name in zf.namelist()
                    if name and not name.endswith("/")
                }

                manifest = FAISS_BACKUP_FILES
                missing = [item["name"] for item in manifest if item["required"] and item["name"] not in members]
                if missing:
                    return jsonify({"error": f"Brakuje wymaganych plików: {', '.join(missing)}"}), 400

                for item in manifest:
                    member_name = members.get(item["name"])
                    if not member_name:
                        continue

                    destination = item["path"]
                    os.makedirs(os.path.dirname(destination), exist_ok=True)
                    tmp_target = os.path.join(tmpdir, f"{item['name']}.tmp")

                    with zf.open(member_name) as src, open(tmp_target, "wb") as dst:
                        shutil.copyfileobj(src, dst)

                    shutil.move(tmp_target, destination)
                    restored.append(item["name"])

    except zipfile.BadZipFile:
        return jsonify({"error": "Nieprawidłowe archiwum ZIP."}), 400
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("FAISS import failed: %s", exc)
        return jsonify({"error": f"Nie udało się wczytać backupu: {exc}"}), 500

    return jsonify({"success": True, "restored": restored})


@webhooks_bp.get("/api/news/faiss/status")
def api_news_faiss_status():
    """Zwraca status indeksu FAISS oraz konfiguracji modeli."""
    try:
        from app.faiss_service import FAISSService

        try:
            faiss_service = FAISSService()
        except RuntimeError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        status = faiss_service.get_index_status()
        vector_count = 0
        loaded = False

        try:
            loaded = faiss_service.load_index()
            if loaded and faiss_service.vector_store and getattr(faiss_service.vector_store, "index", None):
                vector_count = int(getattr(faiss_service.vector_store.index, "ntotal", 0))
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning("FAISS status load failed: %s", exc)

        backup_info = _faiss_backup_manifest()
        payload = {
            **status,
            "loaded": loaded,
            "vector_count": vector_count,
            "embedding_model": faiss_service.embeddings.model,
            "chat_model": faiss_service.chat_model,
            "backup_files": backup_info,
            "backup_ready": all(item["exists"] for item in backup_info if item["required"]),
        }
        return jsonify({"success": True, "status": payload})

    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("FAISS status endpoint failed: %s", exc)
        return jsonify({"success": False, "error": f"Błąd statusu FAISS: {exc}"}), 500


@webhooks_bp.get("/api/news/indices")
def api_news_indices():
    payload = _faiss_indices_payload()
    cfg = _load_news_config()
    active_name = cfg.get("active_index", "faiss_openai_index")
    for item in payload.get("items", []):
        item["active"] = item.get("name") == active_name
    return jsonify(payload)


@webhooks_bp.post("/api/news/indices/active")
def api_news_set_active_index():
    payload = request.get_json(force=True, silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Podaj nazwę indeksu."}), 400

    available = [item.get("name") for item in _faiss_indices_payload().get("items", [])]
    if name not in available:
        return jsonify({"error": "Nie znaleziono indeksu."}), 404

    cfg = _load_news_config()
    cfg["active_index"] = name
    saved = _save_news_config(cfg)

    # Ensure minimal files exist for selected index
    paths = _faiss_index_files(name)
    os.makedirs(paths["base"], exist_ok=True)
    try:
        if not os.path.exists(paths["docs"]):
            with open(paths["docs"], "w", encoding="utf-8") as f:
                json.dump([], f)
        if not os.path.exists(paths["npz"]):
            try:
                import numpy as _np
                _np.savez_compressed(paths["npz"], embeddings=_np.zeros((0, 0)), ids=_np.array([], dtype=object))
            except Exception:
                # fallback: create empty file
                open(paths["npz"], "a").close()
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning("Failed to initialize empty index files: %s", exc)

    return jsonify({"active_index": saved.get("active_index")})


@webhooks_bp.delete("/api/news/indices/<name>")
def api_news_delete_index(name: str):
    safe_name = (name or "").strip()
    if not safe_name:
        return jsonify({"error": "Podaj nazwę indeksu."}), 400

    if safe_name != "faiss_openai_index":
        return jsonify({"error": "Nieobsługiwany indeks."}), 400

    result = _delete_faiss_index(safe_name)
    return jsonify({"success": True, **result})


@webhooks_bp.post("/api/news/test-faiss")
def api_news_test_faiss():
    """
    Test FAISS query with custom prompt.
    """
    payload = request.get_json(force=True, silent=True) or {}
    query = (payload.get("query") or "").strip()
    mode = str(payload.get("mode") or "standard").strip().lower()
    per_category_k = int(payload.get("per_category_k") or DEFAULT_PER_CATEGORY_K)
    top_k = int(payload.get("top_k") or 5)
    
    if mode == "all_categories":
        query = query or ALL_CATEGORIES_PROMPT
    elif not query:
        return jsonify({"success": False, "error": "Podaj zapytanie (query)."}), 400
    
    try:
        from app.faiss_service import FAISSService
        
        try:
            faiss_service = FAISSService()
        except RuntimeError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        loaded = faiss_service.load_index()
        
        if not loaded:
            return jsonify({
                "success": False,
                "error": "Brak indeksu FAISS. Najpierw wykonaj scraping i zbuduj indeks."
            }), 404
        
        # Wykonaj query
        if mode == "all_categories":
            response = faiss_service.answer_query_all_categories(query, per_category_k=max(1, per_category_k))
        else:
            response = faiss_service.answer_query(query, top_k=max(1, top_k))
        
        if response.get("success"):
            payload = {
                "success": True,
                "query": query,
                "answer": response.get("answer", ""),
                "llm_used": response.get("llm_used", False),
                "count": response.get("count", 0),
                "results": response.get("results", []),
                "context_preview": response.get("context_preview", ""),
                "search_info": response.get("search_info", {}),
                "chat_model": response.get("chat_model"),
                "mode": "all_categories" if mode == "all_categories" else "standard",
            }
            if mode == "all_categories":
                payload["per_category_k"] = max(1, per_category_k)
            return jsonify(payload)
        else:
            return jsonify({
                "success": False,
                "error": response.get("error", "Nieznany błąd")
            }), 500
            
    except Exception as exc:
        current_app.logger.exception("FAISS test query failed: %s", exc)
        return jsonify({
            "success": False,
            "error": f"Błąd zapytania: {exc}"
        }), 500


@webhooks_bp.post("/api/news/indices/build")
def api_news_build_index():
    """
    Manually build FAISS index from existing scraped .txt files.
    """
    try:
        from app.faiss_service import FAISSService
        
        try:
            faiss_service = FAISSService()
        except RuntimeError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        success = faiss_service.build_index_from_category_files(SCRAPED_DIR)
        
        if success:
            cfg = _load_news_config()
            cfg["last_build_at"] = datetime.utcnow().isoformat() + "Z"
            _save_news_config(cfg)
            
            return jsonify({
                "success": True,
                "message": "Indeks FAISS został zbudowany pomyślnie",
                "built_at": cfg["last_build_at"]
            })
        else:
            return jsonify({
                "success": False,
                "error": "Nie udało się zbudować indeksu. Sprawdź czy istnieją pliki .txt."
            }), 500
            
    except Exception as exc:
        current_app.logger.exception("FAISS build failed: %s", exc)
        return jsonify({
            "success": False,
            "error": f"Błąd budowania indeksu: {exc}"
        }), 500


@webhooks_bp.post("/twilio/status")
def message_status():
    app = current_app
    if not _validate_twilio_signature(request):
        return jsonify({"status": "forbidden", "message": "Invalid signature"}), 403

    data = request.form.to_dict()
    app.logger.info("Message status update: %s", data)
    
    message_sid = (data.get("MessageSid") or data.get("SmsSid") or "").strip() or None
    status = (data.get("MessageStatus") or data.get("SmsStatus") or "").strip() or None

    # Build error message if present
    error: str | None = None
    if data.get("ErrorMessage"):
        error = str(data["ErrorMessage"]).strip()
    elif data.get("ErrorCode"):
        error = f"Error code: {data['ErrorCode']}"

    if not message_sid:
        app.logger.warning("Received status update without MessageSid: %s", data)
        return jsonify({"status": "error", "message": "Missing MessageSid"}), 400

    if not status:
        app.logger.warning("Received status update without status for SID %s", message_sid)
        return jsonify({"status": "error", "message": "Missing status"}), 400

    try:
        updated = update_message_status_by_sid(sid=message_sid, status=status, error=error)
        if updated:
            app.logger.info("Updated status for message %s to %s", message_sid, status)
        else:
            app.logger.warning("Received status for unknown message SID: %s", message_sid)
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Failed to update message status for SID %s: %s", message_sid, exc)
        return jsonify({"status": "error", "message": str(exc)}), 500

    return jsonify({"status": "ok"})


@webhooks_bp.post("/api/send-message")
def api_send_message():
    """REST endpoint for sending SMS/MMS messages via Twilio API."""

    payload = request.get_json(force=True, silent=True) or {}
    
    # Validate and sanitize input parameters (SMS only)
    to = (payload.get("to") or "").strip()
    body = payload.get("body")  # Can be None for MMS-only

    content_sid = payload.get("content_sid")
    content_variables = _encode_content_variables(payload.get("content_variables"))
    media_urls = _coerce_media_urls(payload.get("media_urls"))
    messaging_service_sid = payload.get("messaging_service_sid")

    raw_use_ms = payload.get("use_messaging_service")
    use_ms = bool(raw_use_ms) if raw_use_ms is not None else None

    if not to:
        return jsonify({"error": "Field 'to' is required."}), 400

    if not any([body, content_sid, media_urls]):
        return jsonify({"error": "Provide at least one of: 'body', 'content_sid', or 'media_urls'."}), 400

    twilio_client: TwilioService = current_app.config["TWILIO_CLIENT"]

    try:
        extra_params: Dict[str, Any] = {}
        if media_urls:
            extra_params["media_url"] = media_urls
        if content_sid:
            extra_params["content_sid"] = content_sid
        if content_variables:
            extra_params["content_variables"] = content_variables

        message = twilio_client.send_message(
            to=to,
            body=body or "",
            use_messaging_service=use_ms,
            messaging_service_sid=messaging_service_sid,
            extra_params=extra_params,
        )
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Error while sending message")
        origin = twilio_client.settings.default_from
        insert_message(
            direction="outbound",
            sid=None,
            to_number=to,
            from_number=origin,
            body=body or "",
            status="failed",
            error=str(exc),
        )
        return jsonify({"error": str(exc)}), 500

    _persist_twilio_message(message)

    return jsonify({"sid": message.sid, "status": message.status})


@webhooks_bp.post("/api/multi-sms/batches")
def api_create_multi_sms_batch():
    payload = request.get_json(force=True, silent=True) or {}
    body = (payload.get("body") or "").strip()
    recipients = _extract_multi_sms_recipients(payload)

    if not body:
        return jsonify({"error": "Treść wiadomości jest wymagana."}), 400

    if not recipients:
        return jsonify({"error": "Dodaj co najmniej jeden numer odbiorcy."}), 400

    max_recipients = 250
    if len(recipients) > max_recipients:
        return jsonify({"error": f"Maksymalnie {max_recipients} odbiorców na jedno zadanie."}), 400

    settings = current_app.config["TWILIO_SETTINGS"]
    has_sender = bool(
        (settings.default_from and settings.default_from.strip())
        or (settings.messaging_service_sid and settings.messaging_service_sid.strip())
    )
    if not has_sender:
        return jsonify({"error": "Skonfiguruj TWILIO_DEFAULT_FROM lub Messaging Service SID."}), 400

    try:
        batch = create_multi_sms_batch(
            body=body,
            recipients=recipients,
            sender_identity=_sender_identity_label(),
            scheduled_at=None,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"batch": batch}), 201


@webhooks_bp.get("/api/multi-sms/batches")
def api_list_multi_sms_batches():
    limit_raw = request.args.get("limit", "20")
    try:
        limit = max(1, min(int(limit_raw), 200))
    except ValueError:
        limit = 20

    include_recipients = (request.args.get("include_recipients") or "").strip().lower() in {"1", "true", "yes", "y"}

    items = list_multi_sms_batches(limit=limit)
    if include_recipients:
        enriched: List[Dict[str, Any]] = []
        for batch in items:
            batch_id = batch.get("id")
            recipients = list_multi_sms_recipients(batch_id, statuses=None) if batch_id is not None else []
            enriched.append({**batch, "recipients": recipients})
        items = enriched

    return jsonify({"items": items, "count": len(items)})


@webhooks_bp.get("/api/multi-sms/batches/<int:batch_id>")
def api_multi_sms_batch_detail(batch_id: int):
    batch = get_multi_sms_batch(batch_id)
    if not batch:
        return jsonify({"error": "Nie znaleziono zadania."}), 404
    return jsonify({"batch": batch})


@webhooks_bp.get("/api/multi-sms/batches/<int:batch_id>/recipients")
def api_multi_sms_batch_recipients(batch_id: int):
    batch = get_multi_sms_batch(batch_id)
    if not batch:
        return jsonify({"error": "Nie znaleziono zadania."}), 404

    statuses_raw = (request.args.get("status") or "").strip()
    statuses = [part.strip() for part in statuses_raw.split(",") if part.strip()] if statuses_raw else None

    items = list_multi_sms_recipients(batch_id, statuses=statuses)
    return jsonify({"items": items, "count": len(items)})


@webhooks_bp.get("/api/messages")
def api_messages():
    limit_raw = request.args.get("limit", "50")
    try:
        limit = max(1, min(int(limit_raw), 500))
    except ValueError:
        limit = 50

    direction = request.args.get("direction")
    _maybe_sync_messages(limit=limit)
    messages = list_messages(limit=limit, direction=direction)
    return jsonify({"items": messages, "count": len(messages)})


@webhooks_bp.get("/api/conversations")
def api_conversations():
    limit_raw = request.args.get("limit", "30")
    try:
        limit = max(1, min(int(limit_raw), 200))
    except ValueError:
        limit = 30

    conversations = list_conversations(limit=limit)
    return jsonify({"items": conversations, "count": len(conversations)})


@webhooks_bp.get("/api/conversations/<path:participant>")
def api_conversation_detail(participant: str):
    normalized_participant = unquote(participant).strip()
    if not normalized_participant:
        return jsonify({"error": "Participant is required."}), 400

    normalized_contact_value = normalize_contact(normalized_participant)
    query_kwargs: Dict[str, Any]
    if normalized_contact_value:
        query_kwargs = {"participant_normalized": normalized_contact_value}
    else:
        query_kwargs = {"participant": normalized_participant}

    _maybe_sync_messages(limit=CHAT_HISTORY_LIMIT)
    messages = list_messages(limit=CHAT_HISTORY_LIMIT, ascending=True, **query_kwargs)
    return jsonify(
        {
            "participant": normalized_participant,
            "items": messages,
            "count": len(messages),
        }
    )


@webhooks_bp.get("/api/messages/stats")
def api_messages_stats():
    _maybe_sync_messages(limit=50)
    stats = get_message_stats()
    return jsonify(stats)


@webhooks_bp.get("/api/messages/remote")
def api_remote_messages():
    limit_raw = request.args.get("limit", "20")
    try:
        limit = max(1, min(int(limit_raw), 100))
    except ValueError:
        limit = 20

    filters: Dict[str, Any] = {"limit": limit}
    to_filter = request.args.get("to")
    if to_filter:
        filters["to"] = to_filter
    from_filter = request.args.get("from")
    if from_filter:
        filters["from_"] = from_filter

    date_sent = _parse_datetime_arg(request.args.get("date_sent"))
    if date_sent:
        filters["date_sent"] = date_sent
    date_sent_before = _parse_datetime_arg(request.args.get("date_sent_before"))
    if date_sent_before:
        filters["date_sent_before"] = date_sent_before
    date_sent_after = _parse_datetime_arg(request.args.get("date_sent_after"))
    if date_sent_after:
        filters["date_sent_after"] = date_sent_after

    twilio_client: TwilioService = current_app.config["TWILIO_CLIENT"]
    try:
        remote_messages = twilio_client.list_messages(**filters)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Unable to list messages")
        return jsonify({"error": str(exc)}), 500

    items = []
    first_inbound_enqueued = False
    for message in remote_messages:
        _persist_twilio_message(message)

        # Enqueue auto-reply for the newest inbound message only (remote list is newest-first)
        if not first_inbound_enqueued and (getattr(message, "direction", "") or "").startswith("inbound"):
            _maybe_enqueue_auto_reply_for_message(message)
            first_inbound_enqueued = True

        items.append(_twilio_message_to_dict(message))

    return jsonify({"items": items, "count": len(items)})


@webhooks_bp.get("/api/messages/<sid>")
def api_message_detail(sid: str):
    twilio_client: TwilioService = current_app.config["TWILIO_CLIENT"]
    try:
        message = twilio_client.fetch_message(sid)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Unable to fetch message %s", sid)
        return jsonify({"error": str(exc)}), 404

    _persist_twilio_message(message)
    return jsonify({"item": _twilio_message_to_dict(message)})


@webhooks_bp.post("/api/messages/<sid>/redact")
def api_redact_message(sid: str):
    twilio_client: TwilioService = current_app.config["TWILIO_CLIENT"]
    try:
        message = twilio_client.redact_message(sid)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Unable to redact message %s", sid)
        return jsonify({"error": str(exc)}), 400

    _persist_twilio_message(message)
    return jsonify({"sid": message.sid, "body": message.body, "status": message.status})


@webhooks_bp.delete("/api/messages/<sid>")
def api_delete_message(sid: str):
    twilio_client: TwilioService = current_app.config["TWILIO_CLIENT"]
    try:
        remote_deleted = twilio_client.delete_message(sid)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Unable to delete message %s", sid)
        return jsonify({"error": f"Nie udało się usunąć wiadomości na Twilio: {exc}"}), 502

    if not remote_deleted:
        current_app.logger.warning("Twilio did not confirm deletion for SID %s", sid)
        return jsonify({"error": "Twilio nie potwierdziło usunięcia wiadomości."}), 502

    deleted_local = delete_message_by_sid(sid)
    return jsonify({
        "sid": sid,
        "deleted_remote": True,
        "deleted_local": bool(deleted_local),
    })


@webhooks_bp.delete("/api/conversations/<path:participant>")
def api_delete_conversation(participant: str):
    participant_value = unquote(participant).strip()
    if not participant_value:
        return jsonify({"error": "Participant is required."}), 400

    normalized_value = normalize_contact(participant_value)
    try:
        message_refs = list_conversation_message_refs(
            participant=participant_value,
            participant_normalized=normalized_value or None,
        )
    except ValueError:
        return jsonify({"error": "Brak identyfikatora rozmowy."}), 400

    if not message_refs:
        return jsonify({"error": "Nie znaleziono rozmowy."}), 404

    missing_sid_ids = [ref["id"] for ref in message_refs if not (ref.get("sid") or "").strip()]
    if missing_sid_ids:
        return (
            jsonify(
                {
                    "error": "Nie wszystkie wiadomości w wątku mają SID Twilio."
                    " Usuń je ręcznie po zsynchronizowaniu.",
                    "missing_local_ids": missing_sid_ids,
                }
            ),
            409,
        )

    twilio_client: TwilioService = current_app.config["TWILIO_CLIENT"]
    failed: List[Dict[str, Any]] = []
    for ref in message_refs:
        sid = ref.get("sid")
        if not sid:
            continue
        try:
            remote_deleted = twilio_client.delete_message(sid)
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning(
                "Unable to delete message %s during conversation cleanup", sid, exc_info=True
            )
            failed.append({"sid": sid, "error": str(exc)})
            continue

        if not remote_deleted:
            current_app.logger.warning(
                "Twilio did not confirm deletion for conversation message %s", sid
            )
            failed.append({"sid": sid, "error": "Twilio nie potwierdziło usunięcia"})

    if failed:
        return (
            jsonify(
                {
                    "error": "Nie udało się usunąć wszystkich wiadomości na Twilio.",
                    "failed": failed,
                }
            ),
            502,
        )

    deleted_local = delete_conversation_messages(
        participant=participant_value,
        participant_normalized=normalized_value or None,
    )
    return jsonify(
        {
            "participant": participant_value,
            "deleted_remote": len(message_refs),
            "deleted_local": deleted_local,
        }
    )

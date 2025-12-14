from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, date
from typing import Optional, Dict

from flask import Flask

from .database import normalize_contact
from .validators import E164_PATTERN as E164_RE
from .twilio_client import TwilioService

logger = logging.getLogger(__name__)


def start_news_scheduler(app: Flask, *, check_interval_seconds: int = 60) -> None:
    """
    Start background scheduler for News notifications.
    
    Checks every minute if it's time to send News notification to any recipient.
    """
    if app.config.get("NEWS_SCHEDULER_STARTED"):
        app.logger.debug("News scheduler already running; skipping startup")
        return

    def scheduler() -> None:
        """Background loop checking if it's time to send News.

        Zasady wysyłki (idempotentne, raz dziennie na odbiorcę):
        - bazujemy na polu `last_sent_at` zapisanym w configu,
        - jeżeli `last_sent_at` ma tę samą datę co "dziś" -> nie wysyłamy ponownie,
        - sprawdzamy godzinę/minutę względem pola `time` (HH:MM, czas serwera).
        """

        while True:
            time.sleep(check_interval_seconds)
            try:
                with app.app_context():
                    from .webhooks import (
                        _load_news_config,
                        _save_news_config,
                        ALL_CATEGORIES_PROMPT,
                        DEFAULT_NEWS_PROMPT,
                        DEFAULT_PER_CATEGORY_K,
                    )
                    from .faiss_service import FAISSService

                    cfg = _load_news_config()
                    
                    if not cfg.get("enabled"):
                        continue
                    
                    recipients = cfg.get("recipients", [])
                    if not recipients:
                        continue

                    now = datetime.now()
                    today = date.today()

                    # Sprawdź każdego odbiorce
                    for recipient in recipients:
                        if not recipient.get("enabled"):
                            continue
                        
                        recipient_id = recipient.get("id")
                        notification_time = recipient.get("time", "08:00")
                        raw_phone = recipient.get("phone") or ""
                        phone = recipient.get("phone_normalized") or normalize_contact(raw_phone)
                        use_all_categories = bool(recipient.get("use_all_categories", True))
                        prompt = (recipient.get("prompt") or "").strip() or (
                            ALL_CATEGORIES_PROMPT if use_all_categories else DEFAULT_NEWS_PROMPT
                        )
                        
                        if not phone or not recipient_id:
                            continue

                        # Walidacja formatu numeru (E.164)
                        if not E164_RE.match(phone):
                            logger.warning(
                                "News scheduler: pomijam odbiorcę %s z nieprawidłowym numerem %s",
                                recipient_id,
                                phone,
                            )
                            continue

                        # Sprawdź czy już wysłano dzisiaj na podstawie last_sent_at
                        last_sent_at = recipient.get("last_sent_at") or ""
                        try:
                            last_sent_dt = (
                                datetime.fromisoformat(last_sent_at.replace("Z", ""))
                                if last_sent_at
                                else None
                            )
                        except ValueError:
                            last_sent_dt = None

                        if last_sent_dt and last_sent_dt.date() == today:
                            # Już wysłano dziś – nie ponawiamy
                            continue
                        
                        # Parse notification time (HH:MM)
                        try:
                            hour, minute = map(int, notification_time.split(":"))
                        except ValueError:
                            logger.error("Invalid time format for recipient %d: %s", recipient_id, notification_time)
                            continue
                        
                        # Sprawdź czy to odpowiedni czas (±1 minuta)
                        if now.hour == hour and abs(now.minute - minute) <= 1:
                            mode_label = "ALL-CAT" if use_all_categories else "STANDARD"
                            logger.info(
                                "News notification triggered for recipient %d at %s (mode=%s)",
                                recipient_id,
                                now.strftime("%H:%M"),
                                mode_label,
                            )
                            
                            try:
                                # Generate summary from FAISS
                                faiss_service = FAISSService()
                                faiss_service.load_index()
                                
                                if use_all_categories:
                                    response = faiss_service.answer_query_all_categories(
                                        prompt,
                                        per_category_k=DEFAULT_PER_CATEGORY_K,
                                    )
                                else:
                                    response = faiss_service.answer_query(prompt, top_k=5)
                                today_str = today.strftime("%Y-%m-%d")  
                                
                                if response.get("success") and response.get("answer"):
                                    message = f"📰 News ({today_str}):\n\n{response['answer']}"
                                else:
                                    # Fallback
                                    from .webhooks import _list_scraped_files
                                    files = _list_scraped_files()
                                    categories = [f["category"] for f in files if f.get("category")][:5]
                                    message = f"📰 Dziś dostępne newsy:\n" + "\n".join(f"• {cat}" for cat in categories)
                                
                                # Send via Twilio
                                twilio_client: TwilioService = app.config["TWILIO_CLIENT"]
                                origin = twilio_client.settings.default_from
                                
                                if not origin:
                                    logger.error("No Twilio default_from configured")
                                    continue
                                
                                result = twilio_client.send_chunked_sms(
                                    from_=origin,
                                    to=phone,
                                    body=message,
                                )
                                
                                if result.get("success"):
                                    logger.info("✅ News notification sent to recipient %d (%s)", recipient_id, phone)

                                    # Update last_sent_at (idempotentne względem restartów)
                                    recipient["last_sent_at"] = now.isoformat() + "Z"
                                    cfg["recipients"] = recipients
                                    _save_news_config(cfg)
                                else:
                                    logger.error("Failed to send News notification to recipient %d: %s", recipient_id, result.get("error"))
                                    
                            except Exception as exc:
                                logger.exception("Error sending News notification to recipient %d: %s", recipient_id, exc)
                                
            except Exception as exc:
                logger.exception("News scheduler error: %s", exc)
    
    thread = threading.Thread(target=scheduler, daemon=True, name="NewsScheduler")
    thread.start()
    app.config["NEWS_SCHEDULER_STARTED"] = True
    app.logger.info("🗓️ News scheduler started (check every %ds)", check_interval_seconds)

# Developer Guide

Przewodnik dla osób rozwijających Twilio Chat App: gdzie dopinać zmiany, jak działa przepływ
żądania, jakie są granice modułów i jak testować funkcje ręcznie.

## Spis treści
- [Architektura i odpowiedzialności katalogów](#architektura-i-odpowiedzialności-katalogów)
- [Przepływ żądania: inbound → DB → worker → outbound](#przepływ-żądania-inbound--db--worker--outbound)
- [UI/Frontend: gdzie dodać nową funkcję](#uifrontend-gdzie-dodać-nową-funkcję)
- [Baza danych i migracje](#baza-danych-i-migracje)
- [Dodawanie nowych endpointów](#dodawanie-nowych-endpointów)
- [Dodawanie nowych workerów / schedulerów](#dodawanie-nowych-workerów--schedulerów)
- [Manualne testy (smoke)](#manualne-testy-smoke)

## Architektura i odpowiedzialności katalogów

- `app/` – logika aplikacji Flask, serwisy, integracje:
  - `webhooks.py` – REST API + webhooki Twilio.
  - `ui.py` – routing widoków HTML (dashboard, chat).
  - `twilio_client.py` – wysyłka SMS (Messaging Service / default_from) + `send_chunked_sms`.
  - `ai_service.py`, `chat_logic.py` – generowanie odpowiedzi AI i fallbackowy bot.
  - `auto_reply.py`, `reminder.py`, `news_scheduler.py`, `multi_sms.py` – workery w tle.
  - `faiss_service.py`, `scraper_service.py` – RAG/FAISS i scraping newsów.
  - `database.py` – SQLite + migracje `SCHEMA_VERSION`.
  - `message_utils.py` – wspólne utilsy SMS (limit znaków, dzielenie na części).
- `templates/`, `static/js/`, `static/css/` – UI (Jinja2 + Bootstrap 5 + JS bez bundlera).
- `data/` – baza SQLite (nie trafia do publicznych paczek release).
- `X1_data/` – indeks FAISS, snapshoty dokumentów, surowe scrapes (nie publikować).
- `deploy/releases/` – release notes (MD/HTML) i pełna dokumentacja HTML.
- `release/` – manifesty i instrukcja budowy czystej paczki (prepare_release_bundle).
- `scripts/` – narzędzia pomocnicze (demo send, PDF przez wkhtmltopdf, bundling release).

## Przepływ żądania: inbound → DB → worker → outbound

1. Twilio wywołuje webhook `/twilio/inbound` (lub `/twilio/status`).
2. `webhooks.py` waliduje sygnaturę (można wyłączyć w dev), normalizuje numery, zapisuje
   wiadomość w `messages` i – dla inbound – enqueuje auto-reply/AI.
3. Worker auto-reply/AI (`auto_reply.py`) pobiera z kolejki i decyduje, czy użyć AI, klasycznego
   auto-reply czy fallback bota. Odpowiedź jest wysyłana przez `TwilioService`.
4. Wysyłka korzysta z `send_message` lub, dla długich treści, z `send_chunked_sms` (limit 1500 znaków
   na część; kilka SID-ów na jedną logiczną odpowiedź).
5. Statusy dostarczenia trafiają do `/twilio/status` i aktualizują rekordy w `messages`.

## UI/Frontend: gdzie dodać nową funkcję

- Widoki: `templates/dashboard.html` (karty, formularze, modale), `templates/chat.html` (wątek 1:1).
- Logika JS: `static/js/dashboard.js` (fetch API, toasty, auto-refresh), `static/js/chat.js`.
- Styl: `static/css/app.css`.
- Dodając zakładkę lub akcję:
  - dołóż sekcję w HTML + hook w JS (fetch do nowego endpointu),
  - w API (`webhooks.py`) dodaj handler i zwróć JSON spójny z istniejącymi strukturami.

## Baza danych i migracje

- Migracje kontroluje `SCHEMA_VERSION` w `database.py`; przy starcie `_ensure_schema()` podnosi
  strukturę automatycznie.
- Dodając nowe tabele/kolumny: zwiększ `SCHEMA_VERSION`, dopisz blok migracji z `PRAGMA user_version`.
- Dostęp do DB przez helpery w `database.py` – unikaj „gołego” sqlite3 w innych modułach.

## Dodawanie nowych endpointów

- Dodaj trasę w `webhooks.py` (Blueprint `webhooks_bp`).
- Waliduj payload (np. numery E.164) i zwracaj spójny JSON (`success`, dane lub `error`).
- Jeśli endpoint ma uruchamiać dłuższy proces, rozważ worker/kolejkę zamiast blokowania requestu.
- Dodaj logi (info/debug) z kontekstem numerów/SID, bez sekretów.

## Dodawanie nowych workerów / schedulerów

- Wzorce: `auto_reply.py`, `reminder.py`, `news_scheduler.py`, `multi_sms.py`.
- Uruchomienie w `create_app()` (app/__init__.py) – dodaj start nowego wątku daemonic.
- Dbaj o bezpieczeństwo konfiguracji (np. czy jest nadawca Twilio) i logowanie błędów.
- Jeśli worker ma wysyłać SMS-y, użyj `TwilioService.send_message` lub `send_chunked_sms` dla długich treści.

## Manualne testy (smoke)

- Webhook Twilio: wyślij SMS na numer Twilio → sprawdź w dashboardzie zapis + status + auto-reply/AI.
- AI: `/api/ai/test` z poprawnym kluczem; w UI zobacz podgląd historii AI.
- News/RAG: `Scrape` w UI, `Test FAISS`, ręczne `Wyślij` do odbiorcy; dla długich streszczeń
  sprawdź, że wiadomość trafia w kilku częściach (brak błędu „exceeds 1600 chars”).
- Multi-SMS: utwórz batch w UI, obserwuj statusy odbiorców.
- Backup: `GET /api/news/faiss/export`, potem `import`, test FAISS po restore.

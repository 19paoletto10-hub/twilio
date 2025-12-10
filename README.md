# Twilio Chat App

Serwer czatu SMS oparty o Flask + Twilio z panelem www, webhookami i asynchronicznym auto‑reply. Obsługuje SQLite, uruchomienie lokalne i w Dockerze. UI korzysta z Bootstrap 5.

## Funkcje
- Auto‑reply (worker w tle, kolejka w pamięci, deduplikacja SID) z konfigurowalną treścią w UI/API.
- Webhooki Twilio: `/twilio/inbound`, `/twilio/status`.
- REST API: wysyłanie SMS/MMS, pobieranie/sync, redakcja, kasowanie.
- Panel www: dashboard, lista wiadomości, widok czatu dla numeru, zakładka konfiguracji auto‑reply.
- Modułowa architektura (`app/config.py`, `app/twilio_client.py`, `app/auto_reply.py`, `app/webhooks.py`, `app/database.py`, `app/chat_logic.py`).

## Szybki start (lokalnie)
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```
Aplikacja startuje na `http://0.0.0.0:3000`.

## Zmienne środowiskowe (.env)
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` – wymagane.
- `TWILIO_DEFAULT_FROM` – numer nadawcy w formacie E.164; wymagany do auto‑reply.
- `TWILIO_MESSAGING_SERVICE_SID` – opcjonalnie, gdy używasz Messaging Service.
- `CHAT_MODE` – `echo` (domyślnie) lub `keywords` (używane tylko, gdy auto‑reply w bazie jest wyłączone).
- `APP_ENV`, `APP_DEBUG`, `APP_HOST`, `APP_PORT` – parametry serwera.
- `DB_PATH` – ścieżka SQLite (domyślnie `data/app.db`).
- `PUBLIC_BASE_URL` – publiczny URL do webhooków (prod/ngrok).
- `TWILIO_VALIDATE_SIGNATURE` – `true` zalecane w prod; w dev możesz ustawić `false` by pominąć weryfikację podpisu.

## Auto‑reply (SMS)
- `/twilio/inbound` zapisuje wiadomość do `messages`, a gdy `auto_reply_config.enabled=1`, odkłada payload do kolejki; worker `app/auto_reply.py` wysyła odpowiedź z tekstem `auto_reply_config.message`.
- Wymagany nadawca: `TWILIO_DEFAULT_FROM` (przekazywany jako `from_`).
- Walidacja numeru: E.164 (`+` i 7–15 cyfr); inne są pomijane z logiem.
- Deduplikacja po SID (ostatnie 1000 w pamięci), pełne logowanie wysyłki/SID.
- Jeśli auto‑reply jest wyłączone, używany jest synchroniczny bot z `chat_logic.py` (`echo`/`keywords`).
- Synchronizacja z Twilio (`GET /api/messages/remote` lub okresowe `_maybe_sync_messages`) także kolejkuje auto‑reply dla najnowszej wiadomości inbound, jeśli funkcja jest włączona.

Konfiguracja:
- UI: zakładka „Auto-odpowiedź” w dashboardzie (przełącznik + treść, limit 640 znaków).
- API: `GET /api/auto-reply/config`, `POST /api/auto-reply/config` z polami `enabled`, `message`.

## Endpointy HTTP
- `POST /twilio/inbound` – webhook wiadomości przychodzących.
- `POST /twilio/status` – statusy dostarczenia.
- `POST /api/send-message` – wysyłanie SMS/MMS (`to`, `body`, opcjonalnie `content_sid`, `media_urls`, `messaging_service_sid`, `use_messaging_service`).
- `GET /api/messages` – lista z bazy (`limit`, `direction`).
- `GET /api/conversations`, `GET /api/conversations/<participant>` – rozmowy i wątki.
- `GET /api/messages/remote` – najnowsze wiadomości z Twilio (`to`, `from`, `date_sent*`, `limit`).
- `GET /api/messages/<sid>` – szczegóły z Twilio.
- `POST /api/messages/<sid>/redact` – wyczyszczenie treści.
- `DELETE /api/messages/<sid>` – kasowanie w Twilio i lokalnie.

Przykład wysyłki:
```bash
curl -X POST http://localhost:3000/api/send-message \
  -H "Content-Type: application/json" \
  -d '{"to":"+48123123123","body":"Test z API"}'
```

## Panel WWW
- Dashboard: statystyki, wysyłka ręczna, lista 50 ostatnich wiadomości z filtrami, auto‑refresh ~15 s.
- Widok czatu `/chat/<numer>`: pełen wątek, auto‑refresh, formularz odpowiedzi.
- Zakładka „Auto-odpowiedź”: włącz/wyłącz + treść, badge stanu, zapisywanie przez API.

## CLI
```bash
python manage.py send --to +48123123123 --body "Siema z CLI" --use-messaging-service
```

## Docker / docker-compose
Build lokalny:
```bash
docker build -t twilio-chat:latest .
docker run --rm -it -p 3000:3000 --env-file .env -v $(pwd)/data:/app/data twilio-chat:latest
```
Compose (prod przykład):
```bash
docker compose -f docker-compose.production.yml up --build
```
Zalecane: montuj `./data`, aby zachować bazę SQLite (`DB_PATH`).

## Twilio – webhooki
1. Incoming: `https://twoja-domena.pl/twilio/inbound` (lub ngrok).
2. Status callback: `https://twoja-domena.pl/twilio/status`.
3. Używaj tego samego numeru / Messaging Service co w `.env` (`TWILIO_DEFAULT_FROM` lub `TWILIO_MESSAGING_SERVICE_SID`).
4. Prod: `TWILIO_VALIDATE_SIGNATURE=true`; Dev: możesz ustawić `false` podczas testów tunelowanych.

## Debugowanie
- Brak auto‑reply? Sprawdź logi: "Inbound webhook hit…", "Enqueue auto-reply payload…", "Auto-reply: sending…".
- Upewnij się, że `TWILIO_DEFAULT_FROM` jest ustawione.
- 403 na webhooku: tymczasowo `TWILIO_VALIDATE_SIGNATURE=false` (tylko dev).
- Numery muszą być w E.164, inaczej są pomijane.

## Rozbudowa
- Dodaj własny silnik w `chat_logic.py` i zaktualizuj `build_chat_engine()`.
- Rozszerz API/blueprinty według potrzeb.
- Dodaj dodatkowe kanały (np. WhatsApp) i walidację numerów.

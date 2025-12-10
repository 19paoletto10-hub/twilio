# Twilio Chat App

Serwer czatu SMS oparty o Flask + Twilio z panelem www, webhookami i asynchronicznym auto‑reply. Obsługuje SQLite, uruchomienie lokalne i w Dockerze. UI korzysta z Bootstrap 5.

## Funkcje
- Auto‑reply (worker w tle, kolejka w pamięci, deduplikacja SID) z konfigurowalną treścią w UI/API.
- Tryb AI auto‑reply – gdy AI jest włączone, wszystkie przychodzące SMS-y dostają odpowiedź wygenerowaną przez OpenAI (z wykorzystaniem historii rozmowy), a klasyczny auto‑reply jest automatycznie wyłączony.
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
- `OPENAI_API_KEY` – klucz używany do odpowiedzi AI; ustaw go, aby nie wpisywać go ręcznie w panelu.
- `OPENAI_MODEL`, `OPENAI_TEMPERATURE` – domyślny model i temperatura (np. `gpt-4o-mini`, `0.7`).
- `AI_TARGET_NUMBER`, `AI_SYSTEM_PROMPT`, `AI_ENABLED` – pozwalają włączyć AI i przypisać numer rozmówcy już przy starcie. Po zapisaniu ustawień w panelu wartością nadrzędną staje się konfiguracja z UI (env służy tylko do początkowego bootstrapu).
- `CHAT_MODE` – `echo` (domyślnie) lub `keywords` (używane tylko, gdy auto‑reply w bazie jest wyłączone).
- `APP_ENV`, `APP_DEBUG`, `APP_HOST`, `APP_PORT` – parametry serwera.
- `DB_PATH` – ścieżka SQLite (domyślnie `data/app.db`).
- `PUBLIC_BASE_URL` – publiczny URL do webhooków (prod/ngrok).
- `TWILIO_VALIDATE_SIGNATURE` – `true` zalecane w prod; w dev możesz ustawić `false` by pominąć weryfikację podpisu.

### Konfiguracja AI
- Przy starcie aplikacji wartości z `OPENAI_*` i `AI_*` automatycznie trafiają do tabeli `ai_config`, więc środowisko produkcyjne jest gotowe bez klikania w UI.
- Jeśli nie ustawisz zmiennych środowiskowych, konfigurację możesz nadal wprowadzić z panelu (zakładka „AI”).
- Aby przetestować lokalnie bez prawdziwych webhooków, ustaw `TWILIO_VALIDATE_SIGNATURE=false`, wprowadź numer testowy w `AI_TARGET_NUMBER`, a następnie wyślij wiadomość z tego numeru.
- Gdy `AI_ENABLED=true` (lub AI włączone z poziomu UI), system działa jak globalny auto‑reply oparty o OpenAI: każdy inbound SMS jest obsługiwany przez AI, a klasyczny auto‑reply z `auto_reply_config` zostaje wyłączony (oba tryby są wzajemnie wykluczające).

## Auto‑reply (SMS)
- `/twilio/inbound` zapisuje wiadomość do `messages`, a gdy `auto_reply_config.enabled=1`, odkłada payload do kolejki; worker `app/auto_reply.py` wysyła odpowiedź z tekstem `auto_reply_config.message`.
- Wymagany nadawca: `TWILIO_DEFAULT_FROM` (przekazywany jako `from_`).
- Walidacja numeru: E.164 (`+` i 7–15 cyfr); inne są pomijane z logiem.
- Deduplikacja po SID (ostatnie 1000 w pamięci), pełne logowanie wysyłki/SID.
- Jeśli auto‑reply jest wyłączone, używany jest synchroniczny bot z `chat_logic.py` (`echo`/`keywords`), o ile nie jest włączone AI.
- Auto‑reply i AI są rozłączne: jeżeli AI jest aktywne (AI config `enabled=true`), worker auto‑reply nie odpowiada na wiadomości – odpowiedzi generuje wyłącznie AI.
- Synchronizacja z Twilio (`GET /api/messages/remote` lub okresowe `_maybe_sync_messages`) także kolejkuje auto‑reply dla najnowszej wiadomości inbound, jeśli funkcja jest włączona.

Konfiguracja:
- UI: zakładka „Auto-odpowiedź” w dashboardzie (przełącznik + treść, limit 640 znaków).
- API: `GET /api/auto-reply/config`, `POST /api/auto-reply/config` z polami `enabled`, `message`.

## Endpointy HTTP
- `POST /twilio/inbound` – webhook wiadomości przychodzących.
- `POST /twilio/status` – statusy dostarczenia.
- `POST /api/send-message` – wysyłanie SMS/MMS (`to`, `body`, opcjonalnie `content_sid`, `media_urls`, `messaging_service_sid`, `use_messaging_service`).
- `POST /api/ai/test` – wykonuje zapytanie do OpenAI i zwraca odpowiedź bez wysyłania SMS.
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
- Zakładka „AI”: konfiguracja OpenAI oraz przycisk „Przetestuj połączenie”, który uderza w `POST /api/ai/test` i wyświetla odpowiedź lub błąd.

## CLI
```bash
python manage.py send --to +48123123123 --body "Siema z CLI" --use-messaging-service

# Wygeneruj wiadomość AI i wyślij ją Twilio
python manage.py ai-send --to +48123123123 --latest "Treść ostatniej wiadomości" --history-limit 30
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

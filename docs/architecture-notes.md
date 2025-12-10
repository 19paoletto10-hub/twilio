# Twilio Chat App – notatki architektoniczne

## Przegląd systemu

- **Framework**: Flask 3.x, aplikacja tworzona przez `app.create_app()`.
- **Warstwa HTTP**: blueprint `webhooks_bp` (`app/webhooks.py`) oraz `ui_bp` (`app/ui.py`).
- **Integracje**:
  - Twilio (SMS/MMS, webhooki inbound/status, sync wiadomości).
  - OpenAI (Chat Completions dla odpowiedzi AI).
- **Persistence**: SQLite z wersjonowanym schematem (`app/database.py`).
- **Background workery**:
  - `auto_reply` – reactive auto-reply/AI auto-reply z kolejki w pamięci.
  - `reminder` – cykliczne przypomnienia z tabeli `scheduled_messages`.

## Tworzenie aplikacji (`app/__init__.py`)

- Funkcja `create_app()`:
  - wczytuje konfigurację z env przez `get_settings()` (`app/config.py`),
  - tworzy klienta Twilio (`TwilioService`) i zapisuje w `app.config["TWILIO_CLIENT"]`,
  - inicjalizuje bazę (`init_database`) i konfig AI z env (`apply_ai_env_defaults`),
  - rejestruje blueprinty HTTP (`webhooks_bp`, `ui_bp`),
  - uruchamia dwa workery w tle: `start_auto_reply_worker`, `start_reminder_worker`,
  - wystawia endpoint healthcheck `GET /api/health`.

## Konfiguracja (`app/config.py`)

- `TwilioSettings` (SID, token, `default_from`, opcjonalny `messaging_service_sid`).
- `AppSettings` (env, debug, host, port, `db_path`).
- `get_settings()`:
  - wymaga `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
  - rozwiązuje `DB_PATH` względnie do katalogu projektu,
  - pozwala na uruchomienie dev (Flask dev server przez `run.py`) i prod (gunicorn z Dockerfile).

## Baza danych i model danych (`app/database.py`)

- Jedna baza SQLite, ścieżka z `APP_SETTINGS.db_path` (domyślnie `data/app.db`).
- Główne tabele:
  - `messages` – wszystkie wiadomości (inbound/outbound) z SID, numerami, statusem, błędami, timestampami.
  - `auto_reply_config` – przełącznik i treść klasycznego auto-reply, pole `enabled_since` (ISO) do filtrowania historycznych wiadomości.
  - `scheduled_messages` – scheduler przypomnień (to_number, body, interval_seconds, enabled, last_sent_at/next_run_at).
  - `ai_config` – konfiguracja AI: `enabled`, `api_key`, `system_prompt`, `target_number`, `target_number_normalized`, `model`, `temperature`, `enabled_source`, `updated_at`.
- Mechanizmy pomocnicze:
  - `normalize_contact()` – normalizacja numerów (usuwanie prefiksów `whatsapp:`, spacji, konwersja `00` → `+`).
  - `_ensure_schema()` + migracje `SCHEMA_VERSION` – automatyczne podnoszenie schematu.
  - `upsert_message()` – bezpieczna aktualizacja/dodawanie wiadomości z Twilio bez duplikatów po SID.
  - `list_messages()`, `list_conversations()` – widoki do UI/API.
  - `get_auto_reply_config()` / `set_auto_reply_config()`.
  - `get_ai_config()` / `set_ai_config()` – single-row config AI (id=1).
  - `apply_ai_env_defaults()` – bootstrap ai_config z env (`OPENAI_*`, `AI_*`) z rozróżnieniem źródła (`enabled_source = env/ui`).

## Klient Twilio (`app/twilio_client.py`)

- Klasa `TwilioService` opakowuje `twilio.rest.Client`.
- Główne metody:
  - `send_message(to, body, use_messaging_service, messaging_service_sid, extra_params)` – uniwersalna wysyłka z obsługą Messaging Service lub klasycznego `from_`.
  - `send_reply_to_inbound(inbound_from, inbound_to, body)` – wysyła SMS jako odpowiedź na inbound (zachowuje wątek po stronie Twilio, preferuje Messaging Service; inaczej używa numeru `inbound_to` lub `default_from`).
  - `send_with_default_origin(to, body)` – prosta wysyłka z `TWILIO_DEFAULT_FROM`.
  - `list_messages`, `fetch_message`, `redact_message`, `delete_message`.

## AI i generowanie odpowiedzi (`app/ai_service.py`)

- `AIResponder`:
  - buduje kontekst rozmowy na podstawie `messages` (filtrowanie po znormalizowanym numerze uczestnika),
  - tworzy listę `messages` dla OpenAI Chat Completions (role: `system`/`user`/`assistant`),
  - wywołuje OpenAI przez klienta `OpenAI(api_key=...)`.
- `send_ai_generated_sms()`:
  - normalizuje numer uczestnika,
  - generuje odpowiedź z `AIResponder` (lub używa `reply_text_override`),
  - wysyła SMS przez `TwilioService`:
    - jeśli znany jest numer, na który przyszła wiadomość (`origin_number`), używa `send_reply_to_inbound`;
    - w przeciwnym razie używa `send_message`.
  - zwraca `AIMessageDispatchResult` (tekst odpowiedzi, numer, SID, status, numer nadawcy).

## Auto-reply / AI worker (`app/auto_reply.py`)

- `start_auto_reply_worker(app)`:
  - tworzy w tle daemon thread, który konsumuje kolejkę `AUTO_REPLY_QUEUE` (dostarczaną przez `/twilio/inbound` i sync z Twilio),
  - dla każdej wiadomości inbound:
    - odczytuje `auto_reply_config` i `ai_config`,
    - filtruje po czasie:
      - klasyczny auto-reply: `received_at` musi być ≥ `auto_reply_config.enabled_since`,
      - AI: `received_at` musi być ≥ `ai_config.updated_at` (AI nie odpowiada na stare wiadomości sprzed włączenia/zmiany konfiguracji),
    - sprawdza numer nadawcy względem `ALLOWED_NUMBER_RE` (E.164) – dotyczy klasycznego auto-reply,
    - deduplikuje po SID (ostatnie 1000 wiadomości).
  - Jeśli AI jest włączone:
    - tworzy `AIResponder` na podstawie `ai_config`,
    - wywołuje `send_ai_generated_sms()` z `origin_number` ustawionym na numer Twilio, który przyjął wiadomość,
    - zapisuje outbound do `messages` ze statusem `ai-auto-reply` lub faktycznym statusem Twilio.
  - Jeśli AI jest wyłączone, a auto-reply włączone:
    - używa szablonu `auto_reply_config.message`,
    - wysyła przez `send_message` z wymuszonym `from_ = TWILIO_DEFAULT_FROM`,
    - zapisuje outbound do `messages`.
- `enqueue_auto_reply(app, ...)` jest wołane z webhooków/sync, aby włożyć payload do kolejki.

## Webhooki i API (`app/webhooks.py`)

- `webhooks_bp` zawiera:
  - `/twilio/inbound` – odbiór SMS z Twilio, walidacja podpisu, zapis do `messages`, enqueuing auto-reply/AI, fallback do prostego chat-bota gdy oba tryby są wyłączone.
  - `/twilio/status` – aktualizacja statusów wiadomości po SID.
  - API do zarządzania konfiguracją:
    - `/api/auto-reply/config` (GET/POST) – klasyczny auto-reply,
    - `/api/ai/config` (GET/POST) – konfiguracja AI (enabled, klucz, prompt, model, temperatura, target number).
  - API do AI:
    - `/api/ai/test` – testowe zapytanie do OpenAI (bez wysyłania SMS),
    - `/api/ai/send` / `/api/ai/reply` – wywołanie AI i wysyłka SMS na numer target.
  - API wiadomości i rozmów:
    - `/api/messages`, `/api/messages/<sid>`, `/api/messages/remote`, `/api/messages/<sid>/redact`, `/api/messages/<sid>` (DELETE),
    - `/api/conversations`, `/api/conversations/<participant>`.
  - API przypomnień (`/api/reminders` itd.).
- `_validate_twilio_signature()` pozwala wyłączyć weryfikację w dev przez `TWILIO_VALIDATE_SIGNATURE=false`.
- `_maybe_sync_messages()` i `api_remote_messages()` potrafią dociągnąć najnowsze wiadomości z Twilio i opcjonalnie zakolejkować auto-reply/AI tylko dla najnowszego inbound.
- `_maybe_enqueue_auto_reply_for_message()` decyduje, czy włączyć AI/auto-reply dla zdalnie zsynchronizowanej wiadomości, uwzględniając:
  - aktywność AI/auto-reply,
  - kierunek `inbound`,
  - obecność klucza API,
  - czas odbioru vs `enabled_since` (auto-reply) lub `updated_at` (AI).

## UI (`app/ui.py`, szablony)

- `dashboard` (`/`) – widok główny z informacjami o środowisku, listą wiadomości, kontrolą auto-reply/AI.
- `chat_view` (`/chat/<numer>`) – wątek rozmowy dla danego uczestnika, integruje się z endpointami `/api/conversations` i `/api/messages`.

## Chat-bot fallback (`app/chat_logic.py`)

- Prosty silnik:
  - tryb `echo` – odbicie treści z prefiksem,
  - tryb `keywords` – proste komendy (HELP/START/STOP).
- Używany, gdy **zarówno AI, jak i auto-reply są wyłączone**.

## Przypomnienia (`app/reminder.py`)

- Worker `start_reminder_worker`:
  - cyklicznie pobiera `list_due_scheduled_messages()`,
  - filtruje po poprawnym numerze, treści i dostępności `TWILIO_DEFAULT_FROM`,
  - wysyła SMS przez `send_message` z explicit `from_`,
  - zapisuje wiadomość do `messages` i aktualizuje `last_sent_at`/`next_run_at`.

## Zarządzanie AI i auto-reply – zasady biznesowe

- Tryby są rozłączne:
  - jeśli AI jest włączone (`ai_config.enabled=true`), klasyczny auto-reply jest deaktywowany (także przez `apply_ai_env_defaults`),
  - worker reaguje w pierwszej kolejności trybem AI, a klasyczny auto-reply jest pomijany.
- AI i auto-reply nigdy nie odpowiadają na wiadomości sprzed momentu włączenia danego trybu:
  - auto-reply: filtr po `auto_reply_config.enabled_since`.
  - AI: filtr po `ai_config.updated_at`.

## Uruchamianie i deployment

- Lokalne dev:
  - `python run.py` – Flask dev server, worker auto-reply i reminder startują automatycznie.
- Produkcja (Docker):
  - Obraz bazowy `python:3.12-slim`, gunicorn jako WSGI (`run:app`, 2 workery, 4 wątki), healthcheck na `/api/health`.
  - Wymagane zmienne `TWILIO_*`, zalecane `OPENAI_*`, `AI_*`, `PUBLIC_BASE_URL` (do webhooków).


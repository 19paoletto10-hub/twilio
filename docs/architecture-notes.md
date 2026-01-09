# Twilio Chat App v3.2.9 – Notatki architektoniczne

> 🏷️ **Wersja**: 3.2.9 (2025-01-09) • **SCHEMA_VERSION**: 9 • **Type Safety**: 0 Pylance errors

## Przegląd systemu

- **Framework**: Flask 3.x, aplikacja tworzona przez `app.create_app()`.
- **Warstwa HTTP**: blueprint `webhooks_bp` (`app/webhooks.py`) oraz `ui_bp` (`app/ui.py`).
- **Code Quality**: Enterprise-grade type safety, professional docstrings, defensive programming.
- **Design Patterns (v3.2.9)**: Railway-Oriented Programming, Circuit Breaker, Command Pattern, Strategy Pattern, Dependency Injection.
- **Performance Monitoring (v3.2.9)**: @timed decorator, MetricsCollector, RateLimiter, Lazy initialization.
- **Integracje**:
  - Twilio (SMS/MMS, webhooki inbound/status, sync wiadomości).
  - OpenAI (Chat Completions dla odpowiedzi AI).
- **Persistence**: SQLite z wersjonowanym schematem (`app/database.py`, SCHEMA_VERSION=9).
- **Background workery**:
  - `auto_reply` – reactive auto-reply/AI auto-reply z kolejki w pamięci.
  - `reminder` – cykliczne przypomnienia z tabeli `scheduled_messages`.

## Nowe moduły architektury (v3.2.9)

### patterns.py – Railway-Oriented Programming

Moduł implementujący zaawansowane wzorce projektowe na poziomie enterprise:

#### Result Type – Success[T] / Failure[E]
- **Zastępuje wyjątki** eksplicytnym typem wyniku operacji
- **Type safety** – kompilator wymusza obsługę obu przypadków
- **Kompozycja** – metody `map()`, `flat_map()` dla chainowania operacji
- **Railway metaphor** – "happy path" i "error path" jako osobne tory

```python
from app.patterns import Success, Failure, result_from_exception

@result_from_exception
def risky_operation() -> Result[str, Exception]:
    return external_api.call()

result = risky_operation()
if result.is_success():
    data = result.unwrap()
else:
    logger.error(result.error)
```

#### Retry Pattern z Exponential Backoff
- **Strategie**: EXPONENTIAL, LINEAR, CONSTANT
- **Jitter** – randomizacja dla uniknięcia thundering herd
- **Max attempts** – konfigurowalna liczba prób
- **Backoff multiplier** – wykładniczy wzrost opóźnienia

```python
from app.patterns import retry, RetryConfig, RetryStrategy

@retry(RetryConfig(
    max_attempts=3,
    strategy=RetryStrategy.EXPONENTIAL,
    base_delay_seconds=1.0,
    max_delay_seconds=10.0,
    jitter=True
))
def call_external_api():
    return requests.get(url, timeout=5)
```

#### Circuit Breaker Pattern
- **Ochrona przed kaskadowymi awariami** zewnętrznych serwisów
- **Stany**: CLOSED (normalny), OPEN (zablokowany), HALF_OPEN (test recovery)
- **Threshold** – liczba błędów do otwarcia obwodu
- **Timeout** – czas przed próbą recovery
- **Thread-safe** – globalny registry dla nazwanych circuit breakerów

```python
from app.patterns import circuit_breaker

@circuit_breaker("twilio_api", failure_threshold=5, timeout_seconds=60)
def send_sms(to: str, body: str):
    return twilio_client.messages.create(to=to, body=body)
```

#### TTL Cache
- **Thread-safe caching** z automatyczną ewolucją
- **Time-to-Live** – configurable expiration time
- **Cleanup** – automatic removal of expired entries
- **Size limits** – optional max_size with LRU eviction

```python
from app.patterns import ttl_cache

@ttl_cache(ttl_seconds=3600, max_size=1000)
def expensive_computation(key: str) -> dict:
    return perform_heavy_operation(key)
```

#### Processor Chain (Chain of Responsibility)
- **Kompozycja handlerów** – każdy procesor może przekazać dalej lub przerwać
- **Immutable messages** – procesory nie modyfikują oryginalnej wiadomości
- **Type safety** – generics dla różnych typów wiadomości i kontekstów

### message_handler.py – Clean Architecture

Moduł implementujący czyste wzorce architektury dla obsługi wiadomości:

#### Command Pattern
- **Każdy handler jako samodzielna komenda** z metodą `execute()`
- **Separation of Concerns** – logika biznesowa oddzielona od infrastruktury
- **Testability** – łatwe mockowanie zależności
- **Single Responsibility** – jeden handler = jedna odpowiedzialność

```python
from app.message_handler import MessageHandler, InboundMessage

class AIReplyHandler(MessageHandler):
    def can_handle(self, message: InboundMessage) -> bool:
        return self.ai_config.enabled
    
    def execute(self, message: InboundMessage) -> ReplyResult:
        response = self.ai_service.generate_reply(message)
        return self.send_reply(message, response)
```

#### Strategy Pattern
- **Różne strategie odpowiedzi**: AI, Template, Listener, Fallback Bot
- **Runtime selection** – wybór strategii w czasie wykonania na podstawie konfiguracji
- **Composable** – strategie można łączyć w chain

#### Value Objects
- **PhoneNumber** – immutable, walidacja E.164 w konstruktorze
- **InboundMessage** – frozen dataclass z all validation at creation
- **ReplyResult** – typ wyniku z statusem (SENT, FAILED, SKIPPED, DUPLICATE)

```python
from app.message_handler import PhoneNumber, InboundMessage, ReplyResult, ReplyStatus

phone = PhoneNumber("+48732070140")  # Validates E.164
message = InboundMessage(
    sid="SM123",
    from_number=phone,
    to_number=PhoneNumber("+48123456789"),
    body="Hello",
    received_at=datetime.now(timezone.utc)
)
```

#### Composable Validators
- **Builder pattern** dla walidacji
- **Fluent API** – chainowanie reguł walidacji
- **Explicit errors** – czytelne komunikaty błędów
- **ValidationResult Type** – Success[T] / Failure

#### Dependency Injection
- **Constructor injection** – wszystkie zależności przez konstruktor
- **Interface segregation** – handlers zależą od abstrakcji (Protocol)
- **Testability** – łatwe podstawianie mocków w testach

### performance.py – Monitoring & Profiling

Moduł narzędzi do monitoringu wydajności i profilowania:

#### @timed Decorator
- **Automatyczne mierzenie** czasu wykonania funkcji
- **Threshold alerts** – logowanie gdy execution time > threshold
- **Context preservation** – zachowuje docstringi i type hints
- **Nested calls** – działa poprawnie z zagnieżdżonymi wywołaniami

```python
from app.performance import timed

@timed(threshold_ms=100)
def slow_database_query(user_id: int) -> dict:
    """Fetch user data from database."""
    return db.query(f"SELECT * FROM users WHERE id = {user_id}")

# Automatyczne logowanie jeśli > 100ms
```

#### MetricsCollector
- **Thread-safe** zbieranie metryk wykonania
- **Bounded buffer** – automatyczne usuwanie najstarszych metryk (max 10k)
- **Aggregation** – statystyki: count, avg, min, max, p50, p95, p99
- **Per-function metrics** – osobne statystyki dla każdej funkcji

```python
from app.performance import MetricsCollector

collector = MetricsCollector(max_size=10000)
# @timed automatically records to global collector

stats = collector.get_stats("slow_database_query")
# → {"count": 150, "avg_ms": 45.2, "p95_ms": 120.5, ...}
```

#### RateLimiter (Token Bucket)
- **Token bucket algorithm** dla throttlingu API calls
- **Thread-safe** – wielowątkowe zapytania obsługiwane poprawnie
- **Configurable rate** – tokens per second, burst size
- **Blocking/non-blocking** – `acquire()` i `try_acquire()`

```python
from app.performance import RateLimiter

limiter = RateLimiter(rate=10, capacity=20)  # 10 req/s, burst 20

@limiter.throttle
def call_external_api():
    return requests.get(api_url)
```

#### Lazy[T] – Lazy Initialization
- **Thread-safe** – pierwszy call inicjalizuje, reszta czeka
- **Expensive resources** – OpenAI client, DB connections, etc.
- **Exception handling** – błąd przy inicjalizacji propagowany przy każdym get()

```python
from app.performance import Lazy

expensive_client = Lazy(lambda: OpenAI(api_key=settings.key))
# Client created only on first .get() call
result = expensive_client.get().chat.completions.create(...)
```

#### timed_block Context Manager
- **Bloki kodu** zamiast całych funkcji
- **Local timing** – bez globalne metrics collector
- **Explicit naming** – nazwa bloku w logach

```python
from app.performance import timed_block

with timed_block("database_transaction"):
    db.execute("BEGIN")
    # ... complex operations ...
    db.execute("COMMIT")
```

## Zoptymalizowane moduły (v3.2.9)

### database.py – Database Optimizations

#### WAL Mode (Write-Ahead Logging)
- **Lepsze współbieżne odczyty/zapisy** – czytelnicy nie blokują pisarzy
- **Durability** – dane najpierw w WAL, potem w głównej bazie
- **Performance** – do 50% szybsze zapisy w niektórych workloadach
- **Automatically enabled** – ustawione przy `init_database()`

```python
# Automatycznie w init_database()
conn.execute("PRAGMA journal_mode = WAL")
```

#### Query Cache
- **In-memory cache** dla często używanych zapytań
- **TTL-based expiration** – domyślnie 60s
- **Thread-safe** – RLock dla wielowątkowego dostępu
- **Cache invalidation** – automatyczne czyszczenie po INSERT/UPDATE/DELETE

```python
# Wewnętrznie używane w helper functions
cached_result = _query_cache.get(cache_key)
if cached_result is None:
    cached_result = conn.execute(sql, params).fetchall()
    _query_cache.set(cache_key, cached_result)
```

#### Transaction Context Manager
- **Automatyczne commit/rollback** – try/except/finally wrapped
- **Nested transactions** – obsługa SAVEPOINT dla zagnieżdżonych transakcji
- **Error logging** – szczegółowe logi przy rollback

```python
from app.database import transaction

with transaction() as conn:
    conn.execute("INSERT INTO messages (...) VALUES (...)")
    conn.execute("UPDATE ai_config SET ...")
    # Automatic commit on success, rollback on exception
```

#### @db_operation Decorator
- **Standardized error handling** – wszystkie DB errors logowane
- **Retry logic** – automatyczne retry dla SQLITE_BUSY
- **Metrics** – integracja z MetricsCollector dla query timing
- **Connection management** – ensures proper connection lifecycle

```python
from app.database import db_operation

@db_operation(retry_on_busy=True, max_retries=3)
def insert_message(...) -> int:
    conn = _get_connection()
    cursor = conn.execute("INSERT INTO messages ...")
    return cursor.lastrowid
```

### faiss_service.py – FAISS Optimizations

#### Embedding Cache (LRU + TTL)
- **LRU eviction** – Least Recently Used gdy cache pełny
- **TTL expiration** – domyślnie 1h dla embeddings
- **Hit rate tracking** – monitoring skuteczności cache
- **Thread-safe** – RLock dla wielowątkowego dostępu

```python
# Wewnętrznie w FAISSService
cached_embedding = self._embedding_cache.get(text)
if cached_embedding is None:
    cached_embedding = self._openai_client.embeddings.create(...)
    self._embedding_cache.set(text, cached_embedding)
```

#### Batched Embeddings
- **Partial cache lookup** – sprawdza cache przed API call
- **Batch API calls** – wysyła do OpenAI tylko brakujące embeddingi
- **Cost optimization** – redukuje liczbę wywołań API
- **Automatic cache population** – nowe embeddingi zapisywane w cache

```python
# Batch processing with cache
texts = ["text1", "text2", "text3"]
embeddings = faiss_service.get_embeddings_batch(texts)
# Only uncached texts sent to OpenAI API
```

#### Cache Stats
- **Hit/miss tracking** – monitoring skuteczności cache
- **Size monitoring** – liczba elementów w cache
- **Eviction tracking** – ile elementów usunięto (LRU/TTL)
- **API call reduction** – metrics pokazujące savings

```python
stats = faiss_service.get_cache_stats()
# → {"size": 450, "hits": 1250, "misses": 180, "hit_rate": 0.874}
```

### validators.py – Validation Improvements

#### ValidationResult Type
- **Type-safe validation** – Success[T] / Failure zamiast wyjątków
- **Composable** – łączenie walidatorów przez `and_then()`, `or_else()`
- **Error accumulation** – zbieranie wielu błędów zamiast fail-fast
- **Immutable results** – frozen dataclasses

```python
from app.validators import ValidationSuccess, ValidationFailure

result = validate_phone("+48123456789")
if result.is_valid():
    phone = result.get_value()
else:
    error = result.get_error()
```

#### Composable Validator (Fluent API)
- **Builder pattern** – chainowanie reguł walidacji
- **Explicit errors** – każda reguła ma własny komunikat błędu
- **Short-circuit** – pierwszy błąd przerywa chain
- **Reusable rules** – te same reguły dla różnych inputów

```python
from app.validators import Validator, E164_PATTERN

result = (Validator(phone_input, "phone")
    .strip()
    .not_empty()
    .matches(E164_PATTERN, "Invalid E.164 format")
    .validate())

if not result.is_valid():
    return {"error": result.get_error()}, 400
```

#### validate_json_payload
- **Schema validation** – sprawdza strukturę JSON payload
- **Required fields** – wymusza obecność kluczowych pól
- **Type checking** – validates field types
- **Nested validation** – obsługa zagnieżdżonych obiektów

```python
from app.validators import validate_json_payload

schema = {
    "to": {"type": "string", "required": True},
    "body": {"type": "string", "required": True},
    "priority": {"type": "int", "required": False}
}

result = validate_json_payload(request.get_json(), schema)
```

#### Batch Validation z skip_invalid
- **Bulk processing** – walidacja wielu wartości jednocześnie
- **Error collection** – zbiera wszystkie błędy zamiast fail-fast
- **Partial success** – `skip_invalid=True` pozwala kontynuować z valid items
- **Detailed errors** – per-item error messages

```python
from app.validators import validate_phone_numbers

numbers = ["+48123", "+48732070140", "invalid"]
result = validate_phone_numbers(numbers, skip_invalid=True)
# → {"valid": ["+48732070140"], "invalid": ["+48123", "invalid"]}
```

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
  - `send_chunked_sms(to, body, from_, max_length)` – wysyła dłuższy tekst jako kilka SMS-ów (limit bezpieczeństwa: 1500 znaków na część), aby uniknąć błędów Twilio dla zbyt długiej treści.
  - `send_reply_to_inbound(inbound_from, inbound_to, body)` – wysyła SMS jako odpowiedź na inbound (zachowuje wątek po stronie Twilio, preferuje Messaging Service; inaczej używa numeru `inbound_to` lub `default_from`).
  - `send_with_default_origin(to, body)` – prosta wysyłka z `TWILIO_DEFAULT_FROM`.
  - `list_messages`, `fetch_message`, `redact_message`, `delete_message`.

### Limity SMS i dzielenie treści

- Twilio odrzuca pojedyncze SMS-y przekraczające limit rozmiaru (w praktyce błąd pojawia się przy sklejonej treści około 1600 znaków).
- Aplikacja stosuje limit bezpieczeństwa 1500 znaków na część (`MAX_SMS_CHARS`) w [app/message_utils.py](app/message_utils.py).
- Dzielenie próbuje ciąć po granicach akapitów i zdań (`\n\n`, `\n`, `. `, `! `, `? `), a gdy to niemożliwe — wykonuje twarde cięcie.
- Funkcjonalność jest używana przez wysyłkę News/RAG i odpowiedzi AI, dzięki czemu backend nie musi ucinać treści.

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


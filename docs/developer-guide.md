# Developer Guide – v3.2.9

> 🏷️ **Wersja**: 3.2.9 (2025-01-09) • **SCHEMA_VERSION**: 9 • **Chunked SMS**: ✅ • **FAISS All-Categories**: ✅ • **Design Patterns**: ✅

Przewodnik dla osób rozwijających Twilio Chat App: gdzie dopinać zmiany, jak działa przepływ
żądania, jakie są granice modułów i jak testować funkcje ręcznie.

## Spis treści
- [Architektura i odpowiedzialności katalogów](#architektura-i-odpowiedzialności-katalogów)
- [Przepływ żądania: inbound → DB → worker → outbound](#przepływ-żądania-inbound--db--worker--outbound)
- [Design Patterns (v3.2.9)](#design-patterns-v329)
- [Performance Monitoring (v3.2.9)](#performance-monitoring-v329)
- [Validation (v3.2.9)](#validation-v329)
- [UI/Frontend: gdzie dodać nową funkcję](#uifrontend-gdzie-dodać-nową-funkcję)
- [Baza danych i migracje](#baza-danych-i-migracje)
- [Dodawanie nowych endpointów](#dodawanie-nowych-endpointów)
- [Dodawanie nowych workerów / schedulerów](#dodawanie-nowych-workerów--schedulerów)
- [Manualne testy (smoke)](#manualne-testy-smoke)
- [Środowiska: dev vs prod](#środowiska-dev-vs-prod)
- [Logi, monitoring i typowe błędy](#logi-monitoring-i-typowe-błędy)
- [Release i bundling](#release-i-bundling)

## Architektura i odpowiedzialności katalogów

- `app/` – logika aplikacji Flask, serwisy, integracje:
  - `webhooks.py` – REST API + webhooki Twilio.
  - `ui.py` – routing widoków HTML (dashboard, chat).
  - **Nowe w v3.2.9**:
    - `patterns.py` – Railway-Oriented Programming (Result Type, Retry, Circuit Breaker, TTL Cache, Processor Chain).
    - `message_handler.py` – Clean Architecture (Command Pattern, Strategy Pattern, Value Objects, Dependency Injection).
    - `performance.py` – Monitoring & Profiling (@timed, MetricsCollector, RateLimiter, Lazy, timed_block).
  - **Zoptymalizowane w v3.2.9**:
    - `database.py` – WAL Mode, Query Cache, Transaction Context Manager, @db_operation decorator.
    - `faiss_service.py` – Embedding Cache (LRU + TTL), Batched Embeddings, Cache Stats.
    - `validators.py` – ValidationResult Type, Composable Validator (fluent API), validate_json_payload, batch validation.
  - `twilio_client.py` – wysyłka SMS (Messaging Service / default_from) + `send_chunked_sms`.
  - `ai_service.py`, `chat_logic.py` – generowanie odpowiedzi AI i fallbackowy bot.
  - `auto_reply.py`, `reminder.py`, `news_scheduler.py`, `multi_sms.py` – workery w tle.
  - `faiss_service.py`, `scraper_service.py` – RAG/FAISS i scraping newsów.
  - `message_utils.py` – wspólne utilsy SMS (limit znaków `MAX_SMS_CHARS=1500`, dzielenie na części).
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
4. Wysyłka korzysta z `send_message` lub, dla długich treści (>1500 znaków), z `send_chunked_sms`
   (limit 1500 znaków na część; kilka SID-ów na jedną logiczną odpowiedź).
5. Statusy dostarczenia trafiają do `/twilio/status` i aktualizują rekordy w `messages`.

## Design Patterns (v3.2.9)

Wersja 3.2.9 wprowadza zaawansowane wzorce projektowe na poziomie enterprise. Oto jak z nich korzystać:

### Result Type - Railway-Oriented Programming

Zamiast wyjątków używamy explicytnego typu `Result[T, E]` dla operacji, które mogą się nie powieść:

```python
from app.patterns import Success, Failure, Result, result_from_exception

# Automatyczna konwersja wyjątków na Result
@result_from_exception
def risky_operation() -> Result[dict, Exception]:
    response = requests.get("https://api.example.com/data", timeout=5)
    response.raise_for_status()
    return response.json()

# Obsługa wyniku
result = risky_operation()
if result.is_success():
    data = result.unwrap()
    logger.info(f"Received data: {data}")
else:
    logger.error(f"API call failed: {result.error}")
    # Graceful degradation - użyj cache lub fallback
    data = get_cached_data()

# Chainowanie operacji (Railway metaphor)
result = (risky_operation()
    .map(lambda data: data["items"])
    .map(lambda items: [item for item in items if item["active"]])
    .unwrap_or([]))  # Domyślna wartość jeśli failed
```

**Kiedy używać:**
- Operacje z external services (Twilio, OpenAI, scraping)
- File I/O, które może się nie powieść
- Walidacja danych z niepewnych źródeł
- Wszędzie, gdzie "błąd nie jest wyjątkiem" (expected failure)

### Retry with Exponential Backoff

Automatyczne ponawianie operacji z inteligentnym opóźnieniem:

```python
from app.patterns import retry, RetryConfig, RetryStrategy

# Podstawowe użycie - domyślne wartości
@retry()
def send_notification():
    return twilio_client.messages.create(...)

# Zaawansowana konfiguracja
@retry(RetryConfig(
    max_attempts=5,                    # Maksymalnie 5 prób
    strategy=RetryStrategy.EXPONENTIAL, # 1s, 2s, 4s, 8s, 16s
    base_delay_seconds=1.0,
    max_delay_seconds=30.0,            # Cap na 30s
    jitter=True,                       # Randomizacja ±10%
    retry_on=(requests.Timeout, requests.ConnectionError)
))
def call_external_api():
    response = requests.get(api_url, timeout=5)
    response.raise_for_status()
    return response.json()

# Retry z custom logic
@retry(RetryConfig(
    max_attempts=3,
    should_retry=lambda exc: isinstance(exc, RateLimitError) and exc.retry_after < 60
))
def rate_limited_operation():
    return api.call()
```

**Best practices:**
- Używaj `jitter=True` dla uniknięcia thundering herd
- Ustaw `max_delay_seconds` aby zapobiec zbyt długiemu czekaniu
- Definiuj `retry_on` tylko dla transient errors (timeout, network)
- NIE retry'uj błędów walidacji lub authentication errors

### Circuit Breaker

Ochrona przed kaskadowymi awariami zewnętrznych serwisów:

```python
from app.patterns import circuit_breaker, CircuitState

# Podstawowe użycie
@circuit_breaker("twilio_api")
def send_sms(to: str, body: str):
    return twilio_client.messages.create(to=to, body=body)

# Zaawansowana konfiguracja
@circuit_breaker(
    name="openai_embeddings",
    failure_threshold=10,     # Otwórz po 10 błędach
    timeout_seconds=120,      # Czekaj 2 min przed próbą recovery
    expected_exception=OpenAIError
)
def get_embeddings(texts: list[str]):
    return openai_client.embeddings.create(input=texts)

# Sprawdzanie stanu circuit breakera
from app.patterns import get_circuit_breaker_state

state = get_circuit_breaker_state("twilio_api")
if state == CircuitState.OPEN:
    logger.warning("Twilio API circuit breaker is OPEN - using fallback")
    return use_fallback_sms_provider()
```

**Stany:**
- **CLOSED** – normalna praca, wszystkie requesty przechodzą
- **OPEN** – zablokowany, wszystkie requesty fail-fast bez wywołania funkcji
- **HALF_OPEN** – test recovery, jeden request przechodzi aby sprawdzić czy serwis wrócił

**Kiedy używać:**
- External API calls (Twilio, OpenAI, scraping)
- Database connections jeśli używasz remote DB
- Mikroserwisy i REST APIs
- Wszystkie I/O operations z timeoutem

### TTL Cache

Thread-safe caching z automatyczną ewolucją:

```python
from app.patterns import ttl_cache, get_cache_stats

# Domyślny TTL (1 godzina)
@ttl_cache()
def expensive_computation(key: str) -> dict:
    # Ten kod wykona się tylko przy cache miss
    return perform_heavy_operation(key)

# Custom TTL i max size
@ttl_cache(ttl_seconds=300, max_size=1000)
def get_user_profile(user_id: int) -> dict:
    return db.query(f"SELECT * FROM users WHERE id = {user_id}")

# Cache stats
stats = get_cache_stats("expensive_computation")
logger.info(f"Cache hit rate: {stats['hit_rate']:.1%}")
# → "Cache hit rate: 87.5%"

# Manual cache invalidation
from app.patterns import clear_cache

clear_cache("expensive_computation")  # Wyczyść specific cache
clear_cache()                         # Wyczyść wszystkie cache
```

**Best practices:**
- Używaj dla operacji >100ms execution time
- Ustaw `max_size` aby zapobiec memory leaks
- Monitoruj `hit_rate` – jeśli <50%, TTL może być za krótki
- Pamiętaj o invalidation po UPDATE operations

### Lazy Initialization

Thread-safe lazy loading expensive resources:

```python
from app.performance import Lazy

# Expensive client initialized only on first use
openai_client = Lazy(lambda: OpenAI(api_key=settings.OPENAI_API_KEY))
twilio_client = Lazy(lambda: Client(settings.TWILIO_SID, settings.TWILIO_TOKEN))

# First call creates the client
response = openai_client.get().chat.completions.create(...)

# Subsequent calls reuse the same instance
response2 = openai_client.get().chat.completions.create(...)

# Lazy with error handling
db_connection = Lazy(lambda: psycopg2.connect(settings.DATABASE_URL))

try:
    conn = db_connection.get()
except Exception as e:
    logger.error(f"Database connection failed: {e}")
    # Fallback to SQLite
    conn = sqlite3.connect(":memory:")
```

**Kiedy używać:**
- Expensive clients (OpenAI, Twilio, database connections)
- Resources które mogą nie być potrzebne (optional features)
- Startup optimization – opóźnij init do pierwszego użycia
- Testing – łatwe mockowanie przez podmianę factory function

## Performance Monitoring (v3.2.9)

Narzędzia do mierzenia i optymalizacji wydajności:

### @timed Decorator

Automatyczne profilowanie funkcji z alertami na slow queries:

```python
from app.performance import timed

# Domyślny threshold (0ms = wszystkie wywołania logowane)
@timed()
def process_message(message: dict):
    # Automatyczne logowanie execution time
    return handle_message(message)

# Custom threshold - loguj tylko jeśli >100ms
@timed(threshold_ms=100)
def slow_database_query(user_id: int):
    # Log tylko jeśli query >100ms
    return db.execute(f"SELECT * FROM users WHERE id = {user_id}")

# Logi:
# INFO: Function 'slow_database_query' took 156.7ms (threshold: 100ms)

# Nested timing - każdy poziom mierzony osobno
@timed(threshold_ms=50)
def parent_function():
    child_function_1()  # Zmierzone osobno
    child_function_2()  # Zmierzone osobno
    return result
```

**Best practices:**
- Używaj threshold_ms aby ograniczyć noise w logach
- Dodaj @timed do wszystkich DB queries (threshold=50-100ms)
- Profile external API calls (threshold=200-500ms)
- Monitoruj workery (auto_reply, reminder) – threshold=1000ms

### MetricsCollector

Zbieranie i agregacja metryk wykonania:

```python
from app.performance import MetricsCollector, get_global_collector

# @timed automatycznie zapisuje do global collector
@timed()
def my_function():
    pass

# Pobierz statystyki dla konkretnej funkcji
collector = get_global_collector()
stats = collector.get_stats("my_function")

print(f"""
Performance stats for my_function:
  Count: {stats['count']}
  Average: {stats['avg_ms']:.1f}ms
  Min: {stats['min_ms']:.1f}ms
  Max: {stats['max_ms']:.1f}ms
  p50: {stats['p50_ms']:.1f}ms
  p95: {stats['p95_ms']:.1f}ms
  p99: {stats['p99_ms']:.1f}ms
  Success rate: {stats['success_rate']:.1%}
""")

# Statystyki dla wszystkich funkcji
all_stats = collector.get_stats()
for func_name, stats in all_stats.items():
    if stats['avg_ms'] > 100:
        logger.warning(f"Slow function: {func_name} avg={stats['avg_ms']:.1f}ms")
```

**Monitoring dashboard example:**
```python
# Endpoint dla monitoring dashboard
@app.route("/api/metrics")
def metrics():
    collector = get_global_collector()
    return jsonify({
        "functions": collector.get_stats(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
```

### RateLimiter (Token Bucket)

Throttling dla external API calls:

```python
from app.performance import RateLimiter

# 10 requests per second, burst do 20
openai_limiter = RateLimiter(rate=10.0, capacity=20)

@openai_limiter.throttle
def call_openai_api(prompt: str):
    # Automatycznie throttled do 10 req/s
    return openai_client.chat.completions.create(...)

# Ręczne acquire
limiter = RateLimiter(rate=5.0, capacity=10)

for message in messages:
    limiter.acquire()  # Czeka jeśli rate exceeded
    send_sms(message)

# Non-blocking try_acquire
if limiter.try_acquire():
    send_sms(message)
else:
    logger.warning("Rate limit exceeded, skipping message")
    queue.put(message)  # Queue for later
```

**Typowe konfiguracje:**
- **Twilio**: 10 req/s (free tier), 100 req/s (paid)
- **OpenAI**: 60 req/min = 1 req/s (free tier), 3500 req/min (paid)
- **Internal APIs**: 100-1000 req/s zależnie od capacity

### timed_block Context Manager

Timing dla bloków kodu zamiast całych funkcji:

```python
from app.performance import timed_block

def complex_operation():
    # Measure specific sections
    with timed_block("database_transaction"):
        conn.execute("BEGIN")
        conn.execute("INSERT INTO ...")
        conn.execute("UPDATE ...")
        conn.execute("COMMIT")
    
    with timed_block("external_api_call"):
        response = requests.post(api_url, json=data)
    
    with timed_block("data_processing"):
        result = process_large_dataset(response.json())
    
    return result

# Logi:
# INFO: Block 'database_transaction' took 45.2ms
# INFO: Block 'external_api_call' took 234.5ms
# INFO: Block 'data_processing' took 189.3ms
```

## Validation (v3.2.9)

Composable validators z fluent API:

### ValidationResult Type

Type-safe validation results zamiast wyjątków:

```python
from app.validators import (
    validate_e164_phone,
    ValidationSuccess,
    ValidationFailure,
    ValidationResult
)

# Validacja zwraca Result type
result: ValidationResult[str] = validate_e164_phone("+48732070140")

if result.is_valid():
    phone = result.get_value()
    logger.info(f"Valid phone: {phone}")
else:
    error = result.get_error()
    logger.error(f"Validation failed: {error}")
    return {"error": error}, 400
```

### Composable Validator (Fluent API)

Chainowanie reguł walidacji z builder pattern:

```python
from app.validators import Validator, E164_PATTERN

# Podstawowa walidacja
result = (Validator(phone_input, "phone")
    .strip()                    # Usuń whitespace
    .not_empty()                # Nie może być puste
    .matches(E164_PATTERN, "Invalid E.164 format")
    .validate())

if not result.is_valid():
    return {"error": result.get_error()}, 400

# Złożona walidacja z custom rules
result = (Validator(message_body, "body")
    .strip()
    .not_empty("Message body is required")
    .min_length(1, "Body must be at least 1 character")
    .max_length(1600, "Body exceeds SMS limit")
    .custom(lambda s: not s.startswith("/admin"), "Admin commands not allowed")
    .validate())

# Walidacja numerów w batch
numbers = ["+48123456789", "+48987654321", "invalid"]
result = (Validator(numbers, "recipients")
    .not_empty()
    .all_match(E164_PATTERN, "All numbers must be valid E.164")
    .validate())
```

**Dostępne metody:**
- `.strip()` – usuń whitespace
- `.not_empty(msg?)` – nie może być puste
- `.matches(pattern, msg)` – regex match
- `.min_length(n, msg?)` – minimum length
- `.max_length(n, msg?)` – maximum length
- `.custom(fn, msg)` – custom validation function
- `.all_match(pattern, msg)` – wszystkie elementy listy muszą matchować
- `.validate()` – finalize i zwróć ValidationResult

### validate_json_payload

Schema validation dla JSON payloads:

```python
from app.validators import validate_json_payload

# Definicja schema
schema = {
    "to": {"type": "string", "required": True},
    "body": {"type": "string", "required": True},
    "priority": {"type": "int", "required": False, "default": 0},
    "metadata": {"type": "dict", "required": False}
}

# Walidacja
payload = request.get_json()
result = validate_json_payload(payload, schema)

if not result.is_valid():
    return {"error": result.get_error()}, 400

validated = result.get_value()  # Dict z filled defaults
```

### Batch Validation z skip_invalid

Walidacja wielu wartości z partial success:

```python
from app.validators import validate_phone_numbers

# Lista numerów (niektóre invalid)
numbers = [
    "+48732070140",  # Valid
    "+48123",        # Invalid - za krótki
    "+48987654321",  # Valid
    "invalid"        # Invalid - nie E.164
]

# Walidacja z skip_invalid=True
result = validate_phone_numbers(numbers, skip_invalid=True)

# Zwraca dict z podziałem
valid = result["valid"]      # ["+48732070140", "+48987654321"]
invalid = result["invalid"]  # [("+48123", "Too short"), ("invalid", "Not E.164")]

logger.info(f"Valid: {len(valid)}, Invalid: {len(invalid)}")

# Kontynuuj z valid numbers
for number in valid:
    send_sms(number, "Your message")

# Raportuj invalid
for number, error in invalid:
    logger.warning(f"Skipped {number}: {error}")
```

## Chunked SMS – wysyłka długich wiadomości

Od v3.2.6 aplikacja automatycznie dzieli długie wiadomości:

```python
# POST /api/messages - automatyczne wykrywanie
if len(body) > MAX_SMS_CHARS:  # 1500 znaków
    result = twilio_client.send_chunked_sms(to, body, max_length=1500)
    # Zwraca: {"parts": 3, "sids": ["SM...", "SM...", "SM..."]}
```

Każda część SMS to osobna wiadomość Twilio z własnym SID. Odpowiedź API zawiera:
- `parts` – liczba części
- `sids` – tablica wszystkich SID-ów
- `characters` – łączna długość wiadomości

## FAISS All-Categories – gwarancja pokrycia

Tryb `all_categories` w `answer_query_all_categories()` zapewnia:

1. **8 kategorii**: Biznes, Giełda, Gospodarka, Nieruchomości, Poradnik Finansowy, Praca, Prawo, Technologie
2. **Skanowanie docstore**: Bezpośredni dostęp do wszystkich dokumentów (nie MMR search)
3. **Eksplicytna lista**: Każda kategoria zostanie uwzględniona, nawet jeśli brak danych

```bash
# Test FAISS z gwarancją kategorii
curl -X POST /api/news/test-faiss \
  -d '{"mode": "all_categories", "send_sms": true}'

# Odpowiedź zawiera:
# "categories_found": 8
# "categories_with_data": ["Biznes", "Giełda", ...]
# "categories_empty": []
```

## UI/Frontend: gdzie dodać nową funkcję

- Widoki: `templates/dashboard.html` (karty, formularze, modale), `templates/chat.html` (wątek 1:1).
- Logika JS: `static/js/dashboard.js` (fetch API, toasty, auto-refresh), `static/js/chat.js`.
- Styl: `static/css/app.css`.
- Dodając zakładkę lub akcję:
  - dołóż sekcję w HTML + hook w JS (fetch do nowego endpointu),
  - w API (`webhooks.py`) dodaj handler i zwróć JSON spójny z istniejącymi strukturami.

## Baza danych i migracje

### Przegląd systemu

Aplikacja używa **SQLite** jako bazy danych. Cały dostęp do bazy jest zenkapsulowany w module
`app/database.py`, który zapewnia:

- Automatyczne migracje schematu przy starcie
- Thread-safe połączenia (Flask `g` object)
- Normalizację numerów telefonów
- Helper functions do CRUD operations

### Aktualna wersja schematu

```python
SCHEMA_VERSION = 9  # W database.py
```

### Struktura tabel

#### Tabela `messages` – historia SMS/wiadomości

| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | INTEGER PK | Auto-increment ID |
| `sid` | TEXT UNIQUE | Twilio Message SID |
| `direction` | TEXT | `'inbound'` lub `'outbound'` |
| `to_number` | TEXT | Numer docelowy |
| `from_number` | TEXT | Numer nadawcy |
| `body` | TEXT | Treść wiadomości |
| `status` | TEXT | Status dostarczenia |
| `error` | TEXT | Komunikat błędu (jeśli jest) |
| `created_at` | TEXT | Timestamp utworzenia (ISO 8601) |
| `updated_at` | TEXT | Timestamp ostatniej aktualizacji |

**Indeksy:**
- `idx_messages_sid` → szybkie wyszukiwanie po SID
- `idx_messages_created_at` → sortowanie chronologiczne
- `idx_messages_direction_created_at` → filtrowanie + sortowanie

#### Tabela `auto_reply_config` – konfiguracja auto-odpowiedzi

| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | INTEGER | Zawsze = 1 (singleton) |
| `enabled` | INTEGER | 0/1 - czy włączone |
| `message` | TEXT | Treść auto-odpowiedzi |
| `enabled_since` | TEXT | Timestamp włączenia |

#### Tabela `scheduled_messages` – zaplanowane przypomnienia

| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | INTEGER PK | Auto-increment ID |
| `to_number` | TEXT | Numer docelowy |
| `body` | TEXT | Treść wiadomości |
| `interval_seconds` | INTEGER | Interwał (min. 60s) |
| `enabled` | INTEGER | 0/1 |
| `last_sent_at` | TEXT | Ostatnie wysłanie |
| `next_run_at` | TEXT | Następne zaplanowane wysłanie |
| `created_at` | TEXT | Timestamp utworzenia |
| `updated_at` | TEXT | Timestamp aktualizacji |

#### Tabela `ai_config` – konfiguracja AI/OpenAI

| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | INTEGER | Zawsze = 1 (singleton) |
| `enabled` | INTEGER | 0/1 - czy AI włączone |
| `api_key` | TEXT | Klucz OpenAI (lub NULL) |
| `system_prompt` | TEXT | System prompt dla LLM |
| `target_number` | TEXT | Numer dla AI |
| `target_number_normalized` | TEXT | Znormalizowany numer |
| `model` | TEXT | Model (domyślnie: gpt-4o-mini) |
| `temperature` | REAL | Temperatura (0.0-2.0) |
| `enabled_source` | TEXT | `'db'` lub `'env'` |
| `updated_at` | TEXT | Timestamp aktualizacji |

#### Tabele `multi_sms_batches` i `multi_sms_recipients` – batch SMS

**multi_sms_batches:**
| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | INTEGER PK | ID batcha |
| `body` | TEXT | Treść wiadomości |
| `sender_identity` | TEXT | Nadawca (opcjonalnie) |
| `status` | TEXT | `pending`, `in_progress`, `completed`, `failed` |
| `total_recipients` | INTEGER | Liczba odbiorców |
| `success_count` | INTEGER | Wysłane pomyślnie |
| `failure_count` | INTEGER | Błędy |
| `scheduled_at` | TEXT | Zaplanowany czas |

**multi_sms_recipients:**
| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | INTEGER PK | ID odbiorcy |
| `batch_id` | INTEGER FK | Odniesienie do batcha |
| `number_raw` | TEXT | Oryginalny numer |
| `number_normalized` | TEXT | Znormalizowany numer |
| `status` | TEXT | Status wysyłki |
| `message_sid` | TEXT | SID wiadomości Twilio |
| `error` | TEXT | Błąd (jeśli jest) |

#### Tabela `listeners` – interaktywne komendy SMS (v3.2.x)

| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | INTEGER PK | Auto-increment ID |
| `name` | TEXT | Nazwa listenera |
| `trigger` | TEXT | Trigger keyword (np. `/news`) |
| `enabled` | INTEGER | 0/1 - czy aktywny |
| `handler_type` | TEXT | Typ handlera (np. `faiss`) |
| `config_json` | TEXT | Konfiguracja JSON |
| `created_at` | TEXT | Timestamp utworzenia |
| `updated_at` | TEXT | Timestamp aktualizacji |

#### Tabela `news_recipients` – odbiorcy newsów RAG (v3.2.x)

| Kolumna | Typ | Opis |
|---------|-----|------|
| `id` | INTEGER PK | Auto-increment ID |
| `number` | TEXT UNIQUE | Numer telefonu (E.164) |
| `prompt` | TEXT | Prompt dla RAG |
| `send_hour` | INTEGER | Godzina wysyłki (0-23) |
| `enabled` | INTEGER | 0/1 - czy aktywny |
| `last_sent_at` | TEXT | Ostatnia wysyłka |
| `created_at` | TEXT | Timestamp utworzenia |
| `updated_at` | TEXT | Timestamp aktualizacji |

### Historia migracji

| Wersja | Funkcja | Opis zmian |
|--------|---------|------------|
| 1→2 | `_migration_add_auto_reply_enabled_since` | Dodaje kolumnę `enabled_since` do `auto_reply_config` |
| 2→3 | `_migration_add_message_indexes` | Dodaje indeksy na `created_at` i `direction+created_at` |
| 3→4 | `_migration_add_ai_config` | Tworzy tabelę `ai_config` |
| 4→5 | `_migration_add_ai_normalized_target` | Dodaje `target_number_normalized` |
| 5→6 | `_migration_add_ai_enabled_source` | Dodaje `enabled_source` i `updated_at` |
| 6→7 | `_migration_add_multi_sms_tables` | Tworzy tabele batch SMS |
| 7→8 | `_migration_add_listeners_table` | Tworzy tabelę `listeners` dla interaktywnych komend SMS |
| 8→9 | `_migration_add_news_recipients_table` | Tworzy tabelę `news_recipients` dla RAG/News |

### Jak działa `_ensure_schema()`

```
┌─────────────────────────────────────────────────────────┐
│                    START APLIKACJI                       │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
               ┌─────────────────────┐
               │  Otwórz połączenie  │
               │    do SQLite        │
               └─────────────────────┘
                         │
                         ▼
               ┌─────────────────────┐
               │ PRAGMA user_version │
               │ → current_version   │
               └─────────────────────┘
                         │
            ┌────────────┴────────────┐
            │                         │
            ▼                         ▼
    version = 0?              version < SCHEMA_VERSION?
    (nowa baza)               (wymaga migracji)
            │                         │
            ▼                         ▼
  ┌─────────────────┐       ┌─────────────────────┐
  │ _create_base_   │       │ Wykonaj migracje    │
  │ schema()        │       │ sekwencyjnie        │
  │ (pełny schemat) │       │ (version+1 → SCHEMA)│
  └─────────────────┘       └─────────────────────┘
            │                         │
            └────────────┬────────────┘
                         │
                         ▼
               ┌─────────────────────┐
               │ PRAGMA user_version │
               │ = SCHEMA_VERSION    │
               └─────────────────────┘
                         │
                         ▼
               ┌─────────────────────┐
               │   COMMIT + CLOSE    │
               └─────────────────────┘
```

### Przykład: Dodawanie nowej tabeli (krok po kroku)

**Scenariusz:** Chcesz dodać tabelę `audit_log` do śledzenia akcji użytkowników.

**Krok 1:** Zwiększ `SCHEMA_VERSION` w `database.py`:

```python
SCHEMA_VERSION = 8  # było 7
```

**Krok 2:** Napisz funkcję migracji:

```python
def _migration_add_audit_log(conn: sqlite3.Connection) -> None:
    """Migracja 7→8: Dodaje tabelę audit_log."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            actor TEXT,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_created_at 
        ON audit_log(created_at DESC)
    """)
```

**Krok 3:** Dodaj wywołanie w `_ensure_schema()`:

```python
def _ensure_schema() -> None:
    # ... istniejący kod ...
    
    if current_version < 8:
        _migration_add_audit_log(conn)
        conn.execute("PRAGMA user_version = 8")
        conn.commit()
```

**Krok 4:** (Opcjonalnie) Dodaj do `_create_base_schema()` dla nowych instalacji:

```python
def _create_base_schema(conn: sqlite3.Connection) -> None:
    # ... istniejące tabele ...
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            actor TEXT,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
```

**Krok 5:** Dodaj helper functions:

```python
def insert_audit_log(*, action: str, actor: str = None, details: str = None) -> int:
    """Zapisz wpis w audit log."""
    conn = _get_connection()
    cursor = conn.execute(
        "INSERT INTO audit_log (action, actor, details) VALUES (?, ?, ?)",
        (action, actor, details)
    )
    conn.commit()
    return cursor.lastrowid

def list_audit_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """Pobierz ostatnie wpisy z audit log."""
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return [dict(row) for row in rows]
```

### Normalizacja numerów telefonów

Funkcja `normalize_contact()` ujednolica format numerów:

```python
normalize_contact("+48 732-070-140")  # → "+48732070140"
normalize_contact("whatsapp:+48732070140")  # → "+48732070140"
normalize_contact("  +48 (732) 070.140  ")  # → "+48732070140"
```

Używaj jej przy porównywaniu numerów i przed zapisem do bazy.

### Główne helper functions

| Funkcja | Opis |
|---------|------|
| `upsert_message(...)` | Insert lub update wiadomości (deduplikacja po SID) |
| `insert_message(...)` | Prosty insert wiadomości |
| `list_messages(...)` | Lista wiadomości z filtrami |
| `list_conversations(...)` | Unikalni uczestnicy z ostatnią wiadomością |
| `get_ai_config()` | Pobierz konfigurację AI |
| `set_ai_config(...)` | Zapisz konfigurację AI |
| `create_scheduled_message(...)` | Utwórz przypomnienie |
| `list_due_scheduled_messages(...)` | Przypomnienia do wysłania |
| `create_multi_sms_batch(...)` | Utwórz batch SMS |
| `reserve_next_multi_sms_batch()` | Pobierz następny batch do przetworzenia |

### Best practices

1. **Zawsze używaj helperów** – nie pisz surowego SQL w innych modułach
2. **Normalizuj numery** – przed porównywaniem i zapisem
3. **Migracje są inkrementalne** – nigdy nie modyfikuj starych migracji
4. **Testuj migracje** – przed deployem na produkcję usuń bazę i uruchom od zera
5. **Backup przed migracją** – w produkcji zawsze `./scripts/backup_db.sh`

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

## Środowiska: dev vs prod

- Dev (rapid): `python run.py` lub `make run-dev`, `APP_DEBUG=true`, opcjonalnie `TWILIO_VALIDATE_SIGNATURE=false` przy tunelu. Baza i dane w repo (`data/`, `X1_data/`).
- Prod (Docker): `make compose-prod` (mapping portu 3000), wolumeny `./data:/app/data`, `./X1_data:/app/X1_data`, healthcheck `/api/health`. Zawsze `TWILIO_VALIDATE_SIGNATURE=true`, `APP_DEBUG=false`.
- Klucze: `OPENAI_API_KEY`/`AI_*` dla czatu AI; `SECOND_OPENAI`/`SECOND_MODEL` dla News/RAG; Twilio: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, nadawca (`TWILIO_DEFAULT_FROM` lub `TWILIO_MESSAGING_SERVICE_SID`).
- Limit SMS: `MAX_SMS_CHARS=1500` (domyślnie) – długie treści są dzielone na części i wysyłane jako wiele SID-ów.

## Logi, monitoring i typowe błędy

- Logi aplikacji (Docker): `docker compose logs -f web`. Szukaj fraz: `Chunked SMS`, `Twilio API error`, `FAISS`, `Multi-SMS`.
- Healthcheck: `curl http://<host>:3000/api/health` (pokazuje env, flagę openai_enabled).
- Typowe błędy Twilio:
  - 20003 (Authenticate): złe SID/token lub zły projekt/subaccount.
  - 21606/21614: nieprawidłowy numer E.164; sprawdź walidację po stronie API/UI.
  - 21617 (body too long): rozwiązane przez `send_chunked_sms` – jeśli wróci, sprawdź `MAX_SMS_CHARS` i logi chunków.
- FAISS brak indeksu: endpointy News zwracają komunikat o konieczności build/import; w UI widać brak aktywnego indeksu.
- AI brak klucza: `/api/ai/test`/`/api/ai/send` zwrócą błąd „Missing OpenAI key”; ustaw `OPENAI_API_KEY`.

## Release i bundling

- Tagowanie: `git tag -a verX.Y.Z -m "verX.Y.Z – title" && git push origin verX.Y.Z`.
- Release notes: katalog `deploy/releases/` (MD + HTML). Utrzymuj spójny opis zmian/kompatybilności/checklist.
- Bundling: `./scripts/prepare_release_bundle.sh verX.Y.Z` → artefakty w `release/dist/verX.Y.Z/` bez `data/`, `X1_data/`, `.env`.
- Publikacja: w GitHub Release wklej treść z `deploy/releases/verX.Y.Z.md` i dołącz paczkę z `release/dist/...` jeśli potrzebna klientom.

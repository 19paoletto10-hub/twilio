# Developer Guide – v3.2.6

> 🏷️ **Wersja**: 3.2.6 (2025-12-27) • **SCHEMA_VERSION**: 9 • **Chunked SMS**: ✅ • **FAISS All-Categories**: ✅

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
- [Środowiska: dev vs prod](#środowiska-dev-vs-prod)
- [Logi, monitoring i typowe błędy](#logi-monitoring-i-typowe-błędy)
- [Release i bundling](#release-i-bundling)

## Architektura i odpowiedzialności katalogów

- `app/` – logika aplikacji Flask, serwisy, integracje:
  - `webhooks.py` – REST API + webhooki Twilio.
  - `ui.py` – routing widoków HTML (dashboard, chat).
  - `twilio_client.py` – wysyłka SMS (Messaging Service / default_from) + `send_chunked_sms`.
  - `ai_service.py`, `chat_logic.py` – generowanie odpowiedzi AI i fallbackowy bot.
  - `auto_reply.py`, `reminder.py`, `news_scheduler.py`, `multi_sms.py` – workery w tle.
  - `faiss_service.py`, `scraper_service.py` – RAG/FAISS i scraping newsów.
  - `database.py` – SQLite + migracje `SCHEMA_VERSION`.
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

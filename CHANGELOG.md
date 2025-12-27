# Changelog

## ver3.2.9 (Code Optimization & Design Patterns)

📅 Data wydania: 2025-12-27

### Podsumowanie

Release 3.2.9 wprowadza zaawansowane wzorce projektowe, optymalizacje wydajności
i profesjonalne techniki programistyczne na poziomie enterprise.

### Najważniejsze zmiany

#### 🎯 Nowe moduły

##### patterns.py - Railway-Oriented Programming
- **Result Type** – `Success[T]` / `Failure[E]` zamiast wyjątków
- **Retry Pattern** – exponential backoff z jitter
- **Circuit Breaker** – ochrona przed kaskadowymi awariami
- **TTL Cache** – thread-safe cache z automatyczną ewolucją
- **Processor Chain** – Chain of Responsibility dla wiadomości

##### message_handler.py - Clean Architecture
- **Command Pattern** – każdy handler jako samodzielna komenda
- **Strategy Pattern** – różne strategie odpowiedzi (AI, template, listener)
- **Value Objects** – immutable `PhoneNumber`, `InboundMessage`, `ReplyResult`
- **Composable Validators** – Builder pattern dla walidacji
- **Dependency Injection** – łatwe testowanie i mockowanie

##### performance.py - Monitoring & Profiling
- **@timed decorator** – automatyczne mierzenie czasu wykonania
- **MetricsCollector** – zbieranie statystyk (avg, p50, p95)
- **RateLimiter** – token bucket dla throttlingu API
- **Lazy[T]** – thread-safe lazy initialization
- **timed_block** – context manager dla bloków kodu

#### ⚡ Optymalizacje

##### database.py
- **WAL Mode** – lepsze współbieżne odczyty/zapisy
- **Query Cache** – cache dla często używanych zapytań SQL
- **Transaction Context Manager** – automatyczne commit/rollback
- **@db_operation** – dekorator z logowaniem błędów
- **Connection Pooling** – lock dla thread-safety

##### faiss_service.py
- **Embedding Cache** – LRU cache z TTL (1h domyślnie)
- **Batched Embeddings** – częściowe cache lookup przed API call
- **Cache Stats** – monitoring hit rate

##### validators.py
- **ValidationResult Type** – `ValidationSuccess` / `ValidationFailure`
- **Composable Validator** – fluent API z chainowaniem
- **validate_json_payload** – walidacja struktury JSON
- **validate_phone_numbers** – batch validation z skip_invalid

### Zaktualizowane pliki

```
app/patterns.py             # Nowy: Design patterns
app/message_handler.py      # Nowy: Clean Architecture handlers
app/performance.py          # Nowy: Monitoring utilities
app/database.py             # WAL mode, query cache, transactions
app/faiss_service.py        # Embedding cache
app/validators.py           # Composable validators
```

### Przykłady użycia

```python
# Result Type - Railway-Oriented Programming
from app.patterns import Success, Failure, result_from_exception

@result_from_exception
def risky_operation():
    return external_api.call()

result = risky_operation()
if result.is_success():
    data = result.unwrap()
else:
    log_error(result.error)

# Retry with Exponential Backoff
@retry(RetryConfig(max_attempts=3, strategy=RetryStrategy.EXPONENTIAL))
def call_external_api():
    return requests.get(url)

# Circuit Breaker
@circuit_breaker("twilio_api")
def send_sms(to: str, body: str):
    return twilio_client.messages.create(to=to, body=body)

# Composable Validators
result = (Validator(phone_input, "phone")
    .strip()
    .not_empty()
    .matches(E164_PATTERN, "Invalid E.164 format")
    .validate())

# Performance Monitoring
@timed(threshold_ms=100)
def slow_database_query():
    ...

# Lazy Initialization
expensive_client = Lazy(lambda: OpenAI(api_key=key))
# Client created only on first .get() call
```

---

## ver3.2.8 (News Command Fallback & Consolidation)

📅 Data wydania: 2025-12-27

### Podsumowanie

Release 3.2.8 wprowadza graceful fallback dla komendy `/news` gdy listener jest wyłączony,
zapewniając użytkownikom jasną informację o niedostępności funkcji.

### Najważniejsze zmiany

#### 📰 /news Disabled Fallback
- **Graceful degradation** – gdy listener `/news` jest wyłączony, użytkownik otrzymuje informację
- **Automatyczna odpowiedź** – "Funkcja /news jest chwilowo niedostępna."
- **Status tracking** – wiadomości oznaczane statusem `news-disabled` w bazie
- **Pełne logowanie** – szczegółowe logi dla diagnozy problemów z konfiguracją

#### 🔧 Improvements
- **Branch consolidation** – wszystkie feature branches zmergowane do main
- **Clean repository** – usunięcie nieużywanych gałęzi

### Zaktualizowane pliki

```
app/auto_reply.py           # Obsługa /news disabled fallback
CHANGELOG.md                # Dokumentacja v3.2.8
```

### Zmiany w auto_reply.py

```python
# Obsługa wyłączonego listenera /news
if not listener_enabled:
    app.logger.info("/news command received but listener is disabled")
    disabled_msg = "Funkcja /news jest chwilowo niedostępna."
    # Wysłanie informacji do użytkownika
    send_sms(to=from_number, body=disabled_msg)
    # Zapis ze statusem news-disabled
    db_save_reply(from_number, disabled_msg, status="news-disabled")
```

---

## ver3.2.7 (Dynamic Chat UI & Documentation Update)

📅 Data wydania: 2025-12-27

### Podsumowanie

Release 3.2.7 wprowadza dynamiczną aktualizację nagłówków konwersacji przy przełączaniu wątków 
oraz profesjonalną dokumentację produktową (app-brochure).

### Najważniejsze zmiany

#### 💬 Dynamic Chat Headers
- **Synchronizacja UI** – nagłówek wątku aktualizuje się dynamicznie przy przełączaniu konwersacji
- **Data ostatniej aktywności** – pobierana z cache konwersacji i z ostatniej wiadomości
- **4 synchronizowane elementy** – chatCurrentTitle, chatCurrentSubtitle, chatSidebarTitle, chatThreadTitle
- **currentLastActivity state** – nowa zmienna przechowująca timestamp ostatniej aktywności

#### 📚 Dokumentacja produktowa
- **app-overview.html** – zaktualizowany do v3.2.7 z sekcją "Co nowego"
- **app-brochure.html** – profesjonalna broszura marketingowa (dark theme, gradient accents)
- **app-brochure.pdf** – wersja gotowa do druku (337 KB)
- **Use cases** – obsługa klienta, briefing biznesowy, kampanie SMS, chatbot
- **Deployment options** – Self-Hosted, Enterprise, Consulting

### Zaktualizowane pliki

```
app/static/js/chat.js       # currentLastActivity, updateCurrentConversationUI()
app/templates/chat.html     # id="chat-thread-title" dodane do h2
docs/app-overview.html      # zaktualizowany do v3.2.7
docs/app-brochure.html      # nowa broszura marketingowa
docs/app-brochure.pdf       # wersja PDF
```

### Zmiany w chat.js

```javascript
// Nowa zmienna stanu
let currentLastActivity = root.dataset.lastActivity || '';

// Rozszerzone przełączanie konwersacji
const conv = conversationsCache.find(c => c.participant === participant);
currentLastActivity = conv?.last_message?.created_at || '';

// Aktualizacja nagłówka wątku
if (chatThreadTitle) chatThreadTitle.textContent = display || 'Nieznany';
if (lastUpdatedInlineEl) {
  lastUpdatedInlineEl.textContent = currentLastActivity ? formatDateTime(currentLastActivity) : '—';
}
```

---

## ver3.2.6 (Chunked SMS & Professional FAISS RAG)

📅 Data wydania: 2025-12-27

### Podsumowanie

Release 3.2.6 wprowadza automatyczne dzielenie długich SMS-ów (>1500 znaków) na części oraz 
profesjonalne streszczenia RAG w stylu reportera biznesowego z gwarancją pokrycia wszystkich 
8 kategorii newsów.

### Najważniejsze zmiany

#### 📱 Chunked SMS
- **Automatyczne dzielenie** – wiadomości >1500 znaków dzielone na części przez `send_chunked_sms()`
- **POST /api/messages** – automatycznie wykrywa długie wiadomości i używa chunked send
- **Nowe pola odpowiedzi** – `parts`, `sids[]`, `characters` w JSON response
- **Limit bezpieczeństwa** – 1500 znaków (bufor 100 znaków przed limitem Twilio 1600)

#### 🎯 FAISS All-Categories Improvements
- **Gwarancja pokrycia** – każda z 8 kategorii zawsze obecna w odpowiedzi
- **Skanowanie docstore** – bezpośredni dostęp do dokumentów zamiast MMR search
- **Nowe pola** – `categories_found`, `categories_with_data`, `categories_empty`
- **per_category_k=2** – zwiększono z 1 do 2 dokumentów per kategoria

#### 📰 Profesjonalne streszczenia
- **Styl reportera** – koherentna proza zamiast bullet points
- **System prompt** – "doświadczony dziennikarz biznesowy przygotowujący poranny briefing"
- **Emoji nagłówki** – 📊 BIZNES, 📈 GIEŁDA, 🏠 NIERUCHOMOŚCI etc.
- **max_tokens=2000** – zapewnia miejsce na wszystkie kategorie

#### 🔧 API Enhancements
- **POST /api/news/test-faiss** – nowa opcja `send_sms: true` z chunked delivery
- **Szczegółowe logowanie** – ilość kategorii, długość odpowiedzi, błędy per kategoria

### Zaktualizowane pliki

```
app/faiss_service.py    # search_all_categories(), answer_query_all_categories()
app/webhooks.py         # POST /api/messages (chunked), POST /api/news/test-faiss (send_sms)
```

### Przykład użycia

```bash
# Test FAISS z wysyłką SMS
curl -X POST /api/news/test-faiss \
  -d '{"mode": "all_categories", "send_sms": true}'

# Odpowiedź:
# {"sms_sent": true, "sms_result": {"parts": 3, "sids": [...]}, "categories_found": 8}
```

---

## ver3.2.5 (Code Quality & Type Safety: Senior-Level Refactoring)

📅 Data wydania: 2025-12-27

### Podsumowanie

Release 3.2.5 to profesjonalny refaktoring kodu z perspektywy Senior Developera. Wersja eliminuje 
wszystkie błędy typów wykryte przez Pylance, dodaje solidną obsługę błędów, rozbudowuje 
dokumentację funkcji oraz implementuje database-level deduplication dla niezawodnego 
przetwarzania wiadomości w trybie asynchronicznym.

### Najważniejsze zmiany

#### 🔒 Type Safety & Error Handling
- **Naprawiono `AIReplyError.reply_text`** – atrybut był w `details` dict, teraz jest dostępny bezpośrednio jako `self.reply_text`
- **Bezpieczne `cursor.lastrowid`** – nowa funkcja `_get_lastrowid()` z walidacją i obsługą błędów
- **Type guards dla `int()`** – wszystkie parsowania `int()` z `request.get_json()` mają explicit `None` check
- **Walidacja `from_number`** – przed każdym wysłaniem SMS sprawdzane jest czy numer odbiorcy nie jest `None`
- **Fix `answer_query()` return** – poprawiona ekstrakcja `answer` z Dict zamiast używania całego Dict jako body SMS

#### 🔄 Database-Level Deduplication
- **Nowa funkcja `has_outbound_reply_for_inbound()`** – sprawdza w bazie czy wysłaliśmy już odpowiedź
- **Zastąpienie in-memory dedupe** – `_LISTENER_PROCESSED_SIDS` deque usunięte na rzecz trwałego sprawdzania DB
- **Działa między restartami** – deduplikacja jest persystentna, nie gubi się przy restarcie procesu
- **Poprawka debug mode** – działa poprawnie z Werkzeug reloader (wiele procesów)

#### 🔧 Auto-Reply Worker Improvements
- **Force restart parameter** – `start_auto_reply_worker(app, force_restart=True)` dla recovery
- **Auto-recovery** – `enqueue_auto_reply()` automatycznie restartuje martwego workera
- **Thread alive check** – sprawdzanie `thread.is_alive()` przed enqueue
- **Usunięty duplicate code** – zmienne `from_number`, `to_number`, `body`, `sid` deklarowane raz
- **AI niezależne od Listener `*`** – AI działa nawet gdy domyślny listener jest wyłączony

#### 📚 Profesjonalna dokumentacja
- **Rozbudowane docstringi** z pełnymi opisami algorytmów, thread safety, performance notes
- **Przykłady użycia** w docstringach (`>>> enqueue_auto_reply(...)`)
- **Type hints** poprawione dla wszystkich funkcji

#### 🗄️ Database Improvements
- **`_get_lastrowid()`** – bezpieczna ekstrakcja ID po INSERT z walidacją
- **`_ensure_listeners_table_after_error()`** – auto-recovery gdy tabela nie istnieje
- **Listener `*`** – nowy domyślny listener kontrolujący auto-reply (AI działa niezależnie)
- **`create_multi_sms_batch()`** – poprawione zwracanie `Dict` zamiast `Optional[Dict]`

### Naprawione błędy typów

| Plik | Problem | Rozwiązanie |
|------|---------|-------------|
| `exceptions.py` | `AIReplyError.reply_text` niedostępny | Dodano atrybut `reply_text: Optional[str]` |
| `database.py` | `cursor.lastrowid` może być `None` | Nowa funkcja `_get_lastrowid()` |
| `webhooks.py` | `answer_query()` zwraca Dict, nie str | Ekstrakcja `answer_result.get("answer")` |
| `webhooks.py` | `int(history_limit_raw)` gdy `None` | Explicit `None` check przed `int()` |
| `auto_reply.py` | `from_number` może być `None` | Walidacja przed `send_chunked_sms()` |

### Zaktualizowane pliki

```
app/exceptions.py                # AIServiceError z reply_text jako atrybut
app/database.py                  # _get_lastrowid(), has_outbound_reply_for_inbound()
app/auto_reply.py                # Force restart, auto-recovery, docstrings
app/webhooks.py                  # Type guards, DB deduplication, fix answer_query
app/twilio_client.py             # Preferuj default_from nad inbound_to
app/ai_service.py                # Comment clarifying origin_number usage
```

### Architektura deduplikacji

```
Inbound SMS ─────────────────────────────────────────────────────────────►
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  1. Webhook: has_outbound_reply_for_inbound(sid, from_number)           │
│     ↓ False                                                              │
│  2. Insert inbound message to DB                                         │
│     ↓                                                                    │
│  3. Enqueue to SimpleQueue                                               │
└──────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Worker Thread:                                                          │
│  4. Get payload from queue                                               │
│  5. has_outbound_reply_for_inbound(sid, from_number)                    │
│     ↓ False (brak duplikatu)                                            │
│  6. Process: AI reply / /news listener / auto-reply                     │
│  7. Send SMS via Twilio                                                  │
│  8. Insert outbound message to DB ← deduplikacja działa od teraz        │
└──────────────────────────────────────────────────────────────────────────┘
```

### Thread Safety & Recovery

```python
# Worker automatycznie restartuje się gdy umrze
def enqueue_auto_reply(app, *, sid, from_number, to_number, body, received_at=None):
    thread = app.config.get("AUTO_REPLY_THREAD")
    if not thread or not thread.is_alive():
        start_auto_reply_worker(app, force_restart=True)
    queue.put(payload)
```

### Kompatybilność

- **Brak zmian łamiących** – wszystkie istniejące API pozostają kompatybilne
- **Brak migracji DB** – schemat pozostaje na wersji 9
- **Backward compatible** – `AIReplyError` alias zachowany dla legacy code

---

## ver3.2.4 (Listeners: SMS Command Processing with FAISS Integration)

📅 Data wydania: 2025-12-23

### Podsumowanie

Release 3.2.4 wprowadza nową zakładkę **Listeners** umożliwiającą dynamiczne zarządzanie
komendami SMS. Odbiorcy mogą wysyłać wiadomości zaczynające się od prefiksu `/news`,
a system automatycznie odpowiada na ich zapytania wykorzystując bazę wiedzy FAISS.

### Najważniejsze zmiany

#### 🎧 Nowa zakładka Listeners
- **Konfiguracja nasłuchiwaczy** – włączanie/wyłączanie komend SMS w czasie rzeczywistym
- **Wizualne karty listenerów** z przełącznikiem, opisem i statusem
- **Panel testowy** – symulacja zapytania `/news` bez wysyłania SMS-a
- **Instrukcja dla odbiorców** – krok po kroku jak używać komendy

#### 📰 Komenda /news
- Odbiorcy SMS mogą wysłać `/news [pytanie]` aby otrzymać odpowiedź z bazy newsów
- **Integracja z FAISS** – wyszukiwanie w zindeksowanych artykułach
- **Synchroniczna obsługa** – odpowiedź wysyłana natychmiast przy odbiorze SMS
- **Deduplikacja** – mechanizm zapobiegający wielokrotnemu przetwarzaniu tej samej wiadomości
- **Domyślne zapytanie** – gdy brak pytania, system pyta o najnowsze wiadomości

#### 🗄️ Nowa tabela bazy danych
- `listeners_config` – przechowuje konfigurację nasłuchiwaczy
- **Automatyczna migracja** – SCHEMA_VERSION = 9
- Domyślny wpis `/news` tworzony przy pierwszym uruchomieniu

#### 🔌 Nowe API Endpoints

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/api/listeners` | GET | Lista wszystkich nasłuchiwaczy |
| `/api/listeners/<id>` | POST | Aktualizacja konfiguracji (enabled, description) |
| `/api/listeners/test` | POST | Test zapytania /news z FAISS |

#### 🎨 Nowe style CSS
- `.listener-card` – karta z efektem hover i cieniem
- `.listener-icon` – ikona z kolorowym tłem (zielone = aktywny)
- `.listener-step-icon` – ikony numerowanych kroków w instrukcji
- `.listener-answer-content` – formatowanie odpowiedzi FAISS

### Zaktualizowane pliki

```
app/database.py                  # SCHEMA_VERSION=9, migracja, CRUD listeners
app/auto_reply.py                # Obsługa komendy /news w workerze
app/webhooks.py                  # Nowe endpointy + synchroniczna obsługa /news
app/templates/dashboard.html     # Zakładka Listeners z UI
app/static/js/dashboard.js       # Funkcje loadListeners, testListenerQuery
app/static/css/app.css           # Style Listeners
```

### Architektura obsługi /news

```
SMS przychodzi ──► Twilio Webhook ──► _handle_news_listener_sync()
                          │                    │
                          ▼                    ▼
                   GET /api/messages    ►  FAISSService.answer_query()
                   (polling)                   │
                          │                    ▼
                          ▼              Twilio send_reply_to_inbound()
            _maybe_enqueue_auto_reply()        │
                          │                    ▼
                          ▼               SMS odpowiedź
            _handle_news_listener_sync()
```

### Workflow użytkownika (odbiorca SMS)

1. Odbiorca wysyła SMS: `/news Jakie są najnowsze wiadomości o rynku?`
2. System wykrywa prefiks `/news` i sprawdza czy listener jest włączony
3. Zapytanie trafia do FAISSService (wyszukiwanie w bazie)
4. OpenAI generuje odpowiedź na podstawie znalezionych artykułów
5. Odpowiedź jest wysyłana jako SMS do nadawcy

### Poprawki błędów

#### 🐛 Listener nie odpowiadał na SMS
**Problem:** Wiadomości `/news` były kolejkowane ale worker ich nie przetwarzał.

**Rozwiązanie:** 
- Dodano synchroniczną obsługę `_handle_news_listener_sync()` w webhooks.py
- Listener jest teraz obsługiwany bezpośrednio przy odbiorze SMS
- Dodano deduplikację `_LISTENER_PROCESSED_SIDS` zapobiegającą wielokrotnej odpowiedzi

### Kompatybilność

- **Brak zmian łamiących** – istniejące funkcje pozostają niezmienione
- Migracja bazy danych jest automatyczna (v8 → v9)
- Listener `/news` jest domyślnie wyłączony – wymaga ręcznego włączenia

---

## ver3.2.3 (News Scraping UX: Live Progress & Professional Content Display)

### Podsumowanie

Release 3.2.3 znacząco ulepsza doświadczenie użytkownika w module News/FAISS.
Wprowadza dynamiczny podgląd postępu skrapowania z wykorzystaniem Server-Sent Events (SSE),
przycisk zatrzymania procesu, masowe usuwanie plików oraz profesjonalne formatowanie
podglądu zeskrapowanych artykułów.

### Najważniejsze zmiany

#### 📡 Dynamiczny postęp skrapowania (SSE)
- **Real-time streaming** – każda kategoria aktualizuje się na żywo podczas skrapowania
- **Wizualne statusy kategorii:**
  - ⚪ Oczekuje – kategoria w kolejce
  - 🔄 Spinner – aktualnie przetwarzana
  - ✅ Sukces – zapisano pliki (z liczbą artykułów)
  - ❌ Błąd – problem z kategorią
- **Licznik postępu** – badge pokazuje `X/Y` ukończonych kategorii
- **Nowy endpoint SSE** – `GET /api/news/scrape/stream` dla streamingu zdarzeń

#### ⏹️ Kontrola procesu skrapowania
- **Przycisk „Zatrzymaj"** – przerywa proces w dowolnym momencie
- Automatyczne ukrywanie przycisku po zakończeniu
- Zachowanie częściowo zapisanych plików po przerwaniu

#### 🗑️ Masowe zarządzanie plikami
- **Przycisk „Usuń wszystkie"** – kasuje wszystkie zeskrapowane pliki jednym kliknięciem
- Potwierdzenie przed usunięciem
- Nowy endpoint `DELETE /api/news/files` dla operacji masowej

#### 📰 Profesjonalny podgląd treści
- **Wyświetlanie tylko plików .txt** – ukryto techniczne pliki .json
- **Eleganckie kafelki kategorii:**
  - Ikona gazety zamiast pliku
  - Nazwa kategorii z wielką literą
  - Data w formacie polskim (np. „23 gru, 14:30")
  - Przycisk usuwania widoczny przy hover
- **Formatowanie artykułów w overlay:**
  - Numerowane karty dla każdego artykułu
  - Pogrubione tytuły (pierwszy wiersz)
  - Czytelna typografia z właściwym line-height
  - **Filtrowanie separatorów** – linie `---` nie są wyświetlane

#### 🎨 Nowe style CSS
- `.news-file-card` – karty z efektem hover i cieniem
- `.news-file-icon` – ikona z gradientowym tłem
- `.news-file-delete-btn` – przycisk X widoczny przy hover
- `.news-article-item` – karta artykułu z numerem
- `.news-article-title` / `.news-article-body` – typografia treści
- Animacja `fadeInScale` dla ikon sukcesu

### Nowe API Endpoints

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/api/news/scrape/stream` | GET | SSE streaming postępu skrapowania |
| `/api/news/files` | DELETE | Usuń wszystkie zeskrapowane pliki |

### Zaktualizowane pliki

```
app/webhooks.py                  # Nowe endpointy SSE i DELETE all
app/static/js/dashboard.js       # Obsługa SSE, zatrzymanie, usuwanie, formatowanie
app/templates/dashboard.html     # Przycisk stop, przycisk usuń wszystkie
app/static/css/app.css           # Style kafelków i podglądu artykułów
```

### Kompatybilność

- **Brak zmian łamiących** – istniejące API pozostaje kompatybilne
- Oryginalny endpoint `POST /api/news/scrape` nadal działa (bez streamingu)
- Wymaga przeglądarki z obsługą EventSource (wszystkie nowoczesne przeglądarki)

---

## ver3.2.2 (UI/UX Modernization: Chat Page + Secrets Manager + Design System Refresh)

### Podsumowanie

Release 3.2.2 wprowadza kompleksową modernizację interfejsu użytkownika z naciskiem na
stronę czatu i nową dedykowaną stronę zarządzania kluczami API (Secrets Manager).
Dodano spójny design system z gradientowymi nagłówkami, ikonami w nawigacji,
oraz ulepszono responsywność całej aplikacji.

### Najważniejsze zmiany

#### 🔐 Secrets Manager (Nowa strona /secrets)
- Centralne zarządzanie kluczami Twilio (SID, Token, Sender, Messaging Service)
- Konfiguracja OpenAI (API Key, Model selection)
- Maskowanie wartości z możliwością odsłonięcia
- Przycisk "Test" do weryfikacji połączenia na żywo
- Opcja "Zapisz do .env" dla trwałej konfiguracji
- Hot reload konfiguracji bez restartu serwera
- Przycisk "Top Secret" w header'ze aplikacji

#### 💬 Modernizacja strony czatu
- Nowoczesny nagłówek strony z awatarem i badge'ami statusu (Online/DEV)
- Awatary z gradientowym tłem (sidebar i header)
- Siatka meta-danych (2 kolumny: aktywność + liczba wiadomości)
- Animowane dymki z efektem `bubbleIn`
- Ikony statusu dostarczenia (✓ wysłano, ✓✓ dostarczono)
- Ikony autorów (👤 Klient, 🎧 Zespół)
- Spinner ładowania historii wiadomości
- Responsywny układ dla wszystkich rozmiarów ekranów

#### 🎨 Design System Refresh
- `.page-icon-badge` – ikona strony z gradientem (42x42px)
- `.page-icon-badge--dark` – ciemny wariant dla strony Secrets
- `.dashboard-header`, `.chat-page-header`, `.secrets-header` – spójne nagłówki
- `.nav-pills-modern` – zakładki z ikonami i efektami hover
- `.chat-meta-grid`, `.chat-meta-item` – siatka meta-danych
- `.chat-composer-form`, `.chat-composer-textarea` – zmodernizowany formularz wysyłki
- Ulepszone `.chat-bubble` z animacjami i ikonami statusu

#### 📊 Panel sterowania
- Nowy nagłówek z gradientem i ikoną strony
- Zakładki z ikonami (💬 🔄 ⏱️ ✨ 📰 👥)
- Ciemny badge środowiska z ikoną serwera

#### 🔌 Nowe API Endpoints
- `GET /api/secrets` – lista kluczy (zmaskowane)
- `POST /api/secrets` – zapisz klucz
- `POST /api/secrets/test` – test połączenia
- `GET /api/models` – lista dostępnych modeli OpenAI
- `POST /api/settings/reload` – hot reload konfiguracji

### Zaktualizowane pliki

```
# Nowe pliki
app/secrets_manager.py           # SecretsManager - CRUD kluczy API
app/templates/secrets.html       # Strona zarządzania kluczami
app/static/js/secrets.js         # Logika strony secrets

# Zmodyfikowane
app/templates/base.html          # Przycisk "Top Secret" w header
app/templates/chat.html          # Zmodernizowany layout czatu
app/templates/dashboard.html     # Nowy nagłówek, ikony w zakładkach
app/static/css/app.css           # Design system refresh (~400 linii)
app/static/js/chat.js            # Ikony statusu, animacje dymków
app/static/js/dashboard.js       # Obsługa responsywnych tabel
app/ui.py                        # Route /secrets
app/webhooks.py                  # Endpointy /api/secrets, /api/models
app/config.py                    # reload_runtime_settings()
app/database.py                  # app_settings + settings_audit tables
```

### Kompatybilność

- **Migracja DB:** Schema version pozostaje 8 (bez zmian)
- **Brak zmian łamiących** – istniejące API pozostaje kompatybilne
- Wymaga przeglądarki z obsługą CSS Custom Properties (Chrome 88+, Firefox 78+, Safari 14+)

---

## ver3.2.1 (Collapsible Sidebar + Compose Modal)

### Podsumowanie

Release 3.2.1 wprowadza znaczące ulepszenia interfejsu użytkownika, koncentrując się na
ergonomii pracy operatora. Główne zmiany to zwijane menu boczne (collapsible sidebar)
oraz nowoczesny modal kompozycji wiadomości, który umożliwia tworzenie SMS bez opuszczania
bieżącego widoku.

### Najważniejsze zmiany

#### 📐 Collapsible Sidebar (Zwijane menu boczne)
- Tryb rozwinięty (280px) z pełnymi etykietami i ikonami
- Tryb zwinięty (84px) z kompaktowymi ikonami i tooltipami
- Persystencja stanu w localStorage przeglądarki
- Płynne animacje CSS (0.25s ease)
- Responsywność: overlay na mobile, automatyczne zwijanie na tabletach

#### 📨 Compose Modal (Modal kompozycji wiadomości)
- Nowoczesne okno dialogowe do tworzenia wiadomości
- Walidacja numeru w formacie E.164
- Licznik znaków z ostrzeżeniem przy przekroczeniu 160
- Skróty klawiszowe: Ctrl+Enter (wyślij), Escape (zamknij)
- Toast z potwierdzeniem sukcesu/błędu

#### 🎨 Ulepszenia CSS
- Nowe zmienne CSS: `--app-sidebar-width`, `--app-sidebar-collapsed-width`
- Gradient accent color (#7c40ff → #f22f46)
- Spójne border-radius i shadows w całej aplikacji

#### 📱 Responsywność
- Desktop (≥992px): sidebar rozwinięty, zwijany ręcznie
- Tablet (<992px): sidebar zwinięty domyślnie
- Mobile (<576px): sidebar jako overlay z animacją slide-in

#### ⚙️ Stabilność startu
- Wyłączony reloader Flask (`use_reloader=False`), aby uniknąć wymogu podwójnego uruchomienia
- Workery tła odpalają się tylko w głównym procesie (guard na `WERKZEUG_RUN_MAIN`)

### Zaktualizowane pliki

```
app/templates/base.html           # Struktura sidebara i header
app/templates/dashboard.html      # Integracja z sidebar i modal
app/static/css/app.css            # Nowy design system + style sidebara
app/static/js/app.js              # Logika collapse
app/static/js/dashboard.js        # Obsługa modala
```

### Kompatybilność

- **Brak zmian łamiących** – wszystkie istniejące funkcjonalności działają bez modyfikacji
- **Brak migracji DB** – schemat pozostaje na wersji 7
- Wymaga przeglądarki z obsługą CSS Custom Properties (Chrome 88+, Firefox 78+, Safari 14+)

---

## ver3.2.0 (Docker Documentation + CI/CD + DevOps Toolkit)

### Podsumowanie

Release 3.2.0 to kompleksowa aktualizacja dokumentacji i narzędzi DevOps. Wprowadza pełny
przewodnik Docker od podstaw (z wyjaśnieniami wszystkich pojęć), automatyzację CI/CD przez
GitHub Actions, skrypt do backupu bazy danych oraz gotową konfigurację SSL/TLS z Let's Encrypt.
Rozbudowano również dokumentację bazy danych w developer-guide.md o pełny schemat tabel,
historię migracji i przykłady dodawania nowych struktur.

### Najważniejsze zmiany

#### 📚 Nowa dokumentacja Docker
- **[docs/docker-guide.md](docs/docker-guide.md)** – kompletny przewodnik Docker od zera:
  - Słownik 25+ pojęć Docker z wyjaśnieniami i analogiami dla początkujących
  - Instalacja Docker na Ubuntu/macOS/Windows
  - Diagramy architektury kontenerów (development vs production)
  - Quick Start w 5 minut
  - Krok po kroku: Development (6 kroków z komentarzami)
  - Krok po kroku: Production (5 kroków + konfiguracja webhooków Twilio)
  - Sekcja Troubleshooting z typowymi problemami
  - FAQ

#### 🔐 SSL/TLS z Let's Encrypt
- **[deploy/nginx/default-ssl.conf](deploy/nginx/default-ssl.conf)** – konfiguracja NGINX z HTTPS
- **[docker-compose.ssl.yml](docker-compose.ssl.yml)** – stack produkcyjny z certbot
- Automatyczne odnawianie certyfikatów (kontener certbot)
- Nagłówki bezpieczeństwa (X-Frame-Options, X-Content-Type-Options, HSTS)

#### 🔄 CI/CD z GitHub Actions
- **[.github/workflows/docker-build.yml](.github/workflows/docker-build.yml)** – workflow automatyzacji:
  - Build obrazu przy push do `main` lub tagu `ver*`
  - Publikacja do GitHub Container Registry (GHCR)
  - Testowanie obrazu (health check)
  - Opcjonalny auto-deploy przez SSH
  - Szczegółowe komentarze wyjaśniające każdy krok

#### 💾 Backup bazy danych
- **[scripts/backup_db.sh](scripts/backup_db.sh)** – profesjonalny skrypt backup:
  - Automatyczne wykrywanie źródła (Docker lub lokalnie)
  - Weryfikacja integralności SQLite
  - Rotacja starych backupów (domyślnie 7 dni)
  - Tryby `--dry-run`, `--list`, `--restore`
  - Kolorowy output i szczegółowe logi

#### 📖 Rozszerzona dokumentacja bazy danych
- **[docs/developer-guide.md](docs/developer-guide.md)** – rozbudowana sekcja DB:
  - Pełna struktura 6 tabel z opisami kolumn
  - Historia migracji (wersja 1→7)
  - Diagram przepływu `_ensure_schema()`
  - Przykład krok po kroku: dodawanie nowej tabeli
  - Opis normalizacji numerów telefonów
  - Tabela helper functions i best practices

#### 🛠️ Rozszerzony Makefile
- Nowe komendy: `make compose-ssl`, `make backup`, `make restore`, `make health`
- Czytelny help z ramkami ASCII

### Nowe pliki

```
.github/workflows/docker-build.yml    # CI/CD workflow
deploy/nginx/default-ssl.conf         # NGINX z SSL
deploy/certbot/www/.gitkeep           # Katalog Let's Encrypt challenge
deploy/certbot/conf/.gitkeep          # Katalog certyfikatów
docker-compose.ssl.yml                # Compose z SSL
docs/docker-guide.md                  # Przewodnik Docker
scripts/backup_db.sh                  # Skrypt backup
```

### Zaktualizowane pliki

```
README.md                             # Rozszerzona sekcja Docker + tabele dokumentacji
docs/README.md                        # Nowy spis treści z linkami
docs/developer-guide.md               # Rozbudowana sekcja bazy danych
Makefile                              # Nowe komendy
```

### Kompatybilność i upgrade

- **Brak zmian łamiących** – wszystkie istniejące funkcjonalności działają bez modyfikacji
- **Brak migracji DB** – schemat pozostaje na wersji 7
- Nowe pliki nie wpływają na działanie aplikacji w istniejących deploymentach
- Zalecane: przejrzenie nowego przewodnika Docker przed kolejnym wdrożeniem

### Użycie opublikowanego obrazu (po merge)

```bash
# Pull z GitHub Container Registry
docker pull ghcr.io/19paoletto10-hub/twilio:latest

# Lub z tagiem wersji
docker pull ghcr.io/19paoletto10-hub/twilio:3.2.0
```

---

## ver3.1.3 (Chunked SMS + docs refresh)

### Podsumowanie

Release 3.1.3 uszczelnia wysyłkę dłuższych treści generowanych przez AI (w tym News/RAG),
tak aby nie kończyły się błędem Twilio przy przekroczeniu limitu długości SMS.
Aplikacja dzieli wiadomości na bezpieczne części (domyślnie 1500 znaków) i wysyła je jako
kilka SMS-ów. Wydanie porządkuje też dokumentację (README + docs + release notes).

### Najważniejsze zmiany

- **Dzielenie długich wiadomości SMS** – [app/message_utils.py](app/message_utils.py)
  wprowadza wspólną logikę dzielenia tekstu (z próbą cięcia po granicach zdań/akapitów).
- **Wysyłka wieloczęściowa przez Twilio** – [app/twilio_client.py](app/twilio_client.py)
  dodaje metodę `send_chunked_sms()` używaną przez moduły wysyłkowe, aby unikać błędu
  „The concatenated message body exceeds the 1600 character limit”.
- **News i AI bez ucinania treści** – ręczne i zaplanowane wysyłki newsów oraz odpowiedzi AI
  wysyłają treść w częściach zamiast obcinać ją do 1600 znaków.
- **Odświeżona dokumentacja** – README i dokumenty w `docs/`/`deploy/releases/` zawierają
  spójne instrukcje uruchomienia, konfiguracji i przewodnik po kodzie.

### Kompatybilność i upgrade

- Brak zmian łamiących w endpointach HTTP.
- Jeśli integrujesz się bezpośrednio z Twilio: pamiętaj, że jedna „odpowiedź” aplikacji może
  zostać wysłana jako kilka SMS-ów (kilka SID-ów).

## ver3.1.2 (Multi-SMS batches & release hygiene)

### Podsumowanie

Release 3.1.2 dodaje pełny moduł Multi-SMS: worker w tle, tabele w SQLite,
REST API oraz zakładkę w panelu WWW. Dzięki temu operator może przygotować
batch z poziomu UI lub API i monitorować postęp wysyłki. Wydanie dostarcza też
skrypt budowania paczek release, aby publiczne artefakty nie zawierały
wrażliwych danych (`data/`, `X1_data/`, `.env`).

### Najważniejsze zmiany

- **Worker & schema v7** – [app/multi_sms.py](app/multi_sms.py) przetwarza batch'e,
  a [app/database.py](app/database.py) dodaje tabele `multi_sms_batches` oraz
  `multi_sms_recipients` wraz z migracją i licznikami sukcesów/błędów.
- **Panel „Multi-SMS”** – [app/templates/dashboard.html](app/templates/dashboard.html)
  i [app/static/js/dashboard.js](app/static/js/dashboard.js) umożliwiają tworzenie
  zadań, obserwowanie historii i rozwijanie statusów odbiorców.
- **REST API** – [app/webhooks.py](app/webhooks.py) udostępnia endpointy
  `POST/GET /api/multi-sms/batches` + szczegóły odbiorców, z walidacją limitów.
- **Release hygiene** – [scripts/prepare_release_bundle.sh](scripts/prepare_release_bundle.sh)
  buduje katalog `release/dist/<tag>/` zawierający tylko kod i dokumentację,
  co ułatwia publikację paczek bez sekretów.

### Kompatybilność i upgrade

- Migracja schematu do wersji 7 uruchamia się automatycznie – przed aktualizacją
  wykonaj backup `data/app.db`.
- Multi-SMS wymaga skonfigurowanego `TWILIO_DEFAULT_FROM` lub Messaging Service SID;
  bez tego API zwróci błąd.
- Przed publikacją release uruchom `./scripts/prepare_release_bundle.sh ver3.1.2`
  i załącz wygenerowaną paczkę (bez `data/`, `X1_data/`, `.env`).

## ver3.1.1 (Precise ALL-CATEGORIES summaries)

### Podsumowanie

Wydanie doprecyzowuje zachowanie trybu podsumowania newsów "ALL‑CATEGORIES".
Model otrzymuje osobne, wyraźnie oznaczone konteksty dla każdej kategorii oraz
jasne instrukcje co do formatu odpowiedzi (nagłówek + 2–3 krótkie zdania na
kategorię, bez wypunktowań). Dzięki temu streszczenia są bardziej
przewidywalne i nie mieszają faktów między kategoriami.

### Najważniejsze zmiany

- **News/RAG – kontekst per kategoria** – `answer_query_all_categories()`
  buduje osobne konteksty FAISS dla każdej kategorii z kontrolowanym budżetem
  znaków, co poprawia separację tematów i ułatwia debugowanie.
- **Stabilny format ALL‑CATEGORIES** – prompty wymagają formatu
  "Kategoria: <nazwa>" + 2–3 krótkie zdania (bez wypunktowań) oraz jawnego
  komunikatu `brak danych`, gdy FAISS nie zwraca fragmentów.
- **Spójne prompty backendowe** – `ALL_CATEGORIES_PROMPT` i prompty w
  `FAISSService` opisują tę samą, jednoznaczną semantykę trybu ALL‑CATEGORIES.

### Kompatybilność i upgrade

- Brak zmian łamiących w webhookach Twilio oraz modułach AI/auto‑reply.
- Istniejąca konfiguracja odbiorców (`use_all_categories`) pozostaje ważna –
  zmienia się jedynie sposób budowy kontekstu i format odpowiedzi.

## ver3.1.0 (All-categories News mode + dashboard UX hardening)

### Podsumowanie

Wydanie domyka tryb podsumowania newsów „ALL‑CATEGORIES” jako funkcję konfigurowalną
z poziomu panelu i API (per‑odbiorca i per‑test), a dodatkowo porządkuje UX w panelu:
wyniki pokazują tryb, prompty są spójne z wybranym trybem, a historia wiadomości ma
stabilny układ tabeli (stała wysokość wierszy w kolumnie treści).

### Najważniejsze zmiany

- **News/RAG – tryb ALL‑CATEGORIES jako opcja** – flagę `use_all_categories` można
  ustawiać w UI (test FAISS + odbiorcy) i przesyłać w API; scheduler respektuje
  ustawienie per‑odbiorca.
- **Prompty per‑tryb** – aplikacja utrzymuje osobny prompt dla STANDARD oraz
  ALL‑CATEGORIES, co ogranicza „dryf” promptów i stabilizuje format odpowiedzi.
- **Dashboard – czytelność historii** – kolumna „Treść” w historii wiadomości ma
  stałą wysokość wierszy (dłuższe teksty są skracane), co poprawia skanowalność.

### Kompatybilność i upgrade

- Brak zmian łamiących w webhookach Twilio i modułach AI/auto‑reply.
- Jeśli integrujesz się z endpointami News, możesz (opcjonalnie) zacząć wysyłać
  `use_all_categories`; w przeciwnym razie zachowanie pozostaje zgodne z domyślną
  konfiguracją (ALL‑CATEGORIES włączone).

## ver3.0.2 (News / FAISS control plane)

### Podsumowanie

Release skupia się na profesjonalizacji modułu News/RAG: baza FAISS korzysta teraz
wyłącznie z embeddingów OpenAI, dashboard dostał dedykowaną sekcję statusową, a
API ułatwia testowanie i diagnostykę bezpośrednio z panelu. Dzięki temu operator
widzi w jednym miejscu stan indeksu, liczbę wektorów i kontekst odpowiedzi.

### Najważniejsze zmiany

- **FAISSService = tylko OpenAI** – usunięto fallbacki hashujące, serwis wymaga
  poprawnie ustawionego `SECOND_OPENAI`/`OPENAI_API_KEY`, raportuje brak
  konfiguracji i zapisuje snapshot dokumentów. Zapytania zwracają teraz również
  użyty kontekst (`context_preview`) i listę fragmentów.
- **Nowe API diagnostyczne** – endpoint `/api/news/faiss/status` udostępnia
  metadane indeksu (rozmiar, liczba wektorów, modele). Wszystkie akcje związane
  z News/RAG (test odbiorcy, wymuszenie wysyłki, ręczne budowanie indeksu,
  `/api/news/test-faiss`) mają twardszą walidację kluczy i informują, gdy brakuje
  indeksu lub uprawnień do OpenAI.
- **Panel „News po AI”** – rozbudowana karta statusowa pokazuje stan indeksu,
  modele i datę ostatniego odświeżenia; dodano szybki test promptu, listę
  fragmentów użytych w odpowiedzi oraz komunikaty o błędach prosto z API.
- **Zależności** – w `requirements.txt` pojawiły się pakiety
  `langchain-text-splitters` oraz `gunicorn`, co odzwierciedla rzeczywiste
  środowisko uruchomieniowe i aktualną integrację z LangChain 0.3.

### Kompatybilność i upgrade

- Przed budową indeksu FAISS ustaw `SECOND_OPENAI=sk-...`; brak klucza kończy się
  błędem już przy starcie serwisu.
- Jeśli masz własne automatyzacje wokół `/api/news/test-faiss`, możesz teraz
  korzystać z pola `results` i `context_preview`, aby pokazywać operatorom
  fragmenty źródłowe.
- Pozostałe moduły aplikacji (AI chat, auto-reply, webhooki Twilio) działają jak
  dotychczas – upgrade wymaga jedynie przeładowania frontendu i instalacji
  nowych zależności Pythona.

## ver3.0.0 (AI auto-reply & Twilio client cleanup)

### Podsumowanie

To wydanie wprowadza tryb AI auto-reply oparty o OpenAI, porządkuje klienta Twilio oraz czyści repozytorium z przypadkowo skomitowanego środowiska wirtualnego. System zachowuje dotychczasowe endpointy HTTP, ale sposób obsługi odpowiedzi SMS jest teraz ściślej zdefiniowany i bardziej przewidywalny.

### Najważniejsze zmiany

- Tryb **AI auto-reply**: gdy AI jest włączone, wszystkie przychodzące SMS-y są obsługiwane przez model OpenAI z wykorzystaniem historii rozmowy.
- Wzajemne wykluczenie trybów: AI auto-reply i klasyczny auto-reply nie mogą działać jednocześnie; AI ma pierwszeństwo.
- Refaktoryzacja klienta Twilio: spójne nazewnictwo (`twilio_client`), poprawne użycie `send_reply_to_inbound` dla odpowiedzi na wiadomości przychodzące.
- Uporządkowana dokumentacja: README opisuje dokładnie zachowanie AI, auto-reply i fallbackowego bota.
- Higiena repozytorium: usunięto katalog `.venv` z historii bieżącej gałęzi, dodano go do `.gitignore`.

### Kompatybilność i upgrade

- Brak zmian w publicznych endpointach HTTP – integracje mogą pozostać bez modyfikacji.
- Zachowanie odpowiedzi SMS może się zmienić, jeśli włączysz AI: odpowiedzi zaczną być generowane przez model OpenAI zamiast statycznego auto-reply.
- Zalecane jest odtworzenie środowiska wirtualnego lokalnie (poza repozytorium) zgodnie z instrukcjami w README.

## v1.2 (Database Reliability & Messaging Hardening)

### Podsumowanie

To wydanie koncentruje się na:
- zwiększeniu niezawodności bazy SQLite (wersjonowane migracje, indeksy),
- uporządkowaniu obsługi wiadomości (brak duplikatów po SID, spójne logowanie),
- bezpieczniejszym auto‑reply i przypomnieniach (brak retro‑odpowiedzi, poprawne numery nadawcy).

Release jest kompatybilny wstecznie, a migracje uruchamiają się automatycznie przy starcie aplikacji.

### Zmiany techniczne

- Dodano kontrolę wersji schematu przez `PRAGMA user_version` (`SCHEMA_VERSION = 3`).
- Nowe lub istniejące bazy są automatycznie podnoszone do aktualnego schematu w `_ensure_schema()`.
- Tabela `messages`:
  - `sid TEXT UNIQUE`,
  - indeksy: `idx_messages_created_at` (`created_at`), `idx_messages_direction_created_at` (`direction`, `created_at`).
- `upsert_message()`:
  - łączy rekordy z Twilio z placeholderami (`sid IS NULL`) po kierunku, numerach i czasie,
  - w razie kolizji `sid` aktualizuje istniejący rekord zamiast zgłaszać błąd `UNIQUE`.
- `insert_message()` przyjmuje `created_at`/`updated_at`, co pozwala wiernie odtwarzać czasy z Twilio.

### Auto‑reply

- Konfiguracja `auto_reply_config` przechowuje `enabled_since` w formacie ISO UTC.
- Worker auto‑reply porównuje `received_at` wiadomości z `enabled_since` i:
  - ignoruje wiadomości sprzed włączenia auto‑reply,
  - przetwarza tylko nowe inboundy, dzięki czemu nie ma „retro‑odpowiedzi”.
- Sync z Twilio (`_maybe_sync_messages`) nie kolejkuje auto‑reply dla historycznych wiadomości sprzed `enabled_since`.

### Przypomnienia (scheduler)

- Worker przypomnień:
  - wymusza użycie `TWILIO_DEFAULT_FROM` jako nadawcy; przy braku – pomija wysyłkę z logiem ostrzegawczym,
  - każdą wysłaną wiadomość zapisuje w `messages` jako outbound z poprawnym `from_number`,
  - przy błędzie zapisuje rekord ze statusem `failed` i szczegółem błędu.

### Kompatybilność i upgrade

- Brak zmian łamiących API/HTTP – UI i integracje pozostają bez zmian.
- Migracje schematu uruchamiają się automatycznie przy starcie aplikacji:
  - nowe instalacje dostają od razu schemat w wersji 3,
  - starsze bazy są bezpiecznie podnoszone (dodanie `enabled_since`, indeksów, aktualizacja `user_version`).

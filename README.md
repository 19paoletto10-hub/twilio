# Twilio Chat App

<div align="center">

![Version](https://img.shields.io/badge/version-3.2.9-blue.svg)
![Python](https://img.shields.io/badge/python-3.12+-green.svg)
![Flask](https://img.shields.io/badge/flask-3.x-red.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)
![Type Safety](https://img.shields.io/badge/pylance-0%20errors-brightgreen.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)

### 🚀 Enterprise-Grade SMS Communication Hub

**Panel WWW • AI Auto-Reply • Semantic Search (FAISS) • Multi-SMS Campaigns**

[🏃 Quick Start](#-5-minutowy-quick-start) • [📖 Dokumentacja](#-dokumentacja) • [🐳 Docker](#-docker) • [🔧 Troubleshooting](#-troubleshooting)

</div>

---

## 📋 Co to jest?

**Twilio Chat App** to kompletne rozwiązanie do zarządzania komunikacją SMS, które łączy:

| Moduł | Opis | Status |
|-------|------|--------|
| 📱 **Panel WWW** | Dashboard z historią, statystykami i czatem 1:1 | ✅ Production |
| 🤖 **AI Auto-Reply** | Inteligentne odpowiedzi przez OpenAI GPT | ✅ Production |
| 📰 **RAG/FAISS** | Baza wiedzy z semantic search dla komend `/news` | ✅ Production |
| 📨 **Multi-SMS** | Kampanie batch do wielu odbiorców | ✅ Production |
| 🔐 **Secrets Manager** | Hot-reload kluczy API bez restartu | ✅ Production |
| 🎧 **Listeners** | Interaktywne komendy SMS (`/news`, custom) | ✅ Production |

---

## ✨ Kluczowe wyróżniki

<table>
<tr>
<td width="50%">

### 🔒 Enterprise Quality
- **Type Safety** – zero błędów Pylance w strict mode
- **Design Patterns** – Railway-Oriented Programming, Circuit Breaker, Command Pattern
- **Defensive Programming** – walidacja na każdym poziomie z Composable Validators
- **Professional Docstrings** – pełna dokumentacja kodu
- **Error Handling** – graceful degradation bez crashy z Result Type

</td>
<td width="50%">

### ⚡ Developer Experience
- **5-minutowy setup** – od zera do działającej aplikacji
- **Hot Reload** – zmiany konfiguracji bez restartu
- **Docker Ready** – compose dla dev/prod/SSL
- **CI/CD** – GitHub Actions z auto-deploy

</td>
</tr>
<tr>
<td>

### 🧠 Inteligentna komunikacja
- **AI Context** – historia rozmów w kontekście GPT
- **Semantic Search** – FAISS embeddings dla /news
- **Smart Chunking** – auto-podział długich wiadomości
- **Deduplication** – ochrona przed duplikatami

</td>
<td>

### 📊 Operacyjna gotowość
- **Healthcheck API** – monitoring stanu systemu
- **Performance Monitoring** – @timed decorator, MetricsCollector, RateLimiter
- **Backup/Restore** – export ZIP z manifestem
- **Logging** – strukturalne logi z poziomami
- **Metrics** – statystyki w real-time z agregacją (avg, p50, p95)

</td>
</tr>
</table>

---

## 📚 Spis treści

<table>
<tr>
<td width="50%">

**🚀 Pierwsze kroki**
- [Quick Start (5 min)](#-5-minutowy-quick-start)
- [Konfiguracja .env](#konfiguracja-środowiska-env)
- [Docker](#uruchomienie-w-dockerze)
- [GitHub Codespaces](#uruchomienie-w-github-codespaces)

**📖 Funkcjonalność**
- [Panel WWW](#panel-www)
- [News / FAISS / RAG](#news--faiss--rag)
- [CLI](#cli--kontrola-z-konsoli)

</td>
<td width="50%">

**🔧 Operacje**
- [Troubleshooting](#-troubleshooting)
- [API Reference](#-api-quick-reference)
- [Runbook produkcyjny](#operacyjny-runbook-prod)
- [Backup i dane](#dane-i-backup)

**👨‍💻 Dla developerów**
- [Architektura](#architektura-i-komponenty)
- [Diagram systemu](#-diagram-architektury)
- [Przewodnik deweloperski](#dla-deweloperów)

</td>
</tr>
</table>

---

## 🏃 5-minutowy Quick Start

<table>
<tr>
<td width="33%">

**1️⃣ Instalacja**
```bash
git clone https://github.com/\
19paoletto10-hub/twilio.git
cd twilio

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

</td>
<td width="33%">

**2️⃣ Konfiguracja**
```bash
cp .env.example .env

# Edytuj .env:
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_DEFAULT_FROM=+48...
```

</td>
<td width="33%">

**3️⃣ Uruchomienie**
```bash
python run.py

# Panel:
# http://localhost:3000

# Health check:
curl localhost:3000/api/health
```

</td>
</tr>
</table>

> 💡 **Następny krok:** Skonfiguruj webhooki Twilio na `PUBLIC_BASE_URL/twilio/inbound` i `/twilio/status`

---

## 📋 TL;DR / kontekst biznesowy

| Aspekt | Opis |
|--------|------|
| **Cel** | Spójny hub SMS z panelem WWW, automatycznymi odpowiedziami (AI), dystrybucją newsów (RAG) |
| **Wartość** | Redukcja czasu obsługi klientów, broadcast podsumowań newsów, przewidywalne SLA |
| **Wymagania** | Konto Twilio, klucz OpenAI (opcjonalnie), Python 3.10+, Docker (opcjonalnie) |
| **Procesy** | Webhook Twilio → Worker auto-reply → Scheduler newsów → Panel do diagnostyki |

## 📖 Dokumentacja

<table>
<tr>
<td width="50%">

**📚 Przewodniki**
| Dokument | Opis |
|----------|------|
| [docker-guide.md](docs/docker-guide.md) | Docker od A do Z |
| [developer-guide.md](docs/developer-guide.md) | Architektura, API, DB |
| [architecture-notes.md](docs/architecture-notes.md) | Przegląd modułów |

</td>
<td width="50%">

**📋 Release**
| Dokument | Opis |
|----------|------|
| [README.html](README.html) | 🆕 Interaktywny HTML |
| [deploy/releases/](deploy/releases/) | Release notes (MD/HTML) |
| [CHANGELOG.md](CHANGELOG.md) | Historia zmian |

</td>
</tr>
</table>

**Skrypty:** `scripts/backup_db.sh` (backup SQLite) • `scripts/demo_send.sh` (test SMS) • `scripts/prepare_release_bundle.sh` (paczka release)

## 🌟 Wyróżniki produktu

<table>
<tr>
<td width="50%">

- 🔗 **Jedno źródło prawdy** – webhooki, panel i CLI korzystają z tej samej bazy SQLite
- 🔄 **Tryby odpowiedzi** – klasyczny template, AI GPT, fallback bot
- 📰 **RAG na sterydach** – scheduler newsów, scraper, FAISS, cross-category
- 💾 **Enterprise Backup** – eksport ZIP z manifestem, import z walidacją

</td>
<td width="50%">

- 🎧 **Listeners** – interaktywne komendy SMS (`/news [pytanie]`)
- 📨 **Multi-SMS** – kampanie batch z deduplikacją i statusami
- ✂️ **Smart Chunking** – auto-podział długich wiadomości (1500 znaków)
- 🐳 **Docker Ready** – compose dla dev/prod/SSL

</td>
</tr>
</table>

---

## 📝 Opis systemu

Aplikacja realizuje kompletny „hub SMS" dla konta Twilio: przyjmuje webhooki, zapisuje wiadomości w SQLite, prowadzi konwersacje 1:1 z panelu, obsługuje trzy tryby odpowiedzi (template, AI, bot) i cyklicznie wysyła newsy przez RAG/FAISS. System lekki (Flask + SQLite), architektura modularna i gotowa na produkcję.
Aplikacja realizuje kompletny „hub SMS" dla konta Twilio: przyjmuje webhooki, zapisuje wiadomości w SQLite, prowadzi konwersacje 1:1 z panelu, obsługuje trzy tryby odpowiedzi (template, AI, bot) i cyklicznie wysyła newsy przez RAG/FAISS. System lekki (Flask + SQLite), architektura modularna i gotowa na produkcję.

Najważniejsze moduły:

- `app/__init__.py` – fabryka Flask (`create_app`): ładuje konfigurację z `.env`, inicjalizuje klienta Twilio, bazę SQLite i uruchamia workery (auto‑reply, przypomnienia, **multi‑sms**).
- `app/patterns.py` – **Railway-Oriented Programming**: Result Type (Success/Failure), Retry z exponential backoff, Circuit Breaker, TTL Cache, Processor Chain.
- `app/message_handler.py` – **Clean Architecture**: Command Pattern, Strategy Pattern, Value Objects (PhoneNumber, InboundMessage, ReplyResult), Composable Validators, Dependency Injection.
- `app/performance.py` – **Monitoring & Profiling**: @timed decorator, MetricsCollector, RateLimiter (token bucket), Lazy initialization, timed_block context manager.
- `app/webhooks.py` – główny blueprint HTTP:
  - webhooki Twilio (`/twilio/inbound`, `/twilio/status`),
  - REST API do wiadomości, AI, auto‑reply,
  - API News/FAISS (scraping, budowa indeksu, test zapytań, lista oraz wysyłka do odbiorców),
  - operacje na plikach scrapów i indeksie (delete, wybór aktywnego indeksu).
- `app/ui.py` + `templates/` + `static/` – panel www (dashboard, czat, zakładki AI, Auto‑reply, News/FAISS).
- `app/database.py` – definicje tabel (wiadomości, konfiguracja AI/auto‑reply, scheduler przypomnień) oraz helpery do zapisu/odczytu. **Optymalizacje v3.2.9**: WAL Mode, Query Cache, Transaction Context Manager, @db_operation decorator.
- `app/twilio_client.py` – cienka warstwa nad `twilio.rest.Client` (wysyłka SMS, odpowiedzi na inbound, integracja z Messaging Service).
- `app/ai_service.py` + `app/chat_logic.py` – generowanie odpowiedzi AI (OpenAI) oraz fallbackowy silnik „echo / keywords”.
- `app/auto_reply.py` – worker, który konsumuje kolejkę auto‑reply i wysyła odpowiedzi (klasyczne lub AI, zależnie od konfiguracji).
- `app/reminder.py` – worker przypomnień SMS oparty o tabelę `scheduled_messages`.
- `app/multi_sms.py` – worker batchowy Multi‑SMS, który rezerwuje zadania z SQLite, wysyła każdy numer przez Twilio i aktualizuje licznik sukcesów/błędów.
- `app/faiss_service.py` – integracja z FAISS i embeddings:
  - budowa indeksu z plików scrapów,
  - wyszukiwanie semantyczne,
  - odpowiedzi RAG z użyciem `NewsOpenAIService` (OpenAI, modele z `SECOND_MODEL`).
  - **Optymalizacje v3.2.9**: Embedding Cache (LRU + TTL 1h), Batched Embeddings, Cache Stats.
- `app/scraper_service.py` – scraper wybranych serwisów newsowych, generujący teksty wejściowe do FAISS.
- `app/validators.py` – **walidacja wejść v3.2.9**: ValidationResult Type (Success/Failure), Composable Validator (fluent API), validate_json_payload, batch validation z skip_invalid.

Dane:

- baza SQLite: `data/app.db`,
- indeks FAISS: katalog `X1_data/faiss_openai_index/`,
- snapshot dokumentów RAG: `X1_data/documents.json`,
- pliki scrapów (surowe teksty / JSON): `X1_data/business_insider_scrapes/`.


### Jak zdobyć i ustawić klucz OpenAI (SECOND_OPENAI)

1. Wejdź na https://platform.openai.com/api-keys.
2. Utwórz nowy **Secret key**.
3. Wklej do `.env`:

```ini
SECOND_OPENAI=sk-...
SECOND_MODEL=gpt-4o-mini
```

4. Zrestartuj aplikację / kontener.
5. W panelu (zakładka AI / News) użyj przycisku „Przetestuj …”, aby upewnić się, że połączenie działa.

Tipy operacyjne:

- `TWILIO_VALIDATE_SIGNATURE=false` tylko w dev/tunelu; w prod zostaw `true`.
- `APP_DEBUG=false` w prod, `LOG_LEVEL=info` lub `warning` aby ograniczyć hałas logów.
- `SECOND_OPENAI` jest używane do embeddings/RAG; `OPENAI_API_KEY`/`AI_*` dla czatu AI. Można ustawić oba, ale nie są współdzielone.
- Ścieżki danych (`DB_PATH`, katalog `X1_data`) mogą być względne (w repo) lub absolutne (np. montowane wolumeny w Docker).

## Dane i backup

- Baza: `data/app.db` (SQLite). Backup: snapshot pliku + lock w czasie kopiowania (np. `sqlite3 .backup`).
- Kanoniczny store artykułów: `X1_data/articles.jsonl` (deduplikacja po URL + hash treści, źródło prawdy dla FAISS/RAG).
- Snapshot chunków: `X1_data/documents.jsonl` (preferowane) oraz `X1_data/documents.json` (legacy) – pozwalają odbudować indeks nawet bez plików binarnych FAISS.
- Indeks FAISS: `X1_data/faiss_openai_index/` (`index.faiss` lub `index.npz` + `docs.json`).
- Surowe scrapes: `X1_data/business_insider_scrapes/*.txt|json`.
- Zalecany backup prod: cały `X1_data/` + `data/app.db`. Przywrócenie: odtworzyć katalogi, uruchomić aplikację, sprawdzić `/api/news/test-faiss`.

### Backup FAISS (zip + manifest)

- `GET /api/news/faiss/export` generuje zip zawierający komplet wymaganych plików (indeks FAISS, snapshot dokumentów, `news_config.json`) wraz z `manifest.json`. Upload odbywa się z poziomu panelu (zakładka News) lub przez cURL.
- `POST /api/news/faiss/import` przyjmuje archiwum `.zip` (limit 250 MB), waliduje manifest i atomowo odtwarza pliki (najpierw do katalogu tymczasowego, potem `shutil.move`).
- `GET /api/news/faiss/status` zwraca kondycję indeksu (liczba wektorów, model embeddings/chat) oraz kompletność backupu (`backup_ready`).
- `DELETE /api/news/indices/faiss_openai_index` usuwa wszystkie artefakty FAISS i dokumenty (również `documents.json(l)` oraz surowe snapshoty), a w odpowiedzi zwraca podsumowanie `removed/missing/failed` – UI pokazuje je w toastach.
- Panel w zakładce News posiada dwa przyciski: „Eksportuj backup” (pobiera zip) oraz „Wgraj backup” (uploaduje poprzez `FormData archive`).

---

## Uruchomienie w Dockerze

> 📚 **Pełna dokumentacja Docker:** [docs/docker-guide.md](docs/docker-guide.md) – kompletny przewodnik od instalacji po produkcję z SSL.

### Quick Start

```bash
# 1. Skopiuj i uzupełnij konfigurację
cp .env.example .env   # lub utwórz .env z wymaganymi zmiennymi

# 2. Utwórz katalogi na dane
mkdir -p data X1_data

# 3. Uruchom (development)
make compose-up        # lub: docker compose up --build

# 4. Otwórz przeglądarkę
# → http://localhost:3000
```

### Obraz lokalny

```bash
docker build -t twilio-chat:latest .

docker run --rm -it \
  -p 3000:3000 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/X1_data:/app/X1_data \
  twilio-chat:latest
```

### docker-compose (dev / prod / SSL)

| Komenda | Środowisko | Opis |
|---------|------------|------|
| `make compose-up` | Development | Port 3000, logi na konsoli |
| `make compose-prod` | Production | NGINX na porcie 80 |
| `make compose-ssl` | Production + SSL | NGINX + Let's Encrypt (porty 80+443) |

```bash
# Development
make compose-up

# Production (NGINX reverse proxy)
make compose-prod

# Production z SSL/TLS
make compose-ssl
```

### Przydatne komendy Docker

```bash
make help              # Wszystkie dostępne komendy
make logs              # Logi kontenerów (na żywo)
make stop              # Zatrzymaj kontenery
make health            # Sprawdź /api/health
make backup            # Backup bazy SQLite
make restore F=...     # Przywróć backup
make clean             # Usuń kontenery i obrazy
```

### Wolumeny (persystencja danych)

Przy pracy z Dockerem **koniecznie** montuj:

| Wolumen | Zawartość |
|---------|-----------|
| `./data:/app/data` | Baza SQLite (`app.db`) |
| `./X1_data:/app/X1_data` | Indeks FAISS, dokumenty RAG |

Dzięki temu restart kontenerów nie kasuje historii wiadomości ani indeksu.

### CI/CD (GitHub Actions)

Repozytorium zawiera workflow [.github/workflows/docker-build.yml](.github/workflows/docker-build.yml), który:

- Automatycznie buduje obraz przy push do `main` lub tagu `ver*`
- Publikuje do GitHub Container Registry (GHCR)
- Testuje obraz (health check)
- Opcjonalnie deployuje na serwer (wymaga konfiguracji sekretów)

```bash
# Użycie opublikowanego obrazu:
docker pull ghcr.io/19paoletto10-hub/twilio:latest
```

---

## Uruchomienie w GitHub Codespaces

1. Utwórz Codespace na tym repozytorium.
2. W katalogu projektu dodaj plik `.env` (warto użyć Secrets Codespaces/Repo).
3. W terminalu Codespace:

```bash
pip install -r requirements.txt
python run.py
```

4. W zakładce „Ports” wystaw port 3000 jako **publiczny**.
5. Skopiuj publiczny adres URL i ustaw go jako `PUBLIC_BASE_URL` w `.env`.
6. W konsoli Twilio skonfiguruj webhooki na `https://PUBLIC_BASE_URL/twilio/inbound` oraz `https://PUBLIC_BASE_URL/twilio/status`.

---

## Panel WWW

Panel jest responsywny (Bootstrap 5) i składa się z kilku głównych widoków:

- **Dashboard**
  - skrócone statystyki,
  - szybka wysyłka SMS,
  - lista ostatnich wiadomości (z filtrami po kierunku/statusie),
  - auto‑odświeżanie.

- **Widok czatu** (`/chat/<numer>`)
  - pełna historia konwersacji z jednym numerem,
  - formularz odpowiedzi,
  - informacja o statusach dostarczenia i ewentualnych błędach z Twilio.

- **Zakładka „Auto‑reply”**
  - przełącznik włączenia/wyłączenia klasycznego auto‑reply,
  - edycja treści szablonu,
  - integracja z webhookiem – worker `auto_reply` odbiera i wysyła odpowiedzi.

- **Zakładka „AI”**
  - konfiguracja OpenAI (model, temperatura, system prompt),
  - numer docelowy AI (`AI_TARGET_NUMBER`),
  - przycisk „Przetestuj połączenie” – prośba do API `/api/ai/test` i podgląd odpowiedzi.

- **Zakładka „News / FAISS”**
  - **Dynamiczny postęp skrapowania** – real-time streaming SSE z wizualnymi statusami kategorii (⚪ oczekuje, 🔄 w trakcie, ✅ sukces, ❌ błąd)
  - **Przycisk „Zatrzymaj"** – przerywa skrapowanie w dowolnym momencie
  - **Kafelki kategorii** – eleganckie karty z ikoną, rozmiarem i datą (tylko pliki .txt)
  - **Profesjonalny podgląd** – numerowane artykuły z pogrubionym tytułem, bez separatorów
  - **Przycisk „Usuń wszystkie"** – masowe kasowanie zeskrapowanych plików
  - Przyciski „Pobierz i zbuduj / Zbuduj indeks FAISS / Test FAISS"
  - Zarządzanie listą odbiorców newsów (numer, prompt, godzina, ON/OFF, Wyślij ręcznie)
  - Sekcja „Backup FAISS" z przyciskiem pobrania zipa oraz uploaderem przywracającym indeks/dokumenty

- **Zakładka „Multi‑SMS”**
  - formularz batch: wklej numery (free‑form, jeden na linię lub przecinki), treść wiadomości, przycisk „Wyślij batch”,
  - worker w tle obsługuje kolejkę – karta historii pokazuje status partii, licznik sukcesów/błędów i rozwijaną listę odbiorców z indywidualnymi statusami.

Uwaga UX: w historii wiadomości kolumna „Treść” ma stałą wysokość wierszy – dłuższe teksty są skracane (dla czytelności tabeli).

---

## News / FAISS / RAG

### Pliki i indeks

- kanoniczny store artykułów: `X1_data/articles.jsonl` (per-URL metadane, dedup i hash treści wykorzystywany przez FAISS),
- snapshot chunków: `X1_data/documents.jsonl` (preferowany) + `X1_data/documents.json` (legacy preview/debug),
- surowe źródła tekstów: `X1_data/business_insider_scrapes/` (`.txt` i `.json` per kategoria),
- indeks FAISS / MinimalVectorStore: `X1_data/faiss_openai_index/` (`index.faiss` / `index.npz` + `docs.json`).

Aplikacja potrafi:

1. **Scrapować z live progressem** – streaming SSE przez `/api/news/scrape/stream` pokazuje dynamicznie statusy kategorii; przycisk „Zatrzymaj" kończy proces w dowolnym momencie.
2. **Zbudować indeks** – automatycznie po scrapowaniu lub ręcznie przez `/api/news/indices/build`.
3. **Testować zapytania** – endpoint `/api/news/test-faiss`, w UI: pole zapytania + wynik (liczba trafień, odpowiedź modelu).
4. **Zarządzać plikami** – usuwać pojedyncze pliki scrapów, usunąć wszystkie pliki jednym kliknięciem (`DELETE /api/news/files`), lub cały indeks z poziomu panelu.
5. **Profesjonalny podgląd** – kafelki plików .txt z eleganckim podglądem artykułów (numerowanie, formatowanie, bez separatorów).
6. **Eksportować / importować backupy** – `GET /api/news/faiss/export` buduje zip z manifestem, a `POST /api/news/faiss/import` przywraca pliki (limit 250 MB, walidacja obecności wymaganych pozycji). `GET /api/news/faiss/status` raportuje gotowość backupu, a `DELETE /api/news/indices/faiss_openai_index` czyści całą bazę FAISS wraz z dokumentami.

### Limity długości SMS (Twilio) i dzielenie wiadomości

Twilio ma twardy limit rozmiaru pojedynczego SMS (w praktyce błąd pojawia się przy ok. 1600 znakach sklejonej treści).
Żeby uniknąć awarii dla dłuższych podsumowań News/RAG oraz odpowiedzi AI, aplikacja stosuje
wewnętrzny limit bezpieczeństwa 1500 znaków na część i wysyła tekst jako kilka SMS-ów.

Implementacja:

- dzielenie tekstu: `app/message_utils.py` (`MAX_SMS_CHARS = 1500`, `split_sms_chunks()`),
- wysyłka wieloczęściowa: `app/twilio_client.py` (`TwilioService.send_chunked_sms()`),
- użycie: News (ręczny send + scheduler) oraz AI auto‑reply/AI send.

`ScraperService` pilnuje, aby kategorie były rozłączne – link musi zaczynać się prefiksem ścieżki kategorii (np. `/technologie/`), dzięki czemu pliki `.json/.txt` nie dublują się między sekcjami.

#### Nowości w wersji 3.0.6

- Panel News prezentuje czas utworzenia indeksów w lokalnej strefie (te same helpery co w historii wiadomości), dzięki czemu dane w tabeli „Bazy FAISS” są spójne z resztą UI.
- Release utrwala też nową sekcję backupową w README oraz szczegółowe opisy API w dokumentacji klienta.

### Tryb podsumowania kategorii

System wspiera dwa tryby generowania podsumowania:

- **STANDARD** – klasyczne streszczenie z top‑K fragmentów niezależnie od kategorii.
- **ALL‑CATEGORIES** – wymusza pobranie fragmentów z każdej kategorii i układa wynik sekcjami „kategoria → bullets”.

Szczegóły techniczne i operacyjne:

- `FAISSService` udostępnia tryb `answer_query_all_categories` (oraz wyszukiwanie cross‑category), wykorzystywany przez scheduler i API.
- Tryb jest sterowany flagą `use_all_categories`:
  - w UI (zakładka News): checkbox w **teście FAISS** oraz w formularzu **dodawania/edycji odbiorcy**,
  - w API (np. `/api/news/test-faiss`, `/api/news/recipients`): pole `use_all_categories` w payload.
- Domyślnie `use_all_categories` jest włączone (dla testu FAISS i nowych odbiorców), aby dzienne powiadomienia zawsze obejmowały wszystkie kategorie.
- Prompt jest rozdzielony na wariant STANDARD i ALL‑CATEGORIES (dzięki temu operator ma spójne wyniki bez ręcznego „przepisywania” promptu).
- Fallback (bez LLM) pozostaje aktywny – gdy brakuje klucza lub indeksu, użytkownik dostaje informacyjny listing kategorii/fragmentów.

### Odbudowa indeksu FAISS

Kod `FAISSService` został napisany tak, aby odtworzenie indeksu było przewidywalne i bezpieczne:

- przy zapisie (`save_faiss_index`) tworzony jest komplet plików (`index.faiss` lub `index.npz` + `docs.json` oraz snapshot `documents.jsonl`),
- przy odczycie (`load_faiss_index`):
  1. najpierw ładowany jest pełny indeks FAISS, jeśli istnieje,
  2. jeśli jest tylko `index.npz`, używany jest `MinimalVectorStore`,
  3. jeśli istnieje samo `docs.json` lub `documents.jsonl` – indeks jest **rekonstruowany od zera** wyłącznie z dokumentów,
  4. dodatkowo, jeśli brakuje plików dla `faiss_openai_index`, ale istnieje globalny snapshot `X1_data/documents.jsonl` / `X1_data/documents.json`, serwis spróbuje odbudować indeks na jego podstawie.

W praktyce: **backup katalogu `X1_data/` wystarcza do pełnej odbudowy indeksu**.

---

## CLI – kontrola z konsoli

Aplikacja ma prosty, ale bardzo użyteczny interfejs CLI oparty o `manage.py`.

```bash
python manage.py send --to +48123123123 --body "Test z CLI" --use-messaging-service

python manage.py ai-send \
  --to +48123123123 \
  --latest "Treść ostatniej wiadomości" \
  --history-limit 30 \
  --use-messaging-service
```

- `send` – wysyła pojedynczy SMS:
  - `--to` – numer odbiorcy (E.164),
  - `--body` – treść wiadomości,
  - `--use-messaging-service` – jeśli ustawione, użyje `TWILIO_MESSAGING_SERVICE_SID` zamiast `TWILIO_DEFAULT_FROM`.

- `ai-send` – generuje treść odpowiedzi z użyciem `AIResponder` i wysyła ją SMS‑em:
  - `--to` – numer odbiorcy; jeśli brak, używany jest numer z konfiguracji AI,
  - `--latest` – (opcjonalnie) ostatnia wiadomość użytkownika, przekazana do modelu,
  - `--history-limit` – ile ostatnich wiadomości uwzględnić przy budowaniu kontekstu,
  - `--use-messaging-service` – jak wyżej.

CLI korzysta z pełnej konfiguracji aplikacji (Flask app context), więc działa w ten sam sposób, co panel / webhooki.

## Operacyjny runbook (prod)

1. **Provision**
  - Przygotuj host z Docker + docker-compose (v2) i dostępem do internetu (Twilio, OpenAI).
  - Utwórz katalog na dane: `data/`, `X1_data/` (z backupu lub pusty).
2. **Konfiguracja**
  - Skopiuj `.env` (bez sekretów w repo). Ustaw: `APP_DEBUG=false`, `TWILIO_VALIDATE_SIGNATURE=true`, `PUBLIC_BASE_URL=https://<domena>`.
  - Zweryfikuj `TWILIO_DEFAULT_FROM` **lub** `TWILIO_MESSAGING_SERVICE_SID` (wymagane do wysyłki).
  - Uzupełnij `SECOND_OPENAI` (embeddings/RAG) i `AI_*`/`OPENAI_API_KEY` (czat AI) w razie potrzeby.
3. **Uruchomienie**
  - Dev/test: `make compose-up` (mapuje port 3000).
  - Prod: `make compose-prod` (daemon). Wolumeny: `./data:/app/data`, `./X1_data:/app/X1_data`.
  - Healthcheck: `curl http://<host>:3000/api/health` (status ok/env/openai_enabled).
4. **Po starcie**
  - W konsoli Twilio ustaw webhooki: `https://PUBLIC_BASE_URL/twilio/inbound`, `https://PUBLIC_BASE_URL/twilio/status`.
  - Wejdź do panelu: skonfiguruj AI/Auto-reply/News, wykonaj testy: `/api/ai/test`, `/api/news/test`, `/api/news/test-faiss`.
5. **Monitoring i logi**
  - Logi aplikacji: `docker compose logs -f web` (domyślny serwis w compose). Szukaj `Inbound webhook hit`, `Message status update`, `FAISS`.
    - Workery uruchamiane w tym samym procesie Flask (auto-reply queue, reminders, news scheduler, multi-sms batch) – logi wspólne.
6. **Backup/restore**
  - Backup plików: `data/app.db`, `X1_data/`.
  - Restore: odtwórz katalogi, uruchom kontener, sprawdź `/api/news/test-faiss` oraz widoczność historii w panelu.
7. **Awaryjne kroki**
  - Brak wysyłki SMS: sprawdź, czy `TWILIO_DEFAULT_FROM` lub Messaging Service jest ustawione; zweryfikuj logi statusów Twilio.
  - Brak wyników RAG: zbuduj indeks `POST /api/news/indices/build` lub uruchom `Scrape` w panelu.
  - Kolejka auto-reply: przy braku odpowiedzi upewnij się, że AI/auto-reply jest włączone i inbound trafia do `/twilio/inbound` (logi + dashboard).

---

## Dla deweloperów

### Struktura projektu

- `app/` – kod aplikacji Flask (blueprinty, serwisy, integracje):
  - **Nowe w v3.2.9**:
    - `patterns.py` – Railway-Oriented Programming, Result Type, Retry, Circuit Breaker
    - `message_handler.py` – Clean Architecture, Command Pattern, Strategy Pattern
    - `performance.py` – monitoring wydajności (@timed, MetricsCollector, RateLimiter)
  - **Zoptymalizowane w v3.2.9**:
    - `database.py` – WAL Mode, Query Cache, Transaction Context Manager
    - `faiss_service.py` – Embedding Cache (LRU + TTL), Batched Embeddings
    - `validators.py` – ValidationResult Type, Composable Validator (fluent API)
- `templates/` – widoki Jinja2,
- `static/` – JS + CSS (dashboard, chat, news manager),
- `data/` – baza SQLite,
- `X1_data/` – indeks FAISS + pliki wejściowe dla RAG,
- `deploy/` – pliki pomocnicze (nginx, statyczna dokumentacja),
- `scripts/` – skrypty narzędziowe (np. generowanie PDF‑ów, demo wysyłki).

### Środowisko dev

1. Utwórz wirtualne środowisko (`venv` lub `.venv`).
2. Zainstaluj zależności z `requirements.txt`.
3. Uruchamiaj w trybie dev `APP_DEBUG=true`, port 3000.
4. Do szybkiego startu możesz użyć:

```bash
make run-dev
```

### Dodawanie nowych endpointów / funkcji

- nowe endpointy HTTP dodawaj do `app/webhooks.py` lub osobnych blueprintów,
- logikę biznesową trzymaj w serwisach (`app/ai_service.py`, `app/faiss_service.py`, itp.),
- DB: rozbudowuj `app/database.py` – tam są helpery do migracji / modeli,
- UI: widoki w `templates/*.html`, logika frontu w `static/js/*.js`.

### Styl i jakość kodu

- Python: PEP‑8, bez nadmiernej magii, dużo jawnych logów przy obsłudze błędów integracji (Twilio, OpenAI).
- Wyjątki z zewnętrznych serwisów zawsze logujemy (z `exc_info=True`) i zwracamy bezpieczny komunikat użytkownikowi.
- Wszędzie, gdzie to możliwe, moduły są odporne na brak kluczy API – zamiast się wywrócić, przechodzą w tryb „no‑LLM” z czytelną informacją w odpowiedzi.

---

## 🔧 Troubleshooting

<details>
<summary><strong>❌ Webhook zwraca 403 Forbidden</strong></summary>

**Przyczyna:** Twilio signature validation jest włączona, ale podpis nie pasuje.

```bash
# Development - wyłącz walidację
TWILIO_VALIDATE_SIGNATURE=false

# Production - ustaw poprawny PUBLIC_BASE_URL
PUBLIC_BASE_URL=https://twoja-domena.com
```

**Checklist:**
- ✅ Czy `PUBLIC_BASE_URL` zgadza się z adresem webhooków w konsoli Twilio?
- ✅ Czy używasz HTTPS w produkcji?
- ✅ Czy ngrok/tunnel URL jest aktualny?

</details>

<details>
<summary><strong>❌ AI nie odpowiada na SMS</strong></summary>

**Checklist:**
1. ✅ Czy AI jest włączone w panelu → zakładka AI?
2. ✅ Czy `OPENAI_API_KEY` jest ustawiony w `.env`?
3. ✅ Czy `AI_TARGET_NUMBER` pasuje do numeru odbiorcy?
4. ✅ Sprawdź logi: `docker compose logs -f | grep -i ai`

**Test połączenia:**
```bash
curl -X POST http://localhost:3000/api/ai/test
```

</details>

<details>
<summary><strong>❌ /news nie zwraca wyników</strong></summary>

**Przyczyna:** Indeks FAISS nie jest zbudowany lub jest pusty.

**Rozwiązanie:**
1. Przejdź do panelu → zakładka **News**
2. Kliknij **"Pobierz i zbuduj"**
3. Poczekaj na zakończenie (progress bar)
4. Przetestuj w polu "Test FAISS"

**API test:**
```bash
curl -X POST http://localhost:3000/api/news/test-faiss \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

</details>

<details>
<summary><strong>❌ SMS nie są wysyłane</strong></summary>

**Checklist:**
- ✅ `TWILIO_ACCOUNT_SID` i `TWILIO_AUTH_TOKEN` poprawne
- ✅ `TWILIO_DEFAULT_FROM` w formacie E.164 (`+48123456789`)
- ✅ Lub `TWILIO_MESSAGING_SERVICE_SID` ustawiony
- ✅ Sprawdź saldo na [console.twilio.com](https://console.twilio.com)

**Test wysyłki:**
```bash
python manage.py send --to +48123456789 --body "Test"
```

</details>

<details>
<summary><strong>❌ Baza danych pusta po restarcie Docker</strong></summary>

**Przyczyna:** Wolumeny nie są zamontowane.

**Rozwiązanie:** Dodaj w `docker-compose.yml`:
```yaml
volumes:
  - ./data:/app/data        # Baza SQLite
  - ./X1_data:/app/X1_data  # Indeks FAISS
```

</details>

<details>
<summary><strong>❌ Port 3000 zajęty</strong></summary>

```bash
# Znajdź proces
lsof -i :3000

# Lub zmień port w .env
APP_PORT=3001
```

</details>

---

## 📊 API Quick Reference

| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/api/health` | Status systemu i healthcheck |
| `GET` | `/api/messages` | Lista wiadomości z filtrowaniem |
| `POST` | `/api/messages/send` | Wyślij pojedynczy SMS |
| `GET` | `/api/ai/config` | Konfiguracja AI auto-reply |
| `POST` | `/api/ai/test` | Test połączenia z OpenAI |
| `GET` | `/api/listeners` | Lista aktywnych listenerów |
| `POST` | `/api/news/indices/build` | Buduj indeks FAISS |
| `POST` | `/api/news/test-faiss` | Test zapytania RAG |
| `GET` | `/api/news/faiss/export` | Eksport backup (ZIP) |
| `POST` | `/api/news/faiss/import` | Import backup |
| `GET` | `/api/news/faiss/status` | Status indeksu FAISS |

Szczegółowa dokumentacja API: [docs/developer-guide.md](docs/developer-guide.md)

---

## 🏛️ Diagram architektury

```
┌─────────────────────────────────────────────────────────────────┐
│                         TWILIO CLOUD                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Inbound SMS │  │ Status Hook │  │ Messaging Service       │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────────┘
          │                │                     │
          ▼                ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FLASK APPLICATION                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    webhooks.py                              ││
│  │  /twilio/inbound  │  /twilio/status  │  /api/*             ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                  │
│  ┌───────────┬───────────┬───┴───────┬─────────────┐           │
│  │           │           │           │             │           │
│  ▼           ▼           ▼           ▼             ▼           │
│ ┌─────┐   ┌─────┐   ┌─────────┐   ┌─────┐   ┌──────────┐      │
│ │ AI  │   │Auto │   │Listeners│   │News │   │ Multi    │      │
│ │Reply│   │Reply│   │ /news   │   │Sched│   │ SMS      │      │
│ └──┬──┘   └──┬──┘   └────┬────┘   └──┬──┘   └────┬─────┘      │
│    │         │           │           │           │             │
│    └─────────┴───────────┴───────────┴───────────┘             │
│                          │                                      │
│  ┌───────────────────────┴────────────────────────────────────┐│
│  │              Design Patterns & Core Services               ││
│  │  • patterns.py (Result, Retry, Circuit Breaker)           ││
│  │  • message_handler.py (Command, Strategy, Value Objects)  ││
│  │  • performance.py (@timed, Metrics, RateLimiter)          ││
│  └─────────────────────────────────────────────────────────────┘│
│                          │                                      │
│  ┌───────────────────────┴────────────────────────────────────┐│
│  │                    twilio_client.py                        ││
│  │  send_message()  │  send_chunked_sms()  │  send_reply()   ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
┌─────────────────────┐      ┌────────────────────────┐
│    SQLite (data/)   │      │   FAISS (X1_data/)     │
│  ├── messages       │      │  ├── index.faiss       │
│  ├── ai_config      │      │  ├── documents.jsonl   │
│  ├── listeners      │      │  └── articles.jsonl    │
│  └── multi_sms      │      │  + Embedding Cache     │
└─────────────────────┘      └────────────────────────┘
```

---

## 🤝 Wsparcie i społeczność

- 📖 **Dokumentacja HTML:** [README.html](README.html) - responsywna wersja z interaktywnym UI
- 🐛 **Issues:** [github.com/19paoletto10-hub/twilio/issues](https://github.com/19paoletto10-hub/twilio/issues)
- 📋 **Releases:** [github.com/19paoletto10-hub/twilio/releases](https://github.com/19paoletto10-hub/twilio/releases)
- 📜 **Changelog:** [CHANGELOG.md](CHANGELOG.md)

---

<div align="center">

**Made with ❤️ by [19paoletto10-hub](https://github.com/19paoletto10-hub)**

© 2025 Twilio Chat App • MIT License

</div>


# Twilio Chat App

> Produkcyjny serwer SMS oparty o Flask + Twilio, z panelem www, AI auto‑reply i wyszukiwaniem semantycznym (FAISS). Dokument napisany z perspektywy twórcy i dewelopera, który ma to realnie utrzymywać.

---

## Spis treści
- [TL;DR / kontekst biznesowy](#tldr--kontekst-biznesowy)
- [Opis systemu](#opis-systemu)
- [Architektura i komponenty](#architektura-i-komponenty)
- [Szybki start (lokalnie)](#szybki-start-lokalnie)
- [Uruchomienie w Dockerze](#uruchomienie-w-dockerze)
- [Uruchomienie w GitHub Codespaces](#uruchomienie-w-github-codespaces)
- [Konfiguracja środowiska (.env)](#konfiguracja-środowiska-env)
- [Dane i backup](#dane-i-backup)
- [Panel WWW](#panel-www)
- [News / FAISS / RAG](#news--faiss--rag)
- [CLI – kontrola z konsoli](#cli--kontrola-z-konsoli)
- [Operacyjny runbook (prod)](#operacyjny-runbook-prod)
- [Dla deweloperów](#dla-deweloperów)
- [Debugowanie i dobre praktyki](#debugowanie-i-dobre-praktyki)

---

## TL;DR / kontekst biznesowy

- Cel: spójny hub SMS (i WhatsApp, jeśli numer Twilio to wspiera) z prostym panelem www, automatycznymi odpowiedziami (szablon + AI), cykliczną dystrybucją newsów i prostym RAG opartym o lokalny FAISS.
- Wartość: redukcja czasu obsługi klientów, możliwość szybkiego broadcastu streszczeń newsów, przewidywalne SLA dzięki workerom i SQLite (brak zewnętrznych baz).
- Wymagania: konto Twilio (numery / Messaging Service), klucz OpenAI (dla AI i embeddings), Python 3.10+, sieć z dostępem do platform Twilio i OpenAI.
- Kluczowe procesy: webhook inbound/status Twilio, worker auto-reply, worker przypomnień, scheduler newsów (RAG + SMS), panel do operacji ręcznych i diagnostyki.

## Opis systemu

Aplikacja realizuje kompletny „hub SMS” dla jednego konta Twilio:

- przyjmuje webhooki z Twilio (`/twilio/inbound`, `/twilio/status`),
- zapisuje wszystkie wiadomości w SQLite,
- pozwala z panelu www prowadzić konwersacje 1:1,
- obsługuje trzy tryby odpowiedzi: klasyczny auto‑reply, AI auto‑reply (OpenAI) oraz prostego chat‑bota,
- potrafi cyklicznie wysyłać newsy / podsumowania (RAG) opierając się o lokalny indeks FAISS.

System jest „lekki” (Flask + SQLite), ale architektura jest modularna i gotowa na produkcję (Docker, docker‑compose, osobne workery, logowanie).

---

## Architektura i komponenty

Najważniejsze moduły:

- `app/__init__.py` – fabryka Flask (`create_app`): ładuje konfigurację z `.env`, inicjalizuje klienta Twilio, bazę SQLite i uruchamia workery (auto‑reply, przypomnienia).
- `app/webhooks.py` – główny blueprint HTTP:
  - webhooki Twilio (`/twilio/inbound`, `/twilio/status`),
  - REST API do wiadomości, AI, auto‑reply,
  - API News/FAISS (scraping, budowa indeksu, test zapytań, lista oraz wysyłka do odbiorców),
  - operacje na plikach scrapów i indeksie (delete, wybór aktywnego indeksu).
- `app/ui.py` + `templates/` + `static/` – panel www (dashboard, czat, zakładki AI, Auto‑reply, News/FAISS).
- `app/database.py` – definicje tabel (wiadomości, konfiguracja AI/auto‑reply, scheduler przypomnień) oraz helpery do zapisu/odczytu.
- `app/twilio_client.py` – cienka warstwa nad `twilio.rest.Client` (wysyłka SMS, odpowiedzi na inbound, integracja z Messaging Service).
- `app/ai_service.py` + `app/chat_logic.py` – generowanie odpowiedzi AI (OpenAI) oraz fallbackowy silnik „echo / keywords”.
- `app/auto_reply.py` – worker, który konsumuje kolejkę auto‑reply i wysyła odpowiedzi (klasyczne lub AI, zależnie od konfiguracji).
- `app/reminder.py` – worker przypomnień SMS oparty o tabelę `scheduled_messages`.
- `app/faiss_service.py` – integracja z FAISS i embeddings:
  - budowa indeksu z plików scrapów,
  - wyszukiwanie semantyczne,
  - odpowiedzi RAG z użyciem `NewsOpenAIService` (OpenAI, modele z `SECOND_MODEL`).
- `app/scraper_service.py` – scraper wybranych serwisów newsowych, generujący teksty wejściowe do FAISS.

Dane:

- baza SQLite: `data/app.db`,
- indeks FAISS: katalog `X1_data/faiss_openai_index/`,
- snapshot dokumentów RAG: `X1_data/documents.json`,
- pliki scrapów (surowe teksty / JSON): `X1_data/business_insider_scrapes/`.

---

## Szybki start (lokalnie)

Minimalne wymagania (workstation / dev):

- Python 3.10+,
- konto Twilio z numerem SMS lub Messaging Service,
- (opcjonalnie) konto OpenAI z aktywnym kluczem API dla AI / embeddings.

Procedura:

```bash
# 1) środowisko
python -m venv venv
source venv/bin/activate              # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                  # wypełnij wartości obowiązkowe

# 2) uruchomienie w dev
python run.py                         # lub: make run-dev
```

Adres panelu: http://0.0.0.0:3000

Po starcie skonfiguruj webhooki Twilio (Incoming i Status Callback) na `PUBLIC_BASE_URL/twilio/inbound` oraz `PUBLIC_BASE_URL/twilio/status`.

---

## Konfiguracja środowiska (.env)

Najważniejsze zmienne (pełna lista w `app/config.py`):

```ini
# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_DEFAULT_FROM=+48123456789       # numer SMS w formacie E.164
TWILIO_MESSAGING_SERVICE_SID=...       # (opcjonalnie) Messaging Service SID

# OpenAI – AI auto-reply do rozmów SMS
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.7

# OpenAI – News/FAISS (RAG)
SECOND_OPENAI=sk-...
SECOND_MODEL=gpt-4o-mini

# Aplikacja
APP_HOST=0.0.0.0
APP_PORT=3000
APP_DEBUG=true
DB_PATH=data/app.db
PUBLIC_BASE_URL=https://twoja-domena.pl
TWILIO_VALIDATE_SIGNATURE=true         # w dev możesz ustawić false
```

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
- Indeks FAISS: `X1_data/faiss_openai_index/` (`index.faiss` lub `index.npz` + `docs.json`).
- Snapshot dokumentów: `X1_data/documents.json` (pozwala odbudować indeks nawet bez plików binarnych FAISS).
- Surowe scrapes: `X1_data/business_insider_scrapes/*.txt|json`.
- Zalecany backup prod: cały `X1_data/` + `data/app.db`. Przywrócenie: odtworzyć katalogi, uruchomić aplikację, sprawdzić `/api/news/test-faiss`.

---

## Uruchomienie w Dockerze

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

### docker-compose (dev / prod)

Dev:

```bash
make compose-up        # alias na: docker compose up --build
```

Prod (np. na serwerze):

```bash
make compose-prod      # docker compose -f docker-compose.production.yml up --build -d
```

Przy pracy z Dockerem **koniecznie** montuj:

- `./data -> /app/data` (baza SQLite),
- `./X1_data -> /app/X1_data` (indeks FAISS i dokumenty RAG).

Dzięki temu restart kontenerów nie kasuje historii wiadomości ani indeksu.

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
  - lista plików scrapów (podgląd, usuwanie),
  - przyciski „Scrape / Build index / Test FAISS”,
  - zarządzanie listą odbiorców newsów (numer, prompt, godzina, ON/OFF, Wyślij ręcznie).

---

## News / FAISS / RAG

### Pliki i indeks

- źródła tekstów: `X1_data/business_insider_scrapes/` (`.txt` i `.json`),
- snapshot dokumentów: `X1_data/documents.json`,
- indeks FAISS / MinimalVectorStore: `X1_data/faiss_openai_index/` (`index.faiss` / `index.npz` + `docs.json`).

Aplikacja potrafi:

1. **Scrapować** – endpoint `/api/news/scrape` oraz przycisk w panelu „Scrape” (używa `ScraperService`).
2. **Zbudować indeks** – automatycznie po scrapowaniu lub ręcznie przez `/api/news/indices/build`.
3. **Testować zapytania** – endpoint `/api/news/test-faiss`, w UI: pole zapytania + wynik (liczba trafień, odpowiedź modelu).
4. **Zarządzać plikami** – usuwać pojedyncze pliki scrapów lub cały indeks z poziomu panelu.

### Odbudowa indeksu FAISS

Kod `FAISSService` został napisany tak, aby odtworzenie indeksu było przewidywalne i bezpieczne:

- przy zapisie (`save_faiss_index`) tworzony jest komplet plików (`index.faiss` lub `index.npz` + `docs.json`),
- przy odczycie (`load_faiss_index`):
  1. najpierw ładowany jest pełny indeks FAISS, jeśli istnieje,
  2. jeśli jest tylko `index.npz`, używany jest `MinimalVectorStore`,
  3. jeśli istnieje samo `docs.json` – indeks jest **rekonstruowany od zera** wyłącznie z dokumentów,
  4. dodatkowo, jeśli brakuje plików dla `faiss_openai_index`, ale istnieje globalny snapshot `X1_data/documents.json`, serwis spróbuje odbudować indeks na jego podstawie.

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
  - Workery uruchamiane w tym samym procesie Flask (auto-reply queue, reminders, news scheduler) – logi wspólne.
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

- `app/` – kod aplikacji Flask (blueprinty, serwisy, integracje),
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

## Debugowanie i dobre praktyki

- **Webhooki Twilio**
  - przy 403 w dev ustaw `TWILIO_VALIDATE_SIGNATURE=false` i korzystaj z tunelu (ngrok, Cloudflare Tunnel),
  - sprawdzaj logi dla wpisów: `Inbound webhook hit...`, `Message status update...`.

- **Auto‑reply / AI**
  - brak odpowiedzi → upewnij się, że odpowiedni tryb jest włączony w panelu oraz że numer jest w formacie E.164,
  - AI wymaga poprawnie ustawionego klucza (w panelu i/lub `.env`).

- **FAISS / News**
  - brak wyników → sprawdź, czy indeks został zbudowany (scraping + build),
  - jeśli ręcznie usuniesz pliki indeksu, aplikacja spróbuje go odbudować z `documents.json`.

- **Bezpieczeństwo**
  - `.env` nigdy nie commitujemy do repozytorium,
  - produkcyjny `PUBLIC_BASE_URL` powinien wskazywać na HTTPS za reverse proxy (nginx),
  - w środowisku produkcyjnym trzymaj `APP_DEBUG=false` i włącz `TWILIO_VALIDATE_SIGNATURE`.

---

> Ten README jest utrzymywany jak kod – jeśli zmienisz coś w API, CLI albo strukturze FAISS, zaktualizuj dokumentację w tym pliku, żeby kolejny deweloper (a często: Ty za 3 miesiące) nie musiał odtwarzać kontekstu z historii gita.


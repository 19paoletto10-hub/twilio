# Twilio Chat App – ver3.1.2

Release tag: `ver3.1.2`
Data wydania: 2025-12-13
Środowisko referencyjne: Docker (Python 3.12, gunicorn)

## Podsumowanie

Wersja 3.1.2 wprowadza moduł Multi-SMS, który pozwala kolejkować i przetwarzać
zbiorcze wysyłki do dziesiątek odbiorców z poziomu API i panelu webowego.
Nowy worker działa w tle, deduplikuje numery, pilnuje limitów i zapisuje
stany w SQLite. Wydanie domyka też opis procesu release'owego – mamy gotowy
skrypt budujący publiczną paczkę bez plików wrażliwych oraz zaktualizowaną
pełną dokumentację produktu.

## Technologie i środowisko

- Język: Python 3.12
- Framework backendowy: Flask 3
- Serwer HTTP: gunicorn
- Baza danych: SQLite (`data/app.db`) z automatycznymi migracjami
- Integracje: Twilio (SMS), OpenAI (AI + embeddings), LangChain/FAISS

## Najważniejsze zmiany

### 1. Worker Multi-SMS i schema v7

- [app/multi_sms.py](app/multi_sms.py) dostarcza dedykowany worker, który rezerwuje
  partie z bazy, wysyła wiadomości przez klienta Twilio i aktualizuje
  statusy (success/failure/invalid) wraz z logowaniem.
- [app/database.py](app/database.py) podnosi schemat do `SCHEMA_VERSION = 7`
  dodając tabele `multi_sms_batches` i `multi_sms_recipients` z indeksami,
  migracją oraz helperami (rezerwacja zadań, przeliczanie liczników).
- Wysyłki respektują limit 250 odbiorców i wymagają poprawnie ustawionego
  `TWILIO_DEFAULT_FROM` lub Messaging Service SID.

### 2. Panel WWW: nowa zakładka „Multi-SMS”

- [app/templates/dashboard.html](app/templates/dashboard.html)
  zawiera nową zakładkę z formularzem wklejania numerów, walidacją treści,
  hintem o pracy w tle i historią zadań.
- [app/static/js/dashboard.js](app/static/js/dashboard.js) dodaje logikę UI:
  wysyłka formularza, tost po utworzeniu batcha, auto-odświeżanie listy
  (z możliwością rozwijania statusów odbiorców) i dodatkowe znaczniki
  dostępności.
- [app/static/css/app.css](app/static/css/app.css) zapewnia styl kart i listy
  odbiorców, tak aby panel był czytelny również po eksporcie do PDF.

### 3. Publiczne API Multi-SMS

- [app/webhooks.py](app/webhooks.py) udostępnia REST API:
  - `POST /api/multi-sms/batches` – waliduje treść i listę numerów (E.164,
    deduplikacja, limit, wymóg nadawcy),
  - `GET /api/multi-sms/batches?include_recipients=1` – zwraca historię
    zadań razem z odbiorcami,
  - `GET /api/multi-sms/batches/<id>` i `/recipients` – szczegóły batcha.
- Każda wysyłka zapisuje się w tabeli `messages`, dzięki czemu historia
  standardowych wiadomości i batchy jest spójna.

### 4. Release hygiene i dokumentacja

- [scripts/prepare_release_bundle.sh](scripts/prepare_release_bundle.sh) tworzy
  katalog `release/dist/<tag>/` zawierający wyłącznie pliki potrzebne na
  produkcję (kod, dokumentację, konfigurację) – bez `.env`, `data/`, `X1_data/`.
- [release/manifest-ver3.1.2.md](release/manifest-ver3.1.2.md) i
  [release/README.md](release/README.md) opisują, co wchodzi do paczki oraz jak ją
  spakować przed publikacją na GitHubie.
- [deploy/releases/full_documentation.html](deploy/releases/full_documentation.html)
  pozostaje źródłem prawdy nt. UI i operacji; sekcje Monitoring/Operations
  zostały rozszerzone pod Multi-SMS.

## Kompatybilność i upgrade

1. Przed wdrożeniem wykonaj backup `data/app.db` (schema zaktualizuje się do v7
   przy pierwszym starcie).
2. Upewnij się, że `.env` zawiera `TWILIO_DEFAULT_FROM` lub Messaging Service SID –
   Multi-SMS nie uruchomi się bez skonfigurowanego nadawcy.
3. Jeżeli chcesz ograniczyć throughput, ustaw `MULTI_SMS_SEND_DELAY_SECONDS`
   (opcjonalny env) – worker doda odstęp między wysyłkami.
4. Po wdrożeniu przetestuj:
   - utworzenie batcha poprzez UI/`POST /api/multi-sms/batches`,
   - logi workera (`docker compose logs -f web | grep Multi-SMS`),
   - monitoring `/api/health` (workery auto-reply, reminders, news, multi-sms
     dzielą logi procesu).
5. Publiczną paczkę zbuduj komendą
   `./scripts/prepare_release_bundle.sh ver3.1.2` i spakuj katalog
   `release/dist/ver3.1.2/` do ZIP/TAR.

## Publikacja release na GitHubie

1. **Releases → Draft a new release**.
2. Wybierz/utwórz tag `ver3.1.2` i użyj tytułu
   `ver3.1.2 – Multi-SMS batches & ops bundling`.
3. Wklej treść tego pliku do pola opisu.
4. Załącz paczkę z `release/dist/ver3.1.2/`.
5. Kliknij **Publish release**.

## Release bundle (TL;DR)

```
./scripts/prepare_release_bundle.sh ver3.1.2
cd release/dist/ver3.1.2
# zweryfikuj zawartość → brak .env, data/, X1_data/
tar -czf ../ver3.1.2-clean.tar.gz .
```

Paczkę można udostępniać klientom bez ryzyka wycieku danych newsowych czy
sekretów środowiskowych.

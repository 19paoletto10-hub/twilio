## Twilio Chat App

> Modułowy serwer czatu SMS oparty o Flask + Twilio z panelem webowym, webhookami oraz asynchronicznym auto‑reply.

### Główne funkcje

- **SMS auto-reply** – system automatycznych odpowiedzi oparty o webhook `/twilio/inbound` i kolejkę w pamięci.
- **Webhooki Twilio** – obsługa wiadomości przychodzących (`/twilio/inbound`) i statusów dostarczenia (`/twilio/status`).
- **REST API** – wysyłanie SMS z Twojej aplikacji (`POST /api/send-message`).
- **Panel www (Bootstrap 5)** – karta statystyk, lista wiadomości, widok czatu dla pojedynczego numeru.
- **Architektura modułowa**:
  - `app/config.py` – konfiguracja i wczytywanie zmiennych środowiskowych,
  - `app/twilio_client.py` – cienka warstwa na `twilio.rest.Client`,
  - `app/chat_logic.py` – silnik odpowiedzi bota (możesz podmienić na własny),
  - `app/webhooks.py` – endpointy Flask + integracja z Twilio,
  - `app/auto_reply.py` – asynchroniczny worker auto‑reply,
  - `app/database.py` – SQLite + schemat + helpery.

Repo jest gotowe do uruchomienia lokalnie, w Dockerze oraz w GitHub Codespaces.

## 1. Instalacja lokalna

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Konfiguracja środowiska

Utwórz plik `.env` na podstawie `.env.example`:

```bash
cp .env.example .env
```

Uzupełnij wartości:

- `TWILIO_ACCOUNT_SID` – SID konta z Twilio Console.
- `TWILIO_AUTH_TOKEN` – Auth Token.
- `TWILIO_DEFAULT_FROM` – numer nadawcy (np. `+4888020...`).
- `TWILIO_MESSAGING_SERVICE_SID` – (opcjonalnie) SID Messaging Service.
- `CHAT_MODE` – tryb bota: `echo` (domyślnie) lub `keywords` (używany tylko, gdy auto‑reply z bazy jest wyłączony).
- `APP_ENV`, `APP_DEBUG`, `APP_HOST`, `APP_PORT` – ustawienia środowiska i serwera.
- `DB_PATH` – ścieżka do bazy SQLite (domyślnie `data/app.db`).
- `PUBLIC_BASE_URL` – publiczny adres używany przez Twilio do webhooków (opcjonalnie).
- `TWILIO_VALIDATE_SIGNATURE` – `true` aby wymusić weryfikację podpisu Twilio.

## 3. Uruchomienie serwera (Flask)

```bash
python run.py
```

Domyślnie aplikacja działa na `http://0.0.0.0:3000`.

## 4. Automatyczne odpowiedzi SMS (Auto‑Reply)

Webhook `/twilio/inbound` zapisuje każdą przychodzącą wiadomość w tabeli `messages`, a następnie:

- jeśli w tabeli `auto_reply_config` (wiersz `id=1`) pole `enabled=1`, endpoint wrzuca zdarzenie do kolejki w pamięci, a worker w `app/auto_reply.py` wysyła SMS z tekstem `message` (tylko numery w formacie `+` + 11 cyfr, np. `+22000123456`),
- jeśli auto‑reply z bazy jest wyłączony, używany jest silnik bota z `chat_logic.py` (`CHAT_MODE=echo/keywords`) i odpowiedź jest wysyłana synchronicznie.

### 4.1 Konfiguracja auto‑reply w bazie

Tabela `auto_reply_config` jest tworzona automatycznie przy starcie aplikacji. Domyślnie auto‑reply jest wyłączony.

Przykład włączenia i ustawienia treści odpowiedzi:

```sql
UPDATE auto_reply_config
SET enabled = 1,
    message = 'Dziękujemy za wiadomość. Skontaktujemy się z Tobą wkrótce.'
WHERE id = 1;
```

Worker jest zdarzeniowy (bez odpytywania bazy), ma prostą deduplikację po `MessageSid` i zapisuje status wysyłki (`auto-reply`/`failed`) w tabeli `messages`.

### Bezpieczeństwo

- Auto-reply obsługuje walidację wszystkich parametrów wejściowych
- Wszystkie błędy są przechwytywane i logowane bez przerywania działania
- Możliwość włączenia weryfikacji podpisu Twilio przez `TWILIO_VALIDATE_SIGNATURE=true`

## 5. Interfejs webowy

- Dashboard (Bootstrap 5) jest dostępny pod `http://localhost:3000/`.
- Formularz pozwala wysyłać wiadomości SMS/MMS.
- Historia konwersacji (ostatnie 50 pozycji) oraz statystyki są pobierane z lokalnej bazy SQLite (`DB_PATH`).
- Statusy wiadomości aktualizują się automatycznie co ok. 15 sekund.
- Każdy numer z listy wiadomości ma przycisk przenoszący na pełny widok czatu (`/chat/<numer>`).
- Dedykowana strona czatu zawiera wątek z bąbelkami wiadomości, szybkie odświeżanie oraz formularz odpowiedzi (SMS).

## 6. Endpointy HTTP (SMS)

- `POST /twilio/inbound` – webhook dla wiadomości przychodzących (SMS)
- `POST /twilio/status` – status dostarczenia wiadomości
- `POST /api/send-message` – wysyłanie wiadomości z backendu
- `GET /api/messages/remote` – pobieranie ostatnich wiadomości bezpośrednio z Twilio (filtry: `to`, `from`, `date_sent*`, `limit`)
- `GET /api/messages/<sid>` – szczegóły konkretnej wiadomości prosto z API Twilio
- `POST /api/messages/<sid>/redact` – redagowanie treści wiadomości (ustawia pusty tekst)
- `DELETE /api/messages/<sid>` – usuwa wiadomość z Twilio oraz lokalnej bazy

Przykładowe zapytanie:

```bash
curl -X POST http://localhost:3000/api/send-message \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+48123123123",
    "body": "Test z API"
  }'
```

### Messaging Service

Wysyłka z Messaging Service dla SMS/MMS działa, gdy aplikacja ma ustawiony `TWILIO_MESSAGING_SERVICE_SID` lub przekażesz własny SID w polu `messaging_service_sid` w zapytaniu `POST /api/send-message`.

## 7. Konfiguracja Twilio (Messaging Service)

1. Wejdź w **Messaging Service** → wybierz swoją usługę (np. `swimbook`).
2. Zakładka **Integration**.
3. W sekcji **Incoming Messages** wybierz:
   - **Send a webhook**
   - URL: `https://twoja-domena.pl/twilio/inbound` (lub URL z Replit / ngrok).
4. W sekcji **Delivery Status Callback** ustaw:
   - URL: `https://twoja-domena.pl/twilio/status`.

Pamiętaj, aby w Twilio używać tego samego numeru / Messaging Service SID, jaki podałeś w `.env`.

## 8. CLI – wysyłanie wiadomości z terminala

```bash
python manage.py send \
  --to +48123123123 \
  --body "Siema z CLI" \
  --use-messaging-service
```

## 9. Rozbudowa

- Dodaj własną klasę w `chat_logic.py` implementującą logikę czatu (np. integracja z OpenAI).
- Podmień funkcję `build_chat_engine()` na własne tryby.
- Dodaj kolejne blueprinty / endpointy Flask do integracji z panelem www.

## 10. Docker (szybkie uruchomienie)

Poniżej przykładowy `Dockerfile` dla tej aplikacji (znajdziesz go w repozytorium). Obraz buduje się z Pythona 3.12-slim, instaluje zależności i uruchamia aplikację przez `gunicorn` na porcie `3000`.

Budowa obrazu i uruchomienie (lokalnie):

```bash
# w katalogu repo
docker build -t twilio-chat:latest .

# uruchomienie (przykład z przekazaniem .env):
docker run --rm -it -p 3000:3000 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  twilio-chat:latest
```

Uwaga: kontener oczekuje, że w katalogu `data/` będzie można zapisać bazę SQLite (`DB_PATH`) — przekazanie wolumenu zapobiega utracie danych po restarcie.

Przykładowe zmienne środowiskowe wymagane w `.env`:

```text
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=xxxx
TWILIO_DEFAULT_FROM=+48123456789
APP_HOST=0.0.0.0
APP_PORT=3000
```

Jeżeli chcesz uruchomić w trybie produkcyjnym za pomocą systemu procesów, dostosuj polecenie `CMD` w `Dockerfile` lub użyj orchestratora (docker-compose / Kubernetes).

## 11. GitHub Codespaces / Dev Container

W repo znajduje się konfiguracja `.devcontainer/` z `devcontainer.json` i przykładowym `Dockerfile`, która pozwala uruchomić środowisko deweloperskie w GitHub Codespaces lub w lokalnym VS Code z rozszerzeniem Remote - Containers.

Uruchomienie w Codespaces / Dev Container:

1. Otwórz repo w GitHub Codespaces lub wybierz w VS Code: `Remote-Containers: Open Folder in Container...`.
2. Kontener zainstaluje zależności i ustawi virtualenv. Po starcie możesz uruchomić aplikację poleceniem:

```bash
python run.py
```

3. Aby użyć debuggera z VS Code, skonfiguruj launch configuration (`python: Flask` lub `Attach to Process`) — domyślne ustawienia środowiska wskażą port `3000`.

Pliki konfiguracji znajdują się w katalogu `.devcontainer/` i można je dostosować (np. zainstalować dodatkowe narzędzia, linters czy CLI).

---



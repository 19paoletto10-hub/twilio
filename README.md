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

## 1a. Instalacja git-lfs (Alpine Linux)

**Wymagane do obsługi dużych plików w repozytorium (np. media, modele ML).**

### Diagnostyka środowiska

Sprawdź uprawnienia i dostępność menedżera pakietów:

```bash
id -u   # powinno zwrócić 0 (root) lub 1000 (user)
cat /etc/os-release   # sprawdź czy to Alpine Linux
command -v apk        # powinno zwrócić /sbin/apk
command -v sudo       # powinno zwrócić /usr/bin/sudo
```

### Instalacja globalna (zalecana)

```bash
sudo apk add --no-cache git-lfs
git lfs install --force
git lfs version
```

### Typowe błędy i rozwiązania

- **Brak uprawnień do sudo/apk:**
  - Skontaktuj się z administratorem lub użyj instalacji per-user (patrz dokumentacja git-lfs).
- **Błąd 'Unable to lock database: Permission denied':**
  - Uruchom terminal jako root lub w kontenerze z uprawnieniami do instalacji pakietów.
- **Brak git-lfs po instalacji:**
  - Sprawdź ścieżkę: `command -v git-lfs` powinno zwrócić `/usr/bin/git-lfs`.
- **Hook pre-push nadal blokuje push:**
  - Upewnij się, że wykonałeś `git lfs install --force` w katalogu repozytorium.
  - Sprawdź czy `.git/hooks/pre-push` zawiera wywołanie git-lfs.

### FAQ

- **Czy muszę używać --no-verify przy push?**
  - Po poprawnej instalacji i konfiguracji git-lfs nie powinno być takiej potrzeby.
- **Jak sprawdzić wersję git-lfs?**
  - `git lfs version`

Więcej: https://github.com/git-lfs/git-lfs/blob/main/INSTALLING.md
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

## ################

docker compose -f docker-compose.production.yml up --build

### ##############

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

## 12. Production & Security (zalecane)

Poniżej zbiór praktycznych kroków i wymagań, które warto wdrożyć przed wystawieniem aplikacji na produkcję.

- **Sekrety i zmienne środowiskowe**: nie przechowuj `.env` w repo; użyj platformy do przechowywania sekretów (GitHub Secrets, AWS Parameter Store, Vault). W `README` jest plik `.env.example` — skopiuj go i wypełnij lokalnie.
- **Wymagane zmienne produkcyjne**:
  - `APP_ENV=production`
  - `APP_API_KEY` — wartość API key używana przez `X-API-KEY` do ochrony REST API (obowiązkowe w prod).
  - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` — nie udostępniaj publicznie.
  - `RATELIMIT_STORAGE_URL` — np. `redis://redis:6379/0` (używane przez `Flask-Limiter`).

  ### Redis — dlaczego i jak wdrożyć

  Redis jest rekomendowanym backendem dla `Flask-Limiter` w środowisku produkcyjnym.
  Użycie Redis pozwala bezpiecznie i spójnie śledzić limity połączeń w wielu instancjach
  aplikacji (skala pozioma). Poniżej krok po kroku jak dodać Redis lokalnie i w `docker-compose`.

  1) Prosty `docker-compose` fragment dodający Redis:

  ```yaml
  services:
    redis:
      image: redis:7-alpine
      restart: unless-stopped
      ports:
        - "6379:6379"
      volumes:
        - redis-data:/data

  volumes:
    redis-data:
  ```

  2) Ustaw w `.env` adres pamięci podręcznej dla limiter:

  ```dotenv
  RATELIMIT_STORAGE_URL=redis://redis:6379/0
  ```

  3) W aplikacji `app/limiter.py` inicjalizacja wygląda poprawnie — limiter jest inicjalizowany
     w `create_app()` i automatycznie użyje `RATELIMIT_STORAGE_URL` z environmentu.

  4) Test redis ping z poziomu aplikacji (przykład):

  ```python
  import redis
  r = redis.from_url("redis://redis:6379/0")
  print(r.ping())
  ```

  5) Monitorowanie i bezpieczeństwo:
   - W production używaj zabezpieczonej sieci (VPC) i, jeśli to możliwe, redisa chronionego hasłem/ACL.
   - Przy zarządzanym Redisie ustaw adres, port i credentials w `RATELIMIT_STORAGE_URL` jak np.
     `redis://:PASSWORD@redis-host.example.com:6379/0`.

  6) Upewnij się, że `RATELIMIT_STORAGE_URL` jest poprawnie ustawiony zanim włączysz restrykcyjne limity —
     błędna konfiguracja może spowodować, że limiter nie zadziała lub wywoła wyjątki.

  ### Healthcheck endpoint

  Dodano `/api/health`, który zwraca:
  - `status`: `ok` lub `degraded` (jeżeli DB/Redis wykryto problem),
  - `env`: aktualne środowisko aplikacji,
  - `database`: wynik kontroli bazy (ok / details),
  - `redis`: wynik kontroli Redis (ok / details) gdy `RATELIMIT_STORAGE_URL` wskazuje Redis.

  Przykładowa odpowiedź (JSON):

  ```json
  {
    "status": "ok",
    "message": "Twilio Chat App running",
    "env": "development",
    "database": {"ok": true, "details": "file=data/app.db"},
    "redis": {"ok": true, "url": "redis://redis:6379/0"}
  }
  ```

  Używaj tego endpointu jako prostego healthchecku w systemach orkiestracji (Docker Swarm, Kubernetes) lub
  do integracji z zewnętrznym monitorem.

  ### Webhook behavior for invalid requests

  The inbound webhook (`/twilio/inbound`) now returns HTTP 200 with an empty body when the
  request is missing required parameters or when phone numbers are invalid. This is intentional:

  - Twilio will only retry webhook delivery when it receives non-2xx responses or a network error.
  - Returning 200 acknowledges receipt and prevents repeated delivery attempts for malformed requests.

  If you prefer TwiML responses, modify `app/webhooks.py` accordingly — but for malformed input
  returning 200 reduces unnecessary retries and log noise.

  ### Walidacja numerów telefonu

  Wprowadziliśmy centralną walidację numerów (`app/validators.py`) która:
  - próbuje użyć biblioteki `phonenumbers` jeśli jest zainstalowana (zalecane),
  - w przeciwnym razie stosuje prosty, rygorystyczny regex `^\\+\\d{11}$` (plus i 11 cyfr),
    zgodnie z wymaganiem projektu.

  Endpointy sprawdzające numery:
  - `/twilio/inbound` — waliduje `From` i `To` przed przetworzeniem (jeżeli numer jest nieprawidłowy webhook zwraca pustą odpowiedź),
  - `/api/send-message` — waliduje pole `to` i odrzuca żądanie z HTTP 400 z opisem.

  Jeżeli chcesz aby akceptować pełniejsze spektrum numerów E.164, zainstaluj bibliotekę `phonenumbers`:

  ```bash
  pip install phonenumbers
  ```

  Po zainstalowaniu `phonenumbers` walidator będzie używał jej automatycznie.

- **Rate limiting (ochrona przed nadużyciami)**: aplikacja korzysta z `Flask-Limiter`. W środowisku produkcyjnym ustaw `RATELIMIT_STORAGE_URL` (Redis) i dopasuj limity do swojej polityki (np. `POST /api/send-message` 10/min per API key).

- **Walidacja podpisów Twilio**: włącz `TWILIO_VALIDATE_SIGNATURE=true` w produkcji (domyślnie walidacja bierze token z `TWILIO_AUTH_TOKEN`). To zapobiega podszywaniu się pod Twilio.

- **Uwierzytelnianie API**: chronione endpointy (np. `/api/send-message`, `/api/messages`) wymagają `X-API-KEY` (implementacja jest w `app/auth.py`). Ustaw `APP_API_KEY` jako tajny klucz w środowisku produkcyjnym.

- **TLS / reverse proxy**: wystaw aplikację przez reverse proxy (nginx / load balancer) z terminacją TLS. W `docker-compose.production.yml` dostarczamy przykładowy `proxy` (nginx). W production użyj certyfikatów (Let's Encrypt lub managed TLS) i wymuś HTTPS.

- **Content Security Policy (CSP)**: ustaw politykę CSP w nagłówkach serwera (nginx lub aplikacja) aby zredukować ryzyko XSS.

- **Logowanie i ochrona danych w logach**: nie loguj pełnych treści wiadomości ani tokenów. Aplikacja maskuje wrażliwe pola w webhookach, ale pamiętaj o rotacji tokenów.

- **Baza danych i backup**: SQLite (`data/app.db`) jest ok do demo i małych instalacji. Dla produkcji rozważ przeniesienie do PostgreSQL i skonfiguruj regularne backupy oraz szyfrowanie kopii.

- **Hardening obrazu Docker**: projekt wykorzystuje multi-stage Dockerfile (buduje wheels w etapie `builder`) aby obraz był mniejszy i deterministyczny. Upewnij się, że `pip` nie ignoruje błędów instalacji (w naszym Dockerfile instalacja jest bez `|| true`).

- **Monitoring i alerty**: monitoruj zużycie API Twilio (koszty) i logi aplikacji; skonfiguruj alerty (np. Sentry + cost alerts w Twilio).

- **Rate-limit & webhooks**: nie nakładaj zbyt agresywnych limitów na endpointy webhook (Twilio może wysyłać callbacki w krótkich odstępach). Ustaw limity per API key / per IP tylko dla administracyjnych endpointów.

### Szybkie komendy produkcyjne

Budowa obrazu i uruchomienie produkcyjne (docker-compose):

```bash
docker compose -f docker-compose.production.yml up --build -d
```

Sprawdź logi nginx i aplikacji:

```bash
docker compose -f docker-compose.production.yml logs -f proxy
docker compose -f docker-compose.production.yml logs -f web
```

Jeżeli używasz GitHub Actions / CI, umieść `APP_API_KEY`, `TWILIO_AUTH_TOKEN` i inne sekrety w GitHub Secrets i wstrzykuj je do środowiska podczas deploymentu.

### Checklist bezpieczeństwa (przed prezentacją klientowi)

- [ ] Ustaw `APP_ENV=production` i `APP_API_KEY` w środowisku produkcyjnym.
- [ ] Włącz `TWILIO_VALIDATE_SIGNATURE=true` i przetestuj podpisy webhooków.
- [ ] Skonfiguruj Redis i `RATELIMIT_STORAGE_URL` dla `Flask-Limiter`.
- [ ] Uruchom aplikację za nginx z TLS (Let's Encrypt lub inny certyfikat).
- [ ] Upewnij się, że `.env` nie jest w repo (`.gitignore`).
- [ ] Przetestuj limity i obserwuj 429 responses przy przekroczeniu.

---

## Skąd brać sekrety i jak je wprowadzić

Kroki krok po kroku, aby zdobyć wszystkie wymagane wartości i uruchomić aplikację produkcyjnie.

- 1) Skopiuj plik przykładowy i wypełnij go:

```bash
cp .env.example .env
# Edytuj .env i wypełnij poniższe wartości
```

- 2) `TWILIO_ACCOUNT_SID` i `TWILIO_AUTH_TOKEN` — pobierz z konsoli Twilio:
  - Zaloguj się do https://www.twilio.com/console
  - W sekcji **Project Info / Account SID** skopiuj `ACCOUNT SID` (to `TWILIO_ACCOUNT_SID`).
  - W sekcji **API Keys & Tokens** (Account > Settings lub bezpośrednio https://www.twilio.com/console/project/settings) skopiuj `Auth Token` (to `TWILIO_AUTH_TOKEN`).

- 3) `TWILIO_DEFAULT_FROM` / `TWILIO_MESSAGING_SERVICE_SID`:
  - Jeżeli chcesz wysyłać z numeru SMS — zakup i użyj numeru SMS w Twilio (Console > Phone Numbers).
  - Alternatywnie skonfiguruj Messaging Service w Twilio i skopiuj `Messaging Service SID` (zalecane przy większych projektach).

- 4) `APP_API_KEY` — klucz do ochrony API (własny sekret):
  - Możesz wygenerować silny klucz lokalnie np. `openssl rand -hex 32` lub `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
  - Ustaw tę wartość w `.env` i nigdy jej nie umieszczaj w repo.

#### Generowanie `APP_API_KEY`

`APP_API_KEY` chroni wszystkie administracyjne endpointy (nagłówek `X-API-KEY`). Wygeneruj go raz i trzymaj poza repozytorium. Przykładowe komendy:

```bash
# Linux / macOS z OpenSSL
openssl rand -hex 32

# Dowolna platforma z Pythonem
python - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

Skopiuj otrzymaną wartość do pola `APP_API_KEY` w `.env` (lub w menedżerze sekretów) i przekazuj ją jako nagłówek `X-API-KEY` w żądaniach do API.

### Tworzenie `APP_API_KEY` krok po kroku

1. Wygeneruj silny klucz lokalnie (przykłady):

```bash
# OpenSSL (Linux/macOS)
openssl rand -hex 32

# Python (dowolna platforma)
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

2. Otwórz plik `.env` w katalogu projektu i wstaw wygenerowany klucz:

```dotenv
APP_API_KEY=tu_wklej_wygenerowany_klucz
```

3. Zrestartuj aplikację / odbuduj kontener, żeby zmienne środowiskowe zostały załadowane.

4. Przykład użycia curl z nagłówkiem `X-API-KEY`:

```bash
curl -X GET "https://your-host/api/messages" -H "X-API-KEY: $APP_API_KEY"
```

Uwaga: traktuj `APP_API_KEY` jak hasło — nie umieszczaj go w repozytorium. Przechowuj w menedżerze sekretów lub CI/CD secrets.

- 5) `RATELIMIT_STORAGE_URL` (Redis dla limiter):
  - Jeżeli uruchamiasz lokalny Redis przez `docker-compose` (w `docker-compose.production.yml` mamy serwis `redis`), użyj `redis://redis:6379/0`.
  - Dla zdalnego Redis (managed) podaj pełny URL, np. `redis://:PASSWORD@redis-host.example.com:6379/0`.

- 6) TLS / certyfikaty (nginx):
  - Dla testów możesz użyć self-signed certów, ale w production użyj Let's Encrypt lub zarządzanego certyfikatu.
  - Przy Let's Encrypt: użyj `certbot` na serwerze proxy (nginx) lub skorzystaj z integracji w platformie hostingowej.

- 7) Uruchomienie (production) — przykład z `.env`:

```bash
# Upewnij się, że .env jest w katalogu repozytorium (nie commituj go)
docker compose -f docker-compose.production.yml up --build -d

# Sprawdź logi
docker compose -f docker-compose.production.yml logs -f web
docker compose -f docker-compose.production.yml logs -f proxy
```

### Najczęstsze problemy i jak je naprawić

- Brak `gunicorn`: dodaj `gunicorn` do `requirements.txt` (już dodane). Jeśli `gunicorn` nie znajduje się na PATH, upewnij się że obraz został odbudowany: `docker compose build --no-cache web`.
- Błędy pip/wheels: jeżeli builder używa `pip wheel --no-deps`, zależności mogą być brakujące. Obraz teraz buduje koło zależności — jeżeli masz błędy instalacji, uruchom build lokalnie i sprawdź szczegóły błędów pip.
- Brak zmiennych środowiskowych: aplikacja wymaga `TWILIO_ACCOUNT_SID` i `TWILIO_AUTH_TOKEN` — w `app/config.py` jest twarde sprawdzenie. Upewnij się, że `.env` jest dostępny podczas startu (docker-compose automatycznie ładuje `.env` w tym katalogu) lub zdefiniuj zmienne w `docker-compose`.
- `ImportError: cannot import name 'limiter'`: występuje, gdy moduł `limiter` nie eksportuje obiektu `limiter` używanego przez dekoratory — naprawiono przez eksport modułowego `limiter` i inicjalizację w `create_app()`.
- `502` od nginx / Connection refused: najczęściej backend nie uruchomił się (sprawdź logi `web` i logi aplikacji — zwykle brak env, błąd migracji DB lub wyjątek przy imporcie).



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



# Docker Guide – Twilio Chat App

Kompletny przewodnik wdrożenia aplikacji Twilio Chat App przy użyciu Docker.
Dokument przeznaczony dla programistów na każdym poziomie zaawansowania.

---

## Spis treści

1. [Słownik pojęć Docker](#słownik-pojęć-docker)
2. [Wymagania wstępne](#wymagania-wstępne)
3. [Architektura kontenerów](#architektura-kontenerów)
4. [Quick Start (5 minut)](#quick-start-5-minut)
5. [Krok po kroku: Development](#krok-po-kroku-development)
6. [Krok po kroku: Production](#krok-po-kroku-production)
7. [Konfiguracja SSL/TLS (Let's Encrypt)](#konfiguracja-ssltls-lets-encrypt)
8. [Backup i restore bazy danych](#backup-i-restore-bazy-danych)
9. [CI/CD z GitHub Actions](#cicd-z-github-actions)
10. [Wolumeny i persystencja danych](#wolumeny-i-persystencja-danych)
11. [Monitorowanie i logi](#monitorowanie-i-logi)
12. [Troubleshooting](#troubleshooting)
13. [FAQ](#faq)

---

## Słownik pojęć Docker

> 💡 **Dla początkujących:** Docker to technologia „konteneryzacji" – pozwala spakować aplikację
> wraz ze wszystkimi zależnościami do jednego przenośnego pakietu, który działa identycznie
> na każdym komputerze.

| Termin | Wyjaśnienie | Analogia |
|--------|-------------|----------|
| **Image (obraz)** | Niemodyfikowalny szablon zawierający kod aplikacji, biblioteki i konfigurację. Tworzony z `Dockerfile`. | Przepis na ciasto |
| **Container (kontener)** | Uruchomiona instancja obrazu. Można mieć wiele kontenerów z tego samego obrazu. | Upieczone ciasto |
| **Dockerfile** | Plik tekstowy z instrukcjami budowy obrazu (np. `FROM`, `COPY`, `RUN`). | Lista składników + instrukcja |
| **Docker Compose** | Narzędzie do definiowania i uruchamiania wielu kontenerów jednocześnie (plik YAML). | Przepis na cały obiad |
| **Volume (wolumen)** | Trwałe miejsce przechowywania danych poza kontenerem. Przetrwa restart/usunięcie kontenera. | Lodówka (ciasto znika, ale lodówka zostaje) |
| **Port mapping** | Połączenie portu hosta z portem kontenera, np. `-p 3000:3000`. | Numer pokoju w hotelu |
| **Network (sieć)** | Wirtualna sieć łącząca kontenery. Kontenery w tej samej sieci widzą się po nazwach. | Wewnętrzna linia telefoniczna |
| **Health check** | Automatyczne sprawdzanie czy aplikacja działa poprawnie. | Puls pacjenta |
| **Layer (warstwa)** | Każda instrukcja w Dockerfile tworzy warstwę. Warstwy są cache'owane dla szybszych buildów. | Warstwy tortu |
| **Registry** | Zdalne repozytorium obrazów (Docker Hub, GitHub Container Registry). | Sklep z przepisami |
| **Tag** | Wersja obrazu, np. `twilio-chat:latest` lub `twilio-chat:v3.1.3`. | Numer wydania książki |
| **ENV (zmienna środowiskowa)** | Konfiguracja przekazywana do kontenera, np. klucze API. | Sekretne składniki |
| **EXPOSE** | Deklaracja portu, który kontener nasłuchuje (nie otwiera go automatycznie). | Oznaczenie drzwi |
| **CMD / ENTRYPOINT** | Domyślna komenda uruchamiana przy starcie kontenera. | Przycisk „Start" |
| **Build context** | Katalog z plikami dostępnymi podczas budowania obrazu. | Pudełko z składnikami |
| **Multi-stage build** | Technika budowania obrazu w etapach, by zmniejszyć rozmiar końcowy. | Użycie kuchni pomocniczej |
| **Non-root user** | Uruchamianie aplikacji jako użytkownik bez uprawnień root (bezpieczeństwo). | Kucharz vs właściciel restauracji |
| **Daemon** | Proces Docker działający w tle, zarządza kontenerami. | Szef kuchni |
| **Gunicorn** | Serwer WSGI dla aplikacji Python (produkcyjny). | Profesjonalny kelner |
| **NGINX** | Serwer proxy/load balancer. Przyjmuje ruch HTTP i przekazuje do aplikacji. | Recepcjonista |
| **Upstream** | W NGINX: definicja serwera/grupy serwerów docelowych. | Lista kucharzy |
| **Reverse proxy** | Serwer pośredniczący między klientem a aplikacją (NGINX w naszym przypadku). | Tłumacz |

---

## Wymagania wstępne

### Minimalne wymagania sprzętowe

| Komponent | Minimum | Zalecane |
|-----------|---------|----------|
| RAM | 2 GB | 4 GB |
| CPU | 1 rdzenie | 2 rdzenie |
| Dysk | 5 GB wolnego | 10 GB wolnego |
| System | Linux x64, macOS, Windows 10/11 Pro | Ubuntu 22.04 LTS |

### Wymagane oprogramowanie

```bash
# Sprawdź czy masz zainstalowane:
docker --version          # Docker Engine 24.0+
docker compose version    # Docker Compose v2.20+
git --version             # Git 2.30+
```

### Instalacja Docker (jeśli brak)

#### Ubuntu / Debian

```bash
# 1. Usuń stare wersje
sudo apt-get remove docker docker-engine docker.io containerd runc

# 2. Zainstaluj oficjalny Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 3. Dodaj użytkownika do grupy docker (unikaj sudo przy każdej komendzie)
sudo usermod -aG docker $USER

# 4. Wyloguj się i zaloguj ponownie LUB:
newgrp docker

# 5. Weryfikacja
docker run hello-world
```

#### macOS

```bash
# Pobierz Docker Desktop z https://docker.com/products/docker-desktop
# lub przez Homebrew:
brew install --cask docker
```

#### Windows

1. Włącz WSL2: `wsl --install`
2. Pobierz [Docker Desktop for Windows](https://docker.com/products/docker-desktop)
3. W ustawieniach Docker Desktop włącz „Use WSL 2 based engine"

---

## Architektura kontenerów

### Development (pojedynczy kontener)

```
┌─────────────────────────────────────────────┐
│                   HOST                       │
│                                              │
│    ┌─────────────────────────────────────┐   │
│    │         twilio-chat:latest          │   │
│    │  ┌───────────────────────────────┐  │   │
│    │  │      Flask + Gunicorn         │  │   │
│    │  │        (port 3000)            │  │   │
│    │  └───────────────────────────────┘  │   │
│    │                 │                    │   │
│    │    ┌────────────▼────────────┐      │   │
│    │    │   Volume: ./data        │      │   │
│    │    │   (SQLite + backups)    │      │   │
│    │    └─────────────────────────┘      │   │
│    └──────────────────│──────────────────┘   │
│                       │                       │
│              Port mapping 3000:3000           │
│                       │                       │
└───────────────────────▼───────────────────────┘
                        │
              http://localhost:3000
```

### Production (dwa kontenery + NGINX)

```
┌──────────────────────────────────────────────────────────────┐
│                           HOST                                │
│                                                               │
│  ┌─────────────────────┐        ┌──────────────────────────┐ │
│  │   nginx:alpine      │        │    twilio-chat:latest    │ │
│  │  (Reverse Proxy)    │        │   (Flask + Gunicorn)     │ │
│  │                     │        │                          │ │
│  │  Port 80 (HTTP)     │───────▶│  Internal port 3000      │ │
│  │  Port 443 (HTTPS)*  │        │  (nie widoczny z zewnątrz)│ │
│  └─────────────────────┘        └──────────────────────────┘ │
│           │                                  │                │
│           │                     ┌────────────▼────────────┐  │
│           │                     │   Volume: ./data        │  │
│           │                     │   (SQLite + backups)    │  │
│           │                     └─────────────────────────┘  │
│           │                                                   │
└───────────▼───────────────────────────────────────────────────┘
            │
   http://twoja-domena.pl
   https://twoja-domena.pl (z SSL)
```

---

## Quick Start (5 minut)

Dla niecierpliwych – minimalne kroki do uruchomienia:

```bash
# 1. Sklonuj repozytorium
git clone https://github.com/19paoletto10-hub/twilio.git
cd twilio

# 2. Skopiuj i uzupełnij konfigurację
cp .env.example .env   # lub utwórz nowy plik .env

# 3. Edytuj .env (minimum te 3 zmienne):
#    TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#    TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#    TWILIO_DEFAULT_FROM=+48123456789

# 4. Utwórz katalog na dane
mkdir -p data

# 5. Zbuduj i uruchom
docker compose up --build

# 6. Otwórz przeglądarkę
# → http://localhost:3000
```

**Zatrzymanie:** `Ctrl+C` lub `docker compose down`

---

## Krok po kroku: Development

### Krok 1: Przygotowanie projektu

```bash
# Sklonuj repozytorium
git clone https://github.com/19paoletto10-hub/twilio.git
cd twilio

# Sprawdź strukturę
ls -la
# Ważne pliki:
# - Dockerfile           ← instrukcje budowy obrazu
# - docker-compose.yml   ← konfiguracja dev
# - .env                 ← zmienne środowiskowe (utwórz!)
# - requirements.txt     ← zależności Python
```

### Krok 2: Konfiguracja zmiennych środowiskowych

```bash
# Utwórz plik .env na podstawie szablonu lub od zera:
cat > .env << 'EOF'
# === Środowisko ===
APP_ENV=dev
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=3000

# === Twilio (WYMAGANE) ===
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_DEFAULT_FROM=+48123456789
TWILIO_MESSAGING_SERVICE_SID=

# === Walidacja (w dev można wyłączyć) ===
TWILIO_VALIDATE_SIGNATURE=false

# === Baza danych ===
DB_PATH=data/app.db

# === OpenAI (opcjonalne, dla funkcji AI) ===
SECOND_OPENAI=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SECOND_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-large

# === AI Chat (opcjonalne) ===
OPENAI_API_KEY=
AI_ENABLED=true
AI_TARGET_NUMBER=
AI_SYSTEM_PROMPT=

# === Logi ===
LOG_LEVEL=debug
EOF
```

> ⚠️ **WAŻNE:** Plik `.env` zawiera sekrety! Nigdy nie commituj go do repozytorium.
> Dodaj `.env` do `.gitignore`.

### Krok 3: Budowanie obrazu Docker

```bash
# Zbuduj obraz z tagiem 'twilio-chat:latest'
docker build -t twilio-chat:latest .

# Co się dzieje podczas budowania:
# 1. FROM python:3.12-slim    → pobiera bazowy obraz Python
# 2. apt-get install ...      → instaluje gcc, curl (do kompilacji)
# 3. pip install ...          → instaluje zależności z requirements.txt
# 4. COPY . /app              → kopiuje kod aplikacji
# 5. useradd app              → tworzy użytkownika non-root
# 6. EXPOSE 3000              → deklaruje port
# 7. CMD gunicorn ...         → definiuje komendę startową
```

Sprawdź zbudowany obraz:

```bash
docker images twilio-chat
# REPOSITORY    TAG       IMAGE ID       CREATED          SIZE
# twilio-chat   latest    abc123def456   10 seconds ago   ~400MB
```

### Krok 4: Uruchomienie kontenera

**Opcja A: Docker Compose (zalecana)**

```bash
# Uruchom w trybie attached (widoczne logi)
docker compose up --build

# LUB w tle (detached):
docker compose up --build -d
```

**Opcja B: docker run (ręcznie)**

```bash
docker run --rm -it \
  -p 3000:3000 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  --name twilio-app \
  twilio-chat:latest
```

| Flaga | Znaczenie |
|-------|-----------|
| `--rm` | Usuń kontener po zatrzymaniu |
| `-it` | Tryb interaktywny + TTY (widoczne logi) |
| `-p 3000:3000` | Mapuj port hosta 3000 → port kontenera 3000 |
| `--env-file .env` | Wczytaj zmienne środowiskowe |
| `-v $(pwd)/data:/app/data` | Zamontuj katalog `data/` jako wolumen |
| `--name twilio-app` | Nazwa kontenera |

### Krok 5: Weryfikacja

```bash
# Sprawdź czy kontener działa
docker ps

# Sprawdź health check
curl http://localhost:3000/api/health
# {"status": "ok", "env": "dev", "openai_enabled": true, ...}

# Otwórz dashboard w przeglądarce
open http://localhost:3000   # macOS
xdg-open http://localhost:3000   # Linux
```

### Krok 6: Przydatne komendy dev

```bash
# Logi na żywo
docker compose logs -f

# Wejdź do kontenera (debug)
docker compose exec web sh

# Sprawdź bazę danych
docker compose exec web sqlite3 /app/data/app.db ".tables"

# Restart aplikacji (po zmianach kodu)
docker compose restart web

# Przebuduj po zmianach w requirements.txt
docker compose up --build

# Zatrzymaj i usuń kontenery
docker compose down

# Zatrzymaj + usuń wolumeny (UWAGA: kasuje dane!)
docker compose down -v
```

---

## Krok po kroku: Production

### Różnice Production vs Development

| Aspekt | Development | Production |
|--------|-------------|------------|
| Port zewnętrzny | 3000 (bezpośrednio) | 80/443 (przez NGINX) |
| Debug mode | `APP_DEBUG=true` | `APP_DEBUG=false` |
| Walidacja Twilio | `false` (wygodne) | `true` (bezpieczeństwo!) |
| SSL/TLS | Brak | Let's Encrypt |
| Logi | Verbose (debug) | Info/Warning |
| Restart policy | `unless-stopped` | `always` |
| Reverse proxy | Brak | NGINX |

### Krok 1: Przygotowanie serwera

```bash
# SSH do serwera produkcyjnego
ssh user@your-server.com

# Zainstaluj Docker (jeśli brak)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# Wyloguj i zaloguj ponownie

# Sklonuj repozytorium
git clone https://github.com/19paoletto10-hub/twilio.git
cd twilio
```

### Krok 2: Konfiguracja produkcyjna

```bash
# Utwórz plik .env z ustawieniami produkcyjnymi
cat > .env << 'EOF'
# === Środowisko PRODUKCJA ===
APP_ENV=production
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=3000

# === Twilio (WYMAGANE) ===
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_DEFAULT_FROM=+48123456789

# === WAŻNE: Włącz walidację sygnatury! ===
TWILIO_VALIDATE_SIGNATURE=true

# === Publiczny URL (dla webhooków Twilio) ===
PUBLIC_BASE_URL=https://twoja-domena.pl

# === Baza danych ===
DB_PATH=data/app.db

# === OpenAI ===
SECOND_OPENAI=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SECOND_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-large

# === Logi ===
LOG_LEVEL=info
EOF
```

### Krok 3: Uruchomienie produkcji

```bash
# Utwórz katalog na dane
mkdir -p data

# Uruchom stack produkcyjny (NGINX + App)
docker compose -f docker-compose.production.yml up --build -d

# LUB użyj Makefile:
make compose-prod
```

### Krok 4: Weryfikacja produkcji

```bash
# Sprawdź statusy kontenerów
docker compose -f docker-compose.production.yml ps

# NAME                IMAGE                 STATUS
# twilio-proxy-1      nginx:stable-alpine   Up (healthy)
# twilio-web-1        twilio-chat:latest    Up (healthy)

# Sprawdź logi
docker compose -f docker-compose.production.yml logs -f

# Test przez NGINX (port 80)
curl -I http://localhost/api/health
# HTTP/1.1 200 OK
# Server: nginx/1.25.3

# Test z zewnątrz (po konfiguracji DNS)
curl https://twoja-domena.pl/api/health
```

### Krok 5: Konfiguracja Twilio Webhooks

W panelu Twilio (https://console.twilio.com):

1. Przejdź do: **Phone Numbers → Manage → Active Numbers**
2. Wybierz numer
3. W sekcji **Messaging**:
   - Webhook URL: `https://twoja-domena.pl/twilio/inbound`
   - Status Callback: `https://twoja-domena.pl/twilio/status`

---

## Konfiguracja SSL/TLS (Let's Encrypt)

> 🔐 **SSL/TLS** szyfruje komunikację między przeglądarką a serwerem.
> **Let's Encrypt** to darmowy urząd certyfikacji.

### Wymagania

- Domena wskazująca na serwer (rekord A w DNS)
- Port 80 i 443 otwarte w firewallu

### Krok 1: Struktura plików SSL

```bash
# Utwórz katalogi dla certyfikatów
mkdir -p deploy/nginx/ssl
mkdir -p deploy/certbot/www
mkdir -p deploy/certbot/conf
```

### Krok 2: Konfiguracja NGINX z SSL

Utwórz plik `deploy/nginx/default-ssl.conf`:

```nginx
# Upstream do aplikacji Flask
upstream twilio_app {
    server web:3000;
}

# Przekierowanie HTTP → HTTPS
server {
    listen 80;
    server_name twoja-domena.pl www.twoja-domena.pl;

    # Let's Encrypt challenge (nie przekierowuj!)
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Wszystko inne → HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}

# Serwer HTTPS
server {
    listen 443 ssl http2;
    server_name twoja-domena.pl www.twoja-domena.pl;

    # Certyfikaty Let's Encrypt
    ssl_certificate /etc/letsencrypt/live/twoja-domena.pl/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/twoja-domena.pl/privkey.pem;

    # Rekomendowane ustawienia SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # HSTS (opcjonalnie, po testach)
    # add_header Strict-Transport-Security "max-age=63072000" always;

    client_max_body_size 10M;

    location / {
        proxy_pass http://twilio_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 120s;
    }

    location = /api/health {
        proxy_pass http://twilio_app/api/health;
    }
}
```

### Krok 3: Docker Compose z SSL

Utwórz plik `docker-compose.ssl.yml`:

```yaml
version: '3.8'
services:
  web:
    build: .
    image: twilio-chat:latest
    env_file:
      - .env
    volumes:
      - ./data:/app/data
    expose:
      - "3000"
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  proxy:
    image: nginx:stable-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/nginx/default-ssl.conf:/etc/nginx/conf.d/default.conf:ro
      - ./deploy/certbot/www:/var/www/certbot:ro
      - ./deploy/certbot/conf:/etc/letsencrypt:ro
    depends_on:
      - web
    restart: always

  certbot:
    image: certbot/certbot
    volumes:
      - ./deploy/certbot/www:/var/www/certbot
      - ./deploy/certbot/conf:/etc/letsencrypt
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"
```

### Krok 4: Uzyskanie certyfikatu

```bash
# 1. Najpierw uruchom NGINX bez SSL (do walidacji domeny)
# Użyj uproszczonej konfiguracji tylko z HTTP

# 2. Uzyskaj certyfikat
docker run --rm \
  -v $(pwd)/deploy/certbot/www:/var/www/certbot \
  -v $(pwd)/deploy/certbot/conf:/etc/letsencrypt \
  certbot/certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  -d twoja-domena.pl \
  -d www.twoja-domena.pl \
  --email twoj@email.com \
  --agree-tos \
  --no-eff-email

# 3. Uruchom pełny stack z SSL
docker compose -f docker-compose.ssl.yml up -d
```

### Krok 5: Automatyczne odnawianie

Certyfikaty Let's Encrypt ważne są 90 dni. Kontener `certbot` w compose automatycznie
odnawia je co 12 godzin (jeśli zbliża się termin).

Możesz też dodać cron:

```bash
# Edytuj crontab
crontab -e

# Dodaj (codziennie o 3:00)
0 3 * * * cd /path/to/twilio && docker compose -f docker-compose.ssl.yml exec certbot certbot renew --quiet
```

---

## Backup i restore bazy danych

### Automatyczny backup (skrypt)

Skrypt `scripts/backup_db.sh` (tworzony automatycznie):

```bash
#!/bin/bash
# =============================================================================
# backup_db.sh - Automatyczny backup bazy SQLite z kontenera Docker
# =============================================================================
# Użycie:
#   ./scripts/backup_db.sh              # Backup do backup/
#   ./scripts/backup_db.sh /custom/path # Backup do wskazanego katalogu
#
# Wymagania:
#   - Docker z uruchomionym kontenerem 'twilio-web-1' lub 'web'
#   - LUB bezpośredni dostęp do pliku data/app.db
# =============================================================================

set -euo pipefail

# Konfiguracja
BACKUP_DIR="${1:-./backup}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DB_NAME="app.db"
BACKUP_FILE="${BACKUP_DIR}/app_${TIMESTAMP}.db"
KEEP_DAYS=7

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Utwórz katalog backupu
mkdir -p "$BACKUP_DIR"

# Wykryj źródło bazy danych
if [ -f "data/${DB_NAME}" ]; then
    # Baza dostępna lokalnie (wolumen zamontowany)
    log_info "Kopiowanie bazy z lokalnego wolumenu..."
    cp "data/${DB_NAME}" "$BACKUP_FILE"
elif docker ps --format '{{.Names}}' | grep -q 'twilio.*web'; then
    # Baza w kontenerze Docker
    CONTAINER=$(docker ps --format '{{.Names}}' | grep 'twilio.*web' | head -1)
    log_info "Kopiowanie bazy z kontenera: $CONTAINER"
    docker cp "${CONTAINER}:/app/data/${DB_NAME}" "$BACKUP_FILE"
else
    log_error "Nie znaleziono bazy danych!"
    log_error "Upewnij się, że:"
    log_error "  - Kontener Docker jest uruchomiony, LUB"
    log_error "  - Plik data/app.db istnieje lokalnie"
    exit 1
fi

# Weryfikacja backupu
if [ -f "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log_info "✅ Backup utworzony: $BACKUP_FILE ($SIZE)"
    
    # Weryfikacja integralności SQLite
    if command -v sqlite3 &> /dev/null; then
        if sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | grep -q "ok"; then
            log_info "✅ Integralność bazy: OK"
        else
            log_warn "⚠️ Integralność bazy: PROBLEM (sprawdź plik)"
        fi
    fi
else
    log_error "❌ Backup nie został utworzony!"
    exit 1
fi

# Usuń stare backupy
if [ "$KEEP_DAYS" -gt 0 ]; then
    log_info "Usuwanie backupów starszych niż $KEEP_DAYS dni..."
    find "$BACKUP_DIR" -name "app_*.db" -mtime +$KEEP_DAYS -delete 2>/dev/null || true
fi

# Podsumowanie
log_info "Backupy w katalogu $BACKUP_DIR:"
ls -lh "$BACKUP_DIR"/app_*.db 2>/dev/null | tail -5 || echo "(brak)"
```

### Restore (przywracanie)

```bash
# 1. Zatrzymaj aplikację
docker compose down

# 2. Przywróć backup
cp backup/app_20251214_120000.db data/app.db

# 3. Uruchom ponownie
docker compose up -d
```

### Cron dla automatycznych backupów

```bash
# Edytuj crontab
crontab -e

# Backup codziennie o 2:00
0 2 * * * cd /path/to/twilio && ./scripts/backup_db.sh >> /var/log/twilio-backup.log 2>&1

# Backup co godzinę (produkcja)
0 * * * * cd /path/to/twilio && ./scripts/backup_db.sh >> /var/log/twilio-backup.log 2>&1
```

---

## CI/CD z GitHub Actions

> 🔄 **CI/CD** (Continuous Integration / Continuous Deployment) to automatyzacja testów
> i wdrożeń. Każdy push do repozytorium automatycznie buduje obraz i może go wdrożyć.

### Słownik CI/CD

| Termin | Wyjaśnienie |
|--------|-------------|
| **Workflow** | Plik YAML definiujący automatyzację (`.github/workflows/*.yml`) |
| **Job** | Grupa kroków wykonywanych na jednym runnerze |
| **Step** | Pojedyncza akcja (komenda, skrypt, gotowa akcja) |
| **Runner** | Maszyna wykonująca workflow (GitHub-hosted lub self-hosted) |
| **Action** | Gotowy komponent do ponownego użycia (np. `actions/checkout`) |
| **Secret** | Zaszyfrowana zmienna (np. klucze API) dostępna w workflow |
| **Artifact** | Plik wyjściowy z workflow (np. logi, zbudowany obraz) |
| **Matrix** | Uruchomienie tego samego job na różnych konfiguracjach |
| **GHCR** | GitHub Container Registry – rejestr obrazów Docker |

### Workflow: Build i Push do GHCR

Plik `.github/workflows/docker-build.yml`:

```yaml
# =============================================================================
# GitHub Actions Workflow: Docker Build & Push
# =============================================================================
# Wyzwalacze:
#   - Push do main → buduje i publikuje obraz
#   - Pull Request → tylko buduje (weryfikacja)
#   - Tag ver* → buduje i publikuje z tagiem wersji
# =============================================================================

name: Docker Build & Push

on:
  push:
    branches:
      - main
    tags:
      - 'ver*'
  pull_request:
    branches:
      - main

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    name: Build Docker Image
    runs-on: ubuntu-latest
    
    # Uprawnienia do publikacji w GHCR
    permissions:
      contents: read
      packages: write
    
    steps:
      # ─────────────────────────────────────────────────────────────────────
      # Krok 1: Checkout kodu
      # ─────────────────────────────────────────────────────────────────────
      - name: 📥 Checkout repository
        uses: actions/checkout@v4
      
      # ─────────────────────────────────────────────────────────────────────
      # Krok 2: Setup Docker Buildx (zaawansowany builder)
      # ─────────────────────────────────────────────────────────────────────
      - name: 🔧 Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      # ─────────────────────────────────────────────────────────────────────
      # Krok 3: Login do GitHub Container Registry
      # Używa automatycznego tokenu GITHUB_TOKEN
      # ─────────────────────────────────────────────────────────────────────
      - name: 🔑 Log in to Container Registry
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      # ─────────────────────────────────────────────────────────────────────
      # Krok 4: Ekstrakcja metadanych (tagi i etykiety)
      # ─────────────────────────────────────────────────────────────────────
      - name: 🏷️ Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            # Tag 'latest' dla głównej gałęzi
            type=raw,value=latest,enable={{is_default_branch}}
            # Tag z SHA commita
            type=sha,prefix=
            # Tag z nazwy brancha
            type=ref,event=branch
            # Tag z wersji (ver3.1.3 → 3.1.3)
            type=match,pattern=ver(.*),group=1
      
      # ─────────────────────────────────────────────────────────────────────
      # Krok 5: Build i Push obrazu
      # Cache przyspiesza kolejne buildy
      # ─────────────────────────────────────────────────────────────────────
      - name: 🐳 Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          # Push tylko dla push (nie dla PR)
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          # Cache warstw między buildami
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
      # ─────────────────────────────────────────────────────────────────────
      # Krok 6: Podsumowanie (widoczne w GitHub UI)
      # ─────────────────────────────────────────────────────────────────────
      - name: 📝 Summary
        if: github.event_name != 'pull_request'
        run: |
          echo "## 🐳 Docker Image Published" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Registry:** \`${{ env.REGISTRY }}\`" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Tags:**" >> $GITHUB_STEP_SUMMARY
          echo "\`\`\`" >> $GITHUB_STEP_SUMMARY
          echo "${{ steps.meta.outputs.tags }}" >> $GITHUB_STEP_SUMMARY
          echo "\`\`\`" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "**Pull command:**" >> $GITHUB_STEP_SUMMARY
          echo "\`\`\`bash" >> $GITHUB_STEP_SUMMARY
          echo "docker pull ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest" >> $GITHUB_STEP_SUMMARY
          echo "\`\`\`" >> $GITHUB_STEP_SUMMARY

  # ═══════════════════════════════════════════════════════════════════════════
  # Job 2: Health Check (opcjonalny - test obrazu)
  # ═══════════════════════════════════════════════════════════════════════════
  test-image:
    name: Test Docker Image
    needs: build-and-push
    runs-on: ubuntu-latest
    if: github.event_name != 'pull_request'
    
    steps:
      - name: 📥 Checkout repository
        uses: actions/checkout@v4
      
      - name: 🧪 Test image health check
        run: |
          # Uruchom kontener w tle
          docker run -d \
            --name test-container \
            -p 3000:3000 \
            -e TWILIO_ACCOUNT_SID=ACtest123456789 \
            -e TWILIO_AUTH_TOKEN=test_token \
            -e TWILIO_DEFAULT_FROM=+15551234567 \
            -e APP_DEBUG=true \
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
          
          # Poczekaj na start
          sleep 10
          
          # Test health endpoint
          curl --retry 5 --retry-delay 2 -f http://localhost:3000/api/health
          
          # Cleanup
          docker stop test-container
          docker rm test-container
```

### Konfiguracja sekretów w GitHub

1. Przejdź do: **Settings → Secrets and variables → Actions**
2. Dodaj sekrety (dla opcjonalnego deploy):

| Sekret | Opis |
|--------|------|
| `SERVER_HOST` | IP/hostname serwera produkcyjnego |
| `SERVER_USER` | Użytkownik SSH |
| `SERVER_SSH_KEY` | Klucz prywatny SSH |
| `TWILIO_ACCOUNT_SID` | (opcjonalnie dla testów) |

### Workflow: Auto-deploy (opcjonalny)

Dodaj do workflow lub utwórz osobny plik `.github/workflows/deploy.yml`:

```yaml
# Deploy na serwer po opublikowaniu obrazu
deploy:
  name: Deploy to Production
  needs: [build-and-push, test-image]
  runs-on: ubuntu-latest
  if: github.ref == 'refs/heads/main'
  
  steps:
    - name: 🚀 Deploy via SSH
      uses: appleboy/ssh-action@v1.0.0
      with:
        host: ${{ secrets.SERVER_HOST }}
        username: ${{ secrets.SERVER_USER }}
        key: ${{ secrets.SERVER_SSH_KEY }}
        script: |
          cd /opt/twilio
          docker compose -f docker-compose.production.yml pull
          docker compose -f docker-compose.production.yml up -d
          docker image prune -f
```

### Użycie obrazu z GHCR

Po opublikowaniu obrazu możesz go użyć na serwerze:

```bash
# Login do GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Pull obrazu
docker pull ghcr.io/19paoletto10-hub/twilio:latest

# Lub w docker-compose.yml:
services:
  web:
    image: ghcr.io/19paoletto10-hub/twilio:latest
    # zamiast: build: .
```

---

## Wolumeny i persystencja danych

### Dane przechowywane w wolumenach

| Ścieżka w kontenerze | Ścieżka na hoście | Zawartość |
|----------------------|-------------------|-----------|
| `/app/data` | `./data` | Baza SQLite (`app.db`) |
| `/app/X1_data` | `./X1_data` | Indeks FAISS, dokumenty, scrapes |

### Konfiguracja wolumenów w docker-compose

```yaml
volumes:
  # Składnia: ./ścieżka_na_hoście:/ścieżka_w_kontenerze
  - ./data:/app/data
  - ./X1_data:/app/X1_data   # opcjonalnie dla FAISS
```

### Named volumes (zaawansowane)

```yaml
services:
  web:
    volumes:
      - twilio_data:/app/data

volumes:
  twilio_data:
    driver: local
```

Zalety named volumes:
- Docker zarządza lokalizacją
- Łatwiejszy backup: `docker volume inspect twilio_data`

---

## Monitorowanie i logi

### Logi kontenerów

```bash
# Wszystkie kontenery
docker compose logs

# Tylko aplikacja, na żywo
docker compose logs -f web

# Ostatnie 100 linii
docker compose logs --tail=100 web

# Z timestampami
docker compose logs -t web

# Filtrowanie po wzorcu
docker compose logs web 2>&1 | grep -i error
```

### Status kontenerów

```bash
# Lista uruchomionych
docker compose ps

# Szczegóły kontenera
docker inspect twilio-web-1

# Zużycie zasobów (na żywo)
docker stats

# Health status
docker inspect --format='{{.State.Health.Status}}' twilio-web-1
```

### Logi aplikacji (wewnątrz)

```bash
# Wejdź do kontenera
docker compose exec web sh

# Sprawdź logi Gunicorn
cat /app/logs/gunicorn.log  # jeśli skonfigurowane

# SQLite - ostatnie wiadomości
sqlite3 /app/data/app.db "SELECT * FROM messages ORDER BY id DESC LIMIT 5;"
```

---

## Troubleshooting

### Problem: Kontener nie startuje

```bash
# Sprawdź logi
docker compose logs web

# Typowe przyczyny:
# - Brak zmiennych w .env
# - Port 3000 zajęty
# - Błąd składni w konfiguracji
```

**Rozwiązanie:**

```bash
# Sprawdź czy port wolny
lsof -i :3000

# Zabij proces na porcie
kill -9 $(lsof -t -i :3000)

# Sprawdź zmienne
docker compose config
```

### Problem: Health check failed

```bash
# Status
docker inspect --format='{{json .State.Health}}' twilio-web-1

# Test ręczny
docker compose exec web curl -v http://localhost:3000/api/health
```

**Rozwiązanie:**
- Poczekaj na `start-period` (10s)
- Sprawdź czy aplikacja się uruchomiła (logi)
- Zweryfikuj zmienne Twilio

### Problem: Brak danych po restarcie

```bash
# Sprawdź wolumeny
docker volume ls
docker inspect twilio_data

# Sprawdź czy plik istnieje
ls -la data/
```

**Rozwiązanie:**
- Upewnij się, że volume jest zamontowany (`-v ./data:/app/data`)
- NIE używaj `docker compose down -v` (usuwa wolumeny!)

### Problem: Permission denied na data/

```bash
# W kontenerze działa user 'app', nie root
# Napraw uprawnienia:
sudo chown -R 1000:1000 data/
chmod 755 data/
```

### Problem: NGINX 502 Bad Gateway

```bash
# Sprawdź czy web działa
docker compose ps

# Sprawdź sieć
docker network ls
docker network inspect twilio_default

# Test połączenia nginx → web
docker compose exec proxy wget -qO- http://web:3000/api/health
```

**Rozwiązanie:**
- Upewnij się, że `web` i `proxy` są w tej samej sieci
- Sprawdź czy `upstream` w nginx wskazuje na `web:3000`

### Problem: Let's Encrypt nie działa

```bash
# Sprawdź challenge
curl http://twoja-domena.pl/.well-known/acme-challenge/test

# Logi certbota
docker compose logs certbot

# Ręczne uzyskanie certyfikatu (debug)
docker compose exec certbot certbot certonly --dry-run ...
```

**Rozwiązanie:**
- DNS musi wskazywać na serwer
- Port 80 musi być otwarty
- Katalog `.well-known` musi być dostępny

---

## FAQ

### Jak zaktualizować aplikację?

```bash
cd /path/to/twilio
git pull origin main
docker compose -f docker-compose.production.yml up --build -d
```

### Jak zmienić port?

W `docker-compose.yml`:

```yaml
ports:
  - "8080:3000"  # host:kontener
```

### Jak podejrzeć bazę danych?

```bash
docker compose exec web sqlite3 /app/data/app.db

# LUB lokalnie (jeśli volume zamontowany):
sqlite3 data/app.db ".tables"
```

### Jak wyczyścić wszystko i zacząć od nowa?

```bash
# UWAGA: Kasuje dane!
docker compose down -v
rm -rf data/*
docker system prune -af
docker compose up --build
```

### Jak skalować aplikację?

```bash
# Uruchom 3 instancje web (wymaga load balancer)
docker compose up -d --scale web=3
```

> ⚠️ SQLite nie wspiera współbieżnego zapisu z wielu procesów.
> Dla skalowania poziomego przejdź na PostgreSQL.

---

## Podsumowanie komend

| Cel | Komenda |
|-----|---------|
| Build obrazu | `docker build -t twilio-chat:latest .` |
| Start dev | `docker compose up --build` |
| Start prod | `docker compose -f docker-compose.production.yml up -d` |
| Logi | `docker compose logs -f web` |
| Stop | `docker compose down` |
| Restart | `docker compose restart web` |
| Shell w kontenerze | `docker compose exec web sh` |
| Status | `docker compose ps` |
| Health check | `curl localhost:3000/api/health` |
| Backup | `./scripts/backup_db.sh` |
| Cleanup | `docker system prune -af` |

---

*Dokumentacja wygenerowana automatycznie. Ostatnia aktualizacja: 2024-12-14*

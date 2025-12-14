# Release Notes: ver3.2.0

**Docker Documentation + CI/CD + DevOps Toolkit**

📅 Data wydania: 2024-12-14

---

## Podsumowanie

Release 3.2.0 to kompleksowa aktualizacja dokumentacji i narzędzi DevOps dla Twilio Chat App.
Wprowadza pełny przewodnik Docker od podstaw (z wyjaśnieniami wszystkich pojęć), automatyzację
CI/CD przez GitHub Actions, skrypt do backupu bazy danych oraz gotową konfigurację SSL/TLS
z Let's Encrypt.

### Dla kogo jest ta wersja?

- **DevOps / Administratorzy** – gotowe narzędzia do wdrożenia produkcyjnego
- **Początkujący z Docker** – szczegółowe wyjaśnienia każdego pojęcia
- **Zespoły deweloperskie** – CI/CD out-of-the-box
- **Operatorzy** – automatyczny backup bazy danych

---

## Najważniejsze zmiany

### 📚 Nowa dokumentacja Docker

Utworzono kompletny przewodnik **[docs/docker-guide.md](../../docs/docker-guide.md)** zawierający:

| Sekcja | Zawartość |
|--------|-----------|
| Słownik pojęć | 25+ terminów Docker z analogiami dla początkujących |
| Wymagania | Instalacja Docker na Ubuntu/macOS/Windows |
| Architektura | Diagramy ASCII dla dev i prod |
| Quick Start | Uruchomienie w 5 minut |
| Development | 6 kroków z komentarzami |
| Production | 5 kroków + webhooks Twilio |
| SSL/TLS | Let's Encrypt + certbot |
| Backup | Skrypt + cron |
| CI/CD | GitHub Actions workflow |
| Troubleshooting | Typowe problemy i rozwiązania |
| FAQ | Często zadawane pytania |

### 🔐 SSL/TLS z Let's Encrypt

Nowe pliki konfiguracyjne:

```
deploy/nginx/default-ssl.conf    # NGINX z HTTPS
docker-compose.ssl.yml           # Stack produkcyjny z certbot
deploy/certbot/www/              # Katalog challenge
deploy/certbot/conf/             # Katalog certyfikatów
```

Funkcjonalności:
- Automatyczne odnawianie certyfikatów (co 12h)
- Nagłówki bezpieczeństwa (X-Frame-Options, HSTS, XSS Protection)
- Przekierowanie HTTP → HTTPS
- OCSP Stapling

### 🔄 CI/CD z GitHub Actions

Workflow **[.github/workflows/docker-build.yml](../../.github/workflows/docker-build.yml)**:

```yaml
# Wyzwalacze:
- Push do main → buduje i publikuje jako 'latest'
- Tag ver* → buduje z tagiem wersji (np. 3.2.0)
- Pull Request → tylko weryfikacja (nie publikuje)

# Funkcje:
- Build z cache (przyspiesza ~70%)
- Publikacja do GHCR (GitHub Container Registry)
- Test obrazu (health check)
- Opcjonalny auto-deploy przez SSH
```

Po merge możesz użyć:
```bash
docker pull ghcr.io/19paoletto10-hub/twilio:latest
docker pull ghcr.io/19paoletto10-hub/twilio:3.2.0
```

### 💾 Backup bazy danych

Skrypt **[scripts/backup_db.sh](../../scripts/backup_db.sh)**:

```bash
# Podstawowe użycie
./scripts/backup_db.sh

# Pomoc
./scripts/backup_db.sh --help

# Lista backupów
./scripts/backup_db.sh --list

# Przywracanie
./scripts/backup_db.sh --restore backup/app_20241214_120000.db

# Dry-run (sprawdź bez tworzenia)
./scripts/backup_db.sh --dry-run
```

Funkcje:
- Automatyczne wykrywanie źródła (Docker lub lokalnie)
- Weryfikacja integralności SQLite
- Rotacja starych backupów (domyślnie 7 dni)
- Kolorowy output

### 📖 Rozszerzona dokumentacja bazy danych

W **[docs/developer-guide.md](../../docs/developer-guide.md)** rozbudowano sekcję "Baza danych i migracje":

- Pełna struktura 6 tabel z opisami kolumn
- Historia migracji (wersja 1→7)
- Diagram przepływu `_ensure_schema()`
- **Przykład krok po kroku: dodawanie nowej tabeli**
- Opis normalizacji numerów telefonów
- Tabela helper functions
- Best practices

### 🛠️ Rozszerzony Makefile

Nowe komendy:

| Komenda | Opis |
|---------|------|
| `make compose-ssl` | Produkcja z SSL/TLS |
| `make backup` | Backup bazy SQLite |
| `make restore F=...` | Przywróć backup |
| `make health` | Sprawdź /api/health |
| `make help` | Czytelny help z ramkami |

---

## Lista nowych plików

```
.github/
└── workflows/
    └── docker-build.yml          # CI/CD workflow

deploy/
├── certbot/
│   ├── conf/.gitkeep             # Katalog certyfikatów
│   └── www/.gitkeep              # Katalog challenge
└── nginx/
    └── default-ssl.conf          # NGINX z SSL

docs/
└── docker-guide.md               # Przewodnik Docker

scripts/
└── backup_db.sh                  # Skrypt backup

docker-compose.ssl.yml            # Compose z SSL
```

## Lista zaktualizowanych plików

```
README.md                         # Rozszerzona sekcja Docker
docs/README.md                    # Nowy spis treści
docs/developer-guide.md           # Rozbudowana sekcja DB
Makefile                          # Nowe komendy
CHANGELOG.md                      # Wpis ver3.2.0
```

---

## Instrukcja upgrade

### Z wersji 3.1.x

```bash
# 1. Backup bazy (nowy skrypt!)
./scripts/backup_db.sh

# 2. Pull zmian
git pull origin main

# 3. Restart kontenerów
docker compose down
docker compose up --build -d

# 4. Weryfikacja
curl localhost:3000/api/health
```

### Świeża instalacja

```bash
# 1. Clone
git clone https://github.com/19paoletto10-hub/twilio.git
cd twilio

# 2. Konfiguracja
cp .env.example .env
# Edytuj .env

# 3. Start
docker compose up --build -d
```

---

## Kompatybilność

| Aspekt | Status |
|--------|--------|
| Breaking changes | ❌ Brak |
| Migracja DB | ❌ Nie wymagana (schema v7) |
| API endpoints | ✅ Bez zmian |
| Docker images | ✅ Kompatybilne wstecznie |

---

## Znane ograniczenia

- CI/CD auto-deploy wymaga skonfigurowania sekretów GitHub (SERVER_HOST, SERVER_USER, SERVER_SSH_KEY)
- SSL/TLS wymaga publicznej domeny z prawidłowym DNS
- Backup weryfikacja integralności wymaga sqlite3 na hoście

---

## Podziękowania

Dziękujemy wszystkim użytkownikom za feedback dotyczący dokumentacji Docker!

---

## Linki

- [Dokumentacja Docker](../../docs/docker-guide.md)
- [Developer Guide](../../docs/developer-guide.md)
- [Główne README](../../README.md)
- [CHANGELOG](../../CHANGELOG.md)

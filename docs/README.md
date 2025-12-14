# Dokumentacja – spis treści

Ten katalog zawiera materiały uzupełniające do głównego README:

## Przewodniki

- **[developer-guide.md](developer-guide.md)** – Przewodnik dla deweloperów: architektura, baza danych, endpointy, workery
- **[docker-guide.md](docker-guide.md)** – Kompletny przewodnik Docker: od instalacji po produkcję z SSL

## Architektura i design

- [architecture-notes.md](architecture-notes.md) – Przegląd architektury aplikacji
- [changes-and-capabilities.md](changes-and-capabilities.md) – Zmiany i capability map

## Dokumentacja produktowa

- [app-overview.html](app-overview.html) – Przegląd produktu (HTML, responsywny)
- [deploy/releases/full_documentation.html](../deploy/releases/full_documentation.html) – Pełna dokumentacja (HTML, gotowa pod PDF)

## Skrypty i narzędzia

| Skrypt | Opis |
|--------|------|
| `scripts/backup_db.sh` | Backup bazy SQLite (Docker + lokalnie) |
| `scripts/prepare_release_bundle.sh` | Budowanie paczki release |
| `scripts/demo_send.sh` | Wysyłka testowego SMS |

## CI/CD

Workflow GitHub Actions znajdują się w `.github/workflows/`:
- `docker-build.yml` – Automatyczny build i publikacja obrazu Docker do GHCR

## Pliki konfiguracyjne Docker

| Plik | Środowisko |
|------|------------|
| `docker-compose.yml` | Development (port 3000) |
| `docker-compose.production.yml` | Produkcja (NGINX na porcie 80) |
| `docker-compose.ssl.yml` | Produkcja z SSL/TLS (Let's Encrypt) |
| `deploy/nginx/default.conf` | Konfiguracja NGINX (HTTP) |
| `deploy/nginx/default-ssl.conf` | Konfiguracja NGINX (HTTPS) |

---

**Uwaga:** Pliki w `deploy/releases/` to źródło prawdy dla release notes (MD/HTML) oraz kompletnej dokumentacji produktowej. Do publikacji paczek używaj `scripts/prepare_release_bundle.sh` i manifestów w katalogu `release/`.

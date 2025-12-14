# Release bundles

Ten katalog gromadzi manifesty i artefakty przygotowujące publiczne paczki wydaniowe.

## Jak zbudować paczkę (ver3.1.2 i kolejne)

1. Upewnij się, że repozytorium jest na odpowiednim tagu (np. `ver3.1.3`).
2. Uruchom skrypt `scripts/prepare_release_bundle.sh` (bez argumentu lub z nazwą taga).
3. Artefakt zostanie zapisany do `release/dist/<tag>/` wraz z plikiem `MANIFEST.md`.
4. Spakuj katalog `release/dist/<tag>/` do ZIP/TAR i załącz w GitHub Release.

### Zawartość paczki

- kod aplikacji (`app/`), dokumentacja (`docs/`), pliki `deploy/`, `scripts/`, top‑level pliki konfiguracyjne,
- brak katalogów `data/`, `X1_data/`, plików `.env` oraz innych potencjalnie wrażliwych zasobów.

### Dlaczego tak?

Repozytorium robocze przechowuje również dane operacyjne (indeksy FAISS, próbki newsów). 
Skrypt i manifest w `release/` gwarantują, że publiczne paczki zawierają tylko to, co potrzebne
klientom: kod źródłowy, dokumentację oraz instrukcje wdrożenia, bez wrażliwych danych.

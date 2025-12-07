# Release v1.1.2

Datum: 2025-12-07

## Summary

Release `v1.1.2` skupia się na stabilizacji serwera webhooków, lepszym zarządzaniu limitem i Redis, poprawkach integracji Twilio (REST-only replies), dokumentacji instalacji `git-lfs` oraz dodaniu automatycznego workflow tworzącego release przy tagowaniu. Dodatkowo wprowadzono drobne poprawki konfiguracji, walidacji numerów i odporności na brak zewnętrznych usług (Redis, Twilio).

Ten release dostarcza:
- Poprawki i ułatwienia uruchomienia lokalnego (virtualenv, dependency install pomijający `git-lfs`).
- Stabilne endpointy webhooków (`/twilio/inbound` i `/twilio/status`) z defensywną obsługą błędów i zwrotem 200 dla niepoprawnych payloadów (aby uniknąć retry Twilio).
- Mechanizm rate-limiter: poprawne parsowanie domyślnych limitów i fallback do pamięci, gdy Redis nie jest dostępny.
- Dokumentację instalacji `git-lfs` oraz GitHub Action tworzący release przy tagowaniu (`.github/workflows/release-on-tag.yml`).
- Automatyczne utworzenie release v1.1.1 w repo (poprzednia operacja).

## Zmiany techniczne (wybrane)

- `app/limiter.py`: domyślne limity zmienione na parsowalny format (string) by uniknąć ValueError w `Flask-Limiter`.
- `README.md`: dodana sekcja instalacji `git-lfs` (Alpine), diagnostyka i FAQ.
- CI: dodany workflow `.github/workflows/release-on-tag.yml` tworzący release na push tagów `v*`.
- Konfiguracja aplikacji: `create_app()` jest odporna na brak Twilio (degraded/demo mode) i nie uruchamia workerów w takim wypadku.
- `app/webhooks.py`: obsługa numerów, redakcja logów (redact sensitive), zwracanie HTTP 200 dla malformed inbound.

## Analiza (dwie perspektywy — „Dwubiegunowy” duet inżynierów)

Inżynier A — Optymista / Pragmatyk:

- Zalety:
  - Uproszczone uruchomienie lokalne — developerzy szybciej reprodukują środowisko.
  - Wyłączenie wymogu `git-lfs` w instalacji pozwala uniknąć blokad w CI, jednocześnie dokumentując właściwy sposób instalacji dla hostów Alpine.
  - Automatyczne tworzenie release przy tagowaniu usprawnia release process i standaryzuje artefakty.
  - Fallbacky na brak Redis/Twilio oznaczają, że aplikacja nie upada przy braku zewnętrznych serwisów.

- Moje rekomendacje:
  - Dodać testy integracyjne na zdrowie endpointów i symulację Twilio (mock). 
  - Dodać Action, który uruchamia sanity checks przed utworzeniem release (smoke tests).

Inżynier B — Pesymista / Analityk Ryzyka:

- Obawy:
  - Fallback do pamięci dla limiter może ukrywać problemy w produkcji (brak spójności przy skali poziomej).
  - Wyłączanie walidacji podpisu Twilio dla testów jest wygodne, lecz może maskować problemy z podpisami w produkcji.
  - Automatyczne release powinno walidować, że tag ma przydzielone unikalne changelogi i że wersja nie koliduje z istniejącym pipeline.

- Moje rekomendacje:
  - Na produkcji wymusić obecność `RATELIMIT_STORAGE_URL` i kontynuować deployment tylko gdy Redis ping=True.
  - Dodać pre-deploy krok, który weryfikuje `TWILIO_VALIDATE_SIGNATURE=true` i testuje podpis webhook dla kilku przykładowych żądań.
  - Zautomatyzować backup bazy SQLite (lub migrację do PostgreSQL) przed aktualizacją.

Suma rekomendacji zespołu:
- Przygotować CI/CD: (1) lint/test, (2) smoke tests, (3) deploy only if health OK (DB + Redis + Twilio validated), (4) create release.
- Dla produkcji — wymiana SQLite na PostgreSQL lub dodanie backup/restore + monitoring.

## Bezpieczeństwo i zmienne środowiskowe

- Wymagane (produkcyjnie):
  - `APP_API_KEY` — sekret chroniący admin endpointy; wymagany w prod.
  - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` — jeśli brak, aplikacja uruchomi się w trybie demo i nie wyśle wiadomości.
  - `RATELIMIT_STORAGE_URL` — zalecany `redis://...` (w prod obowiązkowy).

- Dobre praktyki:
  - Nie commitować `.env` do repozytorium.
  - Przechowywać sekrety w sekcjach `Secrets` CI/CD.
  - W produkcji ustawić `TWILIO_VALIDATE_SIGNATURE=true` i testować webhooki z prawidłowym X-Twilio-Signature.

## Obsługa błędów i monitorowanie

- Endpoint `/api/health` zwraca `status: ok|degraded` z detalami DB i Redis. System deploymentowy powinien używać tego endpointu.
- Logi maskują wrażliwe części webhooków (`Body`, `From`).
- W przypadku braku połączenia z Redis, limiter używa pamięci i loguje warning; w prod powinno to proaktywnie uruchamiać alarm.

## Testy i instrukcje lokalne

1. Uruchom venv:
```bash
python -m venv venv
source venv/bin/activate
pip install -r <(grep -vE '^\s*#|git-lfs' requirements.txt)
export TWILIO_VALIDATE_SIGNATURE=false
export RATELIMIT_STORAGE_URL=''
python run.py
```

2. Healthcheck:
```bash
curl http://127.0.0.1:3000/api/health
```

3. Symulacja webhooka:
```bash
curl -X POST http://127.0.0.1:3000/twilio/inbound -d 'From=+48123456789' -d 'To=+48987654321' -d 'Body=Test'
```

## Rollback i migracje

- Tag pozwala na szybki rollback: `git checkout v1.1.1` i deploy.
- Jeżeli planujesz migracje schematu DB, dodaj skrypt migracji w `scripts/` i uruchom go przed zamknięciem aktualizacji.

## Changelog (skrót)

- Poprawka parsera limitów i defensywne fallbacky (Redis)
- Dodano instrukcję instalacji git-lfs
- Dodano workflow release-on-tag
- Stabilizacja webhooków i walidacji numerów

---

Pełny opis i dalsze instrukcje znajdują się w repo i w `README.md`.

---

Generated by the release tooling on 2025-12-07.

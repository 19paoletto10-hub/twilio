# Release Notes – ver3.2.9

**Data:** 2025-12-27  \
**Zakres:** Railway-Oriented Programming, optymalizacje wydajności, czysta architektura

## Najważniejsze funkcje

- **Railway-Oriented Core (patterns.py)** – Result/Success/Failure, retry z exponential backoff + jitter, circuit breaker, TTL cache, Processor Chain dla wiadomości.
- **Clean Architecture Handlers (message_handler.py)** – Command/Strategy, Value Objects (`PhoneNumber`, `InboundMessage`), kompozycyjne walidatory, łatwe mocki i DI.
- **Performance Suite (performance.py, database.py, faiss_service.py)** – WAL w SQLite, cache zapytań, transakcje z auto rollback, TTL cache dla embeddings FAISS, metryki czasu i rate limiting.
- **Walidatory (validators.py)** – Fluent API, `ValidationSuccess` / `ValidationFailure`, gotowe walidatory JSON i numerów telefonów.
- **Broszura produktowa** – aktualizacja do v3.2.9, dane autora i CTA kierujące na tanski.pawel@icloud.com.

## Zmodyfikowane / nowe pliki

- app/patterns.py
- app/message_handler.py
- app/performance.py
- app/database.py
- app/faiss_service.py
- app/validators.py
- docs/app-brochure.html (update wersji i kontaktu)
- CHANGELOG.md (sekcja ver3.2.9)

## Kompatybilność i uwagi

- Brak zmian breaking w API HTTP lub webhookach.
- Nowe dekoratory (retry, circuit_breaker, timed) są opt-in – nie zmieniają istniejącego zachowania bez użycia.
- WAL w SQLite wymaga jednorazowego przełączenia bazy; skrypt `database.py` ustawia `PRAGMA journal_mode=WAL` automatycznie.

## Instrukcja wydania

1. Upewnij się, że `main` zawiera commit z ver3.2.9.
2. Oznacz wersję: `git tag ver3.2.9 && git push origin ver3.2.9`.
3. Przygotuj paczkę: `./scripts/prepare_release_bundle.sh ver3.2.9` (artefakt w `release/dist/ver3.2.9/`).
4. Utwórz GitHub Release „ver3.2.9 – Design patterns & performance suite” i załącz paczkę z kroku 3 + broszurę `docs/app-brochure.html` / PDF (jeśli generowany).
5. Zweryfikuj deploy: `docker-compose pull && docker-compose up -d --build` (środowisko produkcyjne) lub analogiczne dla SSL.

## Testy rekomendowane

- Jednostkowe/integracyjne modułów: patterns.py, validators.py, faiss_service.py.
- Manualne: komenda `/news` (fallback działa), AI auto-reply, multi-SMS, scheduler newsów, przypomnienia.
- Smoke: wejście/wyjście REST API, webhook Twilio, panel webowy (chat przełączanie wątków), tryb drukowania broszury.

## Znane ograniczenia

- Brak migracji DB – w razie lokalnych custom schemas zweryfikuj kompatybilność WAL.
- Cache embeddings: TTL domyślne 1h; w środowiskach o małej pamięci rozważ skrócenie TTL.

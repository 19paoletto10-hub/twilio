# Changelog

## v1.2 (Database Reliability & Messaging Hardening)

### Podsumowanie

To wydanie koncentruje się na:
- zwiększeniu niezawodności bazy SQLite (wersjonowane migracje, indeksy),
- uporządkowaniu obsługi wiadomości (brak duplikatów po SID, spójne logowanie),
- bezpieczniejszym auto‑reply i przypomnieniach (brak retro‑odpowiedzi, poprawne numery nadawcy).

Release jest kompatybilny wstecznie, a migracje uruchamiają się automatycznie przy starcie aplikacji.

### Zmiany techniczne

- Dodano kontrolę wersji schematu przez `PRAGMA user_version` (`SCHEMA_VERSION = 3`).
- Nowe lub istniejące bazy są automatycznie podnoszone do aktualnego schematu w `_ensure_schema()`.
- Tabela `messages`:
  - `sid TEXT UNIQUE`,
  - indeksy: `idx_messages_created_at` (`created_at`), `idx_messages_direction_created_at` (`direction`, `created_at`).
- `upsert_message()`:
  - łączy rekordy z Twilio z placeholderami (`sid IS NULL`) po kierunku, numerach i czasie,
  - w razie kolizji `sid` aktualizuje istniejący rekord zamiast zgłaszać błąd `UNIQUE`.
- `insert_message()` przyjmuje `created_at`/`updated_at`, co pozwala wiernie odtwarzać czasy z Twilio.

### Auto‑reply

- Konfiguracja `auto_reply_config` przechowuje `enabled_since` w formacie ISO UTC.
- Worker auto‑reply porównuje `received_at` wiadomości z `enabled_since` i:
  - ignoruje wiadomości sprzed włączenia auto‑reply,
  - przetwarza tylko nowe inboundy, dzięki czemu nie ma „retro‑odpowiedzi”.
- Sync z Twilio (`_maybe_sync_messages`) nie kolejkuje auto‑reply dla historycznych wiadomości sprzed `enabled_since`.

### Przypomnienia (scheduler)

- Worker przypomnień:
  - wymusza użycie `TWILIO_DEFAULT_FROM` jako nadawcy; przy braku – pomija wysyłkę z logiem ostrzegawczym,
  - każdą wysłaną wiadomość zapisuje w `messages` jako outbound z poprawnym `from_number`,
  - przy błędzie zapisuje rekord ze statusem `failed` i szczegółem błędu.

### Kompatybilność i upgrade

- Brak zmian łamiących API/HTTP – UI i integracje pozostają bez zmian.
- Migracje schematu uruchamiają się automatycznie przy starcie aplikacji:
  - nowe instalacje dostają od razu schemat w wersji 3,
  - starsze bazy są bezpiecznie podnoszone (dodanie `enabled_since`, indeksów, aktualizacja `user_version`).

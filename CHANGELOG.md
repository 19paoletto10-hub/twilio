# Changelog

## ver3.0.2 (News / FAISS control plane)

### Podsumowanie

Release skupia się na profesjonalizacji modułu News/RAG: baza FAISS korzysta teraz
wyłącznie z embeddingów OpenAI, dashboard dostał dedykowaną sekcję statusową, a
API ułatwia testowanie i diagnostykę bezpośrednio z panelu. Dzięki temu operator
widzi w jednym miejscu stan indeksu, liczbę wektorów i kontekst odpowiedzi.

### Najważniejsze zmiany

- **FAISSService = tylko OpenAI** – usunięto fallbacki hashujące, serwis wymaga
  poprawnie ustawionego `SECOND_OPENAI`/`OPENAI_API_KEY`, raportuje brak
  konfiguracji i zapisuje snapshot dokumentów. Zapytania zwracają teraz również
  użyty kontekst (`context_preview`) i listę fragmentów.
- **Nowe API diagnostyczne** – endpoint `/api/news/faiss/status` udostępnia
  metadane indeksu (rozmiar, liczba wektorów, modele). Wszystkie akcje związane
  z News/RAG (test odbiorcy, wymuszenie wysyłki, ręczne budowanie indeksu,
  `/api/news/test-faiss`) mają twardszą walidację kluczy i informują, gdy brakuje
  indeksu lub uprawnień do OpenAI.
- **Panel „News po AI”** – rozbudowana karta statusowa pokazuje stan indeksu,
  modele i datę ostatniego odświeżenia; dodano szybki test promptu, listę
  fragmentów użytych w odpowiedzi oraz komunikaty o błędach prosto z API.
- **Zależności** – w `requirements.txt` pojawiły się pakiety
  `langchain-text-splitters` oraz `gunicorn`, co odzwierciedla rzeczywiste
  środowisko uruchomieniowe i aktualną integrację z LangChain 0.3.

### Kompatybilność i upgrade

- Przed budową indeksu FAISS ustaw `SECOND_OPENAI=sk-...`; brak klucza kończy się
  błędem już przy starcie serwisu.
- Jeśli masz własne automatyzacje wokół `/api/news/test-faiss`, możesz teraz
  korzystać z pola `results` i `context_preview`, aby pokazywać operatorom
  fragmenty źródłowe.
- Pozostałe moduły aplikacji (AI chat, auto-reply, webhooki Twilio) działają jak
  dotychczas – upgrade wymaga jedynie przeładowania frontendu i instalacji
  nowych zależności Pythona.

## ver3.0.0 (AI auto-reply & Twilio client cleanup)

### Podsumowanie

To wydanie wprowadza tryb AI auto-reply oparty o OpenAI, porządkuje klienta Twilio oraz czyści repozytorium z przypadkowo skomitowanego środowiska wirtualnego. System zachowuje dotychczasowe endpointy HTTP, ale sposób obsługi odpowiedzi SMS jest teraz ściślej zdefiniowany i bardziej przewidywalny.

### Najważniejsze zmiany

- Tryb **AI auto-reply**: gdy AI jest włączone, wszystkie przychodzące SMS-y są obsługiwane przez model OpenAI z wykorzystaniem historii rozmowy.
- Wzajemne wykluczenie trybów: AI auto-reply i klasyczny auto-reply nie mogą działać jednocześnie; AI ma pierwszeństwo.
- Refaktoryzacja klienta Twilio: spójne nazewnictwo (`twilio_client`), poprawne użycie `send_reply_to_inbound` dla odpowiedzi na wiadomości przychodzące.
- Uporządkowana dokumentacja: README opisuje dokładnie zachowanie AI, auto-reply i fallbackowego bota.
- Higiena repozytorium: usunięto katalog `.venv` z historii bieżącej gałęzi, dodano go do `.gitignore`.

### Kompatybilność i upgrade

- Brak zmian w publicznych endpointach HTTP – integracje mogą pozostać bez modyfikacji.
- Zachowanie odpowiedzi SMS może się zmienić, jeśli włączysz AI: odpowiedzi zaczną być generowane przez model OpenAI zamiast statycznego auto-reply.
- Zalecane jest odtworzenie środowiska wirtualnego lokalnie (poza repozytorium) zgodnie z instrukcjami w README.

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

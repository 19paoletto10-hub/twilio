# Twilio Chat App – ver3.0.0

Release tag: `ver3.0.0`
Data wydania: 2025-12-10
Środowisko referencyjne: Docker (Python 3.12, gunicorn)

## Podsumowanie

To wydanie koncentruje się na wprowadzeniu trybu AI auto‑reply opartego o OpenAI, uporządkowaniu klienta Twilio oraz higienie repozytorium. Aplikacja pozostaje kompatybilna z istniejącymi integracjami HTTP, a główne zmiany dotyczą sposobu generowania i wysyłania odpowiedzi SMS.

## Technologie i środowisko

- Język: Python 3.12 (obraz bazowy `python:3.12-slim`).
- Framework backendowy: Flask 3.0.3.
- Serwer HTTP w produkcji: gunicorn (2 workerów, 4 wątki każdy).
- Baza danych: SQLite (plikowo, domyślnie `data/app.db`).
- Integracje zewnętrzne:
  - Twilio (`twilio==9.3.1`) – obsługa SMS/MMS, webhooki, statusy.
  - OpenAI (`openai==1.59.3`) – generowanie odpowiedzi AI.
- Uruchomienie produkcyjne przez Docker/Docker Compose (port 3000, healthcheck na `/api/health`).

## Kluczowe funkcje aplikacji

- Webhooki Twilio: `/twilio/inbound`, `/twilio/status`.
- REST API: wysyłanie SMS/MMS, pobieranie/sync wiadomości, redakcja i kasowanie.
- Panel WWW: dashboard, widok czatu, konfiguracja auto‑reply i AI.
- Auto‑reply (worker w tle, kolejka w pamięci, deduplikacja SID, walidacja numerów w E.164).
- Tryb AI auto‑reply – globalne odpowiedzi AI na przychodzące SMS-y, z wykorzystaniem historii rozmowy.

## Zmiany w ver3.0.0

### 1. Nowy tryb AI auto‑reply

- System może automatycznie odpowiadać na wszystkie przychodzące SMS-y, wykorzystując model OpenAI oraz historię rozmowy przechowywaną w SQLite (`messages`).
- Włączenie AI (`AI_ENABLED=true` lub z poziomu UI) powoduje, że klasyczny auto‑reply oparty o szablon zostaje wyłączony – unikamy podwójnych odpowiedzi.
- Historia konwersacji jest budowana na podstawie wiadomości inbound/outbound dla danego numeru, co pozwala modelowi generować spójne, kontekstowe odpowiedzi.

### 2. Wzajemne wykluczenie AI i klasycznego auto‑reply

- Backend egzekwuje zasadę, że tryb AI auto‑reply i klasyczny auto‑reply nie działają równocześnie.
- Jeżeli AI jest aktywne dla danego numeru docelowego, worker auto‑reply nie kolejkuje ani nie wysyła odpowiedzi – całość obsługuje AI.
- Gdy AI jest wyłączone, a auto‑reply włączone, nadal działa dotychczasowy worker oparty o `auto_reply_config.message`.

### 3. Refaktoryzacja klienta Twilio

- Ujednolicone nazewnictwo: w całej aplikacji używany jest `twilio_client` oparty o klasę `TwilioService` z `app/twilio_client.py`.
- Dodano metodę `send_reply_to_inbound(inbound_from, inbound_to, body)`, która:
  - preferuje Messaging Service, jeśli jest skonfigurowany,
  - w przeciwnym razie używa numeru, na który przyszła wiadomość (`inbound_to`) lub `TWILIO_DEFAULT_FROM`,
  - utrzymuje poprawny wątek konwersacji po stronie Twilio.
- Metody `send_message` i `send_with_default_origin` zostały zachowane i wykorzystywane tam, gdzie kontekst inbound nie jest dostępny (np. CLI, scheduler przypomnień).

### 4. Uporządkowana dokumentacja

- `README.md` zawiera aktualny opis trybu AI auto‑reply, klasycznego auto‑reply oraz fallbackowego bota (`chat_logic.py`).
- Doprecyzowano zachowanie w zależności od ustawień:
  - AI **włączone** → globalny AI auto‑reply (OpenAI), auto‑reply wyłączony.
  - AI **wyłączone**, auto‑reply **włączone** → klasyczny auto‑reply worker.
  - AI **wyłączone**, auto‑reply **wyłączone** → prosty synchroniczny bot (`echo`/`keywords`).

### 5. Higiena repozytorium

- Usunięto przypadkowo skomitowany katalog `.venv` z historii bieżącej gałęzi.
- Dodano `.venv/` do `.gitignore`, tak aby środowisko wirtualne było tworzone lokalnie, poza kontrolą wersji.

## Kompatybilność i zalecenia upgrade

- Publiczne endpointy HTTP pozostają bez zmian – integracje oparte o API nie wymagają aktualizacji.
- Po włączeniu AI sposób generowania odpowiedzi SMS zmienia się z prostego szablonu na odpowiedzi generowane przez OpenAI, przy zachowaniu tych samych webhooków.
- Zalecane kroki po aktualizacji do `ver3.0.0`:
  1. Zaktualizuj kod aplikacji do commita/tagu `ver3.0.0`.
  2. Upewnij się, że środowisko wirtualne **nie** jest śledzone przez git (`.venv/` ignorowane).
  3. Ustaw zmienne środowiskowe `TWILIO_*`, `OPENAI_*` oraz `AI_*` zgodnie z sekcją "Zmienne środowiskowe" w `README.md`.
  4. Zweryfikuj działanie webhooków Twilio (`/twilio/inbound`, `/twilio/status`) oraz healthchecka `/api/health`.

## Jak utworzyć GitHub Release z tego tagu

1. Wejdź na stronę repozytorium w GitHub.
2. Przejdź do zakładki **Releases** → **Draft a new release**.
3. W polu **Tag** wybierz istniejący tag `ver3.0.0`.
4. W polu **Release title** wpisz np.: `ver3.0.0 – AI auto-reply and Twilio client cleanup`.
5. Jako treść opisu wklej zawartość tego pliku (lub jego skróconą wersję).
6. Opcjonalnie dołącz artefakty (np. wygenerowaną wersję HTML release notes z `deploy/releases/ver3.0.0.html`).
7. Zapisz release jako **Publish release**.

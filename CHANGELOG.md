# Changelog

## ver3.2.1 (Collapsible Sidebar + Compose Modal)

### Podsumowanie

Release 3.2.1 wprowadza znaczące ulepszenia interfejsu użytkownika, koncentrując się na
ergonomii pracy operatora. Główne zmiany to zwijane menu boczne (collapsible sidebar)
oraz nowoczesny modal kompozycji wiadomości, który umożliwia tworzenie SMS bez opuszczania
bieżącego widoku.

### Najważniejsze zmiany

#### 📐 Collapsible Sidebar (Zwijane menu boczne)
- Tryb rozwinięty (280px) z pełnymi etykietami i ikonami
- Tryb zwinięty (84px) z kompaktowymi ikonami i tooltipami
- Persystencja stanu w localStorage przeglądarki
- Płynne animacje CSS (0.25s ease)
- Responsywność: overlay na mobile, automatyczne zwijanie na tabletach

#### 📨 Compose Modal (Modal kompozycji wiadomości)
- Nowoczesne okno dialogowe do tworzenia wiadomości
- Walidacja numeru w formacie E.164
- Licznik znaków z ostrzeżeniem przy przekroczeniu 160
- Skróty klawiszowe: Ctrl+Enter (wyślij), Escape (zamknij)
- Toast z potwierdzeniem sukcesu/błędu

#### 🎨 Ulepszenia CSS
- Nowe zmienne CSS: `--app-sidebar-width`, `--app-sidebar-collapsed-width`
- Gradient accent color (#7c40ff → #f22f46)
- Spójne border-radius i shadows w całej aplikacji

#### 📱 Responsywność
- Desktop (≥992px): sidebar rozwinięty, zwijany ręcznie
- Tablet (<992px): sidebar zwinięty domyślnie
- Mobile (<576px): sidebar jako overlay z animacją slide-in

### Zaktualizowane pliki

```
app/templates/base.html           # Struktura sidebara i header
app/templates/dashboard.html      # Integracja z sidebar i modal
app/static/css/app.css            # Nowy design system + style sidebara
app/static/js/app.js              # Logika collapse
app/static/js/dashboard.js        # Obsługa modala
```

### Kompatybilność

- **Brak zmian łamiących** – wszystkie istniejące funkcjonalności działają bez modyfikacji
- **Brak migracji DB** – schemat pozostaje na wersji 7
- Wymaga przeglądarki z obsługą CSS Custom Properties (Chrome 88+, Firefox 78+, Safari 14+)

---

## ver3.2.0 (Docker Documentation + CI/CD + DevOps Toolkit)

### Podsumowanie

Release 3.2.0 to kompleksowa aktualizacja dokumentacji i narzędzi DevOps. Wprowadza pełny
przewodnik Docker od podstaw (z wyjaśnieniami wszystkich pojęć), automatyzację CI/CD przez
GitHub Actions, skrypt do backupu bazy danych oraz gotową konfigurację SSL/TLS z Let's Encrypt.
Rozbudowano również dokumentację bazy danych w developer-guide.md o pełny schemat tabel,
historię migracji i przykłady dodawania nowych struktur.

### Najważniejsze zmiany

#### 📚 Nowa dokumentacja Docker
- **[docs/docker-guide.md](docs/docker-guide.md)** – kompletny przewodnik Docker od zera:
  - Słownik 25+ pojęć Docker z wyjaśnieniami i analogiami dla początkujących
  - Instalacja Docker na Ubuntu/macOS/Windows
  - Diagramy architektury kontenerów (development vs production)
  - Quick Start w 5 minut
  - Krok po kroku: Development (6 kroków z komentarzami)
  - Krok po kroku: Production (5 kroków + konfiguracja webhooków Twilio)
  - Sekcja Troubleshooting z typowymi problemami
  - FAQ

#### 🔐 SSL/TLS z Let's Encrypt
- **[deploy/nginx/default-ssl.conf](deploy/nginx/default-ssl.conf)** – konfiguracja NGINX z HTTPS
- **[docker-compose.ssl.yml](docker-compose.ssl.yml)** – stack produkcyjny z certbot
- Automatyczne odnawianie certyfikatów (kontener certbot)
- Nagłówki bezpieczeństwa (X-Frame-Options, X-Content-Type-Options, HSTS)

#### 🔄 CI/CD z GitHub Actions
- **[.github/workflows/docker-build.yml](.github/workflows/docker-build.yml)** – workflow automatyzacji:
  - Build obrazu przy push do `main` lub tagu `ver*`
  - Publikacja do GitHub Container Registry (GHCR)
  - Testowanie obrazu (health check)
  - Opcjonalny auto-deploy przez SSH
  - Szczegółowe komentarze wyjaśniające każdy krok

#### 💾 Backup bazy danych
- **[scripts/backup_db.sh](scripts/backup_db.sh)** – profesjonalny skrypt backup:
  - Automatyczne wykrywanie źródła (Docker lub lokalnie)
  - Weryfikacja integralności SQLite
  - Rotacja starych backupów (domyślnie 7 dni)
  - Tryby `--dry-run`, `--list`, `--restore`
  - Kolorowy output i szczegółowe logi

#### 📖 Rozszerzona dokumentacja bazy danych
- **[docs/developer-guide.md](docs/developer-guide.md)** – rozbudowana sekcja DB:
  - Pełna struktura 6 tabel z opisami kolumn
  - Historia migracji (wersja 1→7)
  - Diagram przepływu `_ensure_schema()`
  - Przykład krok po kroku: dodawanie nowej tabeli
  - Opis normalizacji numerów telefonów
  - Tabela helper functions i best practices

#### 🛠️ Rozszerzony Makefile
- Nowe komendy: `make compose-ssl`, `make backup`, `make restore`, `make health`
- Czytelny help z ramkami ASCII

### Nowe pliki

```
.github/workflows/docker-build.yml    # CI/CD workflow
deploy/nginx/default-ssl.conf         # NGINX z SSL
deploy/certbot/www/.gitkeep           # Katalog Let's Encrypt challenge
deploy/certbot/conf/.gitkeep          # Katalog certyfikatów
docker-compose.ssl.yml                # Compose z SSL
docs/docker-guide.md                  # Przewodnik Docker
scripts/backup_db.sh                  # Skrypt backup
```

### Zaktualizowane pliki

```
README.md                             # Rozszerzona sekcja Docker + tabele dokumentacji
docs/README.md                        # Nowy spis treści z linkami
docs/developer-guide.md               # Rozbudowana sekcja bazy danych
Makefile                              # Nowe komendy
```

### Kompatybilność i upgrade

- **Brak zmian łamiących** – wszystkie istniejące funkcjonalności działają bez modyfikacji
- **Brak migracji DB** – schemat pozostaje na wersji 7
- Nowe pliki nie wpływają na działanie aplikacji w istniejących deploymentach
- Zalecane: przejrzenie nowego przewodnika Docker przed kolejnym wdrożeniem

### Użycie opublikowanego obrazu (po merge)

```bash
# Pull z GitHub Container Registry
docker pull ghcr.io/19paoletto10-hub/twilio:latest

# Lub z tagiem wersji
docker pull ghcr.io/19paoletto10-hub/twilio:3.2.0
```

---

## ver3.1.3 (Chunked SMS + docs refresh)

### Podsumowanie

Release 3.1.3 uszczelnia wysyłkę dłuższych treści generowanych przez AI (w tym News/RAG),
tak aby nie kończyły się błędem Twilio przy przekroczeniu limitu długości SMS.
Aplikacja dzieli wiadomości na bezpieczne części (domyślnie 1500 znaków) i wysyła je jako
kilka SMS-ów. Wydanie porządkuje też dokumentację (README + docs + release notes).

### Najważniejsze zmiany

- **Dzielenie długich wiadomości SMS** – [app/message_utils.py](app/message_utils.py)
  wprowadza wspólną logikę dzielenia tekstu (z próbą cięcia po granicach zdań/akapitów).
- **Wysyłka wieloczęściowa przez Twilio** – [app/twilio_client.py](app/twilio_client.py)
  dodaje metodę `send_chunked_sms()` używaną przez moduły wysyłkowe, aby unikać błędu
  „The concatenated message body exceeds the 1600 character limit”.
- **News i AI bez ucinania treści** – ręczne i zaplanowane wysyłki newsów oraz odpowiedzi AI
  wysyłają treść w częściach zamiast obcinać ją do 1600 znaków.
- **Odświeżona dokumentacja** – README i dokumenty w `docs/`/`deploy/releases/` zawierają
  spójne instrukcje uruchomienia, konfiguracji i przewodnik po kodzie.

### Kompatybilność i upgrade

- Brak zmian łamiących w endpointach HTTP.
- Jeśli integrujesz się bezpośrednio z Twilio: pamiętaj, że jedna „odpowiedź” aplikacji może
  zostać wysłana jako kilka SMS-ów (kilka SID-ów).

## ver3.1.2 (Multi-SMS batches & release hygiene)

### Podsumowanie

Release 3.1.2 dodaje pełny moduł Multi-SMS: worker w tle, tabele w SQLite,
REST API oraz zakładkę w panelu WWW. Dzięki temu operator może przygotować
batch z poziomu UI lub API i monitorować postęp wysyłki. Wydanie dostarcza też
skrypt budowania paczek release, aby publiczne artefakty nie zawierały
wrażliwych danych (`data/`, `X1_data/`, `.env`).

### Najważniejsze zmiany

- **Worker & schema v7** – [app/multi_sms.py](app/multi_sms.py) przetwarza batch'e,
  a [app/database.py](app/database.py) dodaje tabele `multi_sms_batches` oraz
  `multi_sms_recipients` wraz z migracją i licznikami sukcesów/błędów.
- **Panel „Multi-SMS”** – [app/templates/dashboard.html](app/templates/dashboard.html)
  i [app/static/js/dashboard.js](app/static/js/dashboard.js) umożliwiają tworzenie
  zadań, obserwowanie historii i rozwijanie statusów odbiorców.
- **REST API** – [app/webhooks.py](app/webhooks.py) udostępnia endpointy
  `POST/GET /api/multi-sms/batches` + szczegóły odbiorców, z walidacją limitów.
- **Release hygiene** – [scripts/prepare_release_bundle.sh](scripts/prepare_release_bundle.sh)
  buduje katalog `release/dist/<tag>/` zawierający tylko kod i dokumentację,
  co ułatwia publikację paczek bez sekretów.

### Kompatybilność i upgrade

- Migracja schematu do wersji 7 uruchamia się automatycznie – przed aktualizacją
  wykonaj backup `data/app.db`.
- Multi-SMS wymaga skonfigurowanego `TWILIO_DEFAULT_FROM` lub Messaging Service SID;
  bez tego API zwróci błąd.
- Przed publikacją release uruchom `./scripts/prepare_release_bundle.sh ver3.1.2`
  i załącz wygenerowaną paczkę (bez `data/`, `X1_data/`, `.env`).

## ver3.1.1 (Precise ALL-CATEGORIES summaries)

### Podsumowanie

Wydanie doprecyzowuje zachowanie trybu podsumowania newsów "ALL‑CATEGORIES".
Model otrzymuje osobne, wyraźnie oznaczone konteksty dla każdej kategorii oraz
jasne instrukcje co do formatu odpowiedzi (nagłówek + 2–3 krótkie zdania na
kategorię, bez wypunktowań). Dzięki temu streszczenia są bardziej
przewidywalne i nie mieszają faktów między kategoriami.

### Najważniejsze zmiany

- **News/RAG – kontekst per kategoria** – `answer_query_all_categories()`
  buduje osobne konteksty FAISS dla każdej kategorii z kontrolowanym budżetem
  znaków, co poprawia separację tematów i ułatwia debugowanie.
- **Stabilny format ALL‑CATEGORIES** – prompty wymagają formatu
  "Kategoria: <nazwa>" + 2–3 krótkie zdania (bez wypunktowań) oraz jawnego
  komunikatu `brak danych`, gdy FAISS nie zwraca fragmentów.
- **Spójne prompty backendowe** – `ALL_CATEGORIES_PROMPT` i prompty w
  `FAISSService` opisują tę samą, jednoznaczną semantykę trybu ALL‑CATEGORIES.

### Kompatybilność i upgrade

- Brak zmian łamiących w webhookach Twilio oraz modułach AI/auto‑reply.
- Istniejąca konfiguracja odbiorców (`use_all_categories`) pozostaje ważna –
  zmienia się jedynie sposób budowy kontekstu i format odpowiedzi.

## ver3.1.0 (All-categories News mode + dashboard UX hardening)

### Podsumowanie

Wydanie domyka tryb podsumowania newsów „ALL‑CATEGORIES” jako funkcję konfigurowalną
z poziomu panelu i API (per‑odbiorca i per‑test), a dodatkowo porządkuje UX w panelu:
wyniki pokazują tryb, prompty są spójne z wybranym trybem, a historia wiadomości ma
stabilny układ tabeli (stała wysokość wierszy w kolumnie treści).

### Najważniejsze zmiany

- **News/RAG – tryb ALL‑CATEGORIES jako opcja** – flagę `use_all_categories` można
  ustawiać w UI (test FAISS + odbiorcy) i przesyłać w API; scheduler respektuje
  ustawienie per‑odbiorca.
- **Prompty per‑tryb** – aplikacja utrzymuje osobny prompt dla STANDARD oraz
  ALL‑CATEGORIES, co ogranicza „dryf” promptów i stabilizuje format odpowiedzi.
- **Dashboard – czytelność historii** – kolumna „Treść” w historii wiadomości ma
  stałą wysokość wierszy (dłuższe teksty są skracane), co poprawia skanowalność.

### Kompatybilność i upgrade

- Brak zmian łamiących w webhookach Twilio i modułach AI/auto‑reply.
- Jeśli integrujesz się z endpointami News, możesz (opcjonalnie) zacząć wysyłać
  `use_all_categories`; w przeciwnym razie zachowanie pozostaje zgodne z domyślną
  konfiguracją (ALL‑CATEGORIES włączone).

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

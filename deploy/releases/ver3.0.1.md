# Twilio Chat App – ver3.0.1

Release tag: `ver3.0.1`
Data wydania: 2025-12-10
Środowisko referencyjne: Docker (Python 3.12, gunicorn)

## Podsumowanie

To wydanie skupia się na dopracowaniu panelu WWW i ergonomii pracy operatora.
Rozszerza możliwości podglądu rozmów, ułatwia nawigację do widoku czatu oraz
porządkuje sposób prezentacji historii wiadomości – bez zmian w publicznych
endpointach HTTP i bez ingerencji w istniejące integracje Twilio.

## Technologie i środowisko

- Język: Python 3.12 (obraz bazowy `python:3.12-slim`).
- Framework backendowy: Flask 3.0.3.
- Serwer HTTP w produkcji: gunicorn (2 workerów, 4 wątki każdy).
- Baza danych: SQLite (plikowo, domyślnie `data/app.db`).
- Integracje zewnętrzne:
  - Twilio (`twilio==9.3.1`) – obsługa SMS/MMS, webhooki, statusy.
  - OpenAI (`openai==1.59.3`) – generowanie odpowiedzi AI.
- Uruchomienie produkcyjne przez Docker/Docker Compose (port 3000, healthcheck na `/api/health`).

## Zakres zmian w ver3.0.1

### 1. Ulepszona historia wiadomości w panelu

- Przebudowano tabelę historii wiadomości (zakładka „Wiadomości”) tak, aby była
  bardziej czytelna i przyjazna przy większej liczbie wpisów:
  - każda wiadomość prezentuje skrócony, jednowierszowy podgląd treści
    (pełna treść dostępna w `title` – po najechaniu kursorem),
  - czas wysłania/odebrania podzielono na godzinę i datę w dedykowanej kolumnie,
  - informacja o uczestniku (numer) zawiera teraz także kontekst kanału i
    kierunku (np. `WhatsApp • od klienta`, `SMS • do klienta`).
- Ujednolicono wygląd kolumny uczestnika oraz pola czasu we wszystkich
  filtrach historii („Wszystkie”, „Przychodzące”, „Wychodzące”), dzięki czemu
  tabela zachowuje spójny layout niezależnie od użytego filtra.

### 2. Szybsza nawigacja do widoku czatu

- Dodano możliwość wejścia do widoku pełnego czatu (ścieżka `/chat/<numer>`) nie
  tylko przez przycisk w kolumnie „Czat”, lecz także przez kliknięcie wiersza
  w tabeli historii wiadomości.
- Klikalne są wszystkie wiersze, dla których aplikacja zna uczestnika
  rozmowy (numer telefonu lub adres kanału, np. `whatsapp:+48123…`).
- Kliknięcie w elementy interaktywne w wierszu (np. przycisk „Otwórz”) nadal
  działa jak dotychczas – mechanizm nawigacji po wierszu został zaprojektowany
  tak, aby nie kolidować z istniejącymi kontrolkami.

### 3. Konsekwentne oznaczenia uczestnika i kanału

- Wprowadzono helper odpowiedzialny za budowanie etykiet uczestnika na frontendzie
  (dla każdego wpisu w historii wiadomości):
  - rozpoznaje kanał po prefiksie (`whatsapp:`, `sms:`, `mms:`),
  - normalizuje wartość do czytelnej postaci (usuwając prefiks do wyświetlenia),
  - dodaje opis roli (`od klienta` / `do klienta`) w zależności od kierunku
    wiadomości (`inbound`/`outbound`).
- Dzięki temu operator od razu widzi, czy dana wiadomość pochodziła od klienta,
  czy została wysłana z aplikacji, a także przez jaki kanał dotarła.

### 4. Uspójnienie doświadczenia użytkownika (UX)

- Drobne poprawki stylistyczne w tabeli historii:
  - specjalne klasy stylów dla kolumny uczestnika (dwuliniowa prezentacja:
    numer + opis meta),
  - małe, spójne opisy czasu z rozdzieleniem godziny i daty,
  - kursor `pointer` dla klikanych wierszy, aby wizualnie sugerować możliwość
    przejścia do szczegółów rozmowy.
- Zmiany te wpisują się w istniejący wygląd dashboardu (skeleton loading,
  modernistyczne karty, gradientowy nagłówek), nie wprowadzając nowych
  zależności ani łamiących zmian w HTML szablonu.

## Kompatybilność i upgrade

- Brak zmian w publicznych endpointach HTTP ani w modelu danych. Aktualizacja
  do `ver3.0.1` jest w pełni kompatybilna z backendem wprowadzonym w `ver3.0.0`.
- Zmiany obejmują wyłącznie warstwę frontendową (CSS/JS) oraz zachowanie panelu
  WWW – backend API oraz logika AI/auto‑reply pozostają bez zmian.
- Po stronie operatora nie są wymagane dodatkowe kroki poza wdrożeniem nowej
  wersji obrazu/kodu:
  1. Zaktualizuj aplikację do commita/tagu `ver3.0.1`.
  2. Odbuduj obraz Dockera lub przeprowadź standardowy deployment.
  3. Odśwież panel WWW w przeglądarce, aby załadować nowe zasoby statyczne.

## Jak utworzyć GitHub Release z tego tagu

1. Wejdź na stronę repozytorium w GitHub.
2. Przejdź do zakładki **Releases** → **Draft a new release**.
3. W polu **Tag** wybierz istniejący tag `ver3.0.1`.
4. W polu **Release title** wpisz np.: `ver3.0.1 – UX improvements for dashboard message history`.
5. Jako treść opisu wklej zawartość tego pliku (lub jego skróconą wersję).
6. Opcjonalnie dołącz artefakty (np. wygenerowaną wersję HTML release notes z
   `deploy/releases/ver3.0.1.html`).
7. Zapisz release jako **Publish release**.

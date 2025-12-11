# Twilio Chat App – ver3.0.2

Release tag: `ver3.0.2`
Data wydania: 2025-12-11
Środowisko referencyjne: Docker (Python 3.12, gunicorn)

## Podsumowanie

Ta wersja zamienia moduł News/RAG w w pełni obserwowalne, biznesowo gotowe narzędzie.
Indeks FAISS opiera się wyłącznie na embeddingach OpenAI, potrafi raportować stan i
liczbę wektorów, a panel WWW zyskał własny pulpit kontrolny z szybkim testem
zapytania oraz podglądem fragmentów źródłowych.

## Technologie i środowisko

- Język: Python 3.12 (obraz bazowy `python:3.12-slim`).
- Framework backendowy: Flask 3.0.3.
- Serwer HTTP: `gunicorn` (dodany do `requirements.txt`).
- Baza danych: SQLite (`data/app.db`).
- Integracje:
  - Twilio (`twilio==9.3.1`) – SMS/MMS, webhooki.
  - OpenAI (`openai==1.59.3`) – embeddingi i generowanie odpowiedzi.
  - LangChain 0.3 (`langchain-core`, `langchain-community`, `langchain-text-splitters`).
- Uruchomienie: Docker / docker-compose, port 3000, healthcheck `/api/health`.

## Zakres zmian w ver3.0.2

### 1. FAISS tylko z OpenAI
- `FAISSService` usuwa fallback hashujący i wymaga poprawnego `SECOND_OPENAI`
  lub `OPENAI_API_KEY`; brak konfiguracji kończy się wyjątkiem jeszcze przed
  budową indeksu, dzięki czemu operator natychmiast wie o problemie.
- Zapis indeksu obejmuje komplet plików (`index.faiss`, `index.pkl`,
  `documents.json`), a odpowiedzi API dostarczają `context_preview` oraz listę
  fragmentów (`results`) użytych w danym RAG.

### 2. Nowe API diagnostyczne
- `/api/news/faiss/status` zwraca informacje o rozmiarze indeksu, liczbie
  wektorów, ścieżkach plików i modelach (embedding + chat).
- `/api/news/test-faiss` zwraca dodatkowo fragmenty i nazwę modelu, a wszystkie
  akcje powiązane z News/RAG (test odbiorcy, wymuszenie wysyłki, build index)
  jasno komunikują brak indeksu lub klucza OpenAI.

### 3. Panel „News po AI”
- Nowa karta statusowa pokazuje stan indeksu (ładowanie/aktywny/brak plików),
  modele, rozmiar, liczbę wektorów oraz datę ostatniego odświeżenia.
- Dodano przycisk „Szybki test”, który wysyła domyślny prompt i natychmiast
  wyświetla odpowiedź oraz fragmenty źródłowe, dzięki czemu operator weryfikuje
  jakość danych bez opuszczania panelu.
- Sekcja „Fragmenty użyte w odpowiedzi” prezentuje fragmenty, które zasiliły
  model LLM – to kluczowe przy audytach i marketingowych QA.

### 4. Zależności i deployment
- `requirements.txt` zawiera teraz `gunicorn` oraz `langchain-text-splitters`,
  co odzwierciedla realne środowisko. Po aktualizacji wykonaj `pip install -r
  requirements.txt`, aby zainstalować brakujące pakiety.
- Dockerfile już w poprzednim wydaniu korzystał z gunicorna – teraz pakiet jest
  oficjalnie trackowany w zależnościach, dzięki czemu build jest powtarzalny.

## Kompatybilność i upgrade

1. Ustaw `SECOND_OPENAI=sk-...` (lub `OPENAI_API_KEY`) w `.env` zanim uruchomisz
   scraping/FAISS – brak klucza przerwie proces.
2. `pip install -r requirements.txt` (nowe paczki LangChain + gunicorn).
3. `docker compose up --build` lub równoważny restart, aby panel WWW pobrał nowe
   zasoby JS/CSS.
4. W panelu News kliknij „Odśwież status” – powinna pojawić się aktualna
   informacja o indeksie. Jeśli dane wyglądają na stare, wykonaj `Scrape + Build`
   lub `🔨 Zbuduj Indeks FAISS`.

## Jak opublikować release na GitHubie

1. Przejdź do zakładki **Releases** i wybierz **Draft a new release**.
2. Ustaw **Tag** i **Release title** na `ver3.0.2` / `ver3.0.2 – News & FAISS control plane`.
3. Wklej treść tego pliku (lub jego wersję HTML z `deploy/releases/ver3.0.2.html`).
4. Opcjonalnie dodaj artefakty (np. plik HTML z opisem).
5. Kliknij **Publish release**.

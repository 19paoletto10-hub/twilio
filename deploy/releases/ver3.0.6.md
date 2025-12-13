# Twilio Chat App – ver3.0.6

Release tag: `ver3.0.6`
Data wydania: 2025-12-13
Środowisko referencyjne: Docker (Python 3.12, gunicorn)

## Podsumowanie

Wydanie skupia się na operacyjnej gotowości modułu News/RAG. Dokumentacja i panel
otrzymały kompletny przewodnik backupu indeksu FAISS (eksport ZIP + manifest,
import z walidacją, checklisty odtworzenia), scraper Business Insider filtruje
linki ściśle wg kategorii, a interfejs wyświetla czasy w lokalnej strefie
(także w tabeli "Bazy FAISS") – indeks zawiera właściwe artykuły i daje się
przewidywalnie przywrócić.

## Technologie i środowisko

- Język: Python 3.12 (`python:3.12-slim`).
- Framework backendowy: Flask 3.0.3.
- Serwer HTTP: `gunicorn` (uruchamiany przez `run.py` / Dockerfile).
- Baza danych: SQLite (`data/app.db`).
- Integracje: Twilio (`twilio==9.3.1`), OpenAI (`openai==1.59.3`), LangChain 0.3.
- Artefakty danych: `X1_data/faiss_openai_index/`, `X1_data/articles.jsonl`,
  `X1_data/documents.jsonl`, `data/app.db` (wszystkie opisane w README wraz
  z procedurą backupu).

## Najważniejsze zmiany

### 1. Pełna dokumentacja backupu FAISS
- README i "Changes & Capabilities" opisują eksport ZIP (GET `/api/news/faiss/export`),
  import (POST `/api/news/faiss/import`) i status (GET `/api/news/faiss/status`).
- Manifest backupu zawiera listę wymaganych plików (`index.faiss`, `index.pkl`,
  `documents.json(l)`, `news_config.json`), co upraszcza audyty i DR.
- UI (zakładka News) prowadzi operatora krok po kroku: przyciski "Eksportuj"
  i "Wgraj" raportują wynik, a status backupu wskazuje kompletność (`backup_ready`).
- Runbook opisuje jak wykonywać kopie `X1_data/` + `data/app.db`, jak testować
  FAISS po restore oraz jak reagować na brak indeksu (rebuild lub import zip).

### 2. Scraper Business Insider – szczelne filtrowanie kategorii
- `ScraperService.extract_article_links()` akceptuje wyłącznie URL-e zgodne z
  bazowym prefiksem kategorii (np. "/biznes" dla sekcji Biznes), co usuwa
  duplikaty między sekcjami i przypadkowe artykuły z innych kanałów.
- W logach pojawia się jasna informacja o odrzuconych linkach, dzięki czemu
  łatwo monitorować zmiany struktury serwisu źródłowego.
- Kanoniczny store `X1_data/articles.jsonl` oraz pliki `*.json`/`*.txt` na
  kategorię zachowują czystość danych, a FAISS build nie musi już deduplikować
  krzyżowo.

### 3. Runbook i panel operacyjny
- Sekcja "Dane i backup" w README precyzuje kolejność backupu, narzędzia (`sqlite3 .backup`,
  panelowe ZIP) i proces walidacji po przywróceniu (test FAISS, lista plików, rebuild).
- `docs/changes-and-capabilities.md` zawiera skrócony scenariusz publikacji backupu
  oraz komunikatów UI, dzięki czemu release notes są jedynym źródłem prawdy dla zespołów
  biznesowych.
- W panelu News guziki „Eksportuj backup” i „Wgraj backup” są opatrzone opisami,
  a sekcja statusu pokazuje liczbę dokumentów, aktywny indeks i spójność backupu.

### 4. UX i spójne strefy czasowe
- Tabela "Bazy FAISS" korzysta z tych samych helperów formatujących datę/godzinę co lista
  wiadomości – operator zawsze widzi lokalny czas (data + godzina w osobnych liniach).
- Komunikaty toast/alert odnoszą się do lokalnych stref, co ułatwia korelację z logami Twilio
  i schedulerów (brak różnic +-1h).

## Kompatybilność i upgrade

1. Zrób snapshot katalogów `X1_data/` oraz `data/app.db` (lub użyj nowego eksportu ZIP).
2. Zdeployuj commit `9a9512a` lub tag `ver3.0.6` (Docker build / `pip install -r requirements.txt`).
3. W panelu News:
   - pobierz świeży backup (powinien zawierać manifest),
   - kliknij "Odśwież status" i upewnij się, że `backup_ready=true` i indeks został załadowany.
4. Uruchom test FAISS (prompt domyślny lub własny) – wynik powinien zawierać listę fragmentów.
5. (Opcjonalnie) Wykonaj ręczny scraping jednej kategorii, aby potwierdzić poprawne filtrowanie URL.

## Publikacja release na GitHubie

1. Przejdź do zakładki **Releases** → **Draft a new release**.
2. Ustaw **Tag** i **Release title** na `ver3.0.6` / `ver3.0.6 – FAISS backup playbook`.
3. Wklej tę notatkę (lub dołącz HTML z `deploy/releases/ver3.0.6.html`).
4. Opcjonalnie załącz wygenerowany ZIP backupu jako artefakt dowodowy.
5. Kliknij **Publish release**.

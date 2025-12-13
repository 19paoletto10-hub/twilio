# Zmiany i aktualne możliwości

Dokument podsumowuje wprowadzone zmiany oraz aktualny zakres funkcji aplikacji Twilio Chat App. Skupia się na perspektywie technicznej i operacyjnej (co zostało dodane, jak działa, jak używać w biznesie/utrzymaniu).

## Kluczowe zmiany (backend)
- Spójna konfiguracja przez dataclasses i walidację env w [app/config.py](app/config.py) (m.in. SECOND_OPENAI, SECOND_MODEL, EMBEDDING_MODEL; maskowanie kluczy w logach dev).
- Rozbudowana warstwa Twilio w [app/twilio_client.py](app/twilio_client.py): wsparcie Messaging Service, bezpieczny fallback do `TWILIO_DEFAULT_FROM`, helper `send_sms()` z bezpiecznym rezultatem.
- Nowe i rozszerzone API w [app/webhooks.py](app/webhooks.py):
  - SMS: wysyłka (`/api/send-message`), lista/filtry/statystyki (`/api/messages*`), rozmowy (`/api/conversations*`), redakcja/usuwanie, webhook statusów `/twilio/status`.
  - Auto-odpowiedzi: odczyt/zapis `/api/auto-reply/config` z koordynacją trybu AI vs klasyczny.
  - AI: konfiguracja/test/podgląd rozmowy `/api/ai/*`, generowanie i wysyłka odpowiedzi `/api/ai/send`.
  - Przypomnienia: CRUD `/api/reminders` (cykliczne SMS).
  - News/RAG: odbiorcy (`/api/news/recipients*`), test łączności, ręczny send, scraping (`/api/news/scrape`), budowa indeksu (`/api/news/indices/build`), test FAISS (`/api/news/test-faiss`), zarządzanie plikami i indeksami.
- RAG/FAISS warstwa w [app/faiss_service.py](app/faiss_service.py):
  - build/load/save indeksu z fallbackiem MinimalVectorStore; odbudowa z `docs.json(l)` lub `articles.jsonl`, multi-source build z per-art. chunków;
  - wyszukiwanie semantyczne + odpowiedzi LLM (NewsOpenAIService) lub fallback tekstowy;
  - tryb `answer_query_all_categories`/`search_all_categories`, który wymusza pokrycie każdej kategorii, używany m.in. przez scheduler newsów;
  - użycie modeli OpenAI z klucza SECOND_OPENAI / fallback hash embeddings.
- Lifecycle backup FAISS w [app/webhooks.py](app/webhooks.py): `GET /api/news/faiss/export` (zip + manifest), `POST /api/news/faiss/import` (walidacja i atomowy restore, limit 250 MB), `GET /api/news/faiss/status` (kondycja indeksu + kompletność backupu) oraz `DELETE /api/news/indices/faiss_openai_index`, który usuwa wszystkie artefakty FAISS i zwraca listy `removed/missing/failed`.
- Scraper Business Insider w [app/scraper_service.py](app/scraper_service.py): sesja z retry + robots cache, czyści treść, zapisuje `.txt` i `.json`, a także kanoniczny store `X1_data/articles.jsonl` (dedup hash/URL) wykorzystywany przez FAISS; opcjonalnie triggeruje budowę indeksu, a link zostaje zaakceptowany tylko gdy pasuje prefiksowi kategorii (eliminuje duplikaty między sekcjami).
- Harmonogram newsów w [app/news_scheduler.py](app/news_scheduler.py): pętla w tle (co minutę) wysyła dzienne powiadomienia SMS do aktywnych odbiorców z konfigiem godziny, pilnuje `last_sent_at`, waliduje numery i korzysta z trybu podsumowania wszystkich kategorii.
- Inicjalizacja serwisów i workerów w [app/__init__.py](app/__init__.py): start auto-reply worker, scheduler przypomnień, scheduler news, healthcheck `/api/health`.

## Kluczowe zmiany (frontend / UX)
- Nowy dashboard w [app/templates/dashboard.html](app/templates/dashboard.html) + logika w [app/static/js/dashboard.js](app/static/js/dashboard.js):
  - zakładki Wiadomości, Auto-odpowiedź, Przypomnienia, AI, News;
  - auto-odświeżanie listy wiadomości i statystyk, szybka wysyłka SMS;
  - pełne formularze dla auto-reply, AI (konfiguracja + test OpenAI), przypomnień, newsów (odbiorcy, test FAISS, scraping, budowa indeksu, podgląd plików, ustawienie aktywnej bazy);
  - skeletony ładowania, toasty, badge statusów.
- Sekcja backupu FAISS w zakładce News: przycisk eksportu zip, uploader importu (z walidacją postępu), wskaźnik kompletności backupu oraz toasty z raportem `removed/missing/failed` po czyszczeniu indeksu.
- Widok „Bazy FAISS” wykorzystuje wspólne helpery czasu (data + godzina w lokalnej strefie), więc UI jest spójny z listą wiadomości oraz logami schedulerów.
- Ulepszona estetyka w [app/static/css/app.css](app/static/css/app.css): gradientowa nawigacja, karty, kafelki plików news, overlay podglądu pliku, dopasowanie do nowych sekcji.

## Aktualne możliwości biznesowe
- Hub SMS/WhatsApp: odbiór webhooków, prowadzenie rozmów 1:1, podgląd historii, ręczna wysyłka/odpowiedź, statusy dostarczenia.
- Tryby odpowiedzi:
  - klasyczna auto-odpowiedź (szablon) z kolejką workerów,
  - AI auto-odpowiedź dla wybranego numeru (OpenAI chat, konfigurowalne parametry, fallback na klasyczne auto-reply gdy AI wyłączone),
  - prosty silnik czatu (fallback gdy AI/auto-reply off).
- Przypomnienia SMS: cykliczne wysyłki na zadany numer i interwał (minuty), możliwość pauzy/usunięcia.
- News / FAISS / RAG:
  - scraping kategorii Business Insider PL (txt+json),
  - budowa indeksu wektorowego, test zapytań FAISS, generowanie podsumowań newsów (LLM lub fallback),
  - lista odbiorców z godziną i promptem, ręczne wysyłki, automatyczna dystrybucja 1x/dziennie przez scheduler,
  - backup zip (eksport/import + status kompletności) oraz pełne czyszczenie indeksu z raportem `removed/missing/failed`.
- Operacje danych: podgląd/usuń pliki scrapów, ustaw aktywny indeks, przebudowa indeksu z plików lub snapshotu.

## Konfiguracja i zależności
- Zależności: [requirements.txt](requirements.txt) (Flask 3, Twilio SDK 9, OpenAI 1.59, FAISS CPU, bs4/trafilatura, numpy/requests).
- Wzór env: [.env.example](.env.example) uzupełniony o SECOND_OPENAI/SECOND_MODEL/EMBEDDING_MODEL, flagę TWILIO_VALIDATE_SIGNATURE, domyślne porty i ścieżki danych (data/, X1_data/).
- Kluczowe oczekiwania środowiskowe:
  - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, oraz `TWILIO_DEFAULT_FROM` lub `TWILIO_MESSAGING_SERVICE_SID`;
  - `SECOND_OPENAI` dla embeddings/RAG + `OPENAI_API_KEY`/`AI_*` dla czatu AI;
  - katalogi danych: `data/app.db`, `X1_data/faiss_openai_index/`, `X1_data/business_insider_scrapes/` (tworzone automatycznie jeśli brak).

## Ścieżki operacyjne (runbook skrócony)
- Dashboard
  1) Wysłanie SMS: zakładka Wiadomości → formularz → `/api/send-message`.
  2) Auto-reply: włącz i zapisz szablon → `/api/auto-reply/config` (wyłącza AI jeśli aktywna).
  3) AI: uzupełnij klucz, numer, prompt, model → zapisz (`/api/ai/config`), test (`/api/ai/test`), podgląd historii (`/api/ai/conversation`).
  4) Przypomnienia: dodaj w formularzu → `/api/reminders`, akcje toggle/delete.
  5) News: dodaj odbiorcę → `/api/news/recipients`, test FAISS (`/api/news/test-faiss`), scraping+build (`/api/news/scrape`), ręczna budowa (`/api/news/indices/build`), podgląd/usuń pliki i indeksy oraz eksport/import backupu (`/api/news/faiss/export|import`).
- API / integracja zewnętrzna
  - Webhooki Twilio: `/twilio/inbound`, `/twilio/status` (walidacja sygnatury zależna od `TWILIO_VALIDATE_SIGNATURE`).
  - Zdrowie: `/api/health` zwraca status, env, flagę OpenAI.
- Background
  - Auto-reply worker (kolejka SID) oraz reminder worker uruchamiane przy starcie.
  - News scheduler (co 60s) dostarcza dzienne powiadomienia i aktualizuje `last_sent_at`.

## Weryfikacja po wdrożeniu
- Twilio: wyślij testowy SMS na numer aplikacji → sprawdź zapis w panelu + status delivery.
- Auto-reply: włącz, wyślij inbound, potwierdź zwrotkę i wpis w bazie.
- AI: przetestuj `/api/ai/test` z kluczem, sprawdź podgląd historii AI w UI.
- News: uruchom `Scrape` w UI, sprawdź kafelki plików i wynik testu FAISS; dodaj odbiorcę, wymuś wysyłkę „Wyślij”.
- Przypomnienia: dodaj rekord, upewnij się że worker wysyła co zadany interwał.

## Ryzyka i notatki
- Brak klucza OpenAI ⇒ embeddings w trybie fallback (hash), LLM odpowiedzi wyłączone; komunikaty w logach i UI.
- Brak `TWILIO_DEFAULT_FROM` i Messaging Service ⇒ blokada wysyłki w [app/twilio_client.py](app/twilio_client.py).
- Indeks FAISS może być pusty po czyszczeniu plików – UI i API sugerują rebuild; backup `X1_data/` i `data/app.db` kluczowy.
- X1_data/scrapes i indeksy mogą być duże – kontroluj wersjonowanie/backupy zgodnie z polityką repo.

## Szybkie odniesienia do kodu
- Konfiguracja i bootstrap: [app/__init__.py](app/__init__.py), [app/config.py](app/config.py).
- API/HTTP: [app/webhooks.py](app/webhooks.py), [app/ui.py](app/ui.py).
- Warstwa Twilio: [app/twilio_client.py](app/twilio_client.py).
- AI / auto-reply / workers: [app/ai_service.py](app/ai_service.py), [app/auto_reply.py](app/auto_reply.py), [app/reminder.py](app/reminder.py).
- News / RAG: [app/scraper_service.py](app/scraper_service.py), [app/faiss_service.py](app/faiss_service.py), [app/news_scheduler.py](app/news_scheduler.py).
- UI/Front: [app/templates/dashboard.html](app/templates/dashboard.html), [app/static/js/dashboard.js](app/static/js/dashboard.js), [app/static/css/app.css](app/static/css/app.css).

# Twilio Chat App – ver3.1.3

Release tag: `ver3.1.3`
Data wydania: 2025-12-14
Środowisko referencyjne: Docker (Python 3.12, gunicorn)

## Podsumowanie

Wersja 3.1.3 usuwa ryzyko błędów Twilio dla długich wiadomości generowanych przez AI i moduł
News/RAG. Treści są automatycznie dzielone na bezpieczne części (limit 1500 znaków) i wysyłane
jako kilka SMS-ów. Wydanie aktualizuje też dokumentację (README, docs/, pełna dokumentacja HTML)
i ujednolica instrukcje release'owe.

### Co to daje operacyjnie
- brak błędów „The concatenated message body exceeds the 1600 character limit” przy długich
  odpowiedziach AI/News,
- spójna dokumentacja: jedna mapa (README), szczegóły techniczne (docs/), pełny HTML i release notes
  gotowe do wklejenia w GitHub Release,
- gotowe instrukcje bundlowania paczki bez danych wrażliwych.

## Technologie i środowisko

- Język: Python 3.12
- Framework backendowy: Flask 3
- Serwer HTTP: gunicorn
- Baza danych: SQLite (`data/app.db`) z automatycznymi migracjami
- Integracje: Twilio (SMS), OpenAI (AI + embeddings), LangChain/FAISS

## Najważniejsze zmiany

### 1. Bezpieczna wysyłka długich treści SMS

- [app/message_utils.py](app/message_utils.py) dodaje `split_sms_chunks()` i stałą
  `MAX_SMS_CHARS = 1500`, które tną tekst po akapitach/zdaniach lub twardo, gdy to konieczne.
- [app/twilio_client.py](app/twilio_client.py) udostępnia `send_chunked_sms()`, zwracając metadane
  o częściach (SID-y, liczba znaków) i kończąc wysyłkę w razie błędu którejkolwiek części.
- News/RAG (ręczny send i scheduler) oraz AI auto-reply/AI send korzystają z wysyłki
  wieloczęściowej zamiast obcinać treść.

### 2. Dokumentacja i release hygiene

- README opisuje mapę dokumentacji (MD/HTML) oraz sekcję o limitach SMS i dzieleniu treści.
- `docs/` i `deploy/releases/full_documentation.html` zostały zaktualizowane o informacje
  o dzieleniu SMS oraz nowe oznaczenie wersji.
- `release/README.md` wskazuje aktualny sposób budowy paczki (prepare_release_bundle).

## Kompatybilność i upgrade

- Brak zmian w publicznych endpointach API.
- Jedna odpowiedź może zostać wysłana jako kilka SMS-ów (kilka SID-ów); integracje korzystające
  bezpośrednio z Twilio powinny to uwzględnić, jeśli monitorują SID per wiadomość.

### Checklist upgrade'u (prod)
1) Backup: `data/app.db` + `X1_data/` (jak przed każdym wydaniem).
2) Środowisko: upewnij się, że masz ustawione `TWILIO_DEFAULT_FROM` lub `TWILIO_MESSAGING_SERVICE_SID`.
3) Klucze AI: `OPENAI_API_KEY`/`AI_*` dla czatu AI, `SECOND_OPENAI`/`SECOND_MODEL` dla News/RAG.
4) Deploy (Docker): przeładuj kontenery (`make compose-prod`), sprawdź healthcheck `/api/health`.
5) Testy dymne:
   - wyślij długi tekst AI/News → potwierdź brak błędu 21617, zobacz kilka SID-ów w logach,
   - webhook inbound + auto-reply/AI,
   - News: `Test FAISS` + ręczne „Wyślij” do odbiorcy,
   - Multi-SMS: mały batch (3–5 numerów), wgląd w statusy.

## Publikacja release na GitHubie

1. **Releases → Draft a new release**.
2. Wybierz/utwórz tag `ver3.1.3` i tytuł `ver3.1.3 – Chunked SMS & docs refresh`.
3. Wklej treść tego pliku do opisu.
4. Jeśli publikujesz paczkę, zbuduj ją `./scripts/prepare_release_bundle.sh ver3.1.3`
   i załącz `release/dist/ver3.1.3/` (bez `data/`, `X1_data/`, `.env`).

## Zaawansowana konfiguracja (skrót)

```ini
# Twilio – wymagane
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_DEFAULT_FROM=+48123456789   # lub TWILIO_MESSAGING_SERVICE_SID=MG...

# AI / RAG
OPENAI_API_KEY=sk-...              # czat AI
AI_MODEL=gpt-4o-mini
SECOND_OPENAI=sk-...               # embeddings/News
SECOND_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-large

# Aplikacja
APP_PORT=3000
PUBLIC_BASE_URL=https://twoja-domena.pl
TWILIO_VALIDATE_SIGNATURE=true     # w dev możesz ustawić false
LOG_LEVEL=info

# SMS chunking (domyślnie 1500)
MAX_SMS_CHARS=1500
```

## Walidacja po wdrożeniu (skrót CLI/API)

- Health: `curl http://<host>:3000/api/health`
- Długi SMS AI (bez wysyłki): `curl -X POST http://<host>:3000/api/ai/test -d '{"prompt":"..."}'`
- Ręczny News send: `curl -X POST http://<host>:3000/api/news/recipients/<id>/send`
- Multi-SMS statusy: `curl http://<host>:3000/api/multi-sms/batches?include_recipients=1`

## Release bundle (TL;DR)

```
./scripts/prepare_release_bundle.sh ver3.1.3
cd release/dist/ver3.1.3
# zweryfikuj zawartość → brak .env, data/, X1_data/
tar -czf ../ver3.1.3-clean.tar.gz .
```

Paczka jest gotowa do udostępnienia klientom bez ryzyka wycieku danych newsowych czy sekretów.

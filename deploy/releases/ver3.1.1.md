# Twilio Chat App – ver3.1.1

Release tag: `ver3.1.1`
Data wydania: 2025-12-13
Środowisko referencyjne: Docker (Python 3.12, gunicorn)

## Podsumowanie

Wydanie doprecyzowuje zachowanie trybu podsumowania newsów "ALL‑CATEGORIES".
Model otrzymuje teraz osobne, wyraźnie oznaczone konteksty dla każdej kategorii
oraz jasne instrukcje co do formatu odpowiedzi. Dzięki temu streszczenia są
bardziej przewidywalne, nie mieszają faktów między kategoriami i mają
spójny, prosty dla odbiorcy układ.

## Technologie i środowisko

- Język: Python 3.12.
- Framework backendowy: Flask 3.
- Serwer HTTP: `gunicorn`.
- Baza danych: SQLite (`data/app.db`).
- Integracje: Twilio (SMS), OpenAI (AI + embeddings dla RAG), LangChain/FAISS.

## Najważniejsze zmiany

### 1. News/RAG: osobne konteksty FAISS per kategoria

- `FAISSService.answer_query_all_categories()` buduje teraz konteksty
  osobno dla każdej kategorii na podstawie wyników wyszukiwania.
- Wprowadzono helper, który dzieli budżet znaków pomiędzy kategorie i
  generuje czytelne sekcje, co ogranicza "rozlewanie się" jednego
  tematu na inną kategorię.
- `context_preview` zawiera teraz logiczne bloki per kategoria, co
  ułatwia debugowanie i audyt jakości odpowiedzi.

### 2. Stabilny format odpowiedzi ALL‑CATEGORIES

- Prompt dla trybu ALL‑CATEGORIES jasno wymaga formatu:
  "Kategoria: <nazwa>" + 2–3 krótkie zdania (bez wypunktowań) na
  kategorię.
- Jeśli dla danej kategorii brakuje fragmentów w indeksie FAISS,
  model ma wygenerować komunikat `brak danych` zamiast próbować
  "dopowiadać" treść.
- System prompt podkreśla zakaz mieszania faktów między kategoriami,
  co poprawia czytelność i wiarygodność streszczeń.

### 3. Spójność API i konfiguracji News

- Stała `ALL_CATEGORIES_PROMPT` w API News została dopasowana do nowej
  logiki: opisuje osobną analizę kategorii i wymaga 2–3 zdań zamiast
  wypunktowań.
- Dzięki temu UI, API i backend FAISS operują na tym samym,
  jednoznacznym założeniu co do formatu ALL‑CATEGORIES.

## Kompatybilność i upgrade

- Brak zmian łamiących w webhookach Twilio, AI auto‑reply ani schedulerze
  newsów.
- Istniejąca konfiguracja odbiorców (`use_all_categories`) pozostaje
  ważna; nowe zachowanie dotyczy sposobu budowy kontekstu i formatu
  odpowiedzi, a nie samych endpointów.
- Po wdrożeniu zaleca się:
  - wykonać test FAISS w trybie ALL‑CATEGORIES z panelu,
  - zweryfikować kilka wiadomości wysłanych do odbiorców korzystających
    z ALL‑CATEGORIES pod kątem separacji kategorii i formatu 2–3 zdań.

## Publikacja release na GitHubie

1. Przejdź do zakładki **Releases** → **Draft a new release**.
2. Ustaw **Tag** i **Release title** na `ver3.1.1` / `ver3.1.1 – precyzyjne podsumowania ALL‑CATEGORIES`.
3. Wklej treść tego pliku jako opis release.
4. Kliknij **Publish release**.

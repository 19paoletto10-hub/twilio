# Twilio Chat App – ver3.1.0

Release tag: `ver3.1.0`
Data wydania: 2025-12-13
Środowisko referencyjne: Docker (Python 3.12, gunicorn)

## Podsumowanie

Wydanie rozszerza moduł News/RAG o w pełni konfigurowalny tryb podsumowania
„ALL‑CATEGORIES” (per test i per odbiorca), tak aby operator mógł świadomie
decydować o formacie streszczeń. Równolegle dopracowano UX panelu: widoczny jest
aktywny tryb, prompty są spójne z wybraną strategią, a tabela historii wiadomości
ma stabilny układ (stała wysokość wierszy w kolumnie treści).

## Technologie i środowisko

- Język: Python 3.12.
- Framework backendowy: Flask 3.
- Serwer HTTP: `gunicorn`.
- Baza danych: SQLite (`data/app.db`).
- Integracje: Twilio (SMS), OpenAI (AI + embeddings dla RAG), LangChain/FAISS.

## Najważniejsze zmiany

### 1. News/RAG: tryb ALL‑CATEGORIES jako ustawienie per‑odbiorca i per‑test

- Dodano flagę `use_all_categories` do konfiguracji odbiorców i do zapytań testowych.
- Panel (zakładka News): checkbox pozwala przełączać tryb dla testu FAISS oraz dla
  dodawania/edycji odbiorcy.
- Scheduler newsów respektuje ustawienie zapisane przy odbiorcy, dzięki czemu ten sam
  indeks FAISS może obsługiwać różne style dystrybucji.
- Domyślnie `use_all_categories` jest włączone, aby dystrybucja dzienna obejmowała
  wszystkie kategorie nawet bez dodatkowej konfiguracji.

### 2. Prompty per‑tryb i stabilizacja formatu odpowiedzi

- Utrzymywany jest osobny prompt dla STANDARD oraz ALL‑CATEGORIES.
- UI utrzymuje spójność promptu z zaznaczonym trybem, ograniczając przypadkowe
  mieszanie „promptu standardowego” z logiką all‑categories.
- Odpowiedzi i metadane w panelu jasno wskazują zastosowany tryb, co ułatwia QA
  oraz diagnostykę jakości streszczeń.

### 3. Dashboard: stabilny układ historii wiadomości

- W historii wiadomości kolumna „Treść” ma stałą wysokość wierszy.
- Dłuższe wiadomości są skracane (clamp), co poprawia skanowalność tabeli
  i zapobiega „rozjeżdżaniu” layoutu przy bardzo długich SMS-ach.

## Kompatybilność i upgrade

- Brak zmian łamiących w webhookach Twilio oraz modułach AI/auto‑reply.
- Integracje korzystające z endpointów News mogą opcjonalnie przekazywać
  `use_all_categories`; jeśli pole nie występuje, stosowane jest zachowanie domyślne.

## Publikacja release na GitHubie

1. Przejdź do zakładki **Releases** → **Draft a new release**.
2. Ustaw **Tag** i **Release title** na `ver3.1.0` / `ver3.1.0 – All‑categories mode & UX hardening`.
3. Wklej treść tego pliku jako opis release.
4. Kliknij **Publish release**.

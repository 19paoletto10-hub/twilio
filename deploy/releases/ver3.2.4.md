# Release Notes: ver3.2.4

**Listeners: SMS Command Processing with FAISS Integration**

📅 Data wydania: 2025-12-23

---

## Podsumowanie

Release 3.2.4 wprowadza nową zakładkę **Listeners** w panelu Dashboard, umożliwiającą
dynamiczne zarządzanie komendami SMS. Odbiorcy mogą wysyłać wiadomości zaczynające się
od prefiksu `/news`, a system automatycznie odpowiada na ich zapytania wykorzystując
bazę wiedzy FAISS zbudowaną z artykułów newsowych.

### Dla kogo jest ta wersja?

- **Administratorzy** – włączanie/wyłączanie listenerów w czasie rzeczywistym
- **Odbiorcy SMS** – możliwość pytania o newsy przez SMS
- **Operatorzy** – testowanie zapytań bez wysyłania SMS-ów
- **Deweloperzy** – nowe API endpoints i architektura listenerów

---

## Najważniejsze zmiany

### 🎧 Nowa zakładka Listeners

Dedykowana zakładka do zarządzania nasłuchiwaczami komend SMS:

```
┌─────────────────────────────────────────────────────────┐
│ 📱 Listeners                                            │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 📰  /news                              [●──○]       │ │
│ │     Odpowiada na pytania o aktualności              │ │
│ │     wykorzystując bazę FAISS                        │ │
│ │                                        Włączony ✓   │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ 🧪 Przetestuj /news                                    │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Wpisz pytanie...                         [Testuj]   │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Funkcje:**
- Karty z przełącznikiem ON/OFF dla każdego listenera
- Kolorowa ikona statusu (zielona = aktywny)
- Panel testowy do symulacji zapytań
- Instrukcja dla odbiorców SMS

### 📰 Komenda /news

Odbiorcy SMS mogą teraz zadawać pytania do bazy newsów:

| Przykład wiadomości | Rezultat |
|---------------------|----------|
| `/news co nowego w gospodarce?` | Odpowiedź z FAISS o gospodarce |
| `/news podsumowanie rynku` | Analiza rynkowa z artykułów |
| `/news` (samo) | Instrukcja użycia |

**Przepływ:**

```
📱 Odbiorca wysyła SMS
    │
    ▼
"/news Jakie są kursy walut?"
    │
    ▼
🔍 FAISS wyszukuje w bazie
    │
    ▼
🤖 OpenAI generuje odpowiedź
    │
    ▼
📨 SMS z odpowiedzią
```

### 🔄 Synchroniczna obsługa

Odpowiedzi są wysyłane **natychmiast** przy odbiorze SMS:

- Bez kolejkowania w tle
- Deduplikacja zapobiega wielokrotnej odpowiedzi
- Działa zarówno przez webhook jak i polling

---

## Zmiany techniczne

### Nowa tabela bazy danych

```sql
CREATE TABLE listeners_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command TEXT UNIQUE NOT NULL,
    enabled INTEGER DEFAULT 0,
    description TEXT,
    created_at TEXT,
    updated_at TEXT
);

-- Domyślny wpis
INSERT INTO listeners_config (command, enabled, description)
VALUES ('/news', 0, 'Odpowiada na pytania o aktualności...');
```

### Nowe funkcje w database.py

| Funkcja | Opis |
|---------|------|
| `get_listeners_config()` | Lista wszystkich listenerów |
| `get_listener_by_command(cmd)` | Pobiera listener po komendzie |
| `update_listener_config(id, enabled, desc)` | Aktualizacja ustawień |
| `create_listener(cmd, desc)` | Tworzenie nowego listenera |
| `delete_listener(id)` | Usuwanie listenera |

### Nowa funkcja w webhooks.py

```python
def _handle_news_listener_sync(from_number, to_number, body, sid):
    """Synchronicznie obsłuż komendę /news."""
    
    # Deduplikacja
    if sid in _LISTENER_PROCESSED_SIDS:
        return
    _LISTENER_PROCESSED_SIDS.append(sid)
    
    # Wyciągnij zapytanie
    query = body.strip()[5:].strip()
    
    # Odpytaj FAISS
    faiss_svc = FAISSService()
    response = faiss_svc.answer_query(query, top_k=5)
    
    # Wyślij SMS
    twilio_client.send_reply_to_inbound(...)
```

---

## API Endpoints

### Nowe endpointy

| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/api/listeners` | Lista wszystkich listenerów |
| `POST` | `/api/listeners/<id>` | Aktualizacja listenera |
| `POST` | `/api/listeners/test` | Test zapytania /news |

### GET /api/listeners

```json
{
  "listeners": [
    {
      "id": 1,
      "command": "/news",
      "enabled": true,
      "description": "Odpowiada na pytania o aktualności...",
      "created_at": "2025-12-23T10:30:00",
      "updated_at": "2025-12-23T12:45:00"
    }
  ]
}
```

### POST /api/listeners/test

**Request:**
```json
{
  "query": "Jakie są najnowsze wiadomości o rynku?"
}
```

**Response:**
```json
{
  "success": true,
  "answer": "📰 News:\n\nNa rynku obserwujemy...",
  "sources_count": 5,
  "llm_used": true
}
```

---

## Nowe komponenty CSS

| Klasa | Opis |
|-------|------|
| `.listener-card` | Karta listenera z cieniem i hover |
| `.listener-icon` | Ikona 48x48px z kolorowym tłem |
| `.listener-step-icon` | Numerowane ikony instrukcji |
| `.listener-answer-content` | Formatowanie odpowiedzi FAISS |

---

## Poprawki błędów

### 🐛 Listener nie odpowiadał na SMS

**Problem:** Wiadomości `/news` były kolejkowane do workera, ale odpowiedzi nie były wysyłane.

**Przyczyna:** Worker nie przetwarzał wiadomości gdy AI i auto-reply były wyłączone.

**Rozwiązanie:**
1. Dodano synchroniczną obsługę `_handle_news_listener_sync()` 
2. Listener jest teraz obsługiwany bezpośrednio przy odbiorze
3. Dodano deduplikację zapobiegającą wielokrotnej odpowiedzi

---

## Statystyki wydania

| Metryka | Wartość |
|---------|---------|
| Pliki zmienione | 6 |
| Linie dodane | +550 |
| Linie usunięte | -20 |
| Nowe endpointy | 3 |
| Nowe funkcje JS | 3 |
| Nowe klasy CSS | 4 |
| Migracja bazy | v8 → v9 |

---

## Upgrade Guide

### Wymagania

- Python 3.10+
- Flask 2.0+
- OpenAI API key (dla generowania odpowiedzi)
- Zbudowany indeks FAISS (zakładka News)

### Migracja

1. Pull zmian z repozytorium
2. Restart aplikacji (automatyczna migracja bazy v8 → v9)
3. Przejdź do zakładki **Listeners**
4. Włącz listener `/news`
5. Przetestuj w panelu testowym

### Aktywacja dla odbiorców

1. W zakładce Listeners włącz `/news`
2. Poinformuj odbiorców o nowej funkcji
3. Format: `/news [pytanie]`

---

## Przykłady użycia

### SMS od odbiorcy

```
/news Jakie są prognozy dla złotówki?
```

### Odpowiedź systemu

```
📰 News:

Według najnowszych analiz, kurs złotówki względem euro 
utrzymuje się na stabilnym poziomie. Eksperci przewidują:

• Możliwe umocnienie PLN w Q1 2026
• Decyzje RPP będą kluczowe dla kursu
• Inflacja pozostaje pod kontrolą

Źródło: Business Insider, sekcja gospodarka
```

---

**Full Changelog:** [v3.2.3...v3.2.4](https://github.com/19paoletto10-hub/twilio/compare/v3.2.3...v3.2.4)

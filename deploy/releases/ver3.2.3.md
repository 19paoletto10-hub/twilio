# Release Notes: ver3.2.3

**News Scraping UX Improvements: SSE Streaming + Process Control + Professional Content Display**

📅 Data wydania: 2025-12-23

---

## Podsumowanie

Release 3.2.3 wprowadza znaczące ulepszenia UX w zakładce News/FAISS. Główną nowością jest
real-time streaming postępu skrapowania z wykorzystaniem Server-Sent Events (SSE), umożliwiający
wizualizację statusu każdej kategorii na żywo. Dodano przycisk zatrzymania procesu,
masowe usuwanie plików oraz profesjonalny podgląd artykułów.

### Dla kogo jest ta wersja?

- **Operatorzy** – śledzenie postępu skrapowania w czasie rzeczywistym
- **Administratorzy** – pełna kontrola nad procesem (zatrzymanie, masowe usuwanie)
- **Analitycy** – profesjonalny podgląd zeskrapowanych artykułów
- **Deweloperzy** – nowe SSE endpoint i API masowego usuwania

---

## Najważniejsze zmiany

### 📡 SSE Streaming dla postępu skrapowania

Real-time aktualizacja statusów kategorii podczas skrapowania:

| Status | Ikona | Opis |
|--------|-------|------|
| Oczekuje | ⚪ | Kategoria w kolejce do skrapowania |
| W trakcie | 🔄 | Aktywne skrapowanie kategorii |
| Sukces | ✅ | Kategoria ukończona pomyślnie |
| Błąd | ❌ | Wystąpił błąd podczas skrapowania |

**Przepływ zdarzeń SSE:**

```
Event: start        → Inicjalizacja, lista kategorii
Event: processing   → Rozpoczęcie skrapowania kategorii
Event: done         → Zakończenie kategorii (success/error)
Event: building_faiss → Budowanie indeksu FAISS
Event: complete     → Zakończenie całego procesu
```

### 🛑 Przycisk „Zatrzymaj"

Nowy przycisk pozwalający przerwać skrapowanie w dowolnym momencie:

```
┌─────────────────────────────────────────────────────────┐
│ 📰 Pobierz i zbuduj        [🛑 Zatrzymaj]              │
├─────────────────────────────────────────────────────────┤
│ Rozpoczynam skrapowanie kategorii...                    │
├─────────────────────────────────────────────────────────┤
│ 🔄 technologie      ← aktualnie przetwarzana           │
│ ✅ biznes           ← ukończona                        │
│ ✅ gospodarka       ← ukończona                        │
│ ⚪ giełda           ← oczekuje                         │
│ ⚪ nieruchomości    ← oczekuje                         │
└─────────────────────────────────────────────────────────┘
```

**Funkcjonalność:**
- Przycisk pojawia się tylko podczas aktywnego skrapowania
- Natychmiastowe przerwanie połączenia EventSource
- Reset UI i aktualizacja statusu

### 🗑️ Przycisk „Usuń wszystkie"

Masowe kasowanie zeskrapowanych plików:

| Funkcja | Opis |
|---------|------|
| Potwierdzenie | Dialog z liczbą plików do usunięcia |
| Filtrowanie | Usuwa tylko pliki .txt i .json z katalogu scrapes |
| Feedback | Toast z informacją o liczbie usuniętych plików |
| Endpoint | `DELETE /api/news/files` |

### 📰 Eleganckie kafelki plików

Przeprojektowane karty plików w stylu gazetowym:

```
┌─────────────────────────────────┐
│ 📰  biznes.txt                  │
│     23.12.2025                  │
│     12.5 KB              [🗑️]  │
└─────────────────────────────────┘
```

**Cechy:**
- Ikona gazety (📰) zamiast standardowej ikony pliku
- Data w polskim formacie (DD.MM.YYYY)
- Rozmiar pliku w czytelnych jednostkach
- Wyświetlanie tylko plików `.txt` (ukrycie technicznych `.json`)
- Efekty hover z delikatnym cieniem
- Elegancki przycisk usuwania

### 📄 Profesjonalny podgląd artykułów

Nowe formatowanie zawartości w overlay:

```
┌─────────────────────────────────────────────────────────┐
│ 📰 biznes.txt                                     [✕]  │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 1  Prezes NBP o stopach procentowych               │ │
│ │    Treść artykułu o polityce monetarnej banku      │ │
│ │    centralnego i perspektywach gospodarczych...    │ │
│ └─────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 2  Kursy walut w dół                               │ │
│ │    Analiza rynku walutowego pokazuje spadek        │ │
│ │    wartości euro względem dolara...                │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Elementy:**
- Numeracja artykułów (badge z liczbą)
- Pogrubiony tytuł (pierwsza linia)
- Treść z zachowaniem formatowania
- Automatyczne filtrowanie separatorów (`----------------`)
- Czyste odstępy między artykułami

---

## Zmiany techniczne

### Nowe komponenty CSS

| Komponent | Opis |
|-----------|------|
| `.news-file-card` | Karta pliku z efektami hover |
| `.news-file-icon` | Ikona gazety 24x24px |
| `.news-file-delete-btn` | Przycisk usuwania z czerwonym akcentem |
| `.news-article-item` | Kontener pojedynczego artykułu |
| `.news-article-number` | Badge z numerem artykułu |
| `.news-article-title` | Pogrubiony tytuł artykułu |
| `.news-article-body` | Treść artykułu |
| `@keyframes fadeInScale` | Animacja pojawiania się ikon sukcesu |

### Nowe funkcje JavaScript

| Funkcja | Opis |
|---------|------|
| `runNewsScrape()` | Przepisana z SSE EventSource |
| `stopNewsScrape()` | Przerwanie aktywnego skrapowania |
| `deleteAllNewsFiles()` | Masowe usuwanie plików |
| `renderCategoryItem()` | Renderowanie statusu kategorii |
| `formatNewsContent()` | Profesjonalne formatowanie artykułów |

---

## API Endpoints

### Nowe endpointy

| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/api/news/scrape/stream` | SSE streaming postępu skrapowania |
| `DELETE` | `/api/news/files` | Masowe usuwanie plików scrape |

### Format zdarzeń SSE

```json
// Event: start
{"event": "start", "categories": ["biznes", "technologie", ...]}

// Event: processing
{"event": "processing", "category": "biznes"}

// Event: done
{"event": "done", "category": "biznes", "success": true, "articles": 15}

// Event: building_faiss
{"event": "building_faiss"}

// Event: complete
{"event": "complete", "total_articles": 120, "faiss_docs": 450}
```

### Response: DELETE /api/news/files

```json
{
  "status": "ok",
  "deleted_count": 16,
  "message": "Usunięto 16 plików"
}
```

---

## Poprawki błędów

### 🐛 Filtrowanie separatorów

**Problem:** Linie separatorów (`----------------`) wyświetlały się jako puste elementy artykułów.

**Rozwiązanie:** Dodano regex filter w `formatNewsContent()`:

```javascript
const separatorPattern = /^[-─—_=]+$/;
if (separatorPattern.test(trimmed)) continue;
if (trimmed.length <= 3) continue;
```

---

## Statystyki wydania

| Metryka | Wartość |
|---------|---------|
| Pliki zmienione | 6 |
| Linie dodane | +658 |
| Linie usunięte | -54 |
| Nowe endpointy | 2 |
| Nowe funkcje JS | 5 |
| Nowe klasy CSS | 8 |

---

## Upgrade Guide

### Wymagania

- Python 3.10+
- Flask 2.0+
- Przeglądarka z obsługą SSE (wszystkie nowoczesne przeglądarki)

### Migracja

1. Pull zmian z repozytorium
2. Restart aplikacji (brak zmian w bazie danych)
3. Odśwież cache przeglądarki (Ctrl+Shift+R)

---

## Podziękowania

Dziękujemy za feedback dotyczący UX modułu News/FAISS, który doprowadził do tych usprawnień!

---

**Full Changelog:** [v3.2.2...v3.2.3](https://github.com/19paoletto10-hub/twilio/compare/v3.2.2...v3.2.3)

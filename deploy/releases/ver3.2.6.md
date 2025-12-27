# Release Notes: ver3.2.6

**Chunked SMS & Professional FAISS RAG**

📅 Data wydania: 2025-12-27

---

## Podsumowanie

Release 3.2.6 wprowadza profesjonalne rozwiązania dla dwóch kluczowych problemów:
1. **Automatyczne dzielenie długich SMS** - wiadomości przekraczające 1500 znaków są automatycznie dzielone na części
2. **Profesjonalne streszczenia RAG** - tryb `all_categories` generuje koherentne podsumowania w stylu reportera biznesowego, z gwarancją pokrycia wszystkich 8 kategorii

### Dla kogo jest ta wersja?

- **Operatorzy News** – pewność że każda kategoria znajdzie się w raporcie dziennym
- **Użytkownicy SMS** – wysyłka długich wiadomości bez obaw o limity Twilio
- **DevOps** – lepsza obserwowalność z rozbudowanym logowaniem
- **QA** – przewidywalne zachowanie FAISS z gwarancją kategorii

---

## Najważniejsze zmiany

### 📱 Chunked SMS (Automatyczne dzielenie wiadomości)

Twilio narzuca limit 1600 znaków na pojedynczy SMS. Wcześniej długie wiadomości (np. z FAISS RAG) 
kończyły się błędem 21617. Teraz:

```python
# POST /api/messages - automatycznie wykrywa długie wiadomości
if len(body) > MAX_SMS_CHARS:  # 1500 znaków (bufor bezpieczeństwa)
    result = twilio_client.send_chunked_sms(to, body, max_length=1500)
```

**Odpowiedź dla długich wiadomości:**
```json
{
  "success": true,
  "parts": 3,
  "sids": ["SM123...", "SM456...", "SM789..."],
  "characters": 4521,
  "message": "SMS wysłany do +48123456789 w 3 częściach"
}
```

**Endpoint `/api/news/test-faiss` z wysyłką SMS:**
```bash
curl -X POST /api/news/test-faiss \
  -d '{"query": "podsumowanie", "mode": "all_categories", "send_sms": true, "to": "+48123456789"}'
```

### 🎯 Gwarancja pokrycia wszystkich kategorii

Poprzednio `search_all_categories()` używało MMR search, które nie gwarantowało dokumentów 
dla każdej kategorii. Teraz:

1. **Skanowanie docstore** – bezpośredni dostęp do wszystkich dokumentów w indeksie
2. **Grupowanie per kategoria** – dokumenty sortowane wg przynależności do kategorii
3. **Eksplicytna lista kategorii** – `list_categories()` zwraca wszystkie 8 kategorii
4. **Puste wpisy dla brakujących** – jeśli brak danych, LLM otrzymuje `(BRAK DANYCH)`

**Obsługiwane kategorie:**
- Biznes
- Giełda
- Gospodarka
- Nieruchomości
- Poradnik Finansowy
- Praca
- Prawo
- Technologie

### 📰 Profesjonalne streszczenia w stylu reportera

Nowy system prompt dla `answer_query_all_categories()`:

```python
system_prompt = (
    "Jesteś doświadczonym dziennikarzem biznesowym przygotowującym poranny briefing "
    "dla kadry zarządzającej. Twój styl: profesjonalny, zwięzły, konkretny. "
    "Używasz liczb, dat, nazw firm i osób gdy są dostępne. "
    "Piszesz płynną, koherentną prozę - NIE używasz wypunktowań ani list. "
    "Każda kategoria to osobny, spójny akapit 2-4 zdań. "
    "MUSISZ uwzględnić KAŻDĄ kategorię z listy."
)
```

**Przykładowa odpowiedź:**

```
📊 BIZNES
Ministerstwo Cyfryzacji pracuje nad podatkiem cyfrowym wymierzonym w gigantów jak 
Google i Meta, ze stawką 3% od obrotów powyżej 750 mln euro. Premier Tusk pozostawia 
decyzję otwartą, sugerując że podatek może, ale nie musi zostać wprowadzony.

📈 GIEŁDA
Rosyjskie indeksy notują silne wzrosty po zapowiedzi rozmów pokojowych, z moskiewską 
giełdą najwyżej od lipca 2023. Gazprom, Sbierbank i Rosnieft świecą na zielono.

🏠 NIERUCHOMOŚCI
Brak nowych informacji w tej kategorii.

[... pozostałe kategorie ...]
```

---

## Zmiany techniczne

### Nowe pola w odpowiedzi FAISS

```python
{
    "success": True,
    "categories_found": ["Biznes", "Giełda", "Gospodarka", ...],  # wszystkie 8
    "categories_with_data": ["Biznes", "Giełda", ...],             # kategorie z dokumentami
    "categories_empty": ["Nieruchomości"],                         # kategorie bez dokumentów
    "characters": 3735,                                            # długość odpowiedzi
    "answer": "📊 BIZNES..."
}
```

### Rozbudowane logowanie

```python
logging.info("answer_query_all_categories: Znaleziono %d kategorii: %s", 
             len(all_categories), all_categories)
logging.info("answer_query_all_categories: Sukces, odpowiedź ma %d znaków", len(answer))
logging.warning("search_all_categories: Brak dokumentów dla kategorii '%s'", cat)
```

### Parametry funkcji

| Funkcja | Parametr | Wartość domyślna | Opis |
|---------|----------|------------------|------|
| `search_all_categories()` | `per_category_k` | 2 | Dokumenty per kategoria |
| `search_all_categories()` | `fetch_k` | 50 | Kandydaci do MMR fallback |
| `answer_query_all_categories()` | `temperature` | 0.3 | Determinizm LLM |
| `answer_query_all_categories()` | `max_tokens` | 2000 | Limit tokenów odpowiedzi |
| `send_chunked_sms()` | `max_length` | 1500 | Limit znaków per część |

---

## Zaktualizowane pliki

```
app/faiss_service.py    # search_all_categories(), answer_query_all_categories()
app/webhooks.py         # POST /api/messages (chunked), POST /api/news/test-faiss (send_sms)
app/message_utils.py    # MAX_SMS_CHARS constant
```

---

## Testy i weryfikacja

### Test chunked SMS

```bash
# Długa wiadomość (>1500 znaków) zostanie podzielona automatycznie
curl -X POST http://localhost:3000/api/messages \
  -H "Content-Type: application/json" \
  -d '{"to": "+48123456789", "body": "'"$(python3 -c "print('Test ' * 400)")"'"}'

# Odpowiedź:
# {"success": true, "parts": 3, "sids": ["SM...", ...], "message": "SMS wysłany w 3 częściach"}
```

### Test FAISS all_categories

```bash
curl -X POST http://localhost:3000/api/news/test-faiss \
  -H "Content-Type: application/json" \
  -d '{"query": "podsumowanie newsów", "mode": "all_categories"}'

# Weryfikacja kategorii:
# "categories_found": 8, "categories_with_data": ["Biznes", ...], "characters": 3735
```

### Test FAISS z wysyłką SMS

```bash
curl -X POST http://localhost:3000/api/news/test-faiss \
  -H "Content-Type: application/json" \
  -d '{"query": "podsumowanie", "mode": "all_categories", "send_sms": true}'

# Odpowiedź zawiera:
# "sms_sent": true, "sms_result": {"parts": 3, "sids": [...]}
```

---

## Kompatybilność wsteczna

- ✅ `POST /api/messages` - działa bez zmian dla krótkich wiadomości
- ✅ `POST /api/news/test-faiss` - działa bez zmian bez flagi `send_sms`
- ✅ `answer_query()` - standardowy RAG bez zmian
- ✅ Scheduler newsów - automatycznie używa nowego trybu all_categories

---

## Znane ograniczenia

1. **Chunked SMS** - każda część to osobna wiadomość, więc odbiorca może je otrzymać w różnej kolejności
2. **Limit Twilio** - nadal obowiązuje limit ~10 części (16000 znaków) przez concatenated SMS
3. **Koszty** - każda część SMS to osobna opłata według cennika Twilio
4. **Kategorie puste** - jeśli brak artykułów w kategorii, LLM napisze "Brak nowych informacji"

---

## Migracja z 3.2.5

Brak wymaganych zmian. Aktualizacja jest w pełni kompatybilna wstecz.

```bash
git pull origin main
pip install -r requirements.txt  # bez zmian
python run.py
```

---

## Autorzy

- Copilot Agent (GitHub Copilot)
- Code review: Human

📦 **Commit**: `932d2c6`  
🔗 **Branch**: `feature/chat-conversation-switcher`

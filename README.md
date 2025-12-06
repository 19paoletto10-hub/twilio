# Twilio Chat App

Zaawansowany, modułowy serwer czatu oparty o Flask + Twilio.

## Funkcje

- Webhook dla wiadomości przychodzących z Twilio (`/twilio/inbound`)
- Webhook statusu dostarczenia (`/twilio/status`)
- REST API do wysyłania wiadomości z Twojej aplikacji (`POST /api/send-message`)
- Modularna architektura:
  - `config.py` – konfiguracja i wczytywanie zmiennych środowiskowych
  - `twilio_client.py` – klient Twilio
  - `chat_logic.py` – logika odpowiedzi bota (łatwa do wymiany/rozbudowy)
  - `webhooks.py` – endpointy Flask
- Gotowe do użycia w Replit / na VPS / Heroku itp.

## Instalacja

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Konfiguracja

Utwórz plik `.env` na podstawie `.env.example`:

```bash
cp .env.example .env
```

Uzupełnij wartości:

- `TWILIO_ACCOUNT_SID` – SID konta z Twilio Console
- `TWILIO_AUTH_TOKEN` – Auth Token
- `TWILIO_DEFAULT_FROM` – numer nadawcy (np. +48..., lub whatsapp:+48...)
- `TWILIO_MESSAGING_SERVICE_SID` – opcjonalnie SID usługi Messaging Service
- `TWILIO_WHATSAPP_FROM` – pełny adres nadawcy WhatsApp (`whatsapp:+48...`) dla wysyłki przez ten kanał

## Uruchomienie serwera

```bash
python run.py
```

Domyślnie aplikacja działa na `http://0.0.0.0:3000`.

## Interfejs webowy

- Dashboard oparty o Bootstrap 5 jest dostępny pod `http://localhost:3000/`.
- Formularz pozwala wysyłać wiadomości SMS/MMS oraz WhatsApp (po ustawieniu `TWILIO_WHATSAPP_FROM`).
- Historia konwersacji (ostatnie 50 pozycji) oraz statystyki są pobierane z lokalnej bazy SQLite (`DB_PATH`).
- Statusy wiadomości aktualizują się automatycznie co 15 sekund.

### Endpointy

- `POST /twilio/inbound` – webhook dla wiadomości przychodzących (SMS/WhatsApp)
- `POST /twilio/status` – status dostarczenia wiadomości
- `POST /api/send-message` – wysyłanie wiadomości z backendu
- `GET /api/messages/remote` – pobieranie ostatnich wiadomości bezpośrednio z Twilio (filtry: `to`, `from`, `date_sent*`, `limit`)
- `GET /api/messages/<sid>` – szczegóły konkretnej wiadomości prosto z API Twilio
- `POST /api/messages/<sid>/redact` – redagowanie treści wiadomości (ustawia pusty tekst)
- `DELETE /api/messages/<sid>` – usuwa wiadomość z Twilio oraz lokalnej bazy

Przykładowe zapytanie:

```bash
curl -X POST http://localhost:3000/api/send-message \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+48123123123",
    "body": "Test z API",
    "channel": "sms"
  }'
```

### WhatsApp oraz Messaging Service

Zgodnie z instrukcjami Twilio:

- Aby wysłać wiadomość WhatsApp ustaw `TWILIO_WHATSAPP_FROM` i podaj odbiorcę w formacie `whatsapp:+48123...`. Możesz również skorzystać z Messaging Service (`messaging_service_sid`).
- Wysyłka z Messaging Service dla SMS/MMS działa, gdy aplikacja ma ustawiony `TWILIO_MESSAGING_SERVICE_SID` lub przekażesz własny SID w polu `messaging_service_sid`.
- API udostępnia też operacje `fetch`, `list`, `update (redact)` oraz `delete` na zasobach Message, bazujące na oficjalnej dokumentacji Twilio Messages API.

## Konfiguracja Twilio (Messaging Service)

1. Wejdź w **Messaging Service** → wybierz swoją usługę (np. `swimbook`).
2. Zakładka **Integration**.
3. W sekcji **Incoming Messages** wybierz:
   - **Send a webhook**
   - URL: `https://twoja-domena.pl/twilio/inbound` (lub URL z Replit / ngrok).
4. W sekcji **Delivery Status Callback** ustaw:
   - URL: `https://twoja-domena.pl/twilio/status`.

Pamiętaj, aby w Twilio używać tego samego numeru / Messaging Service SID, jaki podałeś w `.env`.

## CLI – wysyłanie wiadomości z terminala

```bash
python manage.py send \
  --to +48123123123 \
  --body "Siema z CLI" \
  --use-messaging-service
```

## Rozbudowa

- Dodaj własną klasę w `chat_logic.py` implementującą logikę czatu (np. integracja z OpenAI).
- Podmień funkcję `build_chat_engine()` na własne tryby.
- Dodaj kolejne blueprinty / endpointy Flask do integracji z panelem www.


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

## Uruchomienie serwera

```bash
python run.py
```

Domyślnie aplikacja działa na `http://0.0.0.0:3000`.

### Endpointy

- `POST /twilio/inbound` – webhook dla wiadomości przychodzących (SMS/WhatsApp)
- `POST /twilio/status` – status dostarczenia wiadomości
- `POST /api/send-message` – wysyłanie wiadomości z backendu

Przykładowe zapytanie:

```bash
curl -X POST http://localhost:3000/api/send-message \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+48123123123",
    "body": "Test z API",
    "use_messaging_service": true
  }'
```

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


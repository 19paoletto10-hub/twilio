# Release Notes: ver3.2.1

**UI/UX Enhancement: Collapsible Sidebar + Compose Modal**

📅 Data wydania: 2025-12-16

---

## Podsumowanie

Release 3.2.1 wprowadza znaczące ulepszenia interfejsu użytkownika, koncentrując się na
ergonomii pracy operatora. Główne zmiany to zwijane menu boczne (collapsible sidebar)
oraz nowoczesny modal kompozycji wiadomości, który umożliwia tworzenie SMS bez opuszczania
bieżącego widoku.

### Dla kogo jest ta wersja?

- **Operatorzy** – lepsza ergonomia pracy z większą przestrzenią roboczą
- **Power users** – skróty klawiszowe i szybkie akcje w sidebar
- **Zespoły mobilne** – responsywny design działający na tabletach i dużych telefonach
- **Deweloperzy** – czystsza architektura CSS z custom properties

---

## Najważniejsze zmiany

### 🎨 Collapsible Sidebar (Zwijane menu boczne)

Nowy sidebar zapewnia lepszą organizację przestrzeni roboczej:

| Funkcja | Opis |
|---------|------|
| Tryb rozwinięty | Pełna nawigacja z ikonami i etykietami (280px) |
| Tryb zwinięty | Kompaktowe ikony dla power users (84px) |
| Przełączanie | Przycisk w headerze lub skrót klawiszowy |
| Persistencja | Stan zapamiętywany w localStorage |
| Animacje | Płynne przejścia CSS (0.25s ease) |

**Struktura nawigacji:**
- 📨 Wiadomości
- 🔄 Auto-odpowiedź
- ⏱️ Przypomnienia
- ✨ AI
- 📰 News
- 👥 Multi-SMS

**Szybkie akcje:**
- ✉️ Wyślij nową wiadomość (otwiera modal)
- 💬 Historia konwersacji (scroll do tabeli)
- 🔄 Odśwież dane

### 📝 Compose Modal (Modal kompozycji)

Nowoczesne okno dialogowe do tworzenia wiadomości:

```
┌─────────────────────────────────────────┐
│  Nowa wiadomość                      ✕  │
├─────────────────────────────────────────┤
│  Numer odbiorcy                         │
│  ┌─────────────────────────────────┐    │
│  │ +48123456789                    │    │
│  └─────────────────────────────────┘    │
│                                         │
│  Treść wiadomości                       │
│  ┌─────────────────────────────────┐    │
│  │                                 │    │
│  │ Wpisz wiadomość...              │    │
│  │                                 │    │
│  └─────────────────────────────────┘    │
│                                         │
│         [Anuluj]  [Wyślij wiadomość]    │
└─────────────────────────────────────────┘
```

**Funkcje:**
- Walidacja numeru w formacie E.164
- Limit 1000 znaków z licznikiem
- Obsługa klawisza Enter (Ctrl+Enter wysyła)
- Spinner podczas wysyłki
- Toast z potwierdzeniem sukcesu/błędu
- Automatyczne zamknięcie po wysłaniu

### 🎯 Ulepszenia UX

1. **Nowy header aplikacji**
   - Logo z gradient background
   - Przycisk zwijania sidebar
   - Badge środowiska (DEV/PROD)

2. **Responsywność**
   - Mobile: sidebar jako overlay (slide-in)
   - Tablet: sidebar zwinięty domyślnie
   - Desktop: sidebar rozwinięty, zwijany ręcznie

3. **Design system**
   - CSS Custom Properties dla łatwej personalizacji
   - Spójne border-radius i shadows
   - Gradient accent color (#7c40ff → #f22f46)

4. **Accessibility**
   - ARIA labels na wszystkich elementach nawigacji
   - Keyboard navigation (Tab, Enter, Escape)
   - Focus states zgodne z WCAG 2.1

### 🔧 Zmiany techniczne

**Nowe zmienne CSS:**
```css
:root {
  --app-sidebar-width: 280px;
  --app-sidebar-collapsed-width: 84px;
  --app-header-height: 68px;
  --app-primary: #7c40ff;
  --app-gradient: linear-gradient(135deg, #7c40ff, #f22f46);
  --app-radius-lg: 1.25rem;
  --app-shadow-sm: 0 12px 30px rgba(15, 23, 42, 0.08);
}
```

**Atrybuty stanu:**
- `[data-app-sidebar-collapsed]` – true/false
- `[data-app-sidebar-state]` – open/closed (mobile)

**Event handlers:**
- `[data-dashboard-nav]` – nawigacja między zakładkami
- `[data-dashboard-modal-target]` – otwieranie modalu
- `[data-dashboard-scroll]` – scroll do elementu
- `[data-dashboard-refresh]` – odświeżanie danych

---

## Lista zaktualizowanych plików

```
app/
├── static/
│   ├── css/
│   │   └── app.css                    # Nowy design system + sidebar styles
│   └── js/
│       └── dashboard.js               # Modal handlers + sidebar toggle
└── templates/
    ├── base.html                      # Nowy layout shell + header
    └── dashboard.html                 # Sidebar block + compose modal
```

---

## Instrukcja upgrade

### Z wersji 3.2.0

```bash
# 1. Backup bazy (zalecane)
./scripts/backup_db.sh

# 2. Pull zmian
git pull origin main

# 3. Restart kontenerów (rebuild dla nowych assetów)
docker compose down
docker compose up --build -d

# 4. Wyczyść cache przeglądarki
# Ctrl+Shift+R lub Cmd+Shift+R
```

### Świeża instalacja

```bash
# 1. Clone
git clone https://github.com/19paoletto10-hub/twilio.git
cd twilio

# 2. Konfiguracja
cp .env.example .env
# Edytuj .env

# 3. Start
docker compose up --build -d
```

---

## Kompatybilność

| Aspekt | Status |
|--------|--------|
| Breaking changes | ❌ Brak |
| Migracja DB | ❌ Nie wymagana |
| API endpoints | ✅ Bez zmian |
| Stare przeglądarki | ⚠️ Wymaga CSS Grid + Custom Properties |
| Schema version | v7 (bez zmian) |

---

## Wymagania przeglądarki

| Przeglądarka | Minimalna wersja |
|--------------|------------------|
| Chrome | 88+ |
| Firefox | 78+ |
| Safari | 14+ |
| Edge | 88+ |

---

## Znane ograniczenia

- Sidebar na urządzeniach < 768px działa jako overlay (nie sticky)
- Tryb druku nie uwzględnia stanu sidebar (domyślnie ukryty)
- Animacje mogą być wyłączone przez `prefers-reduced-motion`

---

## Podziękowania

Dziękujemy użytkownikom za feedback dotyczący ergonomii panelu operatora!

---

## Linki

- [Dokumentacja Docker](../../docs/docker-guide.md)
- [Developer Guide](../../docs/developer-guide.md)
- [Główne README](../../README.md)
- [CHANGELOG](../../CHANGELOG.md)

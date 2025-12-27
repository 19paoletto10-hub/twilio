# Release Notes - ver3.2.8

## News Command Fallback & Consolidation

📅 **Data wydania:** 2025-12-27

---

## 🎯 Podsumowanie

Release 3.2.8 wprowadza graceful fallback dla komendy `/news` gdy listener jest wyłączony,
zapewniając użytkownikom jasną informację o niedostępności funkcji zamiast ciszy.

---

## ✨ Najważniejsze zmiany

### 📰 /news Disabled Fallback

Gdy użytkownik wysyła komendę `/news` a listener jest wyłączony w konfiguracji,
system teraz automatycznie:

1. **Wykrywa wyłączony listener** – sprawdza konfigurację przed przetwarzaniem
2. **Wysyła informację zwrotną** – "Funkcja /news jest chwilowo niedostępna."
3. **Zapisuje do bazy** – ze statusem `news-disabled` dla śledzenia
4. **Loguje szczegóły** – pełne informacje diagnostyczne

```python
# Nowa obsługa w auto_reply.py
if not listener_enabled:
    app.logger.info("/news command received but listener is disabled")
    disabled_msg = "Funkcja /news jest chwilowo niedostępna."
    send_sms(to=from_number, body=disabled_msg)
```

### 🔧 Repository Consolidation

- Wszystkie feature branches zmergowane do `main`
- Usunięcie nieużywanych gałęzi (`feature/*`, `release/*`, `ver*`)
- Czyste repozytorium z jedną główną gałęzią

---

## 📁 Zaktualizowane pliki

| Plik | Opis |
|------|------|
| `app/auto_reply.py` | Obsługa /news disabled fallback |
| `CHANGELOG.md` | Dokumentacja v3.2.8 |
| `deploy/releases/ver3.2.8.md` | Release notes |

---

## 🚀 Upgrade

```bash
git pull origin main
git checkout v3.2.8
```

---

## 📋 Poprzednie wersje

- [ver3.2.7](ver3.2.7.md) - Dynamic Chat UI & Documentation Update
- [ver3.2.6](ver3.2.6.md) - Chunked SMS & Professional FAISS RAG
- [ver3.2.5](ver3.2.5.md) - Code Quality & Type Safety

---

*Twilio SMS AI Platform © 2025*

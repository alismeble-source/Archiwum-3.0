# ⚠️ ВАЖЛИВО: Автовідправка Email через Telegram

## Поточний статус: AUTO_SEND = False ✅

Система **НЕ відправляє** email автоматично при реакції ✅ в Telegram.

---

## Як працює система

### 1. AI Responder (`ai_responder.py`)
- Читає email з `CASES/_INBOX`
- Генерує draft відповідь через Claude AI
- Відправляє draft в Telegram для перегляду
- **НЕ відправляє** клієнту без підтвердження

### 2. Telegram Approval Listener (`telegram_approval_listener.py`)
- Моніторить реакції на повідомлення в Telegram
- ✅ = approve (схвалити)
- ❌ = skip (пропустити)

**Поточна поведінка:**
- При ✅: **ТІЛЬКИ логує** реакцію, НЕ відправляє email
- При ❌: логує як "skip"

---

## Як увімкнути автовідправку (небезпечно!)

### Крок 1: Змінити прапорець

Відкрий `99_SYSTEM\_SCRIPTS\MAIL\telegram_approval_listener.py`:

```python
# Рядок 36:
AUTO_SEND = False  # ⚠️ Змінити на True
```

Стане:
```python
AUTO_SEND = True  # ⚠️ Email відправляються автоматично!
```

### Крок 2: Запустити listener

```powershell
cd "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SCRIPTS\MAIL"
python telegram_approval_listener.py
```

Bot буде працювати **постійно** в фоні і чекати реакції.

---

## ⚠️ Ризики автовідправки

1. **Відправиш клієнту по помилці:**
   - Випадково натиснеш ✅ на повідомленні
   - Email негайно відправиться БЕЗ можливості скасувати

2. **Draft може бути неправильний:**
   - AI може неправильно зрозуміти запит
   - Ціни/терміни можуть бути застарілі
   - Tone може бути занадто різкий

3. **Технічні помилки:**
   - Gmail API може додати текст не в тому місці
   - Thread може бути неправильний
   - Attachment може не додатися

---

## Рекомендована робота (AUTO_SEND = False)

### 1. Генерувати draft автоматично

```powershell
# Один раз
cd "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SCRIPTS\MAIL"
python ai_responder.py --email-id "20260204__abc123"
```

Отримаєш draft в Telegram.

### 2. Переглянути в Telegram

- Читай draft
- Якщо OK → реакція ✅
- Якщо треба змінити → реакція ❌

### 3. Відправити ВРУЧНУ

```powershell
# Після перегляду і схвалення
python gmail_send_reply.py "20260204__abc123" approve
```

Цей підхід:
- ✅ Контролюєш кожен email
- ✅ Можеш редагувати draft перед відправкою
- ✅ Немає ризику помилкової відправки

---

## Де дивитись логи

### Approval State
`00_INBOX\_ROUTER_LOGS\telegram_approval_state.json`

Містить історію всіх реакцій:
```json
{
  "20260204__abc123_✅": {
    "timestamp": "2026-02-04T15:30:00Z",
    "action": "approve",
    "status": "logged_only"  ← НЕ відправлено
  }
}
```

### Email Send Log
`00_INBOX\_ROUTER_LOGS\gmail_send_log.csv`

Історія відправлених email:
```csv
timestamp,email_id,action,status,message
2026-02-04 15:35:00,20260204__abc123,approve,success,Sent to client
```

---

## Запитання?

**Хочу тестувати безпечно:**
→ Залиш `AUTO_SEND = False`
→ Використовуй `DRY_RUN = True` в `ai_responder.py`

**Хочу автоматизацію але обережно:**
→ Спочатку тестуй на тестовому email
→ Перевір Gmail Sent folder після кожної відправки
→ Увімкни AUTO_SEND тільки після 10+ успішних тестів

**Щось пішло не так:**
→ Зупини listener: `Ctrl+C`
→ Перевір `telegram_approval_state.json`
→ Перевір Gmail Sent items

---

**Останнє оновлення:** 2026-02-04  
**AUTO_SEND:** False ✅ (безпечний режим)

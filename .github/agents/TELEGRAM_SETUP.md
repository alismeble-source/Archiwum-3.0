# Telegram Integration Setup

**Status:** ✅ Scripts ready, ⏳ Awaiting token configuration

---

## 🤖 Quick Setup (5 minutes)

### Step 1: Create Telegram Bot
1. Open Telegram app
2. Find @BotFather
3. Send: `/newbot`
4. Choose name: `Archiwum 3.0 Notifications`
5. Choose username: `archiwum3_bot` (or similar)
6. **Copy the token** (looks like: `<BOT_TOKEN_FROM_BOTFATHER>`)

### Step 2: Find Your Chat ID
1. Find @GetIDs_bot in Telegram
2. Send any message
3. Bot will reply with your Chat ID (usually 9-10 digits, like: `987654321`)

### Step 3: Add Tokens to Archiwum

**File 1:** `telegram_bot_token.txt`
```
c:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SECRETS\telegram_bot_token.txt
```
Replace `YOUR_BOT_TOKEN_HERE` with:
```
<BOT_TOKEN_FROM_BOTFATHER>
```

**File 2:** `telegram_chat_id.txt`
```
c:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SECRETS\telegram_chat_id.txt
```
Replace `YOUR_CHAT_ID_HERE` with:
```
987654321
```

### Step 4: Test Connection
```bash
cd "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SCRIPTS\MAIL"
python telegram_notify_router.py
```

Expected: Either "Telegram not configured" (if still using template) or success message

---

## 📊 What Telegram Notifier Does

**Triggered by:** `run_mail_pipeline.ps1` (3/3 stage - after routing)

**Sends:**
```
📬 New client message
Decision: KLIENTS
From: customer@email.com
Subject: Wycena kuchni
Risk: low | Type: major | Quality: clear

Draft reply saved:
C:\Users\alimg\Dropbox\Archiwum 3.0\00_INBOX\_DRAFTS\20260202_233304__wycena_kuchni.txt

Tip: usuń plik draftu, jeśli temat zamknięty (stop reminder).
```

**Features:**
- ✅ Sends notification for EVERY new routed email
- ✅ Auto-generates draft replies (Polish templates)
- ✅ 2-hour reminders if draft still pending
- ✅ Stops reminders if draft file is deleted
- ✅ Tracks state in `telegram_notify_state.json`

---

## 🔧 Draft Reply Templates

### Administrative (faktury, bank, system)
```
Dzień dobry,
potwierdzam otrzymanie wiadomości.
W razie potrzeby doprecyzuję dane.

Pozdrawiam,
AlisMeble
```

### Major/Minor/Consultation (vague)
```
Dzień dobry, dziękuję za wiadomość.
Aby przygotować wycenę, potrzebuję kilku danych:
1) Lokalizacja montażu
2) Wymiary / rysunek / projekt
3) Materiał / kolor / styl
4) Termin realizacji

Pozdrawiam,
AlisMeble
```

### Major/Minor/Consultation (clear)
```
Dzień dobry, dziękuję za zapytanie.
Na podstawie przesłanych informacji mogę przygotować wstępną wycenę.
Proszę jeszcze o:
1) Lokalizacja montażu
2) Wymiary / rysunek / projekt
3) Materiał / kolor / styl
4) Termin realizacji

Pozdrawiam,
AlisMeble
```

---

## 📁 Important Files

| Path | Purpose |
|------|---------|
| `telegram_bot_token.txt` | Bot token (secret!) |
| `telegram_chat_id.txt` | Your Telegram ID |
| `telegram_notify_state.json` | Tracks sent notifications |
| `_DRAFTS/` | Auto-generated reply drafts |

---

## 🚀 Integration with Pipeline

### Before (2/3 stages):
```
1. Import Gmail → CASES\_INBOX
2. Route (classify) → KLIENTS/FIRMA/CAR/REVIEW
```

### After (3/3 stages):
```
1. Import Gmail → CASES\_INBOX
2. Route (classify) → KLIENTS/FIRMA/CAR/REVIEW
3. Telegram notify → Send message + draft reply
```

---

## ⚠️ Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| "Telegram not configured" | Missing token/chat_id | Add files in _SECRETS/ |
| "urlopen error: [Errno 11001]" | No internet or bad token | Check token format |
| No message received | Bot not started | Send `/start` to your bot |
| Duplicate notifications | State file corrupted | Delete `telegram_notify_state.json` |

---

## 📝 Next Steps

1. ✅ Get bot token from @BotFather
2. ✅ Get chat ID from @GetIDs_bot
3. ✅ Edit `telegram_bot_token.txt`
4. ✅ Edit `telegram_chat_id.txt`
5. ✅ Test: `python telegram_notify_router.py`
6. ✅ Integrate into scheduled task (daily 08:00)

---

**Status:** Ready to go! Just add the tokens! 🎉

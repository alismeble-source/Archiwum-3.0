# Telegram Finance Bot - Quick Reference

## Запуск бота

```powershell
cd "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SCRIPTS\FINANCE"

# Запустити в фоні
.\run_finance_bot.ps1 start

# Перевірити статус
.\run_finance_bot.ps1 status

# Зупинити
.\run_finance_bot.ps1 stop

# Перезапустити
.\run_finance_bot.ps1 restart
```

## Telegram команди

| Команда | Опис |
|---------|------|
| `/start` | Привітання + список команд |
| `/help` | Показати команди |
| `/finance` | Повний звіт (файли + дедлайни + inbox) |
| `/deadlines` | Тільки дедлайни |
| `/inbox` | Скільки незроблених файлів |

## Приклади відповідей

### `/finance`
```
📊 FINANCE SUMMARY
2026-02-04 15:30

Organized Files:
├ ZUS: 7 (newest 2026-01-12)
├ VAT: 2 (newest 2025-11-26)
├ PIT: 2 (newest 2025-11-26)
├ FAKTURY: 9 (5 issued, 4 received)
├ RACHUNKI: 3 (newest 2025-11-06)
├ ZAKUPY: 17 (newest 2025-12-21)

Deadlines:
✅ 16d ZUS 01-2026 (2026-02-20)
✅ 21d US VAT 01-2026 (2026-02-25)
❌ OVERDUE 5d FAKTURA PAYCHECK (2026-01-30)

Inbox: 421 unprocessed
└ PDF: 379, XLSX: 32, XML: 10
```

### `/deadlines`
```
📅 DEADLINES
2026-02-04 15:30

❌ OVERDUE 5d FAKTURA PAYCHECK
└ Due: 2026-01-30

❌ OVERDUE 17d WYCENA follow-up
└ Due: 2026-01-18

✅ 16d ZUS 01-2026
└ Due: 2026-02-20

✅ 21d US VAT 01-2026
└ Due: 2026-02-25
```

### `/inbox`
```
📥 INBOX STATUS
2026-02-04 15:30

Total unprocessed: 421
├ PDF: 379
├ XLSX: 32
└ XML: 10

💡 Run: organize_finance_docs.py --run
```

## Безпека

Bot читає `telegram_chat_id.txt` з `99_SYSTEM/_SECRETS/` для авторизації.

Якщо файл є - тільки цей chat_id може використовувати бота.
Якщо файл відсутній - бот відкритий для всіх (⚠️).

### Дізнатись свій chat_id:

1. Напиши боту `/start`
2. Bot відповість (якщо chat_id не обмежено)
3. Якщо хочеш обмежити - додай свій chat_id до `telegram_chat_id.txt`

## Інтеграція з іншими скриптами

Bot використовує ті самі функції що і `show_finance_summary.py`:
- `get_organized_files()` - статистика з FINANCE/DOCS/
- `get_deadlines()` - парсить DEADLINES.csv
- `get_inbox_stats()` - рахує FINANCE_DOCS/_INBOX/

Якщо зміниш структуру в organize_finance_docs.py → автоматично працюватиме в боті.

## Логи

- **PID file:** `99_SYSTEM/_LOGS/finance_bot.pid`
- **Logs:** `99_SYSTEM/_LOGS/finance_bot.log`

```powershell
# Дивитись останні логи
Get-Content "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_LOGS\finance_bot.log" -Tail 20
```

## Автозапуск (опціонально)

### Task Scheduler:

```powershell
# Створити task для автозапуску при старті Windows
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" `
    -Argument "-File `"C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SCRIPTS\FINANCE\run_finance_bot.ps1`" start" `
    -WorkingDirectory "C:\Users\alimg\Dropbox\Archiwum 3.0"

$trigger = New-ScheduledTaskTrigger -AtStartup

Register-ScheduledTask -TaskName "FinanceTelegramBot" `
    -Action $action `
    -Trigger $trigger `
    -Description "Archiwum 3.0 Finance Bot" `
    -User $env:USERNAME
```

## Troubleshooting

### Bot не відповідає:
```powershell
.\run_finance_bot.ps1 status  # Перевірити чи працює
.\run_finance_bot.ps1 restart  # Перезапустити
```

### Error "Unauthorized":
- Перевір `99_SYSTEM/_SECRETS/telegram_chat_id.txt`
- Або видали файл щоб дозволити всім

### Bot не стартує:
```powershell
# Запустити вручну для діагностики
cd "C:\Users\alimg\Dropbox\Archiwum 3.0"
.\.venv\Scripts\python.exe "99_SYSTEM\_SCRIPTS\FINANCE\telegram_finance_bot.py"
```

### Wrong token:
- Перевір `99_SYSTEM/_SECRETS/telegram_bot_token.txt`
- Token має бути від @BotFather в Telegram

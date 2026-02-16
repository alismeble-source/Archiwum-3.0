# Archiwum 3.0 - Project Complete Status (Repo + Scale Snapshot)

**Updated (UTC):** 2026-02-16
**Owner Goal:** стабильный фундамент под ERP/CRM без поломки текущего рабочего контура.

---

## 1) Что уже сделано (факт по проекту)

### Working Core
- `99_SYSTEM/_SCRIPTS/MAIL/run_mail_pipeline.ps1` работает как главный оркестратор пайплайна.
- `99_SYSTEM/_SCRIPTS/MAIL/import_gmail_attachments.py` и `router_cases_inbox.py` формируют импорт + роутинг.
- Логи/операционный трейс идут в `00_INBOX/_ROUTER_LOGS/`.
- Telegram dashboard активен в `99_SYSTEM/_SCRIPTS/FINANCE/telegram_dashboard_bot_v2.py`.
- Launcher/restart-контур для бота: `99_SYSTEM/_SCRIPTS/FINANCE/run_dashboard_bot.ps1`.

### Repo Bootstrap (сделано)
- Подготовлен безопасный `.gitignore` для кода/доков без утечки секретов и бизнес-данных.
- Добавлен каркас масштабируемой структуры: `docs/`, `src/`, `scripts/`, `config/`, `tests/`, `tools/`.
- Добавлен безопасный скрипт синхронизации `sync.ps1` (стейджит только рабочие code/doc пути, без `git add .`).

### Dashboard (уже внедрено)
- One-message UI (редактирование одного сообщения вместо спама).
- Плитки по данным: почта, оплаты, клиенты/выцены, бух, поиск, статус.
- `/health` содержит техметрики (`pipeline_status`, `quotes_rows`, `quotes_missing_amount` и др.).
- Есть AI mode в интерфейсе (ответы по локальным CSV/логам).

### Data Sources (привязка к реальным файлам)
- Почта/роутинг: `00_INBOX/_ROUTER_LOGS/router_log.csv`, `pipeline_run.log`, `pipeline_errors.jsonl`.
- Оплаты: `FINANCE/PAYMENTS.csv`.
- Выцены: `FINANCE/CLIENT_QUOTES.csv`.
- Бух-документы: `FINANCE/DOCS/`.

### Snapshot на момент обновления
- `FINANCE/PAYMENTS.csv`: 6 строк.
- `FINANCE/CLIENT_QUOTES.csv`: 7 строк.
- `router_log.csv` (последние 7 дней): высокий поток `REVIEW`, есть `FIRMA/KLIENTS/CAR`.

---

## 2) High-Level карта системы

### A. Ingestion Layer
- Gmail/iCloud import scripts.
- Attachment extraction + metadata.

### B. Routing Layer
- Keyword/decision routing в категории `KLIENTS / FIRMA / CAR / REVIEW`.
- Логирование решений в `router_log.csv`.

### C. Business Layer
- Payments (`PAYMENTS.csv`).
- Quotes (`CLIENT_QUOTES.csv`).
- Accounting docs (`FINANCE/DOCS`).

### D. Control Layer
- Telegram dashboard (операторский интерфейс).
- Health/selftest/notify jobs.

### E. Ops Layer
- PowerShell launchers.
- Runtime logs, lock files, state files.

---

## 3) Что мешает масштабировать (риски и конфликты)

### Дубли и конфликты версий
- Telegram bot versions: `telegram_dashboard_bot.py`, `telegram_dashboard_bot_new.py`, `telegram_dashboard_bot_v2.py`.
- Router versions: `inbox_router.ps1`, `inbox_router_v2.ps1`, `inbox_router_v3.ps1`.
- Draft builder versions: `draft_builder_v4.ps1`, `v41`, `v42`, `v43`.

### Риски при первом Git commit
- В дереве есть секреты (`99_SYSTEM/_SECRETS`, OAuth token/credentials, token files в разных местах).
- Много операционных и бизнес-данных (документы, PDF, медиа, отчеты) - очень большой и чувствительный commit.
- Логи и runtime-state могут дать постоянный шум в diff.
- Есть конфликтные Dropbox-копии и бинарные хвосты.

### Технические риски
- Много абсолютных путей в скриптах (Windows-only привязка).
- Возможен конфликт двух экземпляров Telegram polling (already seen `terminated by other getUpdates request`).
- Часть документации устарела и в смешанной кодировке.

---

## 4) Рекомендованная структура репозитория (без ломки текущей логики)

```text
Archiwum-3.0/
  .github/
    agents/
    workflows/              # позже
  docs/
    architecture/
    operations/
    security/
  src/
    mail/                   # импорт/роутинг
    finance/                # dashboard, отчеты
    calendar/
    common/
  scripts/
    windows/
  config/
    examples/               # только шаблоны
  tests/
  tools/
  data/                     # локально, в .gitignore
  runtime/                  # локально, в .gitignore
```

**Переезд делаем постепенно**: пока оставляем текущие пути рабочими, репо строим вокруг них с alias/README и поэтапным переносом.

---

## 5) Политика Git: что versioned / ignored / вынесено

### Versioned (в Git)
- Код: `99_SYSTEM/_SCRIPTS/**` (кроме secrets/forensic/runtime).
- Документация: `.github/**`, `docs/**`, README/agent файлы.
- Безопасные конфиги и шаблоны: `.vscode/launch.json`, `.vscode/tasks.json`, `.env.example`.

### Ignored (в .gitignore)
- Все секреты/токены/credentials.
- Runtime logs, lock/state files.
- Бизнес-данные и документы (CASES/FINANCE docs/архивы/медиа).
- Forensic/history dumps.

### Вынести отдельно
- Secrets в `99_SYSTEM/_SECRETS` + менеджер секретов/env vars.
- Большие файлы - отдельно (Dropbox/NAS/S3), не в git.
- Генерируемые отчеты и кэш - в `runtime/` или `data/processed/` (игнорируются).

---

## 6) Naming Convention (рекомендуемый минимум)

- Python: `snake_case.py`
- PowerShell: `verb_noun.ps1` (например `run_mail_pipeline.ps1`)
- Доки: `UPPER_SNAKE.md` для статусов, `kebab-case.md` для гайдов
- Версии: не `*_new`, а `*_v2`, `*_v3` + `CURRENT.md` с официальным entrypoint.

---

## 7) Immediate plan (без рефакторинга «всё сразу»)

1. Зафиксировать единый production-entrypoint:
   - Bot: `telegram_dashboard_bot_v2.py`
   - Pipeline: `run_mail_pipeline.ps1`
2. Держать старые версии как legacy (не удалять), но пометить в `docs/operations/CURRENT_COMPONENTS.md`.
3. Первый clean commit: только код + доки + безопасные конфиги.
4. После первого commit - добавить минимальные smoke-tests для bot/pipeline health.

---

## 8) Definition of Done для этапа Repo Bootstrap

- Репозиторий не содержит секретов.
- `git status` стабильно показывает только код/доки/конфиги.
- Telegram bot и mail pipeline запускаются из текущих путей как раньше.
- Есть один понятный документ «что прод», «что legacy», «что следующий шаг».


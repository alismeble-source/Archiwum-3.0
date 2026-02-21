# Archiwum 3.0 — System Overview for AI Agents

## What this repository is

Personal document management and email archiving system built on Dropbox.
Automatically imports email attachments from Gmail/iCloud, routes them into
categorized folders, and detects/reports duplicates.

## Architecture

```
Email Sources (Gmail / iCloud forwarded to Gmail)
  ↓
[IMPORT]   import_gmail_attachments.py  → CASES/_INBOX  (file + .meta.json)
  ↓
[ROUTE]    router_cases_inbox.py        → 01_KLIENTS/_INBOX | 02_FIRMA/_INBOX | 03_CAR/_INBOX | _REVIEW
  ↓
[NOTIFY]   telegram_notify_router.py   → Telegram
  ↓
[CALENDAR] gmail_to_calendar.py        → Google Calendar (non-critical)
```

Nightly orchestration: `scripts/windows/nightly_autopilot.ps1`
Full pipeline runner:  `99_SYSTEM/_SCRIPTS/MAIL/run_mail_pipeline.ps1`

## Key paths

| Purpose | Path |
|---------|------|
| Pipeline runner | `99_SYSTEM/_SCRIPTS/MAIL/run_mail_pipeline.ps1` |
| Gmail importer | `99_SYSTEM/_SCRIPTS/MAIL/import_gmail_attachments.py` |
| Router | `99_SYSTEM/_SCRIPTS/MAIL/router_cases_inbox.py` |
| Finance bot | `99_SYSTEM/_SCRIPTS/FINANCE/telegram_dashboard_bot_v2.py` |
| Health report | `99_SYSTEM/_SCRIPTS/FINANCE/send_telegram_health_report.py` |
| Nightly autopilot | `scripts/windows/nightly_autopilot.ps1` |
| Secrets (gitignored) | `99_SYSTEM/_SECRETS/` |
| Config examples | `config/examples/` |

## Routing logic (router_cases_inbox.py)

Priority order: **CAR > FIRMA > KLIENTS > REVIEW**

Keyword sets match against `filename | subject | from | original_filename`.
Files without a match go to `CASES/_REVIEW`.

## State files (gitignored)

- `00_INBOX/MAIL_RAW/_STATE/processed_gmail_all.txt` — processed message IDs
- `00_INBOX/MAIL_RAW/_STATE/pipeline.lock` — anti-parallel lock

## Python packages

See `requirements.txt`. Install with `pip install -r requirements.txt`.
Optional extras: `pdfplumber` (PDF extraction), `anthropic` (AI evaluator).

## Safe git workflow

```powershell
.\sync.ps1 "your commit message"
```

`sync.ps1` stages only `99_SYSTEM/_SCRIPTS`, `docs`, `src`, `scripts`, `config`,
`tests`, `tools`, `.github`, `.vscode`, `.gitignore`, `AGENTS.md`, `sync.ps1`.
Live business data folders are excluded by `.gitignore`.

## Rules for agents

- Use `$PSScriptRoot` (not hardcoded paths) in PowerShell scripts.
- Python ROOT for operational scripts: `Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")`.
  For library-style scripts that must be portable, derive root from `Path(__file__)`.
- Secrets live in `99_SYSTEM/_SECRETS/` and are **never** committed.
- CSV logs: append-only (`"a"` mode), UTF-8, headers on first row.
- Atomic writes (temp + rename) for state files.
- Do not use `&&` in PowerShell; use `;` or separate statements.

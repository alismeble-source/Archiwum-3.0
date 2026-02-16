# Archiwum 3.0 - Full System Status & Audit

**Generated:** 2026-02-02  
**Status:** ✅ Active & Running  
**Last Pipeline Run:** 2026-01-19 (12:51:42)

---

## 🎯 System Overview

**Archiwum 3.0** is a multi-pipeline automation system for:
1. **Email Import** - Gmail/iCloud → CASES\_INBOX
2. **File Classification** - Smart keyword routing (CAR/FIRMA/KLIENTS/REVIEW)
3. **Duplicate Detection** - SHA1-based dedup with reporting
4. **Calendar Sync** - DEADLINES.csv → Google Calendar
5. **Client Email Evaluation** - Claude-based risk assessment
6. **Training Data Processing** - Email evaluation datasets

---

## 📊 Pipeline Architecture

```
┌─ run_mail_pipeline.ps1 (ORCHESTRATOR)
│  ├─ import_gmail_attachments.py (IMPORT stage)
│  ├─ router_cases_inbox.py (CLASSIFY & ROUTE)
│  └─ telegram_notify_router.py (NOTIFY stage)
│
├─ RUN_CASES_PIPELINE.ps1 (CASES management)
├─ RUN_CALENDAR_SYNC.ps1 (Google Calendar)
│  └─ deadlines_to_gcal.py
│
└─ Support utilities:
   ├─ find_duplicates.py
   ├─ client_evaluator.py
   ├─ process_training_emails.py
   └─ cleanup_backups.py
```

---

## 📁 Directory Structure

```
Archiwum 3.0/
├── CASES/                        # Main document storage
│   ├── _INBOX/                   # Raw imported files (before routing)
│   ├── 01_KLIENTS/_INBOX/        # Client projects (meble, wyceny, etc.)
│   ├── 02_FIRMA/_INBOX/          # Firm docs (ZUS, US, faktury, banks)
│   ├── 03_CAR/_INBOX/            # Car docs (BMW, VECTRA, OC, AC)
│   ├── _REVIEW/                  # Unclassified files (manual review)
│   ├── _ARCHIVE/                 # Archived cases
│   ├── _DIGEST/                  # Summary reports
│   ├── _QUARANTINE/              # Failed/suspicious files
│   ├── _QUARANTINE_NO_REPLY_30D/ # Old unresolved cases
│   └── 2026/CASE_*               # Dated case folders
│
├── FINANCE/
│   ├── _CALENDAR/
│   │   ├── DEADLINES.csv         # Source of truth for calendar sync
│   │   └── _STATE/               # token.json for Google auth
│   └── ...
│
├── 00_INBOX/
│   └── _ROUTER_LOGS/             # ✅ PRIMARY LOG DIR
│       ├── pipeline_run.log      # Main pipeline transcript
│       ├── router_log.csv        # Routing decisions (appended)
│       ├── gmail_import_log.csv  # Import details
│       ├── CASES_ROUTER_*.csv    # Per-run routing logs
│       ├── duplicates_report_*.csv # Latest: 20260202_181848
│       └── ICLOUD_ATTACH_*.csv   # iCloud import logs
│
├── 99_SYSTEM/
│   ├── _SCRIPTS/                 # Python/PowerShell orchestration
│   │   ├── MAIL/
│   │   │   ├── run_mail_pipeline.ps1 ⭐ MAIN ENTRY
│   │   │   ├── import_gmail_attachments.py
│   │   │   ├── router_cases_inbox.py
│   │   │   ├── client_evaluator.py
│   │   │   ├── process_training_emails.py
│   │   │   ├── telegram_notify_router.py
│   │   │   ├── find_duplicates.py
│   │   │   ├── cleanup_backups.py
│   │   │   └── unify_state_files.py
│   │   ├── CALENDAR/
│   │   │   └── deadlines_to_gcal.py
│   │   ├── CASES/
│   │   │   └── cases_pipeline.ps1
│   │   └── [other scripts]
│   ├── _LOGS/                    # System operation logs
│   ├── _SECRETS/                 # Credentials (git-ignored)
│   │   ├── gmail/
│   │   │   ├── credentials.json  # Gmail OAuth client secret
│   │   │   └── token.json        # Gmail OAuth token
│   │   ├── anthropic_key.txt     # Claude API key
│   │   └── ...
│   └── _FORENSIC/HISTORY/        # Version history + backups
│
├── .github/
│   ├── copilot-instructions.md   # System rules (v170)
│   └── agents/
│       ├── Archiwum-Main.agent.md # Previous agent summary
│       └── SYSTEM_STATUS.md      # This file
│
└── _REPLIES_TRAINING/            # Training dataset
    └── 2025/MSG/                 # Message folders for evaluation
```

---

## 🔑 Key Classifications

### File Keywords by Category

| Category | Keywords | Purpose |
|----------|----------|---------|
| **CAR** | bmw, vin, oc, ac, polisa, ubezpiec, koliz, szkoda, warsztat, przegl | Vehicle/insurance docs |
| **FIRMA** | zus, pue, us, vat, pit, cit, faktura, rachunek, invoice, ksef, ksieg | Accounting/legal docs |
| **KLIENTS** | kuchnia, szafa, zabud, meble, pomiar, wycena, oferta, projekt, dom | Client furniture projects |
| **REVIEW** | (fallback) | Unclassified → manual review |

**Priority:** CAR > FIRMA > KLIENTS > REVIEW (greedy match)

---

## 📝 Important Logs & Reports

### Latest Activity

| File | Timestamp | Status |
|------|-----------|--------|
| `pipeline_run.log` | 2026-01-12 09:54:15 | ✅ COMPLETE |
| `CASES_PIPELINE_20260119_125142.log` | 2026-01-19 12:51:42 | ✅ COMPLETE |
| `duplicates_report_20260202_181848.csv` | 2026-02-02 18:18:48 | 📊 Latest Report |

### Duplicate Report Highlights

**Top Duplicates Found (by frequency):**
- **120x desktop.ini** (system files)
- **6x header-category-icon.png** (email templates)
- **4x footer/social media PNGs** (email signatures)
- **3x smime.p7s, PDF statements, invoice images**

Total unique SHA1s with duplicates: 400+

### CSV Logs Pattern

All logs follow UTC ISO format + append-only (never truncated):
```csv
timestamp,filename,classification,status,metadata
2026-01-19T12:51:42Z,IMG_5861.jpeg,KLIENTS,MOVED,"from _INBOX"
```

---

## ⚙️ State Management

**Single Source of Truth:** `00_INBOX/MAIL_RAW/_STATE/`

| File | Purpose | Format |
|------|---------|--------|
| `processed_gmail_all.txt` | Processed Gmail IDs (prevent re-import) | One ID per line |
| `gmail_icloud_processed_ids.txt` | Legacy unified state | One ID per line |
| `pipeline.lock` | Anti-parallel execution lock | File exists = locked |

**Safety:** Atomic writes (temp file + rename)

---

## 🔐 Credentials & Auth

### Gmail API
```
Location: 99_SYSTEM/_SECRETS/gmail/
├── credentials.json    # OAuth client ID/secret (from Google Cloud)
└── token.json         # OAuth access token (auto-refreshed)
```

### Google Calendar
```
CSV Source: FINANCE/_CALENDAR/DEADLINES.csv
Columns: TYPE, TITLE, DUE_DATE, CASE_ID
Token: FINANCE/_CALENDAR/_STATE/token.json
Calendar ID: "primary" (or custom, via env var GCAL_CALENDAR_ID)
```

### Claude (Anthropic)
```
Key Source: FINANCE/_SYSTEM/_SECRETS/anthropic_key.txt
or env var: ANTHROPIC_API_KEY
Model: claude-opus-4-1-20250805
Usage: evaluate_client_email() in client_evaluator.py
```

---

## 🚀 Running Pipelines

### Main Mail Pipeline
```powershell
cd "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SCRIPTS\MAIL"
python -m run_mail_pipeline.ps1
# OR
& ".\run_mail_pipeline.ps1"
```

**Steps:**
1. Import Gmail attachments → CASES\_INBOX
2. Route files (classify + move)
3. Send Telegram notifications

### Calendar Sync
```powershell
cd "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SCRIPTS\CALENDAR"
python deadlines_to_gcal.py
```

### Process Training Emails
```bash
cd "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SCRIPTS\MAIL"
python process_training_emails.py
# Output: 00_INBOX/TRAINING_EVALUATIONS.json
```

---

## ⚠️ Known Issues & Solutions

| Issue | Cause | Fix |
|-------|-------|-----|
| "can't find credentials.json" | Missing Gmail OAuth setup | Place file in `99_SYSTEM/_SECRETS/gmail/` |
| Token refresh fails | Expired OAuth token | Delete `token.json`, re-run (will prompt login) |
| Files not routing | Keywords not matching | Add keywords to CAR/FIRMA/KLIENTS sets in `router_cases_inbox.py` |
| Duplicate false positives | System files (desktop.ini) | Exclude via `if file_path.name.endswith(".meta.json") or ".bak" in file_path.name` |
| Pipeline locked | Anti-parallel mechanism | Delete `pipeline.lock` from `_STATE/` if stuck |

---

## 📋 File Naming Convention

### Attachment Pattern
```
{DATE}_{MSG_ID_SHORT}_{SANITIZED_FILENAME}

Examples:
20260104__19b88f58__IMG_20260104_125223.jpg
20260107__19b9a0a2__1.png
20260103__19b83e8e__BUD_6_LOK_2.pdf

Metadata file: {FILENAME}.meta.json (paired)
```

### Case Pattern (Dated Folders)
```
CASES/2026/CASE_{DATE}__{SUBJECT}/
├── 01_INBOX_RAW/          # Raw email + attachments
├── 02_ATTACHMENTS/        # Extracted files
├── 03_CLIENT_INPUT/       # Client information
├── 04_PROJECT/            # Project details
├── 05_FINANCE/            # Financial data
├── 06_OUTPUT/             # Generated output
│   └── MAIL_OUT/          # Outgoing emails
└── _META/                 # Metadata + timeline
```

---

## 🛠️ Development Workflows

### Test With Dry-Run
```python
# In router_cases_inbox.py:
DRY_RUN = True  # Don't move files, just show what would happen
# Then: python router_cases_inbox.py
```

### Reset State (Re-import All)
```bash
# Delete state file to re-process all emails:
rm "00_INBOX/MAIL_RAW/_STATE/processed_gmail_all.txt"
# Next pipeline run will import all again
```

### Generate Dedup Report
```bash
python find_duplicates.py
# Output: 00_INBOX/_ROUTER_LOGS/duplicates_report_{TIMESTAMP}.csv
```

### Cleanup Backups
```bash
python cleanup_backups.py
# Removes .bak_* files that are older than 30 days
```

---

## 📊 Statistics (as of 2026-02-02)

| Metric | Value |
|--------|-------|
| Total duplicate groups | 400+ |
| System files (desktop.ini) | 120 instances |
| Email attachments processed | ~500 |
| Cases in _INBOX | ~50 active |
| Training emails (2025) | ~100+ folders |
| Calendar events synced | ~50 |

---

## ✅ Checklist for Daily Operations

- [ ] Verify `pipeline_run.log` for errors
- [ ] Check `router_log.csv` for routing anomalies
- [ ] Monitor `CASES/_REVIEW/` for unclassified files
- [ ] Run `find_duplicates.py` weekly
- [ ] Review training evaluations in `TRAINING_EVALUATIONS.json`
- [ ] Calendar sync: Check `deadlines_to_gcal.py` logs
- [ ] Clean old logs: `cleanup_backups.py`

---

## 📞 Quick Reference

**Main Entry Points:**
- PowerShell: `run_mail_pipeline.ps1`
- Python CLI: `python -m router_cases_inbox`
- Calendar: `python deadlines_to_gcal.py`
- Evaluation: `python process_training_emails.py`

**Log Directory:** `00_INBOX/_ROUTER_LOGS/`  
**State Directory:** `00_INBOX/MAIL_RAW/_STATE/`  
**Secrets Directory:** `99_SYSTEM/_SECRETS/`

---

**Last Verified:** 2026-02-02 23:26:56 UTC  
**Next Maintenance:** 2026-02-09

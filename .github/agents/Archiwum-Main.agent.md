# Archiwum 3.0 - Email Automation System

**Status:** Active  
**Last Updated:** 2026-02-02  
**Maintainer Patterns:** Python (import/route/cleanup), PowerShell (orchestration), CSV logging

## System Overview

**Archiwum 3.0** is a personal document management and email archiving system:
- Automatically imports email attachments from Gmail/iCloud
- Routes them into categorized folders (KLIENTS, FIRMA, CAR, REVIEW)
- Detects/reports duplicates with SHA1 tracking
- Maintains state files to prevent re-importing

## Core Pipelines

### Mail Import Pipeline (`run_mail_pipeline.ps1`)
```
PowerShell entrypoint → import_gmail_attachments.py → router_cases_inbox.py
```
- Logs to: `00_INBOX/_ROUTER_LOGS/pipeline_run.log`
- State files: `00_INBOX/MAIL_RAW/_STATE/`
- Anti-parallel lock: `pipeline.lock`

### Key Scripts

| File | Purpose |
|------|---------|
| `import_gmail_attachments.py` | Pull Gmail attachments, create `.meta.json` |
| `router_cases_inbox.py` | Route files by keyword classification |
| `client_evaluator.py` | Assess email inquiries using Claude API |
| `process_training_emails.py` | Evaluate training emails from `_REPLIES_TRAINING` |
| `find_duplicates.py` | Generate dedup report (SHA1-based) |

## Classification Keywords

```python
CAR_KEYS = {"bmw", "vin", "oc", "ac", "polisa", "ubezpiec", ...}
FIRMA_KEYS = {"zus", "pue", "us", "vat", "pit", "faktura", "mbank", ...}
KLIENTS_KEYS = {"kuchnia", "szafa", "meble", "wycena", ...}
```

**Priority:** CAR > FIRMA > KLIENTS > REVIEW (fallback)

## File Naming & State

- **Attachments:** `{DATE}_{MSG_ID_SHORT}_{SANITIZED_FILENAME}`
- **Metadata:** Paired `.meta.json` with: `gmail_id`, `from`, `subject`, `date_utc`, `original_filename`, `sha1`
- **State:** `gmail_icloud_processed_ids.txt` / `processed_gmail_all.txt`

## Critical Patterns

✅ Use `$PSScriptRoot` in PowerShell (Dropbox sync creates `Archiwum_3.0` variant on iOS)  
✅ Atomic writes: temp file + rename for state/config  
✅ CSV logging: UTF-8, append-only (never truncate)  
✅ SHA1 for duplicate detection  

❌ Don't hardcode `C:\Users\alimg\` paths  
❌ Don't use `&&` in PowerShell; use `;` instead  

## External Dependencies

- **Google API:** `credentials.json` + `token.json` in `99_SYSTEM/_SECRETS/gmail/`
- **Anthropic API:** `anthropic_key.txt` in `99_SYSTEM/_SECRETS/` (for client evaluator)
- **Dropbox:** File sync for `.meta.json` metadata

## Active Tasks

- [ ] Process training emails from `_REPLIES_TRAINING/2025/MSG/`
- [ ] Generate evaluation report with payment risk/project type
- [ ] Monitor pipeline logs for sync errors
- [ ] Quarterly state file unification

---

**Next Action:** Run pipeline validation or process new training emails

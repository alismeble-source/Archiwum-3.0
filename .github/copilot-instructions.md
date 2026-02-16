# AI Coding Agent Instructions - Archiwum 3.0

## Project Overview

**Archiwum 3.0** is a personal document management and email archiving system built on Dropbox. It automatically imports email attachments from Gmail/iCloud, routes them into categorized folders, and detects/reports duplicates.

### Architecture

```
Email Sources (Gmail/iCloud)
  ↓
[IMPORT] → CASES/_INBOX (raw attachments + .meta.json)
  ↓
[ROUTE] → 01_KLIENTS/_INBOX, 02_FIRMA/_INBOX, 03_CAR/_INBOX, _REVIEW
  ↓
[CLEANUP] → Deduplication, state management, backup rotation
```

## Core Pipelines & Workflows

### 1. Mail Import Pipeline (`run_mail_pipeline.ps1`)

**Location:** `99_SYSTEM/_SCRIPTS/MAIL/run_mail_pipeline.ps1`

**Workflow:**
```
1. PowerShell entrypoint with anti-parallel lock
2. Calls: import_gmail_attachments.py
3. Calls: router_cases_inbox.py
4. Logs to: 00_INBOX/_ROUTER_LOGS/pipeline_run.log
```

**Key Files:**
- `import_gmail_attachments.py` - Pulls Gmail attachments, creates `.meta.json`
- `router_cases_inbox.py` - Routes files based on keyword classification
- `00_INBOX/MAIL_RAW/_STATE/` - Stores processed message IDs (prevent re-import)

**Important:** Use `$PSScriptRoot` not hardcoded paths; Dropbox syncs create `Archiwum_3.0` (underscore) variants on iOS.

### 2. File Classification Logic

**Pattern:** Greedy keyword matching on `(filename | subject | from | original_filename)`:

```python
CAR_KEYS = {"bmw", "vin", "oc", "ac", "polisa", "ubezpiec", ...}
FIRMA_KEYS = {"zus", "pue", "us", "vat", "pit", "faktura", "mbank", ...}
KLIENTS_KEYS = {"kuchnia", "szafa", "meble", "wycena", ...}
```

- **Priority:** CAR > FIRMA > KLIENTS (avoid flooding client folder)
- **Fallback:** REVIEW if no keywords match
- **Collision:** Files go to REVIEW to prevent overwrites

### 3. State Management

**Single Source of Truth:** `00_INBOX/MAIL_RAW/_STATE/`

**Files:**
- `gmail_icloud_processed_ids.txt` (legacy, being unified)
- `processed_gmail_all.txt` (new unified file)
- `pipeline.lock` (anti-parallel execution)

**Convention:** One ID per line, sorted. Use atomic writes (temp + rename) for safety.

## File Naming Conventions

### Attachment Storage

Pattern: `{DATE}_{MSG_ID_SHORT}_{SANITIZED_FILENAME}`

Example: `20260104__19b88f58__IMG_20260104_125223.jpg`

- **Metadata:** Paired `.meta.json` file contains: `gmail_id`, `from`, `subject`, `date_utc`, `original_filename`, `sha1`
- **Safety:** SHA1 computed and stored to detect true duplicates vs. filesystem duplicates

### Logs

- **Router logs:** `00_INBOX/_ROUTER_LOGS/router_log.csv` (routing decisions + timestamps)
- **Pipeline logs:** `pipeline_run.log` (transcript output, rotated at 5MB)
- **Duplicate reports:** `duplicates_report_{YYYYMMDD_HHMMSS}.csv` (findduplicates.py output)

## Critical Patterns & Gotchas

### 1. Path Handling

- **Root:** Always reference `ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")`
- **Dropbox Sync Issue:** iPhone creates `Archiwum_3.0` (underscore). Use `$PSScriptRoot` in PowerShell to auto-detect correct path.

### 2. Duplicate Handling

- **File Pairs:** Every attachment has a `.meta.json` companion. Router checks both exist.
- **SHA1 Tracking:** Stored in meta.json for manual dedup later.
- **Missing File:** Meta goes to REVIEW with timestamp suffix to avoid overwrites.

### 3. CSV Logging

- All CSVs use UTF-8 with proper CSV escaping (double-quote quotes).
- Headers written on first row if file missing.
- Append-only (never truncate, always `"a"` mode).

### 4. PowerShell Lock Mechanism

```powershell
$lock = Join-Path $root "00_INBOX\MAIL_RAW\_STATE\pipeline.lock"
if (Test-Path $lock) { exit 0 }  # Skip if locked
New-Item -ItemType File -Path $lock | Out-Null
# ... run pipeline ...
Remove-Item $lock  # Always clean up
```

## Development Workflows

### Testing Changes

1. **Pipeline validation (dry-run):**
   ```
   Set DRY_RUN = True in router_cases_inbox.py
   python router_cases_inbox.py
   ```

2. **State file reset (for re-importing):**
   ```
   Delete 00_INBOX/MAIL_RAW/_STATE/processed_gmail_all.txt
   Next run will re-process all emails
   ```

3. **Cleanup utilities:**
   ```
   python find_duplicates.py      # Generate dedup report
   python cleanup_backups.py       # Remove .bak_* files
   python unify_state_files.py     # Consolidate state
   ```

### Adding New Routes/Categories

1. Add keyword set to `router_cases_inbox.py` (CAR_KEYS, FIRMA_KEYS, etc.)
2. Create destination folder: `CASES/{01_KLIENTS|02_FIRMA|03_CAR}/_INBOX/`
3. Update priority if needed (CAR/FIRMA/KLIENTS/REVIEW order)
4. Test with `DRY_RUN = True`

## External Dependencies

- **Google API:** Requires `credentials.json` + `token.json` in `99_SYSTEM/_SECRETS/gmail/`
- **Gmail Label:** Query assumes `label:"SOURCE/ICLOUD"` exists in Gmail
- **Dropbox:** `.meta.json` files stored alongside attachments for metadata persistence

## Known Issues & Solutions

| Issue | Location | Solution |
|-------|----------|----------|
| "can't open file" in pipeline | `run_mail_pipeline.ps1` | Use `$PSScriptRoot`, not hardcoded paths |
| Dropbox path inconsistency | Multi-device sync | Always read from `ROOT` constant; handle `_` variants |
| Duplicate classifications | `router_cases_inbox.py` | Lower KLIENTS priority; use CAR/FIRMA first |
| State file fragmentation | `00_INBOX/MAIL_RAW/_STATE/` | Run `unify_state_files.py` quarterly |

## When Adding Features

- ✅ Always create `.meta.json` companions for new files
- ✅ Use atomic writes (temp file + rename) for state/config
- ✅ Log decisions to CSV (append, not overwrite)
- ✅ Test with small sample before full run
- ✅ Keep paths relative to `ROOT` for portability
- ❌ Don't hardcode `C:\Users\alimg\` paths
- ❌ Don't use `&&` in PowerShell; use `;` instead
- ❌ Don't truncate CSVs; always append

---

**Last Updated:** 2026-02-02  
**Key Maintainer Patterns:** Python (import/route/cleanup), PowerShell (orchestration), CSV logging

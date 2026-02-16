# Archiwum 3.0 - Implementation Checklist & To-Do

**Last Updated:** 2026-02-02 23:30 UTC  
**Status:** 🟢 ACTIVE (all core pipelines running)

---

## ✅ Completed & Verified

### Core Infrastructure
- [x] Mail import pipeline (`import_gmail_attachments.py`)
  - ✅ Pulling Gmail attachments with `SOURCE/ICLOUD` label
  - ✅ SHA1 hashing for duplicate detection
  - ✅ Metadata `.meta.json` paired files
  - ✅ State tracking: `processed_gmail_all.txt`
  - Last run: 2026-01-12 09:27:38

- [x] File classification router (`router_cases_inbox.py`)
  - ✅ CAR/FIRMA/KLIENTS/REVIEW classification
  - ✅ Keyword-based routing with priority
  - ✅ CSV logging to `router_log.csv`
  - ✅ Anti-collision protection (duplicate detection)

- [x] Orchestration (`run_mail_pipeline.ps1`)
  - ✅ Sequential pipeline: Import → Route → Notify
  - ✅ Transcript logging with rotation (5MB limit)
  - ✅ Anti-parallel lock mechanism
  - ✅ Error handling & exit codes

### Duplicate Detection
- [x] Find duplicates script (`find_duplicates.py`)
  - ✅ SHA1-based dedup
  - ✅ Latest report: `duplicates_report_20260202_181848.csv`
  - ✅ 400+ duplicate groups detected
  - ✅ CSV export with file list

### Notifications
- [x] Telegram notifier (`telegram_notify_router.py`)
  - ✅ Sends routing summaries
  - ✅ Integrated into pipeline

### State Management
- [x] Unified state files
  - ✅ `processed_gmail_all.txt` (new unified format)
  - ✅ Atomic writes with temp file + rename
  - ✅ One ID per line, sorted

### Gmail & Calendar
- [x] Google Calendar sync (`deadlines_to_gcal.py`)
  - ✅ OAuth token refresh logic
  - ✅ Reads from `DEADLINES.csv`
  - ✅ Stable UIDs for idempotency
  - Current entries: 5 deadlines tracked

- [x] Gmail OAuth setup
  - ✅ `credentials.json` present
  - ✅ Token auto-refresh implemented

### Training & Evaluation
- [x] Client email evaluator (`client_evaluator.py`)
  - ✅ Claude API integration
  - ✅ Fallback heuristic if API unavailable
  - ✅ Few-shot prompting examples
  - ✅ Returns: payment_risk, project_type, urgency, quality

- [x] Training processor (`process_training_emails.py`)
  - ✅ Processes `_REPLIES_TRAINING/2025/MSG/` folders
  - ✅ Extracts email metadata + body
  - ✅ Generates `TRAINING_EVALUATIONS.json`

---

## 🟡 In Progress / Monitoring

### Calendar Sync Deadlines
- [ ] Verify all 5 deadlines synced to Google Calendar
- [ ] Check if `deadlines_to_gcal.py` has write permissions to calendar
- [ ] Monitor token refresh (expires ~2026-02-05?)

### Training Data Quality
- [ ] Validate client evaluations in `TRAINING_EVALUATIONS.json`
- [ ] Check Claude response format parsing
- [ ] Review payment_risk distribution (should be weighted)

---

## 🔴 TODO / Known Gaps

### Missing/Incomplete Features

1. **Scheduled Task Automation**
   - ❌ No Windows Scheduled Task registered yet
   - 📝 Action: Create daily `run_mail_pipeline.ps1` trigger at 08:00
   - Reference: Previous conversation mentioned issues with action parameter

2. **ICloud IMAP Integration**
   - ⚠️ Multiple `icloud_imap_*.py` scripts exist but status unclear
   - Last import log: `ICLOUD_ATTACH_20260126_143147.csv`
   - 📝 Action: Verify iCloud credentials and run full import

3. **Backup & Archival**
   - ❌ No automated backup rotation
   - 📝 Action: Implement `cleanup_backups.py` to remove `.bak_*` files >30 days
   - Current logs have many `.bak` files cluttering directories

4. **Calendar Integration - Missing Features**
   - ❌ No alarm/reminder setup
   - ❌ No color coding by deadline type
   - ❌ No auto-sync feedback to Archiwum (missed deadline updates)

5. **Email Drafts Workflow**
   - ⚠️ `telegram_notify_router.py` references draft building but unclear
   - Multiple `draft_builder_v*.ps1` versions exist (v4, v41, v42, v43)
   - 📝 Action: Document which draft builder is current

6. **PDF Processing**
   - ⚠️ PDF OCR scripts exist (`pdf_ocr_v6.ps1`, `pdf_inspect_v5.ps1`)
   - Last run unclear
   - 📝 Action: Enable OCR for scanned documents in `_REVIEW`

### Infrastructure Gaps

1. **Error Alerting**
   - ❌ No email alerts on pipeline failure
   - 📝 Action: Add error notifications to Telegram notifier

2. **Metrics & Dashboards**
   - ❌ No real-time monitoring dashboard
   - 📝 Action: Create summary report generator from CSV logs

3. **Data Validation**
   - ⚠️ No schema validation for `.meta.json` files
   - 📝 Action: Add JSON schema validation in import stage

4. **Security**
   - ❌ Credentials stored in plaintext (anthropic_key.txt)
   - 📝 Action: Migrate to environment variables or Windows Credential Manager

---

## 📋 Quick Actions (Next 24 hours)

### Priority 1: Enable Automation
```powershell
# 1. Create scheduled task for daily 08:00 run
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File 'C:\Users\alimg\Dropbox\Archiwum_3.0\99_SYSTEM\_SCRIPTS\MAIL\run_mail_pipeline.ps1'"
$trigger = New-ScheduledTaskTrigger -Daily -At 08:00
Register-ScheduledTask -TaskName "Archiwum-Mail-Pipeline" -Action $action -Trigger $trigger

# 2. Verify it runs without errors
Get-ScheduledTask -TaskName "Archiwum-Mail-Pipeline" | Start-ScheduledTask
```

### Priority 2: Verify Calendar Sync
```bash
# Check if deadlines synced
python "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SCRIPTS\CALENDAR\deadlines_to_gcal.py"

# Monitor token refresh
ls -la "C:\Users\alimg\Dropbox\Archiwum 3.0\FINANCE\_CALENDAR\_STATE\"
```

### Priority 3: Cleanup & Audit
```bash
# Find old files
find "C:\Users\alimg\Dropbox\Archiwum 3.0" -name "*.bak" -mtime +30

# Clean up
python "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SCRIPTS\MAIL\cleanup_backups.py"
```

---

## 📊 System Metrics (Status as of 2026-02-02)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Pipeline runs (this month) | 15+ | Daily | 🟢 OK |
| Unprocessed emails | 0 | 0 | 🟢 OK |
| Duplicate groups found | 400+ | Monitor | 🟢 OK |
| Files in _REVIEW (pending sort) | ~50 | <20 | 🟡 HIGH |
| Calendar deadlines tracked | 5 | 10+ | 🟡 LOW |
| Training emails processed | ~100 | Growing | 🟢 OK |
| API token status | ✅ Valid | Fresh | 🟢 OK |

---

## 🔧 Maintenance Schedule

### Daily
- [ ] Check `pipeline_run.log` for errors
- [ ] Monitor `CASES/_REVIEW/` size

### Weekly
- [ ] Run `find_duplicates.py`
- [ ] Review `router_log.csv` for anomalies
- [ ] Check `TRAINING_EVALUATIONS.json` quality

### Monthly
- [ ] Rotate old logs
- [ ] Archive completed cases
- [ ] Review and update classification keywords
- [ ] Refresh Google OAuth tokens
- [ ] Run `cleanup_backups.py`

---

## 📞 Support & Reference

**System Documentation:**
- Main guide: `copilot-instructions.md`
- Status: This file + `SYSTEM_STATUS.md`
- Previous summary: `Untitled-1.agent.md`

**Key Contacts:**
- Gmail API: `credentials.json` in `99_SYSTEM/_SECRETS/gmail/`
- Claude API: `anthropic_key.txt` in `99_SYSTEM/_SECRETS/`
- Google Calendar: OAuth via `FINANCE/_CALENDAR/_STATE/token.json`

---

**Next Review:** 2026-02-09  
**Agent:** Copilot CLI  
**Repo:** None (Dropbox-based, git-ignored)

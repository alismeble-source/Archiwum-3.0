# Archiwum 3.0 - Project Complete Status

**Updated (UTC):** 2026-02-16
**Goal:** stable repo foundation for ERP/CRM growth without breaking current production flow.

---

## Current state

### Production entrypoints
- Mail pipeline: `99_SYSTEM/_SCRIPTS/MAIL/run_mail_pipeline.ps1`
- Telegram dashboard: `99_SYSTEM/_SCRIPTS/FINANCE/telegram_dashboard_bot_v2.py`
- Bot launcher/restart loop: `99_SYSTEM/_SCRIPTS/FINANCE/run_dashboard_bot.ps1`

### Data sources in use
- Routing and pipeline logs: `00_INBOX/_ROUTER_LOGS/`
- Payables: `FINANCE/PAYMENTS.csv`
- Quotes: `FINANCE/CLIENT_QUOTES.csv`
- Accounting docs: `FINANCE/DOCS/`

---

## Repository milestones completed

1. Safe repository bootstrap completed.
- `.gitignore` hardened for secrets, runtime logs, state files, and business data folders.
- Initial code/documentation baseline committed to `main`.

2. Project scaffolding for scale completed.
- Added: `docs/`, `src/`, `scripts/`, `config/`, `tests/`, `tools/`, `data/`, `runtime/`.
- Added safe sync helper: `sync.ps1` (stages only allowed code/doc paths).

3. CORE knowledge base connected.
- Added `CORE/` into git to keep business logic/policy documents versioned.

4. Branch model enabled.
- Stable branch: `main`
- Working integration branch: `dev` (remote branch created and tracking enabled).

5. CI smoke check enabled.
- Added workflow: `.github/workflows/ci-smoke.yml`
- Checks:
  - Python syntax compile under `99_SYSTEM/_SCRIPTS`
  - PowerShell parse validation under `99_SYSTEM/_SCRIPTS`
  - Required file presence smoke check

6. Autopilot v1 components prepared.
- Runner: `scripts/windows/nightly_autopilot.ps1`
- Task setup: `scripts/windows/register_autopilot_task.ps1`
- Health telegram sender: `99_SYSTEM/_SCRIPTS/FINANCE/send_telegram_health_report.py`
- Ops docs: `docs/operations/AUTOPILOT_V1.md`, `docs/operations/GIT_WORKFLOW.md`
- Config templates: `config/examples/secrets.env.example`, `config/examples/autopilot.settings.example.json`

---

## Open risks (still relevant)

- Multiple legacy script versions exist (`*_v2`, `*_v3`, `*_new`, draft builders).
- Absolute Windows paths remain in several scripts.
- Telegram polling conflict can happen if two bot instances run in parallel.
- Runtime data quality depends on log consistency (`router_log.csv`, `pipeline_errors.jsonl`).

---

## Next practical steps

1. Register and test nightly task:
```powershell
.\scripts\windows\register_autopilot_task.ps1 -At "06:30"
Start-ScheduledTask -TaskName "Archiwum-Nightly-Autopilot"
```

2. Keep all daily changes in `dev`, merge to `main` only after CI passes.

3. Start phase-1 modularization:
- move reusable helpers to `src/common`
- keep production entrypoints unchanged during migration

---

## Definition of done for this phase

- Repo contains code/docs/config templates only (no secrets, no heavy business data).
- `main` stays stable, `dev` used for integration.
- CI smoke checks run on push/PR.
- Nightly autopilot scripts are available for one-command activation.

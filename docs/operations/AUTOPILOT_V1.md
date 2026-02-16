# Autopilot v1 (Nightly)

## Scope
- Run mail pipeline once per night.
- Send one Telegram health summary after pipeline run.
- Keep logs in `00_INBOX/_ROUTER_LOGS`.

## Scripts
- Runner: `scripts/windows/nightly_autopilot.ps1`
- Task registration: `scripts/windows/register_autopilot_task.ps1`
- Telegram health sender: `99_SYSTEM/_SCRIPTS/FINANCE/send_telegram_health_report.py`

## Prerequisites
- `.venv` exists and contains Python.
- `99_SYSTEM/_SECRETS/telegram_bot_token.txt` exists.
- `99_SYSTEM/_SECRETS/telegram_chat_id.txt` exists.

## Setup
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\windows\register_autopilot_task.ps1 -At "06:30"
```

## Manual test
```powershell
.\scripts\windows\nightly_autopilot.ps1
```

## Runtime outputs
- `00_INBOX/_ROUTER_LOGS/nightly_autopilot.log`
- `00_INBOX/_ROUTER_LOGS/nightly_pipeline_rc.txt`

## Failure model
- Pipeline fails -> health report still attempts to send with non-zero `pipeline_exit_code`.
- If Telegram send fails, error is logged in `nightly_autopilot.log`.

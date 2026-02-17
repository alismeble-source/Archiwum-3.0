# check_auto_send_status.ps1 - check safety status for auto-send flow

$ErrorActionPreference = "Stop"

Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host "AUTO-SEND STATUS CHECK" -ForegroundColor Yellow
Write-Host ("=" * 80) -ForegroundColor Cyan

$root = "C:\Users\alimg\Dropbox\Archiwum 3.0"
$listenerScript = Join-Path $root "99_SYSTEM\_SCRIPTS\MAIL\telegram_approval_listener.py"
$stateFile = Join-Path $root "00_INBOX\_ROUTER_LOGS\telegram_approval_state.json"

Write-Host "`n[1] AUTO_SEND flag" -ForegroundColor White
if (Test-Path $listenerScript) {
    $content = Get-Content $listenerScript -Raw
    if ($content -match "AUTO_SEND\s*=\s*False") {
        Write-Host "  OK: AUTO_SEND=False (safe mode)" -ForegroundColor Green
    }
    elseif ($content -match "AUTO_SEND\s*=\s*True") {
        Write-Host "  WARNING: AUTO_SEND=True (emails can be sent automatically)" -ForegroundColor Red
    }
    else {
        Write-Host "  UNKNOWN: AUTO_SEND flag not found" -ForegroundColor Yellow
    }
}
else {
    Write-Host "  ERROR: telegram_approval_listener.py not found" -ForegroundColor Red
}

Write-Host "`n[2] Running processes" -ForegroundColor White
$pythonProcs = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and (
        $_.CommandLine -like "*telegram_approval_listener*" -or
        $_.CommandLine -like "*ai_responder*"
    )
}

if ($pythonProcs) {
    Write-Host "  ACTIVE: listener/responder processes found:" -ForegroundColor Yellow
    foreach ($proc in $pythonProcs) {
        Write-Host ("    PID: {0}" -f $proc.ProcessId) -ForegroundColor Gray
        Write-Host ("    CMD: {0}" -f $proc.CommandLine) -ForegroundColor Gray
        Write-Host ""
    }
}
else {
    Write-Host "  OK: no active listener/responder process" -ForegroundColor Green
}

Write-Host "`n[3] Approval state" -ForegroundColor White
if (Test-Path $stateFile) {
    $stateContent = Get-Content $stateFile -Raw | ConvertFrom-Json
    $approvalCount = ($stateContent.PSObject.Properties | Measure-Object).Count
    Write-Host "  INFO: approval state exists" -ForegroundColor Cyan
    Write-Host ("  Logged reactions: {0}" -f $approvalCount) -ForegroundColor Gray

    if ($approvalCount -gt 0) {
        $recent = $stateContent.PSObject.Properties |
            Sort-Object { [datetime]$_.Value.timestamp } -Descending |
            Select-Object -First 3
        Write-Host "  Recent reactions:" -ForegroundColor Gray
        foreach ($r in $recent) {
            $status = $r.Value.status
            $timestamp = [datetime]::Parse($r.Value.timestamp).ToString("yyyy-MM-dd HH:mm")
            Write-Host ("    {0} - {1}" -f $timestamp, $status) -ForegroundColor Gray
        }
    }
}
else {
    Write-Host "  OK: no approval state file (clean slate)" -ForegroundColor Green
}

Write-Host "`n[4] Summary" -ForegroundColor White
Write-Host "  OK: emails are not sent automatically when AUTO_SEND=False" -ForegroundColor Green
Write-Host "  Workflow: draft -> telegram reaction -> logged decision -> manual send if needed" -ForegroundColor Gray
Write-Host ("=" * 80) -ForegroundColor Cyan

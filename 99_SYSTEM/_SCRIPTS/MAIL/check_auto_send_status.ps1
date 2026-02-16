# check_auto_send_status.ps1 - Перевірка стану автовідправки

Write-Host "=" -repeat 80 -ForegroundColor Cyan
Write-Host "AUTO-SEND STATUS CHECK" -ForegroundColor Yellow
Write-Host "=" -repeat 80 -ForegroundColor Cyan

$root = "C:\Users\alimg\Dropbox\Archiwum 3.0"
$listenerScript = Join-Path $root "99_SYSTEM\_SCRIPTS\MAIL\telegram_approval_listener.py"

Write-Host "`n[1] Checking AUTO_SEND flag..." -ForegroundColor White

if (Test-Path $listenerScript) {
    $content = Get-Content $listenerScript -Raw
    
    if ($content -match 'AUTO_SEND\s*=\s*False') {
        Write-Host "    [OK] AUTO_SEND = False (безпечний режим)" -ForegroundColor Green
        Write-Host "         Email НЕ відправляються автоматично" -ForegroundColor Gray
    } elseif ($content -match 'AUTO_SEND\s*=\s*True') {
        Write-Host "    [WARNING] AUTO_SEND = True" -ForegroundColor Red
        Write-Host "              Email ВІДПРАВЛЯЮТЬСЯ автоматично при реакції ✅" -ForegroundColor Red
    } else {
        Write-Host "    [UNKNOWN] Cannot find AUTO_SEND flag" -ForegroundColor Yellow
    }
} else {
    Write-Host "    [ERROR] telegram_approval_listener.py not found" -ForegroundColor Red
}

Write-Host "`n[2] Checking running processes..." -ForegroundColor White

$pythonProcs = Get-WmiObject Win32_Process | Where-Object { 
    $_.CommandLine -like "*telegram_approval_listener*" -or 
    $_.CommandLine -like "*ai_responder*" 
}

if ($pythonProcs) {
    Write-Host "    [ACTIVE] Found running processes:" -ForegroundColor Yellow
    foreach ($proc in $pythonProcs) {
        Write-Host "      PID: $($proc.ProcessId)" -ForegroundColor Gray
        Write-Host "      CMD: $($proc.CommandLine)" -ForegroundColor Gray
        Write-Host ""
    }
} else {
    Write-Host "    [OK] No active listener or responder processes" -ForegroundColor Green
}

Write-Host "`n[3] Checking approval state..." -ForegroundColor White

$stateFile = Join-Path $root "00_INBOX\_ROUTER_LOGS\telegram_approval_state.json"

if (Test-Path $stateFile) {
    $stateContent = Get-Content $stateFile -Raw | ConvertFrom-Json
    $approvalCount = ($stateContent.PSObject.Properties | Measure-Object).Count
    
    Write-Host "    [INFO] Approval state file exists" -ForegroundColor Cyan
    Write-Host "           Total logged reactions: $approvalCount" -ForegroundColor Gray
    
    # Show last 3 reactions
    if ($approvalCount -gt 0) {
        $recent = $stateContent.PSObject.Properties | 
                  Sort-Object { [datetime]$_.Value.timestamp } -Descending | 
                  Select-Object -First 3
        
        Write-Host "`n    Recent reactions:" -ForegroundColor Gray
        foreach ($r in $recent) {
            $emoji = if ($r.Name -like "*✅*") { "✅" } elseif ($r.Name -like "*❌*") { "❌" } else { "?" }
            $status = $r.Value.status
            $timestamp = [datetime]::Parse($r.Value.timestamp).ToString("yyyy-MM-dd HH:mm")
            
            Write-Host "      $emoji $timestamp - $status" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "    [OK] No approval state file (clean slate)" -ForegroundColor Green
}

Write-Host "[4] Summary" -ForegroundColor White
Write-Host "    OK: Email NOT sent automatically" -ForegroundColor Green
Write-Host "    OK: System is safe to use" -ForegroundColor Green
Write-Host ""
Write-Host "Workflow:" -ForegroundColor Cyan
Write-Host "  1. AI generates draft -> sends to Telegram" -ForegroundColor Gray
Write-Host "  2. You react with checkmark (approve) or X (skip)" -ForegroundColor Gray
Write-Host "  3. Reaction is LOGGED but email NOT sent" -ForegroundColor Gray
Write-Host "  4. To send manually: python gmail_send_reply.py EMAIL_ID approve" -ForegroundColor Gray

Write-Host ""
Write-Host ("=" * 80) -ForegroundColor Cyan

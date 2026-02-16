# run_finance_bot.ps1 - Start Telegram Finance Bot in background
# Usage: .\run_finance_bot.ps1 [start|stop|status]

$root = $PSScriptRoot | Split-Path | Split-Path
$script = Join-Path $root "99_SYSTEM\_SCRIPTS\FINANCE\telegram_finance_bot.py"
$python = Join-Path $root ".venv\Scripts\python.exe"
$logsDir = Join-Path $root "99_SYSTEM\_LOGS"
$pidFile = Join-Path $logsDir "finance_bot.pid"
$logFile = Join-Path $logsDir "finance_bot.log"

# Ensure logs directory exists
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}

function Start-Bot {
    # Check if already running
    if (Test-Path $pidFile) {
        $botPid = Get-Content $pidFile
        if (Get-Process -Id $botPid -ErrorAction SilentlyContinue) {
            Write-Host "[!] Bot already running (PID: $botPid)" -ForegroundColor Yellow
            return
        } else {
            Remove-Item $pidFile
        }
    }
    
    Write-Host "[+] Starting Finance Bot..." -ForegroundColor Cyan
    
    # Start bot directly
    $cmd = "& '$python' '$script' *>&1 | Out-File -FilePath '$logFile' -Append"
    
    # Start in new hidden process
    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = "powershell.exe"
    $processInfo.Arguments = "-NoProfile -WindowStyle Hidden -Command `"$cmd`""
    $processInfo.UseShellExecute = $false
    $processInfo.CreateNoWindow = $true
    
    $process = [System.Diagnostics.Process]::Start($processInfo)
    
    if (-not $process) {
        Write-Host "[ERROR] Failed to start bot" -ForegroundColor Red
        return
    }
    
    # Save PID
    $process.Id | Out-File -FilePath $pidFile -Encoding utf8
    
    Start-Sleep -Seconds 2
    
    if (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
        Write-Host "[OK] Bot started (PID: $($process.Id))" -ForegroundColor Green
        Write-Host "[LOG] $logFile" -ForegroundColor Gray
    } else {
        Write-Host "[ERROR] Bot failed to start" -ForegroundColor Red
        Write-Host "Check log: $logFile" -ForegroundColor Gray
    }
}

function Stop-Bot {
    if (-not (Test-Path $pidFile)) {
        Write-Host "[INFO] Bot not running (no PID file)" -ForegroundColor Gray
        return
    }
    
    $botPid = Get-Content $pidFile
    
    if (Get-Process -Id $botPid -ErrorAction SilentlyContinue) {
        Write-Host "[STOP] Stopping bot (PID: $botPid)..." -ForegroundColor Cyan
        Stop-Process -Id $botPid -Force
        Start-Sleep -Seconds 1
        Write-Host "[OK] Bot stopped" -ForegroundColor Green
    } else {
        Write-Host "[INFO] Bot not running (process not found)" -ForegroundColor Gray
    }
    
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}

function Show-Status {
    if (Test-Path $pidFile) {
        $botPid = Get-Content $pidFile
        
        if (Get-Process -Id $botPid -ErrorAction SilentlyContinue) {
            Write-Host "[RUNNING] Bot active (PID: $botPid)" -ForegroundColor Green
            
            # Show last log lines
            if (Test-Path $logFile) {
                Write-Host "`n[LOG] Last entries:" -ForegroundColor Gray
                Get-Content $logFile -Tail 5 | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
            }
        } else {
            Write-Host "[ERROR] Bot NOT RUNNING (stale PID file)" -ForegroundColor Red
            Remove-Item $pidFile
        }
    } else {
        Write-Host "[STOPPED] Bot NOT RUNNING" -ForegroundColor Red
    }
}

# Main
switch ($args[0]) {
    "start" { Start-Bot }
    "stop" { Stop-Bot }
    "status" { Show-Status }
    "restart" {
        Stop-Bot
        Start-Sleep -Seconds 1
        Start-Bot
    }
    default {
        Write-Host "Usage: .\run_finance_bot.ps1 [start|stop|status|restart]" -ForegroundColor Yellow
        Write-Host ""
        Show-Status
    }
}

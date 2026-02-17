$ErrorActionPreference = "Stop"

$root = "C:\Users\alimg\Dropbox\Archiwum 3.0"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$bot = Join-Path $root "99_SYSTEM\_SCRIPTS\FINANCE\telegram_dashboard_bot_v2.py"
$botRelative = ".\99_SYSTEM\_SCRIPTS\FINANCE\telegram_dashboard_bot_v2.py"
$logDir = Join-Path $root "00_INBOX\_ROUTER_LOGS"
$launcherLog = Join-Path $logDir "telegram_dashboard_launcher.log"

if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: Python not found in .venv: $venvPython" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $bot)) {
    Write-Host "ERROR: Bot file not found: $bot" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $logDir)) {
    New-Item -Path $logDir -ItemType Directory -Force | Out-Null
}

function Write-LauncherLog([string]$msg) {
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    try {
        Add-Content -Path $launcherLog -Value "$ts $msg" -Encoding UTF8
    } catch {
        try {
            # Recovery path for corrupted/locked launcher log files.
            Remove-Item -Path $launcherLog -Force -ErrorAction SilentlyContinue
            Set-Content -Path $launcherLog -Value "$ts log reset after write failure" -Encoding UTF8
            Add-Content -Path $launcherLog -Value "$ts $msg" -Encoding UTF8
        } catch {
            # Logging must never stop launcher workflow.
        }
    }
}

function Stop-ExistingDashboardBots {
    try {
        $procs = Get-CimInstance Win32_Process | Where-Object {
            $_.Name -match '^python(\.exe)?$' -and
            $_.CommandLine -match 'telegram_dashboard_bot_v2\.py'
        }
        foreach ($p in $procs) {
            try {
                Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
                Write-Host "Stopped stale bot process PID $($p.ProcessId)" -ForegroundColor DarkYellow
                Write-LauncherLog "stopped stale pid=$($p.ProcessId)"
            } catch {
                Write-LauncherLog "failed to stop stale pid=$($p.ProcessId): $($_.Exception.Message)"
            }
        }
    } catch {
        Write-LauncherLog "failed to enumerate stale processes: $($_.Exception.Message)"
    }
}

Write-Host "Starting Telegram dashboard bot..." -ForegroundColor Cyan
Write-LauncherLog "launcher start"
Stop-ExistingDashboardBots

$restartDelaySec = 6
$maxRestarts = 20
$restarts = 0

while ($true) {
    Push-Location $root
    try {
        # Use relative script path to avoid path-splitting issues with spaces in root path.
        & $venvPython $botRelative
    } finally {
        Pop-Location
    }
    $rc = $LASTEXITCODE

    if ($rc -eq 0) {
        Write-Host "Bot exited normally (code 0)." -ForegroundColor Green
        Write-LauncherLog "bot exit code=0"
        break
    }

    $restarts += 1
    Write-Host "Bot crashed (code $rc). Restart $restarts/$maxRestarts in $restartDelaySec sec..." -ForegroundColor Yellow
    Write-LauncherLog "bot crash code=$rc restart=$restarts"

    if ($restarts -ge $maxRestarts) {
        Write-Host "Too many restarts. Stop." -ForegroundColor Red
        Write-LauncherLog "stop after max restarts"
        exit 1
    }

    Start-Sleep -Seconds $restartDelaySec
}

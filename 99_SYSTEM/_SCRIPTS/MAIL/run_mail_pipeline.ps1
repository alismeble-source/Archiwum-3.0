$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$pythonExe = if (Test-Path $venvPython) { $venvPython } else { "python" }

# Pipeline stages with retry logic
$importer = Join-Path $scriptDir "import_gmail_attachments.py"
$importerAlim = Join-Path $scriptDir "import_gmail_alim.py"  # alimgulov1992@gmail.com
$router = Join-Path $scriptDir "router_cases_inbox.py"
$notifier = Join-Path $scriptDir "telegram_notify_router.py"
$calendarSync = Join-Path $root "99_SYSTEM\_SCRIPTS\CALENDAR\gmail_to_calendar.py"
$calendarCleanup = Join-Path $root "99_SYSTEM\_SCRIPTS\CALENDAR\cleanup_recurring_events.py"

# Logging (transcript with rotation)
$logDir = Join-Path $root "00_INBOX\_ROUTER_LOGS"
$logFile = Join-Path $logDir "pipeline_run.log"
$errorLogFile = Join-Path $logDir "pipeline_errors.jsonl"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

# Rotate log if > 5MB
if (Test-Path $logFile) {
    $size = (Get-Item $logFile).Length
    if ($size -gt 5MB) {
        $stamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
        Rename-Item $logFile "$logFile.$stamp.bak"
    }
}

Start-Transcript -Path $logFile -Append | Out-Null

# Helper: Run Python script with retries
function Invoke-PythonScript {
    param(
        [string]$ScriptPath,
        [string]$StageName,
        [int]$MaxRetries = 2,
        [bool]$IsCritical = $true
    )
    
    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        Write-Host "  [$StageName] Attempt $attempt/$MaxRetries..."
        & $pythonExe $ScriptPath
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [$StageName] ✓ Success" -ForegroundColor Green
            return $true
        }
        
        if ($attempt -lt $MaxRetries) {
            Write-Host "  [$StageName] Failed, waiting 5 seconds before retry..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        }
    }
    
    if ($IsCritical) {
        Write-Host "  [$StageName] ✗ CRITICAL FAILURE (exit $LASTEXITCODE)" -ForegroundColor Red
        return $false
    }
    else {
        Write-Host "  [$StageName] ⚠ Non-critical failure (exit $LASTEXITCODE)" -ForegroundColor Yellow
        return $true  # Non-critical, continue pipeline
    }
}

# Helper: Write errors to JSONL
function Write-ErrorLog {
    param([string]$Stage, [string]$Message, [string]$ExitCode)
    $entry = @{
        ts_utc    = (Get-Date).ToUniversalTime().ToString("o")
        stage     = $Stage
        message   = $Message
        exit_code = $ExitCode
    } | ConvertTo-Json -Compress
    Add-Content -Path $errorLogFile -Value $entry
}

# SYNCHRONOUS LOCK (anti-parallel runs)
$lock = Join-Path $root "00_INBOX\MAIL_RAW\_STATE\pipeline.lock"
$lockTimeout = 600  # 10 minutes
$lockWaitTime = 0

Write-Host "Checking pipeline lock..."
while (Test-Path $lock) {
    if ($lockWaitTime -gt $lockTimeout) {
        Write-Host "LOCK TIMEOUT ($lockTimeout s) - force clearing: $lock" -ForegroundColor Red
        Remove-Item $lock -Force -ErrorAction SilentlyContinue
        break
    }
    Write-Host "  Lock exists, waiting... ($lockWaitTime / $lockTimeout s)" -ForegroundColor Yellow
    Start-Sleep -Seconds 1
    $lockWaitTime += 1
}

New-Item -ItemType File -Path $lock -Force | Out-Null
Write-Host "Lock acquired: $lock" -ForegroundColor Cyan

try {
    Write-Host ""
    Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  MAIL PIPELINE START" -ForegroundColor Cyan
    Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ("UTC: " + (Get-Date).ToUniversalTime().ToString("s") + "Z")
    Write-Host ""

    # STAGE 1: IMPORT - alismeble@gmail.com inbox (CRITICAL)
    Write-Host "STAGE 1A/6: IMPORT - Gmail alismeble@gmail.com → CASES\_INBOX"
    $result = Invoke-PythonScript -ScriptPath $importer -StageName "IMPORT_GMAIL" -MaxRetries 2 -IsCritical $true
    if (-not $result) {
        throw "IMPORT_GMAIL stage failed"
    }

    Write-Host ""
    # STAGE 1B: IMPORT - alimgulov1992@gmail.com (DISABLED - no OAuth configured yet)
    # Write-Host "STAGE 1B/6: IMPORT - Gmail alimgulov1992 (ZUS/Skarbowa) → CASES\_INBOX"
    # $result = Invoke-PythonScript -ScriptPath $importerAlim -StageName "IMPORT_ALIM" -MaxRetries 2 -IsCritical $true
    # if (-not $result) {
    #     throw "IMPORT alimgulov1992 stage failed"
    # }

    Write-Host ""
    # STAGE 2: ROUTER (CRITICAL)
    Write-Host "STAGE 2/6: ROUTER - CASES\_INBOX → (KLIENTS/FIRMA/CAR/REVIEW)"
    $result = Invoke-PythonScript -ScriptPath $router -StageName "ROUTER" -MaxRetries 2 -IsCritical $true
    if (-not $result) {
        throw "ROUTER stage failed"
    }

    Write-Host ""
    # STAGE 3: TELEGRAM (CRITICAL)
    Write-Host "STAGE 3/6: TELEGRAM - Send drafts + notifications"
    $result = Invoke-PythonScript -ScriptPath $notifier -StageName "TELEGRAM" -MaxRetries 2 -IsCritical $true
    if (-not $result) {
        throw "TELEGRAM notifier failed"
    }

    Write-Host ""
    # STAGE 4: CALENDAR SYNC (NON-CRITICAL)
    Write-Host "STAGE 4/6: CALENDAR - Sync Gmail events (wyceny, risks, faktury)"
    Invoke-PythonScript -ScriptPath $calendarSync -StageName "CALENDAR" -MaxRetries 1 -IsCritical $false | Out-Null

    Write-Host ""
    # STAGE 5: CALENDAR CLEANUP (NON-CRITICAL)
    Write-Host "STAGE 5/6: CLEANUP - Remove Focus time/Lunch auto-events"
    Invoke-PythonScript -ScriptPath $calendarCleanup -StageName "CLEANUP" -MaxRetries 1 -IsCritical $false | Out-Null

    Write-Host ""
    Write-Host "════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  MAIL PIPELINE DONE ✓" -ForegroundColor Green
    Write-Host "════════════════════════════════════════════════" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "════════════════════════════════════════════════" -ForegroundColor Red
    Write-Host "  PIPELINE ERROR ✗" -ForegroundColor Red
    Write-Host "════════════════════════════════════════════════" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    
    # Extract stage from error (best-effort)
    $stage = "UNKNOWN"
    if ($_ -match "IMPORT_GMAIL") { $stage = "IMPORT_GMAIL" }
    elseif ($_ -match "IMPORT") { $stage = "IMPORT" }
    elseif ($_ -match "ROUTER") { $stage = "ROUTER" }
    elseif ($_ -match "TELEGRAM") { $stage = "TELEGRAM" }
    
    Write-ErrorLog -Stage $stage -Message $_.Exception.Message -ExitCode $LASTEXITCODE
}
finally {
    Remove-Item $lock -ErrorAction SilentlyContinue
    Write-Host ""
    Write-Host "Lock released"
    Stop-Transcript | Out-Null
}




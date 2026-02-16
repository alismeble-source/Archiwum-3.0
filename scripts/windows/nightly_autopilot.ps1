[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$pipelineScript = Join-Path $repoRoot "99_SYSTEM\_SCRIPTS\MAIL\run_mail_pipeline.ps1"
$healthReportPy = Join-Path $repoRoot "99_SYSTEM\_SCRIPTS\FINANCE\send_telegram_health_report.py"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$logDir = Join-Path $repoRoot "00_INBOX\_ROUTER_LOGS"
$autopilotLog = Join-Path $logDir "nightly_autopilot.log"
$rcFile = Join-Path $logDir "nightly_pipeline_rc.txt"

if (-not (Test-Path $logDir)) {
    New-Item -Path $logDir -ItemType Directory -Force | Out-Null
}

function Write-AutopilotLog([string]$msg) {
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    Add-Content -Path $autopilotLog -Value "$ts $msg"
}

Write-AutopilotLog "nightly autopilot start"

$pipelineRc = 1
try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $pipelineScript
    $pipelineRc = $LASTEXITCODE
    if ($pipelineRc -eq 0) {
        Write-AutopilotLog "pipeline ok"
    } else {
        Write-AutopilotLog "pipeline failed rc=$pipelineRc"
    }
} catch {
    $pipelineRc = 1
    Write-AutopilotLog "pipeline exception: $($_.Exception.Message)"
}

Set-Content -Path $rcFile -Value "$pipelineRc" -Encoding utf8

try {
    if (-not (Test-Path $venvPython)) {
        throw "Python not found: $venvPython"
    }
    & $venvPython $healthReportPy
    if ($LASTEXITCODE -eq 0) {
        Write-AutopilotLog "health report sent"
    } else {
        Write-AutopilotLog "health report failed rc=$LASTEXITCODE"
    }
} catch {
    Write-AutopilotLog "health report exception: $($_.Exception.Message)"
}

Write-AutopilotLog "nightly autopilot end"

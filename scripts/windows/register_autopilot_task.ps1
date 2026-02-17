[CmdletBinding()]
param(
    [string]$TaskName = "Archiwum-Nightly-Autopilot",
    [string]$At = "06:30"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$runner = Join-Path $repoRoot "scripts\windows\nightly_autopilot.ps1"
$runnerCmd = Join-Path $repoRoot "scripts\windows\nightly_autopilot.cmd"

if (-not (Test-Path $runner)) {
    throw "Runner script not found: $runner"
}

try {
    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`""

    $trigger = New-ScheduledTaskTrigger -Daily -At $At
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null

    Write-Host "OK: task '$TaskName' registered at $At" -ForegroundColor Green
    Write-Host "Run now: Start-ScheduledTask -TaskName '$TaskName'"
}
catch {
    Write-Warning "Register-ScheduledTask failed: $($_.Exception.Message)"
    Write-Host "Trying fallback via schtasks.exe for current user..." -ForegroundColor Yellow

    if (-not (Test-Path $runnerCmd)) {
        throw "Fallback runner not found: $runnerCmd"
    }
    $runnerShort = (cmd /c "for %I in (""$runnerCmd"") do @echo %~sI").Trim()
    if (-not $runnerShort) {
        $runnerShort = $runnerCmd
    }
    $args = @('/Create', '/F', '/SC', 'DAILY', '/TN', $TaskName, '/TR', $runnerShort, '/ST', $At, '/RL', 'LIMITED')
    $proc = Start-Process -FilePath "schtasks.exe" -ArgumentList $args -Wait -NoNewWindow -PassThru

    if ($proc.ExitCode -ne 0) {
        throw "schtasks fallback failed with exit code $($proc.ExitCode)"
    }

    Write-Host "OK: task '$TaskName' registered at $At via schtasks fallback" -ForegroundColor Green
    Write-Host "Run now: schtasks /Run /TN $TaskName"
}

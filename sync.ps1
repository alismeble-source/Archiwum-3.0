param(
    [string]$Message = "sync: code and docs update",
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$inside = git rev-parse --is-inside-work-tree 2>$null
if ($LASTEXITCODE -ne 0 -or $inside -ne "true") {
    throw "Current folder is not a git repository: $repoRoot"
}

$allowedPaths = @(
    ".gitignore",
    ".github",
    ".vscode",
    "AGENTS.md",
    "99_SYSTEM/_SCRIPTS",
    "docs",
    "src",
    "scripts",
    "config",
    "tests",
    "tools",
    "sync.ps1"
)

Write-Host "[sync] Staging safe paths..." -ForegroundColor Cyan
git add --all -- $allowedPaths

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "[sync] Nothing to commit in safe paths." -ForegroundColor Yellow
    exit 0
}

Write-Host "[sync] Commit..." -ForegroundColor Cyan
git commit -m $Message

if ($NoPush) {
    Write-Host "[sync] Commit created. Push skipped (-NoPush)." -ForegroundColor Green
    exit 0
}

Write-Host "[sync] Rebase + push..." -ForegroundColor Cyan
git pull --rebase origin main
git push origin main

Write-Host "[sync] Done." -ForegroundColor Green

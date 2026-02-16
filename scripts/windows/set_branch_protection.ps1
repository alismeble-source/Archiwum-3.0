[CmdletBinding()]
param(
    [string]$Owner = "alismeble-source",
    [string]$Repo = "Archiwum-3.0",
    [string]$Branch = "main",
    [string]$RequiredStatusCheck = "smoke"
)

$ErrorActionPreference = "Stop"

if (-not $env:GITHUB_TOKEN) {
    throw "GITHUB_TOKEN is not set. Create a PAT with repo/admin:repo_hook scope and set it in environment."
}

$uri = "https://api.github.com/repos/$Owner/$Repo/branches/$Branch/protection"
$headers = @{
    Authorization = "Bearer $($env:GITHUB_TOKEN)"
    Accept        = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

$body = @{
    required_status_checks = @{
        strict   = $true
        contexts = @($RequiredStatusCheck)
    }
    enforce_admins = $false
    required_pull_request_reviews = @{
        dismiss_stale_reviews = $false
        require_code_owner_reviews = $false
        required_approving_review_count = 0
    }
    restrictions = $null
    required_linear_history = $true
    allow_force_pushes = $false
    allow_deletions = $false
    block_creations = $false
    required_conversation_resolution = $true
    lock_branch = $false
    allow_fork_syncing = $false
}

Write-Host "Applying protection to ${Owner}/${Repo}:${Branch} ..." -ForegroundColor Cyan

$json = $body | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -Body $json -ContentType "application/json" | Out-Null

Write-Host "OK: branch protection applied for '$Branch'." -ForegroundColor Green
Write-Host "Required status check: $RequiredStatusCheck"

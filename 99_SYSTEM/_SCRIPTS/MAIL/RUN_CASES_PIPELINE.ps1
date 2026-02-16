param(
  [string]$Root = "C:\Users\alimg\Dropbox\Archiwum 3.0",
  [int]$Max = 200,
  [string]$Query = "label:SOURCE/ICLOUD has:attachment"
)

$ErrorActionPreference = "Stop"

$pull   = Join-Path $Root "99_SYSTEM\_SCRIPTS\MAIL\gmail_pull_icloud_attachments.py"
$router = Join-Path $Root "99_SYSTEM\_SCRIPTS\MAIL\cases_router.py"

Write-Host "=== PIPELINE START ==="
Write-Host "Root:   $Root"
Write-Host "Max:    $Max"
Write-Host "Query:  $Query"
Write-Host "PULL:   $pull"
Write-Host "ROUTER: $router"

# sanity checks
if (-not (Test-Path $pull))   { throw "PULL script not found: $pull" }
if (-not (Test-Path $router)) { throw "ROUTER script not found: $router" }

# folders (safe)
$dirs = @(
  (Join-Path $Root "CASES\_INBOX"),
  (Join-Path $Root "CASES\_REVIEW"),
  (Join-Path $Root "CASES\01_KLIENTS\_INBOX"),
  (Join-Path $Root "CASES\02_FIRMA\_INBOX"),
  (Join-Path $Root "CASES\03_CAR\_INBOX")
)
$dirs | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

Write-Host "RUNNING: py `"$pull`" --query `"$Query`" --max $Max"
py "$pull" --query "$Query" --max $Max

Write-Host "RUNNING: py `"$router`""
py "$router"

Write-Host "=== COUNTS ==="
"CASES\_INBOX:      " + (Get-ChildItem (Join-Path $Root "CASES\_INBOX") -File -ErrorAction SilentlyContinue | Measure-Object).Count
"01_KLIENTS\_INBOX: " + (Get-ChildItem (Join-Path $Root "CASES\01_KLIENTS\_INBOX") -File -ErrorAction SilentlyContinue | Measure-Object).Count
"02_FIRMA\_INBOX:   " + (Get-ChildItem (Join-Path $Root "CASES\02_FIRMA\_INBOX") -File -ErrorAction SilentlyContinue | Measure-Object).Count
"03_CAR\_INBOX:     " + (Get-ChildItem (Join-Path $Root "CASES\03_CAR\_INBOX") -File -ErrorAction SilentlyContinue | Measure-Object).Count
"CASES\_REVIEW:     " + (Get-ChildItem (Join-Path $Root "CASES\_REVIEW") -File -ErrorAction SilentlyContinue | Measure-Object).Count

Write-Host "=== PIPELINE DONE ==="

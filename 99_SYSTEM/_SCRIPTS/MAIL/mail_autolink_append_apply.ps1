param(
  [string]$ArchiwumRoot = "C:\Users\alimg\Dropbox\Archiwum 3.0",
  [string]$IndexPath    = "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_INDEX\clients_index.json",
  [string]$DryRunCsv     = ""
)

$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$p){ if(-not (Test-Path -LiteralPath $p)){ New-Item -ItemType Directory -Path $p | Out-Null } }
function Read-Utf8([string]$path){ [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8) }
function Write-Utf8([string]$path,[string]$text){ [System.IO.File]::WriteAllText($path,$text,[System.Text.Encoding]::UTF8) }

if([string]::IsNullOrWhiteSpace($DryRunCsv)){
  throw "DryRunCsv is required. Pass -DryRunCsv <path to MAIL_APPEND_DRYRUN_*.csv>"
}
if(-not (Test-Path -LiteralPath $DryRunCsv)){ throw "DryRunCsv not found: $DryRunCsv" }
if(-not (Test-Path -LiteralPath $IndexPath)){ throw "IndexPath not found: $IndexPath" }

$index = (Read-Utf8 $IndexPath) | ConvertFrom-Json

# Ensure email_map exists
if(-not $index.email_map){
  $index | Add-Member -MemberType NoteProperty -Name email_map -Value ([pscustomobject]@{})
}

# Convert email_map to hashtable for safe update
$emailMap = @{}
foreach($p in $index.email_map.PSObject.Properties){
  $emailMap[$p.Name.ToLower()] = [string]$p.Value
}

$rows = Import-Csv -LiteralPath $DryRunCsv
$toAdd = $rows | Where-Object { $_.action -eq "PROPOSE_ADD" -and $_.email }

$added = 0
foreach($r in $toAdd){
  $e = $r.email.ToLower()
  if(-not $emailMap.ContainsKey($e)){
    $emailMap[$e] = $r.proposed_case_rel
    $added++
  }
}

# Rebuild email_map object
$newEmailMapObj = New-Object PSObject
foreach($k in ($emailMap.Keys | Sort-Object)){
  $newEmailMapObj | Add-Member -MemberType NoteProperty -Name $k -Value $emailMap[$k]
}
$index.email_map = $newEmailMapObj
$index.updated = (Get-Date).ToString("s")

# Backup index
$bak = $IndexPath + ".bak_" + (Get-Date -Format "yyyyMMdd_HHmmss")
Copy-Item -LiteralPath $IndexPath -Destination $bak -Force

# Write updated index
$json = $index | ConvertTo-Json -Depth 8
Write-Utf8 $IndexPath $json

Write-Host "DONE. UPDATED INDEX: $IndexPath"
Write-Host "BACKUP: $bak"
Write-Host "ADDED EMAILS: $added"

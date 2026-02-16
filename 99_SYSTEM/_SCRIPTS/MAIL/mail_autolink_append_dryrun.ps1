param(
  [string]$ArchiwumRoot = "C:\Users\alimg\Dropbox\Archiwum 3.0",
  [string]$MailRaw      = "C:\Users\alimg\Dropbox\Archiwum 3.0\00_INBOX\MAIL_RAW",
  [string]$IndexPath    = "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_INDEX\clients_index.json"
)

$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$p){ if(-not (Test-Path -LiteralPath $p)){ New-Item -ItemType Directory -Path $p | Out-Null } }
function Read-Utf8([string]$path){ [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8) }
function Write-Utf8([string]$path,[string]$text){ [System.IO.File]::WriteAllText($path,$text,[System.Text.Encoding]::UTF8) }
function Nz($v){ if($null -eq $v){""} else {[string]$v} }

function Extract-Email([string]$s){
  if([string]::IsNullOrWhiteSpace($s)){ return "" }
  $m=[regex]::Match($s,"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}","IgnoreCase")
  if($m.Success){ return $m.Value.ToLower() }
  return ""
}

function Extract-Domain([string]$e){
  if($e -and $e.Contains("@")){ return $e.Split("@")[1].ToLower() }
  return ""
}

function SafeCaseToken([string]$s,[int]$maxLen){
  if([string]::IsNullOrWhiteSpace($s)){ return "unknown" }
  $x = $s.ToLower()
  $x = [regex]::Replace($x, "[^a-z0-9ąćęłńóśżź]+", "_").Trim("_")
  if($x.Length -gt $maxLen){ $x = $x.Substring(0,$maxLen) }
  if([string]::IsNullOrWhiteSpace($x)){ return "unknown" }
  return $x
}

# --- Load INDEX ---
if(-not (Test-Path -LiteralPath $IndexPath)){ throw "IndexPath not found: $IndexPath" }
$index = (Read-Utf8 $IndexPath) | ConvertFrom-Json

# build emailMap hash for quick check
$emailMap = @{}
if($index.email_map){
  foreach($p in $index.email_map.PSObject.Properties){
    $emailMap[$p.Name.ToLower()] = [string]$p.Value
  }
}

# build domain rules set (domains that are "known non-client")
$domainRules = @()
if($index.domain_rules){ $domainRules = @($index.domain_rules) }

$blockedDomains = New-Object System.Collections.Generic.HashSet[string]
foreach($r in $domainRules){
  if($r -and $r.PSObject.Properties["domain"]){
    $null = $blockedDomains.Add(([string]$r.domain).ToLower())
  }
}

$defaultsNewBase = "02_KLIENCI\_NEW_FROM_MAIL"
if($index.defaults -and $index.defaults.new_client_case_base){
  $defaultsNewBase = [string]$index.defaults.new_client_case_base
}

# --- Logs ---
$logDir = Join-Path $ArchiwumRoot "00_INBOX\_ROUTER_LOGS"
Ensure-Dir $logDir
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$log = Join-Path $logDir ("MAIL_APPEND_DRYRUN_" + $ts + ".csv")

# --- Collect candidates ---
$rows = @()

if(-not (Test-Path -LiteralPath $MailRaw)){ throw "MailRaw not found: $MailRaw" }

Get-ChildItem -LiteralPath $MailRaw -Recurse -Filter "meta.json" | ForEach-Object {
  $meta = (Read-Utf8 $_.FullName) | ConvertFrom-Json

  $from = Nz $meta.headers.from
  $subj = Nz $meta.headers.subject
  $snippet = Nz $meta.snippet

  $email = Extract-Email ($from + " " + $subj)
  $dom = Extract-Domain $email

  # filters: must look like client mail
  $subjL = $subj.ToLower()
  $isWycena = ($subjL -match "\bwycena\b")
  $isUmowa  = ($subjL -match "\bumowa\b")
  $okTopic  = ($isWycena -or $isUmowa)

  # exclude obvious system addresses
  $isNoReply = ($email -match "no-?reply|noreply|donotreply")

  $reason = @()
  if(-not $email){ $reason += "NO_EMAIL" }
  if(-not $okTopic){ $reason += "TOPIC_NOT_WYCENA_UMOWA" }
  if($isNoReply){ $reason += "NO_REPLY" }
  if($dom -and $blockedDomains.Contains($dom)){ $reason += "DOMAIN_IS_RULED_NONCLIENT" }
  if($email -and $emailMap.ContainsKey($email)){ $reason += "ALREADY_IN_EMAIL_MAP" }

  $action = "SKIP"
  $proposedCase = ""
  $confidence = 0.0

  if($email -and $okTopic -and (-not $isNoReply) -and (-not ($dom -and $blockedDomains.Contains($dom))) -and (-not $emailMap.ContainsKey($email))){
    $action = "PROPOSE_ADD"
    # deterministic proposal: base\email_at_domain
    $proposedCase = ($defaultsNewBase + "\" + ($email -replace "@","_at_"))
    $confidence = 0.70
  }

  $rows += [pscustomobject]@{
    action = $action
    email = $email
    domain = $dom
    subject = $subj
    proposed_case_rel = $proposedCase
    confidence = $confidence
    gmail_id = (Nz $meta.gmail_id)
    saved_path = (Nz $meta.saved_path)
    skip_reason = ($reason -join ";")
  }
}

# Keep only PROPOSE_ADD rows in top part (but write all for audit)
$rows | Export-Csv -LiteralPath $log -NoTypeInformation -Encoding UTF8
Write-Host "DONE. DRYRUN LOG: $log"
Write-Host ("ROWS: " + $rows.Count)
Write-Host ("EMAIL_MAP_EXISTING: " + $emailMap.Count)
Write-Host ("BLOCKED_DOMAINS_FROM_RULES: " + $blockedDomains.Count)

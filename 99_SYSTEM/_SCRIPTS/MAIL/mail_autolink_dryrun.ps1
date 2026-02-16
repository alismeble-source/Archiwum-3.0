param(
  [string]$ArchiwumRoot = "C:\Users\alimg\Dropbox\Archiwum 3.0",
  [string]$MailRaw      = "C:\Users\alimg\Dropbox\Archiwum 3.0\00_INBOX\MAIL_RAW",
  [string]$IndexPath    = "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_INDEX\clients_index.json"
)

$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$p){
  if(-not (Test-Path -LiteralPath $p)){
    New-Item -ItemType Directory -Path $p | Out-Null
  }
}

function Read-Utf8([string]$path){
  return [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
}

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

# LOAD INDEX (no -Raw)
if(-not (Test-Path -LiteralPath $IndexPath)){
  throw "IndexPath not found: $IndexPath"
}
$index = (Read-Utf8 $IndexPath) | ConvertFrom-Json

$emailMap = @{}
if($index.email_map){
  foreach($p in $index.email_map.PSObject.Properties){
    $emailMap[$p.Name.ToLower()] = [string]$p.Value
  }
}
$domainRules = @()
if($index.domain_rules){ $domainRules = @($index.domain_rules) }

# LOG
$logDir = Join-Path $ArchiwumRoot "00_INBOX\_ROUTER_LOGS"
Ensure-Dir $logDir
$log = Join-Path $logDir ("MAIL_LINK_" + (Get-Date -Format yyyyMMdd_HHmmss) + ".csv")
$rows=@()

if(-not (Test-Path -LiteralPath $MailRaw)){
  throw "MailRaw not found: $MailRaw"
}

Get-ChildItem -LiteralPath $MailRaw -Recurse -Filter "meta.json" | ForEach-Object {

  $meta = (Read-Utf8 $_.FullName) | ConvertFrom-Json

  $from = Nz $meta.headers.from
  $subj = Nz $meta.headers.subject

  $email = Extract-Email ($from + " " + $subj)

  $status="NEW"; $match=""; $conf=0.0

  if($email -and $emailMap.ContainsKey($email)){
    $status="MATCH_INDEX_EMAIL"
    $match=$emailMap[$email]
    $conf=1.0
  }
  else{
    $dom = Extract-Domain $email
    foreach($r in $domainRules){
      $rd = ""
      if($r -and $r.PSObject.Properties["domain"]){ $rd = ([string]$r.domain).ToLower() }
      if($dom -and $rd -and ($dom -eq $rd -or $dom.EndsWith("." + $rd))){
        $status="MATCH_INDEX_DOMAIN"
        $match=[string]$r.case

        $conf = 0.70
        if($r.PSObject.Properties["confidence"]){ $conf=[double]$r.confidence }

        break
      }
    }
  }

  $rows += [pscustomobject]@{
    status     = $status
    gmail_id   = (Nz $meta.gmail_id)
    email      = $email
    match      = $match
    confidence = $conf
    saved_path = (Nz $meta.saved_path)
  }
}

$rows | Export-Csv -LiteralPath $log -NoTypeInformation -Encoding UTF8
Write-Host "DONE. LOG: $log"
Write-Host ("ROWS: " + $rows.Count)
Write-Host ("INDEX EMAIL MAP: " + $emailMap.Count)
Write-Host ("INDEX DOMAIN RULES: " + $domainRules.Count)

param(
  [string]$ArchiwumRoot = "C:\Users\alimg\Dropbox\Archiwum 3.0",
  [string]$MailRaw      = "C:\Users\alimg\Dropbox\Archiwum 3.0\00_INBOX\MAIL_RAW",
  [switch]$CopyOnly     = $true
)

$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$p){
  if(-not (Test-Path -LiteralPath $p)){
    New-Item -ItemType Directory -Path $p | Out-Null
  }
}

function Nz([object]$v){
  if($null -eq $v){ return "" }
  return [string]$v
}

function Get-Header([object]$meta, [string]$name){
  if($meta -and $meta.headers -and $meta.headers.PSObject.Properties[$name]){
    return [string]$meta.headers.$name
  }
  return ""
}

function Classify-Mail([object]$meta){
  $from = (Get-Header $meta "from").ToLower()
  $subj = (Get-Header $meta "subject").ToLower()
  $snippet = (Nz $meta.snippet).ToLower()
  $text = "$from $subj $snippet"

  if($text -match "faktura|invoice|fs-|fv-|paragon"){ return "FIN_FAKTURA" }
  if($text -match "wycena|oferta|quotation"){ return "KLIENT_WYCENA" }
  if($text -match "umowa|contract|zlecenie"){ return "KLIENT_UMOWA" }
  if($text -match "meble\.pl|kronospan|egger|blum|zamówienie|zamowienie"){ return "DOSTAWCA_ZAMOWIENIE" }
  if($text -match "allegro|inpost|dpd|gls|dhl|paczka|przesyłka|przesylka"){ return "LOGISTYKA" }
  if($text -match "zus|pue|urząd|urzad|skarb|ksef|vat|pit|cit"){ return "URZAD" }

  return "INNE"
}

function Suggest-Target([string]$type){
  switch ($type) {
    "FIN_FAKTURA"         { return "03_FINANSE\01_FAKTURY" }
    "URZAD"               { return "04_DOKUMENTY\URZEDY" }
    "DOSTAWCA_ZAMOWIENIE" { return "01_FIRMA\DOSTAWCY" }
    "LOGISTYKA"           { return "01_FIRMA\LOGISTYKA" }
    # Клиентские кейсы НЕ раскидываем автоматически — только в review
    "KLIENT_WYCENA"       { return "00_INBOX\_TO_REVIEW\KLIENT_WYCENA" }
    "KLIENT_UMOWA"        { return "00_INBOX\_TO_REVIEW\KLIENT_UMOWA" }
    default               { return "00_INBOX\_TO_REVIEW\INNE" }
  }
}

function SafeName([string]$s, [int]$maxLen){
  if([string]::IsNullOrWhiteSpace($s)){ return "empty" }
  $x = $s.Trim()
  $x = [regex]::Replace($x, "\s+", " ")
  $x = [regex]::Replace($x, '[<>:"/\\|?*\x00-\x1F]', "_")
  $x = $x.Replace("..",".").Trim(" ._")
  if($x.Length -gt $maxLen){ $x = $x.Substring(0,$maxLen) }
  if([string]::IsNullOrWhiteSpace($x)){ return "empty" }
  return $x
}

# --- LOGS ---
$logDir = Join-Path $ArchiwumRoot "00_INBOX\_ROUTER_LOGS"
Ensure-Dir $logDir
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDir ("MAIL_COPY_" + $ts + ".csv")

$rows = @()

if(-not (Test-Path -LiteralPath $MailRaw)){
  throw "MailRaw path not found: $MailRaw"
}

# --- DEDUPE STATE ---
$stateDir = Join-Path $ArchiwumRoot "00_INBOX\MAIL_RAW\_STATE"
Ensure-Dir $stateDir
$copiedDb = Join-Path $stateDir "copied_ids.txt"
if(-not (Test-Path -LiteralPath $copiedDb)){ "" | Set-Content -Encoding UTF8 -LiteralPath $copiedDb }

$copied = New-Object System.Collections.Generic.HashSet[string]
Get-Content -LiteralPath $copiedDb -Encoding UTF8 | ForEach-Object { if($_){ [void]$copied.Add($_.Trim()) } }

# --- PROCESS ---
$metaFiles = Get-ChildItem -LiteralPath $MailRaw -Recurse -Force -Filter "meta.json"

foreach($mf in $metaFiles){
  $meta = $null
  try{
    $meta = Get-Content -LiteralPath $mf.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  } catch {
    $rows += [pscustomobject]@{
      status="ERROR_META_JSON"
      type=""
      target=""
      action=""
      gmail_id=""
      saved_path=$mf.DirectoryName
      note=$_.Exception.Message
    }
    continue
  }

  $gmailId = Nz $meta.gmail_id
  if([string]::IsNullOrWhiteSpace($gmailId)){
    $rows += [pscustomobject]@{
      status="ERROR_NO_GMAIL_ID"
      type=""
      target=""
      action=""
      gmail_id=""
      saved_path=(Nz $meta.saved_path)
      note="meta.gmail_id missing"
    }
    continue
  }

  if($copied.Contains($gmailId)){
    $rows += [pscustomobject]@{
      status="SKIP_ALREADY_COPIED"
      type=(Classify-Mail $meta)
      target=""
      action="SKIP"
      gmail_id=$gmailId
      saved_path=(Nz $meta.saved_path)
      note=""
    }
    continue
  }

  $type = Classify-Mail $meta
  $targetRel = Suggest-Target $type
  $targetBase = Join-Path $ArchiwumRoot $targetRel

  # Build destination path
  $dt = Nz $meta.local_datetime
  $y = "unknown"; $mo="00"; $d="00"
  if($dt.Length -ge 10){
    $y  = $dt.Substring(0,4)
    $mo = $dt.Substring(5,2)
    $d  = $dt.Substring(8,2)
  }

  $from = SafeName (Get-Header $meta "from") 40
  $subj = SafeName (Get-Header $meta "subject") 60
  $short = $gmailId
  if($short.Length -gt 10){ $short = $short.Substring(0,10) }

  $destDir = Join-Path $targetBase ("MAIL\" + $y + "\" + $mo + "\" + $d + "\" + $from + "__" + $subj + "__" + $short)
  $destAtt = Join-Path $destDir "attachments"

  # Source dir (folder of meta.json)
  $srcDir = $mf.DirectoryName
  $srcEml = Join-Path $srcDir "message.eml"
  $srcBody = Join-Path $srcDir "body.txt"
  $srcMeta = Join-Path $srcDir "meta.json"
  $srcAttDir = Join-Path $srcDir "attachments"

  # Copy
  try{
    Ensure-Dir $destDir
    Ensure-Dir $destAtt

    if(Test-Path -LiteralPath $srcEml){ Copy-Item -LiteralPath $srcEml -Destination (Join-Path $destDir "message.eml") -Force }
    if(Test-Path -LiteralPath $srcBody){ Copy-Item -LiteralPath $srcBody -Destination (Join-Path $destDir "body.txt") -Force }
    if(Test-Path -LiteralPath $srcMeta){ Copy-Item -LiteralPath $srcMeta -Destination (Join-Path $destDir "meta.json") -Force }

    if(Test-Path -LiteralPath $srcAttDir){
      Get-ChildItem -LiteralPath $srcAttDir -File -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $destAtt $_.Name) -Force
      }
    }

    # Mark copied (append + update hashset)
    Add-Content -Encoding UTF8 -LiteralPath $copiedDb -Value $gmailId
    [void]$copied.Add($gmailId)

    $rows += [pscustomobject]@{
      status="OK"
      type=$type
      target=$targetRel
      action="COPY"
      gmail_id=$gmailId
      saved_path=(Nz $meta.saved_path)
      dest_path=$destDir
      note=""
    }
  } catch {
    $rows += [pscustomobject]@{
      status="ERROR_COPY"
      type=$type
      target=$targetRel
      action="COPY_FAIL"
      gmail_id=$gmailId
      saved_path=(Nz $meta.saved_path)
      dest_path=$destDir
      note=$_.Exception.Message
    }
  }
}

$rows | Export-Csv -LiteralPath $logPath -NoTypeInformation -Encoding UTF8
Write-Host "DONE. LOG: $logPath"
Write-Host ("META FILES: " + $metaFiles.Count)
Write-Host ("COPIED_DB: " + $copiedDb)

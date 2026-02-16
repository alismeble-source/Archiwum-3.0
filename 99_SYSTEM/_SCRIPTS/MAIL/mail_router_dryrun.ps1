param(
  [string]$ArchiwumRoot = "C:\Users\alimg\Dropbox\Archiwum 3.0",
  [string]$MailRaw      = "C:\Users\alimg\Dropbox\Archiwum 3.0\00_INBOX\MAIL_RAW"
)

$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$p){
  if(-not (Test-Path -LiteralPath $p)){
    New-Item -ItemType Directory -Path $p | Out-Null
  }
}

function Get-Header([object]$meta, [string]$name){
  if($meta -and $meta.headers -and $meta.headers.PSObject.Properties[$name]){
    return [string]$meta.headers.$name
  }
  return ""
}

function Nz([object]$v){
  if($null -eq $v){ return "" }
  return [string]$v
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
    default               { return "00_INBOX\_TO_REVIEW" }
  }
}

$logDir = Join-Path $ArchiwumRoot "00_INBOX\_ROUTER_LOGS"
Ensure-Dir $logDir

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logDir ("MAIL_ROUTER_" + $ts + ".csv")

$rows = @()

if(-not (Test-Path -LiteralPath $MailRaw)){
  throw "MailRaw path not found: $MailRaw"
}

$metaFiles = Get-ChildItem -LiteralPath $MailRaw -Recurse -Force -Filter "meta.json"

foreach($mf in $metaFiles){
  try{
    $meta = Get-Content -LiteralPath $mf.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
  } catch {
    $rows += [pscustomobject]@{
      status="ERROR_META_JSON"
      type=""
      target=""
      from=""
      subject=""
      date=""
      saved_path=$mf.DirectoryName
      note=$_.Exception.Message
    }
    continue
  }

  $type = Classify-Mail $meta
  $target = Suggest-Target $type

  $rows += [pscustomobject]@{
    status="OK"
    type=$type
    target=$target
    from=(Get-Header $meta "from")
    subject=(Get-Header $meta "subject")
    date=(Nz $meta.local_datetime)
    saved_path=(Nz $meta.saved_path)
    gmail_id=(Nz $meta.gmail_id)
  }
}

$rows | Export-Csv -LiteralPath $logPath -NoTypeInformation -Encoding UTF8
Write-Host "DONE. LOG: $logPath"
Write-Host ("META FILES: " + $metaFiles.Count)

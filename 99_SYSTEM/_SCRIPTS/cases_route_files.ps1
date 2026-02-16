param(
  [string]$Root = "C:\Users\alimg\Dropbox\Archiwum 3.0",
  [switch]$DryRun
)

$src = Join-Path $Root "CASES\_INBOX\FILES"
$cases = Join-Path $Root "CASES"

$destClients = Join-Path $cases "01_CLIENTS\_INBOX"
$destFirma   = Join-Path $cases "02_FIRMA\_INBOX"
$destCar     = Join-Path $cases "03_CAR\_INBOX"
$destReview  = Join-Path $cases "_REVIEW"

# Безопасно создаём папки
@($src,$destClients,$destFirma,$destCar,$destReview) | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

# Правила (простые слова/шаблоны). Не распознали -> REVIEW
$rules = @(
  @{ name="CAR";    dest=$destCar;    rx=@("bmw","e91","vin","oc","ac","szkoda","warsztat","vectra","hestia","polisa","dowod","rejestr") },
  @{ name="FIRMA";  dest=$destFirma;  rx=@("faktura","invoice","rachunek","paragon","ksef","kse-f","zus","pue","us ","vat","pit","cit","bank","mbank","pekao","revolut","umowa-zlecenie","skladk") },
  @{ name="CLIENT"; dest=$destClients;rx=@("wycena","projekt","kuchnia","szafa","garderoba","zamowien","zlecen","pomiar","oferta","klient","front","blum","egger","kronospan") }
)

# Анти-хаос: такие штуки не раскидываем автоматом — только REVIEW
$forceReview = @("certyfikat","certificate","dyplom","kurs","rzęsy","lashes","brow","laminac")

function Get-UniquePath($path){
  if(!(Test-Path $path)){ return $path }
  $dir = Split-Path $path -Parent
  $base = [System.IO.Path]::GetFileNameWithoutExtension($path)
  $ext  = [System.IO.Path]::GetExtension($path)
  for($i=1; $i -le 999; $i++){
    $p = Join-Path $dir ("{0}_DUP{1}{2}" -f $base, $i, $ext)
    if(!(Test-Path $p)){ return $p }
  }
  throw "Too many duplicates: $path"
}

$files = Get-ChildItem -Path $src -File -ErrorAction SilentlyContinue
if(!$files){ Write-Host "[ROUTE] No files in $src"; exit 0 }

$logDir = Join-Path $Root "00_INBOX\_ROUTER_LOGS"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$log = Join-Path $logDir ("CASES_ROUTE_{0}.csv" -f $ts)

"ts,action,rule,src,dst" | Out-File -Encoding UTF8 $log

foreach($f in $files){
  $name = ($f.Name + " " + $f.BaseName).ToLowerInvariant()

  $dest = $destReview
  $ruleName = "REVIEW"

  foreach($fr in $forceReview){
    if($name -like "*$fr*"){
      $dest = $destReview; $ruleName="FORCE_REVIEW"
      break
    }
  }

  if($ruleName -ne "FORCE_REVIEW"){
    foreach($r in $rules){
      foreach($pat in $r.rx){
        if($name -like "*$pat*"){
          $dest = $r.dest; $ruleName=$r.name
          break
        }
      }
      if($ruleName -ne "REVIEW"){ break }
    }
  }

  $target = Get-UniquePath (Join-Path $dest $f.Name)

  if($DryRun){
    Write-Host "[DRY] $($f.FullName)  ->  $target"
    "{0},DRY,{1},""{2}"",""{3}""" -f $ts,$ruleName,$f.FullName,$target | Add-Content -Encoding UTF8 $log
  } else {
    Move-Item -LiteralPath $f.FullName -Destination $target
    Write-Host "[MOVE] $($f.Name) -> $ruleName"
    "{0},MOVE,{1},""{2}"",""{3}""" -f $ts,$ruleName,$f.FullName,$target | Add-Content -Encoding UTF8 $log
  }
}

Write-Host "[DONE] Log: $log"


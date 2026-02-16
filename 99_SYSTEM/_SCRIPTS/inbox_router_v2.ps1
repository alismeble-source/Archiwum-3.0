# inbox_router_v2.ps1
# V2: files -> TYPE/CASE/ARCHIVE, subfolders -> DUMPS (date-stamped), with logs

$ROOT   = "C:\Users\alimg\Dropbox\Archiwum 3.0"
$INBOX  = Join-Path $ROOT "00_INBOX"
$CASES  = Join-Path $ROOT "CASES"
$ARCH   = Join-Path $ROOT "06_ARCHIWUM\_ARCHIVES"
$DUMPS  = Join-Path $ARCH "_INBOX_DUMPS"
$LOGS   = Join-Path $ROOT "99_SYSTEM\_LOGS"

New-Item -ItemType Directory -Path $INBOX,$CASES,$ARCH,$DUMPS,$LOGS -Force | Out-Null
$log = Join-Path $LOGS ("inbox_router_{0}.log" -f (Get-Date -Format "yyyyMMdd"))

function Log($m){ ("{0} | {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m) | Out-File -Append -Encoding UTF8 $log }

function Get-TypeFromText([string]$text) {
    $t = $text.ToLower()
    if ($t -match "vectra|internet|operator|umowa") { return "UMOWA_ROZWIAZANIE_ZMIANA_ADRESU" }
    if ($t -match "kara|nieustojk|penalt|1400")     { return "UMOWA_KARA_UMOWNA" }
    if ($t -match "odmow|nie uznaj|brak podstaw")   { return "OPERATOR_ODMOWA_UZNANIA_DOKUMENTU" }
    if ($t -match "wezwanie|windyk|zapłat")        { return "WEZWANIE_DO_ZAPLATY" }
    if ($t -match "zus|pue|składk")                 { return "ZUS_SKLADKI_TERMIN" }
    if ($t -match "zaleg|odsetk")                   { return "ZUS_ZALEGLOSC" }
    if ($t -match "oc|szkoda|hestia|pzu|warta")     { return "AUTO_OC_ODMOWA" }
    if ($t -match "rata|kredyt|cofidis|leasing")    { return "AUTO_KREDYT_RATA_SPOR" }
    if ($t -match "reklamac")                       { return "KLIENT_REKLAMACJA" }
    if ($t -match "zmian|zakres|dopłat|aneks")      { return "KLIENT_ZMIANA_ZAKRESU" }
    if ($t -match "wycen|ofert|zapytan")            { return "KLIENT_WYCENA_ZAPYTANIE" }
    return "UNCLASSIFIED"
}

function Ensure-Case([string]$type){
    $stamp = Get-Date -Format "yyyyMM"
    $id = "{0}__{1}" -f $type, $stamp
    $path = Join-Path $CASES $id
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    $type | Out-File -Encoding UTF8 (Join-Path $path "TYPE.txt")
    $status = Join-Path $path "STATUS.txt"
    if (!(Test-Path $status)) { "ACTIVE" | Out-File -Encoding UTF8 $status }
    return $path
}

function Is-Risk([string]$text){
    $t=$text.ToLower()
    return ($t -match "termin|7 dni|14 dni|ostatecz|przedsąd|windyk|komornik|sąd|kara|odsetk|zaleg")
}

# 1) MOVE SUBFOLDERS -> DUMPS
$subs = Get-ChildItem $INBOX -Directory -ErrorAction SilentlyContinue
if ($subs){
    $dumpDay = Join-Path $DUMPS (Get-Date -Format "yyyyMMdd")
    New-Item -ItemType Directory -Path $dumpDay -Force | Out-Null
    foreach($d in $subs){
        $dest = Join-Path $dumpDay $d.Name
        if (Test-Path $dest){
            $dest = Join-Path $dumpDay ("{0}__{1}" -f (Get-Date -Format "HHmmss"), $d.Name)
        }
        Move-Item $d.FullName $dest -Force
        Log "DUMP DIR: $($d.Name) -> $dest"
    }
}

# 2) PROCESS FILES IN ROOT
$files = Get-ChildItem $INBOX -File -ErrorAction SilentlyContinue
if (!$files){
    Log "INBOX empty or no files."
    Write-Host "INBOX processed."
    exit
}

foreach($f in $files){
    $type = Get-TypeFromText $f.Name
    $casePath = Ensure-Case $type

    if (Is-Risk $f.Name){
        "RISK" | Out-File -Encoding UTF8 (Join-Path $casePath "STATUS.txt")
    }

    $destDir = Join-Path $ARCH $type
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null

    $dest = Join-Path $destDir $f.Name
    if (Test-Path $dest){
        $dest = Join-Path $destDir ("{0}__{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss"), $f.Name)
    }

    Move-Item $f.FullName $dest -Force
    "{0} | {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm"), $dest |
        Out-File -Append -Encoding UTF8 (Join-Path $casePath "LINKS.txt")

    Log "FILE: $($f.Name) -> TYPE=$type -> $dest"
    Write-Host "OK:" $f.Name "->" $type
}

Write-Host "INBOX processed."

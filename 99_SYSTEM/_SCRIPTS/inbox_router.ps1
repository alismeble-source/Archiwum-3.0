# inbox_router.ps1
# INBOX -> TYPE -> CASE -> ARCHIVE

$ROOT   = "C:\Users\alimg\Dropbox\Archiwum 3.0"
$INBOX  = Join-Path $ROOT "00_INBOX"
$CASES  = Join-Path $ROOT "CASES"
$ARCH   = Join-Path $ROOT "06_ARCHIWUM\_ARCHIVES"

New-Item -ItemType Directory -Path $INBOX,$CASES,$ARCH -Force | Out-Null

function Get-TypeFromText([string]$text) {
    $t = $text.ToLower()
    if ($t -match "vectra|internet|operator|umowa") { return "UMOWA_ROZWIAZANIE_ZMIANA_ADRESU" }
    if ($t -match "kara|nieustojk|penalt|1400")     { return "UMOWA_KARA_UMOWNA" }
    if ($t -match "wezwanie|windyk|zapłat")        { return "WEZWANIE_DO_ZAPLATY" }
    if ($t -match "zus|pue|składk")                 { return "ZUS_SKLADKI_TERMIN" }
    if ($t -match "oc|szkoda|hestia|pzu")           { return "AUTO_OC_ODMOWA" }
    if ($t -match "reklamac")                       { return "KLIENT_REKLAMACJA" }
    if ($t -match "wycen|ofert|zapytan")            { return "KLIENT_WYCENA_ZAPYTANIE" }
    return "UNCLASSIFIED"
}

function Ensure-Case($type) {
    $stamp = Get-Date -Format "yyyyMM"
    $id = "$type`__$stamp"
    $path = Join-Path $CASES $id
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    "$type" | Out-File -Encoding UTF8 (Join-Path $path "TYPE.txt")
    if (!(Test-Path (Join-Path $path "STATUS.txt"))) {
        "ACTIVE" | Out-File -Encoding UTF8 (Join-Path $path "STATUS.txt")
    }
    return $path
}

Get-ChildItem $INBOX -File | ForEach-Object {
    $type = Get-TypeFromText $_.Name
    $casePath = Ensure-Case $type
    $destDir = Join-Path $ARCH $type
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    Move-Item $_.FullName (Join-Path $destDir $_.Name) -Force
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm') | $($_.Name)" |
        Out-File -Append -Encoding UTF8 (Join-Path $casePath "LINKS.txt")
    Write-Host "OK:" $_.Name "->" $type
}

Write-Host "INBOX processed."

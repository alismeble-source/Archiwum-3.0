# draft_builder_v43.ps1
# V4.3: versioned drafts + auto-extracted details from filenames/paths/LINKS

$ROOT  = "C:\Users\alimg\Dropbox\Archiwum 3.0"
$CASES = Join-Path $ROOT "CASES"

function Draft-ByType([string]$type){
    switch ($type) {
        "UMOWA_ROZWIAZANIE_ZMIANA_ADRESU" {
@"
Szanowni Państwo,

w nawiązaniu do Państwa odpowiedzi informuję, że rozwiązanie umowy nastąpiło z przyczyn niezależnych ode mnie, tj. zmiany miejsca zamieszkania, co zostało potwierdzone przekazanymi dokumentami.

Proszę o ponowne rozpatrzenie sprawy oraz wskazanie podstawy prawnej naliczenia kary umownej.

Z poważaniem
"@
        }
        "WEZWANIE_DO_ZAPLATY" {
@"
Szanowni Państwo,

potwierdzam otrzymanie wezwania do zapłaty. Jednocześnie informuję, że sprawa jest w toku wyjaśniania i proszę o wstrzymanie dalszych czynności do czasu jej rozpatrzenia.

Z poważaniem
"@
        }
        default {
@"
Szanowni Państwo,

potwierdzam otrzymanie pisma. Proszę o przesłanie pełnej podstawy prawnej oraz dokumentów, na których opierają Państwo swoje stanowisko.

Z poważaniem
"@
        }
    }
}

function Parse-Operator([string]$text){
    $t=$text.ToLower()
    if ($t -match "vectra") { return "VECTRA" }
    if ($t -match "zus|pue") { return "ZUS" }
    if ($t -match "hestia|pzu|warta|link4") { return "UBEZPIECZYCIEL" }
    if ($t -match "cofidis|leasing|bank") { return "FINANSOWANIE" }
    return "NIEZNANY"
}

function Parse-ContractNo([string]$text){
    # looks for long numeric tokens or markers like nr/umowa/contract
    $m = [regex]::Match($text, '(nr|umowa|contract)?\s*([0-9]{6,14})', 'IgnoreCase')
    if ($m.Success) { return $m.Groups[2].Value }
    return ""
}

function Parse-Dates([string[]]$lines){
    # try to catch YYYY-MM-DD or DD.MM.YYYY
    $dates=@()
    foreach($l in $lines){
        if ($l -match '20\d{2}[-\.]\d{2}[-\.]\d{2}') { $dates += $Matches[0] }
        if ($l -match '\d{2}\.\d{2}\.20\d{2}') { $dates += $Matches[0] }
    }
    return ($dates | Select-Object -Unique)
}

function Get-LastEvidence([string]$linksFile, [int]$maxItems = 5){
    if (!(Test-Path $linksFile)) { return @(), @() }
    $lines = Get-Content $linksFile -ErrorAction SilentlyContinue
    if (!$lines) { return @(), @() }

    $blocks=@(); $buf=New-Object System.Collections.Generic.List[string]
    foreach($ln in $lines){
        if ($ln.Trim() -eq "----"){ if($buf.Count){ $blocks+=,($buf.ToArray()); $buf.Clear() } }
        else{ $buf.Add($ln) }
    }
    if($buf.Count){ $blocks+=,($buf.ToArray()) }
    if(!$blocks.Count){ return @(), @() }

    $take=[Math]::Min($maxItems,$blocks.Count)
    $last=$blocks[($blocks.Count-$take)..($blocks.Count-1)]

    $out=@(); $flat=@()
    foreach($b in $last){
        $date=($b | Where-Object { $_ -like "DATE:*" } | Select-Object -First 1)
        $path=($b | Where-Object { $_ -like "PATH:*" } | Select-Object -First 1)
        if($date -or $path){
            $out+=("- {0} | {1}" -f ($date -replace 'DATE:\s*',''), ($path -replace 'PATH:\s*',''))
        }
        $flat += $b
    }
    return $out, $flat
}

Get-ChildItem $CASES -Directory | ForEach-Object {
    $casePath=$_.FullName
    $statusFile=Join-Path $casePath "STATUS.txt"
    $typeFile=Join-Path $casePath "TYPE.txt"
    $linksFile=Join-Path $casePath "LINKS.txt"

    if(!(Test-Path $statusFile) -or !(Test-Path $typeFile)){ return }
    $status=(Get-Content $statusFile | Select-Object -First 1).Trim()
    if($status -ne "RISK"){ return }

    $type=(Get-Content $typeFile | Select-Object -First 1).Trim()

    $evidence,$flat = Get-LastEvidence $linksFile 5
    $flatText = ($flat -join " ")
    $op = Parse-Operator ($_.Name + " " + $flatText)
    $cn = Parse-ContractNo ($_.Name + " " + $flatText)
    $dates = Parse-Dates $flat

    $draft = Draft-ByType $type
    $stamp = Get-Date -Format "yyyyMMdd_HHmm"
    $draftFile = Join-Path $casePath ("DRAFT_{0}.txt" -f $stamp)

    @(
      "CASE:   $($_.Name)"
      "TYPE:   $type"
      "STATUS: $status"
      "DATE:   $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
      "----"
      "DANE WYCIĄGNIĘTE AUTOMATYCZNIE:"
      ("OPERATOR:    {0}" -f $op)
      ("NR UMOWY:    {0}" -f ($(if($cn){$cn}else{"(nie wykryto)"})))
      ("DATY:        {0}" -f ($(if($dates){$dates -join ', '}else{"(brak)"})))
      "----"
      $draft
      ""
      "Ostatnie dokumenty w sprawie (z archiwum):"
      $evidence
      ""
      "Uwagi (do uzupełnienia):"
      "- TODO: potwierdzić dane automatyczne"
      "- TODO: wskazać żądanie końcowe"
    ) | Out-File -Encoding UTF8 $draftFile
}

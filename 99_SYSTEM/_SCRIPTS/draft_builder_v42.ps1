# draft_builder_v42.ps1
# V4.2: versioned drafts for RISK cases + last evidence from LINKS.txt

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

function Get-LastEvidence([string]$linksFile, [int]$maxItems = 5){
    if (!(Test-Path $linksFile)) { return @("BRAK: LINKS.txt nie znaleziono.") }
    $lines = Get-Content $linksFile -ErrorAction SilentlyContinue
    if (!$lines) { return @("BRAK: LINKS.txt pusty.") }

    $blocks = @(); $buf = New-Object System.Collections.Generic.List[string]
    foreach($ln in $lines){
        if ($ln.Trim() -eq "----") { if ($buf.Count){ $blocks += ,($buf.ToArray()); $buf.Clear() } }
        else { $buf.Add($ln) }
    }
    if ($buf.Count){ $blocks += ,($buf.ToArray()) }
    if (!$blocks.Count){ return @("BRAK: brak bloków w LINKS.txt.") }

    $take = [Math]::Min($maxItems, $blocks.Count)
    $last = $blocks[($blocks.Count - $take)..($blocks.Count - 1)]

    $out = @()
    foreach($b in $last){
        $date = ($b | Where-Object { $_ -like "DATE:*" } | Select-Object -First 1)
        $path = ($b | Where-Object { $_ -like "PATH:*" } | Select-Object -First 1)
        if (!$date){ $date = "DATE: (brak)" }
        if (!$path){ $path = "PATH: (brak)" }
        $out += ("- {0} | {1}" -f $date.Replace("DATE:","").Trim(), $path.Replace("PATH:","").Trim())
    }
    return $out
}

Get-ChildItem $CASES -Directory | ForEach-Object {
    $casePath   = $_.FullName
    $statusFile = Join-Path $casePath "STATUS.txt"
    $typeFile   = Join-Path $casePath "TYPE.txt"
    $linksFile  = Join-Path $casePath "LINKS.txt"

    if (!(Test-Path $statusFile) -or !(Test-Path $typeFile)) { return }
    $status = (Get-Content $statusFile | Select-Object -First 1).Trim()
    if ($status -ne "RISK") { return }

    $type  = (Get-Content $typeFile | Select-Object -First 1).Trim()
    $draft = Draft-ByType $type
    $evidence = Get-LastEvidence $linksFile 5

    $stamp = Get-Date -Format "yyyyMMdd_HHmm"
    $draftFile = Join-Path $casePath ("DRAFT_{0}.txt" -f $stamp)

    @(
      "CASE:   $($_.Name)"
      "TYPE:   $type"
      "STATUS: $status"
      "DATE:   $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
      "----"
      $draft
      ""
      "Ostatnie dokumenty w sprawie (z archiwum):"
      $evidence
      ""
      "Uwagi (do uzupełnienia):"
      "- TODO: numer umowy / konto klienta"
      "- TODO: daty wysłania/odbioru"
      "- TODO: oczekiwany finał"
    ) | Out-File -Encoding UTF8 $draftFile
}

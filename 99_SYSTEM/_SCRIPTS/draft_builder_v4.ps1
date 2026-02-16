# draft_builder_v4.ps1
# V4: build draft reply for CASE when STATUS=RISK

$ROOT  = "C:\Users\alimg\Dropbox\Archiwum 3.0"
$CASES = Join-Path $ROOT "CASES"

function Draft-ByType([string]$type){
    switch ($type) {
        "UMOWA_ROZWIAZANIE_ZMIANA_ADRESU" {
@"
Szanowni Państwo,

w nawiązaniu do Państwa odpowiedzi informuję, że rozwiązanie umowy nastąpiło z przyczyn niezależnych ode mnie, tj. zmiany miejsca zamieszkania, co zostało potwierdzone załączonymi dokumentami.

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

Get-ChildItem $CASES -Directory | ForEach-Object {
    $casePath = $_.FullName
    $statusFile = Join-Path $casePath "STATUS.txt"
    $typeFile   = Join-Path $casePath "TYPE.txt"
    $draftFile  = Join-Path $casePath "DRAFT_REPLY.txt"

    if (!(Test-Path $statusFile) -or !(Test-Path $typeFile)) { return }
    $status = (Get-Content $statusFile | Select-Object -First 1).Trim()
    if ($status -ne "RISK") { return }
    if (Test-Path $draftFile) { return } # do not overwrite

    $type = (Get-Content $typeFile | Select-Object -First 1).Trim()
    $draft = Draft-ByType $type

    @(
      "CASE:   $($_.Name)"
      "TYPE:   $type"
      "STATUS: $status"
      "DATE:   $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
      "----"
      $draft
    ) | Out-File -Encoding UTF8 $draftFile
}

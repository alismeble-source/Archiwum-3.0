$ROOT  = "$env:USERPROFILE\Dropbox\Archiwum 3.0"
$INBOX = Join-Path $ROOT "00_INBOX"

$rules = @(
    @{ dst="02_KLIENCI\_AUTO"; kw=@("kuchnia","salon","sypialnia","zabud","mebl","projekt","rysun","wizual") },
    @{ dst="03_FINANSE\_AUTO"; kw=@("faktura","invoice","vat","zus","pit","jpk","paragon","koszt") },
    @{ dst="04_DOKUMENTY\_AUTO"; kw=@("umowa","wniosek","pobyt","sad","orzec","decyzja","gov","urzad") },
    @{ dst="05_PROJEKTY\_AUTO"; kw=@("bmw","auto","dwg","cad","konfigurator") }
)

foreach ($r in $rules) {
    New-Item -ItemType Directory -Path (Join-Path $ROOT $r.dst) -Force | Out-Null
}

Get-ChildItem -Path $INBOX -Recurse -File | ForEach-Object {
    $name = $_.Name.ToLower()
    foreach ($r in $rules) {
        if ($r.kw | Where-Object { $name -like "*$_*" }) {
            Move-Item $_.FullName -Destination (Join-Path $ROOT $r.dst) -Force
            break
        }
    }
}

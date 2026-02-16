# pdf_inspect_v5.ps1
# V5: inspect PDF text (no OCR) and enrich draft with facts

$ROOT  = "C:\Users\alimg\Dropbox\Archiwum 3.0"
$CASES = Join-Path $ROOT "CASES"
$POPPLER = "C:\Tools\poppler\Library\bin\pdftotext.exe"

if (!(Test-Path $POPPLER)) {
    Write-Host "pdftotext not found:" $POPPLER
    exit
}

function Parse-Operator([string]$t){
    $t=$t.ToLower()
    if ($t -match "vectra") { return "VECTRA" }
    if ($t -match "zus|zakład ubezpieczeń społecznych") { return "ZUS" }
    if ($t -match "pzu|hestia|warta|link4") { return "UBEZPIECZYCIEL" }
    if ($t -match "cofidis|bank|leasing") { return "FINANSOWANIE" }
    return ""
}

function Parse-ContractNo([string]$t){
    $m=[regex]::Match($t,'(nr umowy|umowa nr|contract)\s*[:\-]?\s*([0-9]{6,14})','IgnoreCase')
    if($m.Success){ return $m.Groups[2].Value }
    return ""
}

function Parse-Dates([string]$t){
    $dates=@()
    foreach($m in [regex]::Matches($t,'20\d{2}[-\.]\d{2}[-\.]\d{2}')){ $dates+=$m.Value }
    foreach($m in [regex]::Matches($t,'\d{2}\.\d{2}\.20\d{2}')){ $dates+=$m.Value }
    return ($dates | Select-Object -Unique)
}

Get-ChildItem $CASES -Directory | ForEach-Object {
    $casePath=$_.FullName
    $draft = Get-ChildItem $casePath -Filter "DRAFT_*.txt" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (!$draft) { return }

    $pdfs = Get-ChildItem $casePath -Recurse -Filter "*.pdf" -ErrorAction SilentlyContinue
    if (!$pdfs) { return }

    foreach($pdf in $pdfs){
        $tmp = [System.IO.Path]::GetTempFileName()
        & $POPPLER $pdf.FullName $tmp | Out-Null
        $text = Get-Content $tmp -Raw -ErrorAction SilentlyContinue
        Remove-Item $tmp -Force

        if (!$text -or $text.Length -lt 50) { continue }

        $op = Parse-Operator $text
        $cn = Parse-ContractNo $text
        $dt = Parse-Dates $text

        Add-Content $draft.FullName ""
        Add-Content $draft.FullName "----"
        Add-Content $draft.FullName "DANE Z PDF (ŹRÓDŁO: PDF_CONTENT)"
        if($op){ Add-Content $draft.FullName "OPERATOR: $op" }
        if($cn){ Add-Content $draft.FullName "NR UMOWY: $cn" }
        if($dt){ Add-Content $draft.FullName ("DATY: " + ($dt -join ", ")) }
        Add-Content $draft.FullName ("PDF: " + $pdf.FullName)
    }
}

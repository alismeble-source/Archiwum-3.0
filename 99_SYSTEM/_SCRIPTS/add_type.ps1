param([Parameter(Mandatory=$true)][string]$TYPE_ID,[string]$CATEGORY="UMOWY")
$flows="C:\Users\alimg\Dropbox\Archiwum 3.0\FLOWS"
$root=Join-Path $flows "TYPES"; New-Item -ItemType Directory -Path $root -Force | Out-Null
$file=Join-Path $root ("TYPE__{0}.md" -f $TYPE_ID)
if(Test-Path $file){Write-Host "TYPE exists: $TYPE_ID"; exit}
@"
TYPE_ID: $TYPE_ID
KATEGORIA: $CATEGORY
WEJSCIA: email / pismo / pdf
TRIGGER_SLOWA:
- TODO
RYZYKO: MED
CEL:
- TODO
NIE_ROBIC:
- TODO
DANE_MIN:
- TODO
RULESET:
- RULE__ZBIERZ_DANE_MIN
OUTPUT: odpowiedz-mail / pismo
"@ | Out-File -Encoding UTF8 $file
Write-Host "TYPE created: $TYPE_ID"

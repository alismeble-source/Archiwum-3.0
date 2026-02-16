param([Parameter(Mandatory=$true)][string]$RULE_ID)
$flows="C:\Users\alimg\Dropbox\Archiwum 3.0\FLOWS"
$root=Join-Path $flows "RULES"; New-Item -ItemType Directory -Path $root -Force | Out-Null
$file=Join-Path $root ("RULE__{0}.md" -f $RULE_ID)
if(Test-Path $file){Write-Host "RULE exists: $RULE_ID"; exit}
@"
RULE_ID: $RULE_ID
KIEDY:
- TODO
WEJSCIA:
- TODO
DECYZJA:
- TODO
DZIALANIA:
1. TODO
STATUS:
- ACTIVE / RISK / CLOSED
OUTPUT:
- PROMPT / TEMPLATE
"@ | Out-File -Encoding UTF8 $file
Write-Host "RULE created: $RULE_ID"

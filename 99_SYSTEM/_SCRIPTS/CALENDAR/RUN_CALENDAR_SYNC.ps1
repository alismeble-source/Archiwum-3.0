$ErrorActionPreference = "Stop"

$root = "C:\Users\alimg\Dropbox\Archiwum 3.0"
$py   = Join-Path $root "99_SYSTEM\_SCRIPTS\CALENDAR\deadlines_to_gcal.py"
$logd = Join-Path $root "FINANCE\_CALENDAR\_LOGS"
New-Item -ItemType Directory -Force -Path $logd | Out-Null

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$log = Join-Path $logd "CALSYNC_$ts.txt"

$env:GCAL_CLIENT_SECRET = Join-Path $root "99_SYSTEM\_SECRETS\credentials.json"

"$(Get-Date -Format s) START" | Out-File -FilePath $log -Encoding UTF8
& "C:\Users\alimg\AppData\Local\Programs\Python\Python312\python.exe" "$py" 2>&1 | Tee-Object -FilePath $log -Append
"$(Get-Date -Format s) END" | Out-File -FilePath $log -Append -Encoding UTF8

"OK. LOG: $log"

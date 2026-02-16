param(
  [int]$MaxNew = 25,
  [string]$Mailbox = "INBOX"
)

$ErrorActionPreference = "Stop"

$root = "C:\Users\alimg\Dropbox\Archiwum 3.0"
$pass = "$root\99_SYSTEM\_SECRETS\icloud_alimgulov_stas.pass"
$py   = "$root\99_SYSTEM\_SCRIPTS\MAIL\icloud_to_inbox_env.py"

if (!(Test-Path -LiteralPath $pass)) { throw "Missing pass file: $pass" }
if (!(Test-Path -LiteralPath $py))   { throw "Missing python script: $py" }

$enc = (Get-Content -LiteralPath $pass -Raw -Encoding ASCII).Trim()
$secure = ConvertTo-SecureString -String $enc
$plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
  [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
)
$plain = ($plain -replace "-", "").Trim()

$env:ICLOUD_APP_PASSWORD = $plain
py $py $MaxNew $Mailbox
Remove-Item Env:\ICLOUD_APP_PASSWORD -ErrorAction SilentlyContinue

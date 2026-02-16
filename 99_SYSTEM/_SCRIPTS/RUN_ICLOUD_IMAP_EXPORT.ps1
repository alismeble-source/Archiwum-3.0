param(
  [int]$Max = 500,
  [string]$Mailbox = "INBOX"
)

$ErrorActionPreference = "Stop"

$root = "C:\Users\alimg\Dropbox\Archiwum 3.0"
$sec  = "$root\99_SYSTEM\_SECRETS"
$pass = "$sec\icloud_alimgulov_stas.pass"
$py   = "$root\99_SYSTEM\_SCRIPTS\MAIL\icloud_imap_export_attachments.py"

if (!(Test-Path $pass)) { throw "Missing pass file: $pass" }
if (!(Test-Path $py))   { throw "Missing python script: $py" }

# pass-file = output of ConvertFrom-SecureString
$secure = Get-Content $pass -Raw | ConvertTo-SecureString
$plain  = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
          )
$plain = ($plain -replace "-", "").Trim()

$env:ICLOUD_APP_PASSWORD = $plain
py $py --max $Max --mailbox $Mailbox
Remove-Item Env:\ICLOUD_APP_PASSWORD -ErrorAction SilentlyContinue

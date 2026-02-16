param()
$ErrorActionPreference = "Stop"

$root = "C:\Users\alimg\Dropbox\Archiwum 3.0"
$pass = "$root\99_SYSTEM\_SECRETS\icloud_alimgulov_stas.pass"
$py   = "$root\99_SYSTEM\_SCRIPTS\MAIL\icloud_imap_probe_env.py"

if (!(Test-Path -LiteralPath $pass)) { throw "Missing pass file: $pass" }
if (!(Test-Path -LiteralPath $py))   { throw "Missing python probe: $py" }

# Read encrypted DPAPI string
$enc = (Get-Content -LiteralPath $pass -Raw -Encoding ASCII).Trim()

# Convert encrypted string -> SecureString (DPAPI)
$secure = ConvertTo-SecureString -String $enc

# SecureString -> plaintext (in memory)
$plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
  [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
)

# Normalize: remove dashes + spaces
$plain = ($plain -replace "-", "").Trim()

$env:ICLOUD_APP_PASSWORD = $plain
py $py

Remove-Item Env:\ICLOUD_APP_PASSWORD -ErrorAction SilentlyContinue

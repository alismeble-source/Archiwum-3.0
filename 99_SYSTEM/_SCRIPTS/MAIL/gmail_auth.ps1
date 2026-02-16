# ==============================
# Gmail OAuth – FIXED VERSION
# ==============================

$SecretsDir = "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SECRETS"
$ScriptsDir = "C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SCRIPTS\MAIL"


$Credentials = Join-Path $SecretsDir "credentials.json"
$Token       = Join-Path $SecretsDir "token.json"
$Log         = Join-Path $SecretsDir "oauth_log.txt"

New-Item -ItemType Directory -Force -Path $SecretsDir | Out-Null

Write-Host "SecretsDir :" $SecretsDir
Write-Host "Credentials:" $Credentials
Write-Host "Token      :" $Token
Write-Host "Log        :" $Log

if (!(Test-Path $Credentials)) {
    Write-Host "ERROR: credentials.json NOT FOUND" -ForegroundColor Red
    exit 1
}

$python = "python"

# ---- Python script (INLINE) ----
$pyFile = Join-Path $ScriptsDir "_oauth_tmp.py"

@"
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import os, json

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

creds = None
token = r"$Token"
cred  = r"$Credentials"

if os.path.exists(token):
    creds = Credentials.from_authorized_user_file(token, SCOPES)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(cred, SCOPES)
        creds = flow.run_local_server(port=0)

with open(token, 'w', encoding='utf-8') as f:
    f.write(creds.to_json())

print("OK: token.json created")
"@ | Set-Content -Encoding UTF8 $pyFile

# ---- Install deps ----
Write-Host "Installing python deps..."
& $python -m pip install --upgrade pip google-auth google-auth-oauthlib google-auth-httplib2 > $Log 2>&1

# ---- Run OAuth ----
Write-Host "Starting OAuth in browser..." -ForegroundColor Cyan
& $python $pyFile >> $Log 2>&1

if (Test-Path $Token) {
    Write-Host "SUCCESS: token.json CREATED" -ForegroundColor Green
} else {
    Write-Host "ERROR: token.json NOT CREATED" -ForegroundColor Red
    Write-Host "Check log:" $Log
}

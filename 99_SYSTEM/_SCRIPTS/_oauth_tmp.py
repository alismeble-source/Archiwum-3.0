from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import os, json

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

creds = None
token = r"C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SECRETS\token.json"
cred  = r"C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SECRETS\credentials.json"

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

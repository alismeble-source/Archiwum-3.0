import json
import imaplib
import os
import win32crypt

ROOT = r"C:\Users\alimg\Dropbox\Archiwum 3.0"
SECRETS = os.path.join(ROOT, "99_SYSTEM", "_SECRETS")

# BOM-safe open
with open(os.path.join(SECRETS, "mail_accounts.json"), encoding="utf-8-sig") as f:
    cfg = json.load(f)["icloud"]

email = cfg["email"]
host  = cfg["imap"]["host"]
port  = cfg["imap"]["port"]
pass_file = os.path.join(SECRETS, cfg["password_file"])

# IMPORTANT: strip to avoid newline issues
with open(pass_file, "r") as f:
    encrypted = f.read().strip()

password = win32crypt.CryptUnprotectData(
    bytes.fromhex(encrypted), None, None, None, 0
)[1].decode("utf-8")

# IMPORTANT: normalize like manual test
password = password.replace("-", "").strip()

print(f"[iCloud IMAP] connecting to {host}:{port} as {email}")

imap = imaplib.IMAP4_SSL(host, port)
imap.login(email, password)

status, folders = imap.list()
print("Folders:")
for f in folders:
    print(" ", f.decode())

imap.logout()
print("\nDONE (probe only, no data downloaded)")

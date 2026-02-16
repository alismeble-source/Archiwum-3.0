import os, json, imaplib

ROOT = r"C:\Users\alimg\Dropbox\Archiwum 3.0"
SECRETS = os.path.join(ROOT, "99_SYSTEM", "_SECRETS")

with open(os.path.join(SECRETS, "mail_accounts.json"), encoding="utf-8-sig") as f:
    cfg = json.load(f)["icloud"]

email = cfg["email"]
host  = cfg["imap"]["host"]
port  = cfg["imap"]["port"]

password = os.environ.get("ICLOUD_APP_PASSWORD", "").replace("-", "").strip()
if not password:
    raise SystemExit("ICLOUD_APP_PASSWORD is empty (wrapper did not pass it)")

print(f"[iCloud IMAP] connecting to {host}:{port} as {email}")

imap = imaplib.IMAP4_SSL(host, port)
imap.login(email, password)

typ, folders = imap.list()
print("Folders:")
for f in folders or []:
    print(" ", f.decode(errors="replace"))

imap.logout()
print("\nDONE (probe only, no data downloaded)")

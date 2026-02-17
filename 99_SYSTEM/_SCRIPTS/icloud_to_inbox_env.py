import os, json, re, sys
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timezone

ROOT = r"C:\Users\alimg\Dropbox\Archiwum 3.0"
MAIL_RAW  = os.path.join(ROOT, "00_INBOX", "MAIL_RAW")
STATE_DIR = os.path.join(MAIL_RAW, "_STATE")
LOG_DIR   = os.path.join(ROOT, "00_INBOX", "_ROUTER_LOGS")
os.makedirs(STATE_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

ACCOUNT = "alimgulov_stas@icloud.com"
STATE_FILE = os.path.join(STATE_DIR, "icloud_processed_uids.txt")

def decode_str(v):
    if not v:
        return ""
    parts = decode_header(v)
    out = ""
    for s, enc in parts:
        if isinstance(s, bytes):
            out += s.decode(enc or "utf-8", errors="replace")
        else:
            out += s
    return out

def slug(s, maxlen=80):
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\-_ ]+", "", s, flags=re.UNICODE)
    s = s.replace(" ", "_")
    return (s[:maxlen] if s else "no_subject")

def read_processed():
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return set(x.strip() for x in f if x.strip())

def append_processed(uid):
    with open(STATE_FILE, "a", encoding="utf-8") as f:
        f.write(uid + "\n")

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def save_msg(uid, internal_dt, msg_bytes, headers):
    dt = internal_dt.astimezone(timezone.utc)
    yyyy = dt.strftime("%Y")
    mm   = dt.strftime("%m")
    dd   = dt.strftime("%d")

    base = os.path.join(MAIL_RAW, "ICLOUD", yyyy, mm, dd)
    ensure_dir(base)

    ts = dt.strftime("%Y%m%d_%H%M%S")
    subj = slug(headers.get("subject",""))
    folder = f"{ts}__icloud__{subj}__uid{uid}"
    outdir = os.path.join(base, folder)
    ensure_dir(outdir)

    eml_path  = os.path.join(outdir, "message.eml")
    meta_path = os.path.join(outdir, "meta.json")

    with open(eml_path, "wb") as f:
        f.write(msg_bytes)

    meta = {
        "provider": "icloud_imap",
        "account": ACCOUNT,
        "imap_uid": uid,
        "saved_path": outdir,
        "headers": headers,
        "internal_date_utc": dt.isoformat()
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def main(max_new=25, mailbox="INBOX"):
    password = os.environ.get("ICLOUD_APP_PASSWORD", "").replace("-", "").strip()
    if not password:
        raise SystemExit("ICLOUD_APP_PASSWORD is empty (wrapper did not pass it)")

    host = "imap.mail.me.com"
    port = 993

    processed = read_processed()

    print(f"[iCloud IMPORT] connect {host}:{port} as {ACCOUNT} | mailbox={mailbox} | max_new={max_new}")
    M = imaplib.IMAP4_SSL(host, port)
    M.login(ACCOUNT, password)

    # INBOX only, readonly
    M.select(mailbox, readonly=True)
    typ, data = M.uid("SEARCH", None, "ALL")
    if typ != "OK":
        print("[iCloud IMPORT] SEARCH failed")
        M.logout()
        return

    uids = data[0].split()
    total = len(uids)
    print(f"[iCloud IMPORT] {mailbox} total={total}")

    saved = 0
    # newest first
    for uid_b in reversed(uids):
        uid = uid_b.decode()
        if uid in processed:
            continue
        if saved >= max_new:
            break

        typ, msg_data = M.uid("FETCH", uid, "(RFC822 INTERNALDATE)")
        if typ != "OK" or not msg_data or not msg_data[0]:
            continue

        raw_bytes = msg_data[0][1]
        meta_line = msg_data[0][0]
        if isinstance(meta_line, bytes):
            meta_line = meta_line.decode("utf-8", errors="replace")
        else:
            meta_line = str(meta_line)

        internal_dt = datetime.now(timezone.utc)
        m = re.search(r'INTERNALDATE "([^"]+)"', meta_line)
        if m:
            try:
                internal_dt = datetime.strptime(m.group(1), "%d-%b-%Y %H:%M:%S %z").astimezone(timezone.utc)
            except:
                pass

        msg = email.message_from_bytes(raw_bytes)
        headers = {
            "from": decode_str(msg.get("From","")),
            "to": decode_str(msg.get("To","")),
            "subject": decode_str(msg.get("Subject","")),
            "date": decode_str(msg.get("Date",""))
        }

        save_msg(uid, internal_dt, raw_bytes, headers)
        append_processed(uid)
        saved += 1
        if saved % 10 == 0:
            print(f"[iCloud IMPORT] saved={saved}")

    M.logout()
    print(f"[iCloud IMPORT] DONE. saved={saved}")

if __name__ == "__main__":
    max_new = 25
    mailbox = "INBOX"
    if len(sys.argv) >= 2:
        try: max_new = int(sys.argv[1])
        except: pass
    if len(sys.argv) >= 3:
        mailbox = sys.argv[2]
    main(max_new=max_new, mailbox=mailbox)


import os
import re
import json
import base64
import hashlib
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

ARCHIWUM_ROOT = r"C:\Users\alimg\Dropbox\Archiwum 3.0"
SECRETS_DIR   = os.path.join(ARCHIWUM_ROOT, "99_SYSTEM", "_SECRETS")
TOKEN_PATH    = os.path.join(SECRETS_DIR, "token.json")
CREDS_PATH    = os.path.join(SECRETS_DIR, "credentials.json")

INBOX_RAW     = os.path.join(ARCHIWUM_ROOT, "00_INBOX", "MAIL_RAW")
STATE_DIR     = os.path.join(INBOX_RAW, "_STATE")
PROCESSED_IDS = os.path.join(STATE_DIR, "processed_gmail_all.txt")  # unified state file
LAST_RUN      = os.path.join(STATE_DIR, "last_run.json")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
MAX_PER_RUN = 50
QUERY = 'in:anywhere newer_than:365d -category:promotions -category:social'

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def safe_filename(s: str, max_len: int = 80) -> str:
    if not s:
        return "empty"
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", s)
    s = s.replace("..", ".")
    s = s.strip(" ._")
    return (s[:max_len] if s else "empty")

def load_processed() -> set:
    if not os.path.exists(PROCESSED_IDS):
        return set()
    with open(PROCESSED_IDS, "r", encoding="utf-8") as f:
        return set(x.strip() for x in f if x.strip())

def mark_processed(msg_id: str):
    with open(PROCESSED_IDS, "a", encoding="utf-8") as f:
        f.write(msg_id + "\n")

def save_json(path: str, obj: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def get_service():
    if not os.path.exists(CREDS_PATH):
        raise FileNotFoundError(f"Missing credentials.json: {CREDS_PATH}")

    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        ensure_dir(SECRETS_DIR)
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)

def get_full_headers(full_msg: dict) -> dict:
    headers = full_msg.get("payload", {}).get("headers", []) or []
    out = {}
    for h in headers:
        k = (h.get("name") or "").lower()
        v = h.get("value") or ""
        if k:
            out[k] = v
    return out

def get_plain_text_from_eml(eml_bytes: bytes) -> str:
    msg = BytesParser(policy=policy.default).parsebytes(eml_bytes)

    def decode_part(part):
        try:
            return part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            return payload.decode(errors="replace")

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", "")).lower()
            if ctype == "text/plain" and "attachment" not in disp:
                return decode_part(part)
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", "")).lower()
            if ctype == "text/html" and "attachment" not in disp:
                html = decode_part(part)
                text = re.sub(r"<[^>]+>", " ", html)
                text = re.sub(r"\s+", " ", text).strip()
                return text
    else:
        return decode_part(msg)

    return ""

def walk_parts(part: dict):
    yield part
    for p in part.get("parts", []) or []:
        yield from walk_parts(p)

def main():
    ensure_dir(INBOX_RAW)
    ensure_dir(STATE_DIR)

    processed = load_processed()
    service = get_service()

    resp = service.users().messages().list(userId="me", q=QUERY, maxResults=MAX_PER_RUN).execute()
    msgs = resp.get("messages", []) or []

    saved = 0
    scanned = len(msgs)

    for m in msgs:
        msg_id = m.get("id")
        if not msg_id or msg_id in processed:
            continue

        try:
            full_msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
            raw_msg  = service.users().messages().get(userId="me", id=msg_id, format="raw").execute()
        except HttpError as e:
            print(f"ERROR fetch {msg_id}: {e}")
            continue

        headers = get_full_headers(full_msg)
        subject = headers.get("subject", "")
        from_   = headers.get("from", "")
        date_h  = headers.get("date", "")

        internal_ms = int(full_msg.get("internalDate", "0") or "0")
        dt = datetime.fromtimestamp(internal_ms / 1000, tz=timezone.utc).astimezone()
        y  = dt.strftime("%Y")
        mo = dt.strftime("%m")
        d  = dt.strftime("%d")
        stamp = dt.strftime("%Y%m%d_%H%M%S")

        msgid_hash = hashlib.sha1(msg_id.encode("utf-8")).hexdigest()[:10]
        folder = f"{stamp}__{safe_filename(from_,40)}__{safe_filename(subject,60)}__{msgid_hash}"

        out_dir = os.path.join(INBOX_RAW, y, mo, d, folder)
        att_dir = os.path.join(out_dir, "attachments")
        ensure_dir(att_dir)

        raw_b64 = raw_msg.get("raw", "") or ""
        eml_bytes = base64.urlsafe_b64decode(raw_b64.encode("utf-8")) if raw_b64 else b""
        with open(os.path.join(out_dir, "message.eml"), "wb") as f:
            f.write(eml_bytes)

        body = get_plain_text_from_eml(eml_bytes)
        with open(os.path.join(out_dir, "body.txt"), "w", encoding="utf-8", errors="replace") as f:
            f.write(body or "")

        payload = full_msg.get("payload", {}) or {}
        for part in walk_parts(payload):
            filename = part.get("filename") or ""
            body_obj = part.get("body", {}) or {}
            att_id = body_obj.get("attachmentId")
            if filename and att_id:
                try:
                    att = service.users().messages().attachments().get(
                        userId="me", messageId=msg_id, id=att_id
                    ).execute()
                    data = att.get("data", "") or ""
                    if data:
                        b = base64.urlsafe_b64decode(data.encode("utf-8"))
                        fn = safe_filename(filename, 140)
                        with open(os.path.join(att_dir, fn), "wb") as f:
                            f.write(b)
                except HttpError as e:
                    print(f"ERROR attachment {msg_id}/{filename}: {e}")

        meta = {
            "gmail_id": msg_id,
            "threadId": full_msg.get("threadId"),
            "labelIds": full_msg.get("labelIds", []),
            "snippet": full_msg.get("snippet", ""),
            "internalDate_ms": internal_ms,
            "local_datetime": dt.isoformat(),
            "headers": {
                "from": from_,
                "to": headers.get("to", ""),
                "cc": headers.get("cc", ""),
                "subject": subject,
                "date": date_h,
                "message-id": headers.get("message-id", "")
            },
            "query": QUERY,
            "saved_path": out_dir
        }

        save_json(os.path.join(out_dir, "meta.json"), meta)

        mark_processed(msg_id)
        saved += 1
        print(f"SAVED: {out_dir}")

    save_json(LAST_RUN, {
        "ts": datetime.now().isoformat(),
        "query": QUERY,
        "scanned": scanned,
        "saved": saved,
        "max_per_run": MAX_PER_RUN
    })

    print(f"DONE. scanned={scanned} saved={saved}")

if __name__ == "__main__":
    main()

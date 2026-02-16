import os
import re
import csv
import json
import hashlib
import base64
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import atomic state operations
import sys
sys.path.insert(0, str(Path(__file__).parent))
from state_file_utils import atomic_read_lines, atomic_write_lines, append_line_atomic

# -----------------------------
# CONFIG
# -----------------------------
DROPBOX_ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")

OUT_DIR = DROPBOX_ROOT / "CASES" / "_INBOX"
STATE_DIR = DROPBOX_ROOT / "00_INBOX" / "MAIL_RAW" / "_STATE"
LOG_DIR = DROPBOX_ROOT / "00_INBOX" / "_ROUTER_LOGS"

SECRETS_DIR = DROPBOX_ROOT / "99_SYSTEM" / "_SECRETS" / "gmail"
CREDENTIALS_JSON = SECRETS_DIR / "credentials.json"
TOKEN_JSON = SECRETS_DIR / "token.json"

# Gmail query:
# Preferred mode for your setup (2 iCloud -> 1 Gmail via forwarding filters):
#   label:"SOURCE/ICLOUD" has:attachment
# If the label does not exist (or wasn't applied by filters), we fall back to inbox.
GMAIL_INBOX_QUERY = 'in:inbox has:attachment -in:spam -in:trash'
GMAIL_LABEL_QUERY = 'label:"SOURCE/ICLOUD" has:attachment -in:spam -in:trash'

# One-off override (highest priority). Example:
#   $env:GMAIL_QUERY_OVERRIDE='label:"SOURCE/ICLOUD" has:attachment newer_than:30d'
GMAIL_QUERY_OVERRIDE = os.environ.get("GMAIL_QUERY_OVERRIDE", "").strip()

# If you have multiple sources (2 iCloud + 3 Gmail → forwarded into 1 inbox),
# you can list which labels define "pipeline inbox" (comma-separated):
#   $env:GMAIL_SOURCE_LABELS='SOURCE/ICLOUD,SOURCE/GMAIL1,SOURCE/GMAIL2,CLIENTS,CAR,WYCENA'
# The importer will use only labels that exist in the account; otherwise it falls back to inbox.
GMAIL_SOURCE_LABELS = [
    s.strip()
    for s in os.environ.get("GMAIL_SOURCE_LABELS", "").split(",")
    if s.strip()
]

# Optional: force label mode even if we can't detect the label.
#   $env:GMAIL_USE_LABEL='1'
GMAIL_USE_LABEL = os.environ.get("GMAIL_USE_LABEL", "").strip().lower() in {"1", "true", "yes", "y", "on"}
# Scopes: read-only Gmail + Calendar write (for pipeline integration)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar"
]

# State files
PROCESSED_IDS_FILE = STATE_DIR / "processed_gmail_all.txt"  # unified state file (MAIN)
LEGACY_IDS_FILE = STATE_DIR / "gmail_icloud_processed_ids.txt"  # legacy (read-only for backcompat)
LOG_CSV = LOG_DIR / "gmail_import_log.csv"

# Behavior
MAX_MESSAGES_PER_RUN = 50  # safety cap
DRY_RUN = False            # set True to test without writing files

# -----------------------------
# HELPERS
# -----------------------------
def ensure_dirs():
    for p in [OUT_DIR, STATE_DIR, LOG_DIR, SECRETS_DIR]:
        p.mkdir(parents=True, exist_ok=True)

def load_processed_ids() -> set[str]:
    """Load from BOTH unified + legacy files (atomic read with retry)"""
    ids = set()
    # Read from main unified file
    lines = atomic_read_lines(PROCESSED_IDS_FILE, max_retries=3)
    ids.update(lines)
    # Also read from legacy file (in case pipeline was interrupted mid-unification)
    legacy_lines = atomic_read_lines(LEGACY_IDS_FILE, max_retries=3)
    ids.update(legacy_lines)
    return ids

def mark_processed(msg_id: str):
    """Mark message as processed (atomic append with retry)"""
    append_line_atomic(PROCESSED_IDS_FILE, msg_id, max_retries=3)

def safe_filename(name: str) -> str:
    name = name.strip().replace("\u200f", "")
    name = re.sub(r"[<>:\"/\\|?*\x00-\x1F]", "_", name)
    name = re.sub(r"\s+", " ", name)
    return name[:180] if len(name) > 180 else name

def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def parse_headers(payload_headers: list[dict]) -> dict:
    h = {}
    for item in payload_headers or []:
        k = (item.get("name") or "").lower()
        v = item.get("value") or ""
        h[k] = v
    return h

def get_datetime_iso(headers: dict) -> str:
    # Prefer RFC2822 "Date" header
    raw = headers.get("date", "")
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()

def write_log_row(row: dict):
    LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    exists = LOG_CSV.exists()
    with LOG_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            w.writeheader()
        w.writerow(row)

def gmail_auth():
    if not CREDENTIALS_JSON.exists():
        raise FileNotFoundError(f"Missing credentials.json at: {CREDENTIALS_JSON}")

    creds = None
    if TOKEN_JSON.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_JSON), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_JSON), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_JSON.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)

def has_label(service, label_name: str) -> bool:
    """Check if a Gmail label exists (by display name)."""
    try:
        res = service.users().labels().list(userId="me").execute()
        labels = res.get("labels", []) or []
        want = label_name.strip().lower()
        for l in labels:
            if (l.get("name") or "").strip().lower() == want:
                return True
    except Exception:
        return False
    return False

def build_multi_label_query(labels: list[str]) -> str:
    """
    Build Gmail search query that matches any of the provided labels.
    Example output:
      (label:"A" OR label:"B") has:attachment -in:spam -in:trash
    """
    safe = []
    for name in labels:
        # Basic quoting. Gmail label names cannot contain a quote char in UI,
        # but we guard anyway.
        n = (name or "").replace('"', "")
        if n:
            safe.append(f'label:"{n}"')
    if not safe:
        return GMAIL_INBOX_QUERY
    inner = " OR ".join(safe)
    return f"({inner}) has:attachment -in:spam -in:trash"

def iter_attachments(service, msg_id: str, payload: dict):
    """Yield (filename, data_bytes) for each attachment."""
    def walk(part):
        if not part:
            return
        filename = part.get("filename") or ""
        body = part.get("body") or {}
        mime_type = part.get("mimeType") or ""
        parts = part.get("parts") or []

        # If this part is an attachment (has filename) and has attachmentId
        if filename and body.get("attachmentId"):
            att_id = body["attachmentId"]
            att = service.users().messages().attachments().get(userId="me", messageId=msg_id, id=att_id).execute()
            data = att.get("data", "")
            if data:
                yield filename, base64.urlsafe_b64decode(data.encode("utf-8"))
        # Some small attachments can be inline in "data"
        elif filename and body.get("data"):
            yield filename, base64.urlsafe_b64decode(body["data"].encode("utf-8"))

        # Recurse
        for p in parts:
            yield from walk(p)

    yield from walk(payload)

# -----------------------------
# MAIN
# -----------------------------
def main():
    ensure_dirs()

    saved_files = 0

    processed = load_processed_ids()
    service = gmail_auth()

    # Decide which query to use.
    # Goal: stable "one-button" operation for a non-technical workflow.
    if GMAIL_QUERY_OVERRIDE:
        gmail_query = GMAIL_QUERY_OVERRIDE
        query_mode = "override"
    elif GMAIL_USE_LABEL:
        gmail_query = GMAIL_LABEL_QUERY
        query_mode = "label_forced"
    else:
        if GMAIL_SOURCE_LABELS:
            existing = [l for l in GMAIL_SOURCE_LABELS if has_label(service, l)]
            if existing:
                gmail_query = build_multi_label_query(existing)
                query_mode = "labels_env"
            else:
                gmail_query = GMAIL_INBOX_QUERY
                query_mode = "labels_env_missing_fallback"
        elif has_label(service, "SOURCE/ICLOUD"):
            gmail_query = GMAIL_LABEL_QUERY
            query_mode = "label_auto"
        else:
            gmail_query = GMAIL_INBOX_QUERY
            query_mode = "inbox_fallback"

    print(f"[GMAIL] Query mode: {query_mode}")
    print(f"[GMAIL] Query: {gmail_query}")

    # Search messages
    res = service.users().messages().list(
        userId="me",
        q=gmail_query,
        maxResults=MAX_MESSAGES_PER_RUN
    ).execute()
    messages = res.get("messages", []) or []

    if not messages:
        print(f"Imported: 0 attachment(s). Saved to: {OUT_DIR}")
        return

    for m in messages:
        msg_id = m["id"]
        if msg_id in processed:
            continue

        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        payload = msg.get("payload", {}) or {}
        headers = parse_headers(payload.get("headers", []))
        subject = headers.get("subject", "")
        from_ = headers.get("from", "")
        date_iso = get_datetime_iso(headers)

        any_saved = False

        for (fname, data) in iter_attachments(service, msg_id, payload):
            any_saved = True
            safe_name = safe_filename(fname) or "attachment.bin"

            # Build deterministic-ish filename: UTC date + msg_id short + original
            date_tag = date_iso[:10].replace("-", "")
            msg_short = msg_id[:8]
            out_name = f"{date_tag}__{msg_short}__{safe_name}"

            out_path = OUT_DIR / out_name
            meta_path = OUT_DIR / (out_name + ".meta.json")

            meta = {
                "source": "GMAIL/SOURCE_ICLOUD",
                "gmail_id": msg_id,
                "from": from_,
                "subject": subject,
                "date_utc": date_iso,
                "original_filename": fname,
                "saved_filename": out_name,
            }

            if DRY_RUN:
                print("[DRY] Would save:", out_path.name)
                continue

            # Write file
            out_path.write_bytes(data)
            saved_files += 1

            # Compute sha1
            meta["sha1"] = sha1_file(out_path)

            # Write meta.json
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            # Log CSV
            write_log_row({
                "ts_utc": datetime.now(timezone.utc).isoformat(),
                "gmail_id": msg_id,
                "saved_file": out_path.name,
                "sha1": meta["sha1"],
                "from": from_,
                "subject": subject[:200],
                "date_utc": date_iso,
            })

        # Mark processed only if message had attachments handled
        if any_saved and not DRY_RUN:
            mark_processed(msg_id)

    print(f"Imported: {saved_files} attachment(s). Saved to: {OUT_DIR}")

if __name__ == "__main__":
    main()




"""
Gmail Import для alimgulov1992@gmail.com
Импорт вложений с ZUS, Skarbowa, лизинг
"""
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

SECRETS_DIR = DROPBOX_ROOT / "99_SYSTEM" / "_SECRETS" / "gmail_alim"
CREDENTIALS_JSON = SECRETS_DIR / "credentials.json"
TOKEN_JSON = SECRETS_DIR / "token.json"

# Gmail query: все письма с вложениями от важных отправителей
GMAIL_QUERY = 'has:attachment (from:zus.pl OR from:mf.gov.pl OR from:skarbowa OR subject:leasing OR subject:лизинг OR subject:ZUS OR subject:VAT)'

# Scopes: read-only Gmail
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]

# State files
PROCESSED_IDS_FILE = STATE_DIR / "processed_gmail_alim.txt"
LOG_CSV = LOG_DIR / "gmail_import_alim_log.csv"

# Behavior
MAX_MESSAGES_PER_RUN = 50  # safety cap
DRY_RUN = False            # set True to test without writing files

# -----------------------------
# HELPERS
# -----------------------------
def ensure_dirs():
    for p in [OUT_DIR, STATE_DIR, LOG_DIR, SECRETS_DIR]:
        p.mkdir(parents=True, exist_ok=True)

def sanitize_filename(name: str) -> str:
    """Remove unsafe characters from filename."""
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    safe = safe.strip('. ')
    return safe[:150] if safe else "untitled"

def compute_sha1(data: bytes) -> str:
    """Compute SHA1 hash of binary data."""
    return hashlib.sha1(data).hexdigest()

def get_gmail_service():
    """Authenticate and return Gmail service."""
    creds = None
    if TOKEN_JSON.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_JSON), SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_JSON.exists():
                print(f"[ERROR] Credentials file not found: {CREDENTIALS_JSON}")
                print(f"[INFO] Создай OAuth 2.0 credentials на https://console.cloud.google.com/apis/credentials")
                print(f"[INFO] Скачай JSON и сохрани как: {CREDENTIALS_JSON}")
                print(f"[INFO] Email: alimgulov1992@gmail.com")
                raise FileNotFoundError(f"Missing {CREDENTIALS_JSON}")
            
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_JSON), SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_JSON, 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)

def load_processed_ids() -> set:
    """Load processed message IDs from state file."""
    if not PROCESSED_IDS_FILE.exists():
        return set()
    return set(atomic_read_lines(PROCESSED_IDS_FILE))

def save_processed_id(msg_id: str):
    """Append message ID to state file (atomic)."""
    append_line_atomic(PROCESSED_IDS_FILE, msg_id)

def log_import(msg_id: str, date: str, from_addr: str, subject: str, attachments_count: int, status: str):
    """Log import to CSV."""
    LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    write_header = not LOG_CSV.exists()
    
    with open(LOG_CSV, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(['timestamp', 'msg_id', 'date', 'from', 'subject', 'attachments', 'status'])
        writer.writerow([datetime.now(timezone.utc).isoformat(), msg_id, date, from_addr, subject, attachments_count, status])

def download_attachment(service, msg_id: str, att_id: str) -> bytes:
    """Download attachment binary data."""
    try:
        att = service.users().messages().attachments().get(userId='me', messageId=msg_id, id=att_id).execute()
        data = att['data']
        return base64.urlsafe_b64decode(data)
    except HttpError as e:
        print(f"[ERROR] Failed to download attachment {att_id}: {e}")
        return None

def process_message(service, msg_id: str, processed_ids: set):
    """Process single Gmail message with attachments."""
    if msg_id in processed_ids:
        return
    
    try:
        msg = service.users().messages().get(userId='me', id=msg_id).execute()
        
        # Extract headers
        headers = {h['name'].lower(): h['value'] for h in msg['payload'].get('headers', [])}
        date_str = headers.get('date', '')
        from_addr = headers.get('from', 'unknown')
        subject = headers.get('subject', '(no subject)')
        
        # Parse date
        try:
            date_obj = parsedate_to_datetime(date_str)
            date_utc = date_obj.astimezone(timezone.utc).isoformat()
            date_filename = date_obj.strftime("%Y%m%d")
        except:
            date_utc = datetime.now(timezone.utc).isoformat()
            date_filename = datetime.now().strftime("%Y%m%d")
        
        # Short message ID for filenames (last 8 chars)
        msg_id_short = msg_id[-8:]
        
        # Find attachments
        attachments = []
        def extract_parts(part):
            if 'parts' in part:
                for subpart in part['parts']:
                    extract_parts(subpart)
            if part.get('filename') and part['body'].get('attachmentId'):
                attachments.append({
                    'filename': part['filename'],
                    'att_id': part['body']['attachmentId'],
                    'mime_type': part.get('mimeType', 'application/octet-stream')
                })
        
        extract_parts(msg['payload'])
        
        if not attachments:
            print(f"[SKIP] No attachments: {subject[:50]}")
            save_processed_id(msg_id)
            log_import(msg_id, date_utc, from_addr, subject, 0, "no_attachments")
            return
        
        print(f"\n[PROCESS] {subject[:60]}")
        print(f"  From: {from_addr}")
        print(f"  Date: {date_str}")
        print(f"  Attachments: {len(attachments)}")
        
        # Download each attachment
        for att in attachments:
            filename = sanitize_filename(att['filename'])
            att_data = download_attachment(service, msg_id, att['att_id'])
            
            if att_data is None:
                print(f"  [ERROR] Failed to download: {filename}")
                continue
            
            # Compute SHA1
            sha1 = compute_sha1(att_data)
            
            # Save attachment
            out_filename = f"{date_filename}__{msg_id_short}__{filename}"
            out_path = OUT_DIR / out_filename
            
            if DRY_RUN:
                print(f"  [DRY-RUN] Would save: {out_filename} ({len(att_data)} bytes, SHA1: {sha1[:8]}...)")
            else:
                out_path.write_bytes(att_data)
                print(f"  [SAVED] {out_filename} ({len(att_data)} bytes)")
                
                # Save metadata JSON
                meta = {
                    "gmail_id": msg_id,
                    "from": from_addr,
                    "subject": subject,
                    "date_utc": date_utc,
                    "original_filename": att['filename'],
                    "mime_type": att['mime_type'],
                    "sha1": sha1,
                    "imported_at": datetime.now(timezone.utc).isoformat(),
                    "source": "gmail_alim"
                }
                meta_path = OUT_DIR / f"{out_filename}.meta.json"
                meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        
        # Mark as processed
        save_processed_id(msg_id)
        log_import(msg_id, date_utc, from_addr, subject, len(attachments), "success")
        
    except Exception as e:
        print(f"[ERROR] Failed to process {msg_id}: {e}")
        log_import(msg_id, "", "", "", 0, f"error: {e}")

def main():
    print("=" * 60)
    print("Gmail Import - alimgulov1992@gmail.com")
    print("=" * 60)
    
    ensure_dirs()
    
    # Load processed IDs
    processed_ids = load_processed_ids()
    print(f"[INFO] Processed messages: {len(processed_ids)}")
    
    # Get Gmail service
    try:
        service = get_gmail_service()
        print("[OK] Gmail authenticated")
    except Exception as e:
        print(f"[ERROR] Authentication failed: {e}")
        return
    
    # Search for messages
    try:
        response = service.users().messages().list(
            userId='me',
            q=GMAIL_QUERY,
            maxResults=MAX_MESSAGES_PER_RUN
        ).execute()
        
        messages = response.get('messages', [])
        print(f"[INFO] Found {len(messages)} messages matching query")
        print(f"[INFO] Query: {GMAIL_QUERY}")
        
        if not messages:
            print("[OK] No new messages")
            return
        
        # Process each message
        for idx, msg in enumerate(messages, 1):
            msg_id = msg['id']
            print(f"\n[{idx}/{len(messages)}] Processing {msg_id}...")
            process_message(service, msg_id, processed_ids)
            time.sleep(0.5)  # rate limit
        
        print(f"\n[OK] Import complete")
        
    except HttpError as e:
        print(f"[ERROR] Gmail API error: {e}")

if __name__ == '__main__':
    main()

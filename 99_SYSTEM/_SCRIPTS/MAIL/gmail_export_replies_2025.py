import os
import re
import json
import base64
import argparse
from datetime import datetime
from pathlib import Path
from email import policy
from email.parser import BytesParser

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def safe_name(s: str, max_len: int = 120) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^\w\-\.\s\(\)\[\]ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s or "no_subject"

def b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode("utf-8"))

def get_header(msg, name: str) -> str:
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "") or ""
    return ""

def list_all_messages(service, user_id: str, q: str):
    messages = []
    page_token = None
    while True:
        resp = service.users().messages().list(
            userId=user_id, q=q, pageToken=page_token, maxResults=500
        ).execute()
        messages.extend(resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return messages

def walk_parts(payload):
    # yields all parts in a message payload tree
    stack = [payload]
    while stack:
        p = stack.pop()
        yield p
        for ch in p.get("parts", []) or []:
            stack.append(ch)

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output folder root (EXPORT_2025)")
    ap.add_argument("--token", required=True, help="Path to token.json")
    ap.add_argument("--client", required=True, help="Path to OAuth client_secret.json")
    ap.add_argument("--query", default="in:sent after:2025/01/01 before:2026/01/01 has:attachment filename:pdf")
    args = ap.parse_args()

    out_root = Path(args.out)
    msg_root = out_root / "MSG"
    idx_root = out_root / "INDEX"
    ensure_dir(msg_root)
    ensure_dir(idx_root)

    # Auth
    creds = None
    if os.path.exists(args.token):
        creds = Credentials.from_authorized_user_file(args.token, SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(args.client, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(args.token, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)

    q = args.query
    msgs = list_all_messages(service, "me", q)
    print(f"FOUND messages: {len(msgs)}")

    index_path = idx_root / "replies_2025.jsonl"
    processed = 0

    for m in msgs:
        mid = m["id"]

        # Get full message (metadata + structure + attachments refs)
        msg = service.users().messages().get(userId="me", id=mid, format="full").execute()

        internal_date_ms = int(msg.get("internalDate", "0"))
        dt_utc = datetime.utcfromtimestamp(internal_date_ms / 1000.0).strftime("%Y-%m-%d")

        subject = get_header(msg, "Subject")
        to_ = get_header(msg, "To")
        frm = get_header(msg, "From")
        thread_id = msg.get("threadId", "")

        # Create folder per message
        folder = msg_root / f"{dt_utc}__{mid}"
        ensure_dir(folder)

        # Save EML raw (for exact training reference)
        raw = service.users().messages().get(userId="me", id=mid, format="raw").execute().get("raw", "")
        if raw:
            eml_bytes = b64url_decode(raw)
            (folder / "reply.eml").write_bytes(eml_bytes)
        else:
            # fallback: build minimal eml from headers (rare)
            (folder / "reply.eml").write_text("", encoding="utf-8")

        # Find and download PDF attachments
        pdf_count = 0
        for part in walk_parts(msg.get("payload", {})):
            filename = part.get("filename", "") or ""
            mime_type = (part.get("mimeType", "") or "").lower()
            body = part.get("body", {}) or {}
            att_id = body.get("attachmentId")

            is_pdf = False
            if filename.lower().endswith(".pdf"):
                is_pdf = True
            elif mime_type == "application/pdf":
                is_pdf = True

            if is_pdf and att_id:
                att = service.users().messages().attachments().get(
                    userId="me", messageId=mid, id=att_id
                ).execute()
                data = att.get("data", "")
                if data:
                    pdf_bytes = b64url_decode(data)
                    pdf_count += 1
                    safe_fn = safe_name(Path(filename).name) if filename else f"attachment_{pdf_count}.pdf"
                    out_name = f"{pdf_count:02d}__{safe_fn}"
                    if not out_name.lower().endswith(".pdf"):
                        out_name += ".pdf"
                    (folder / out_name).write_bytes(pdf_bytes)

        meta = {
            "message_id": mid,
            "thread_id": thread_id,
            "date_utc": dt_utc,
            "from": frm,
            "to": to_,
            "subject": subject,
            "query": q,
            "pdf_count": pdf_count,
        }
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        # Only keep entries that truly have PDFs downloaded
        # (на случай редких “ложных совпадений”)
        if pdf_count > 0:
            with open(index_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(meta, ensure_ascii=False) + "\n")
            processed += 1
        else:
            # если pdf не скачался — папка остаётся как диагностика
            pass

    print(f"DONE. Indexed messages with PDF: {processed}")
    print(f"INDEX: {index_path}")

if __name__ == "__main__":
    main()

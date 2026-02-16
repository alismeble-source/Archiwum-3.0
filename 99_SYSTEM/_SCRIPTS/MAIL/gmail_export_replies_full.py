import argparse
import base64
import json
import os
import re
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def ensure_creds(token_path: str, client_path: str) -> Credentials:
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # refresh handled internally by google-auth, but some envs need explicit refresh; simplest: re-auth
            pass
        flow = InstalledAppFlow.from_client_secrets_file(client_path, SCOPES)
        creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return creds

def b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode("utf-8"))

def extract_text_from_payload(payload: dict) -> str:
    """
    Prefer text/plain; fallback to stripped text from text/html.
    """
    def walk(part):
        mime = part.get("mimeType", "")
        body = part.get("body", {}) or {}
        data = body.get("data")
        if data and mime == "text/plain":
            try:
                return b64url_decode(data).decode("utf-8", errors="replace")
            except Exception:
                return ""
        # recurse
        for p in part.get("parts", []) or []:
            t = walk(p)
            if t:
                return t
        # fallback: html
        if data and mime == "text/html":
            try:
                html = b64url_decode(data).decode("utf-8", errors="replace")
            except Exception:
                return ""
            # crude strip tags
            html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
            txt = re.sub(r"(?is)<.*?>", " ", html)
            txt = re.sub(r"[ \t]+", " ", txt)
            txt = re.sub(r"\n{3,}", "\n\n", txt)
            return txt.strip()
        return ""

    return walk(payload) or ""

def get_header(headers, name):
    name_l = name.lower()
    for h in headers:
        if h.get("name","").lower() == name_l:
            return h.get("value","")
    return ""

def list_message_ids(service, query: str):
    ids = []
    page_token = None
    while True:
        resp = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=500,
            pageToken=page_token
        ).execute()
        for m in resp.get("messages", []) or []:
            ids.append(m["id"])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--client", required=True)
    ap.add_argument("--query", required=True)
    args = ap.parse_args()

    creds = ensure_creds(args.token, args.client)
    service = build("gmail", "v1", credentials=creds)

    msg_ids = list_message_ids(service, args.query)
    print(f"FOUND messages: {len(msg_ids)}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    with open(args.out, "w", encoding="utf-8") as f:
        for mid in msg_ids:
            msg = service.users().messages().get(
                userId="me",
                id=mid,
                format="full"
            ).execute()

            payload = msg.get("payload", {}) or {}
            headers = payload.get("headers", []) or []
            subject = get_header(headers, "Subject")
            to = get_header(headers, "To")
            cc = get_header(headers, "Cc")
            frm = get_header(headers, "From")
            date_h = get_header(headers, "Date")

            internal_ms = int(msg.get("internalDate", "0"))
            dt_utc = datetime.fromtimestamp(internal_ms / 1000, tz=timezone.utc).isoformat()

            text = extract_text_from_payload(payload)

            # attachment info (names only, without downloading)
            att_names = []
            def collect_attachments(part):
                filename = (part.get("filename") or "").strip()
                body = part.get("body", {}) or {}
                if filename and body.get("attachmentId"):
                    att_names.append(filename)
                for p in part.get("parts", []) or []:
                    collect_attachments(p)
            collect_attachments(payload)

            row = {
                "message_id": msg.get("id"),
                "thread_id": msg.get("threadId"),
                "dt_utc": dt_utc,
                "from": frm,
                "to": to,
                "cc": cc,
                "subject": subject,
                "date_header": date_h,
                "snippet": msg.get("snippet", ""),
                "attachments": att_names,
                "body": text
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"DONE. OUT={args.out}")

if __name__ == "__main__":
    main()

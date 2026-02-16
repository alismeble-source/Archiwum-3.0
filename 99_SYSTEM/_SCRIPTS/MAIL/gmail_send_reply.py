#!/usr/bin/env python3
"""
AI Auto-Responder - Send Approved Responses to Clients
Listens for Telegram reactions (✅/❌) and sends approved responses via Gmail.

Workflow:
1. ai_responder.py sends draft to Telegram
2. You react with ✅ (approve) or ❌ (skip)
3. telegram_approval_listener.py detects reaction
4. Calls gmail_send_reply.py to send response to client
5. Marks email as processed
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone
import csv

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

# =====================
# CONFIG
# =====================

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")

DRAFTS_DIR = ROOT / "00_INBOX" / "_DRAFTS"
SENT_DIR = ROOT / "00_INBOX" / "_SENT_RESPONSES"
LOG_DIR = ROOT / "00_INBOX" / "_ROUTER_LOGS"
CASES_INBOX = ROOT / "CASES" / "_INBOX"

SECRETS_DIR = ROOT / "99_SYSTEM" / "_SECRETS"
CREDENTIALS_JSON = SECRETS_DIR / "gmail" / "credentials.json"
TOKEN_JSON = SECRETS_DIR / "gmail" / "token.json"

APPROVAL_LOG = LOG_DIR / "approval_log.csv"
SEND_LOG = LOG_DIR / "send_log.csv"

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Behavior
DRY_RUN = False

# =====================
# GMAIL AUTH
# =====================

def get_gmail_service():
    """Authenticate and return Gmail service"""
    if not GMAIL_AVAILABLE:
        raise ImportError("Google API client not available")
    
    creds = None
    
    # Load token if exists
    if TOKEN_JSON.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_JSON, SCOPES)
    
    # Refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_JSON, SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Save token
        with open(TOKEN_JSON, "w") as token:
            token.write(creds.to_json())
    
    return build("gmail", "v1", credentials=creds)

# =====================
# SEND EMAIL
# =====================

def send_email_reply(service, original_message_id: str, to: str, subject: str, body: str) -> bool:
    """
    Send reply to original email via Gmail API
    
    Args:
        service: Gmail service object
        original_message_id: Gmail message ID to reply to
        to: Recipient email
        subject: Email subject (auto-prefixed with "Re: ")
        body: Email body (plain text)
    """
    try:
        import base64
        from email.mime.text import MIMEText
        
        # Create reply subject
        if not subject.startswith("Re:"):
            subject = f"Re: {subject}"
        
        # Create message
        message = MIMEText(body, "plain", "utf-8")
        message["to"] = to
        message["subject"] = subject
        
        # Encode
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        if DRY_RUN:
            print(f"[DRY_RUN] Would send email to {to}:")
            print(f"Subject: {subject}")
            print(f"Body:\n{body}")
            return True
        
        # Send via Gmail API
        send_message = {
            "raw": raw_message,
            "threadId": original_message_id  # Reply to thread
        }
        
        service.users().messages().send(userId="me", body=send_message).execute()
        return True
    
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def get_gmail_thread_info(service, message_id: str) -> dict:
    """Get email thread info (To, Subject) from Gmail"""
    try:
        message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = message["payload"]["headers"]
        
        info = {}
        for header in headers:
            if header["name"] == "From":
                info["from"] = header["value"]
            elif header["name"] == "Subject":
                info["subject"] = header["value"]
            elif header["name"] == "Message-ID":
                info["message_id"] = header["value"]
        
        return info
    except Exception as e:
        print(f"Error getting thread info: {e}")
        return {}

# =====================
# PROCESS APPROVAL
# =====================

def process_approved_draft(draft_file: Path, approval_action: str) -> bool:
    """
    Process approved draft and send to client
    
    Args:
        draft_file: Path to draft JSON file
        approval_action: "approve" or "skip"
    """
    
    if approval_action == "skip":
        print(f"Skipping {draft_file.stem}")
        log_approval(draft_file.stem, "skip", "User rejected")
        return True
    
    if approval_action != "approve":
        return False
    
    try:
        # Load draft
        draft_data = json.loads(draft_file.read_text(encoding="utf-8"))
        draft_response = draft_data.get("draft_response_PL", "")
        
        if not draft_response:
            print(f"No response in {draft_file}")
            return False
        
        # Find original email metadata
        email_id = draft_file.stem.replace("_draft", "")
        meta_file = CASES_INBOX / f"{email_id}.meta.json"
        
        if not meta_file.exists():
            print(f"Meta file not found: {meta_file}")
            return False
        
        # Extract recipient and subject
        meta_data = json.loads(meta_file.read_text(encoding="utf-8"))
        to_email = meta_data.get("from", "")
        subject = meta_data.get("subject", "Odpowiedź")
        gmail_message_id = meta_data.get("gmail_id", "")
        
        if not to_email:
            print(f"No recipient email found in {meta_file}")
            return False
        
        # Send email
        if not GMAIL_AVAILABLE:
            print("Gmail API not available, saving for manual send")
            save_pending_send(email_id, to_email, subject, draft_response)
            return True
        
        service = get_gmail_service()
        
        if send_email_reply(service, gmail_message_id, to_email, subject, draft_response):
            # Save sent response
            save_sent_response(email_id, to_email, subject, draft_response)
            log_approval(email_id, "approved_and_sent", f"Sent to {to_email}")
            
            # Move meta file to processed
            archive_path = CASES_INBOX / "_PROCESSED" / f"{email_id}.meta.json"
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            meta_file.rename(archive_path)
            
            print(f"✅ Sent response to {to_email}")
            return True
        else:
            print(f"Failed to send email to {to_email}")
            log_approval(email_id, "send_failed", "Gmail API error")
            return False
    
    except Exception as e:
        print(f"Error processing approval: {e}")
        return False

def save_sent_response(email_id: str, to: str, subject: str, body: str):
    """Archive sent response"""
    SENT_DIR.mkdir(parents=True, exist_ok=True)
    
    sent_file = SENT_DIR / f"{email_id}_sent.json"
    sent_file.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "to": to,
        "subject": subject,
        "body": body
    }, indent=2, ensure_ascii=False), encoding="utf-8")

def save_pending_send(email_id: str, to: str, subject: str, body: str):
    """Save response for manual sending (if Gmail API not available)"""
    SENT_DIR.mkdir(parents=True, exist_ok=True)
    
    pending_file = SENT_DIR / f"{email_id}_pending.json"
    pending_file.write_text(json.dumps({
        "status": "pending",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "to": to,
        "subject": subject,
        "body": body
    }, indent=2, ensure_ascii=False), encoding="utf-8")

def log_approval(email_id: str, action: str, note: str):
    """Log approval action"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(APPROVAL_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            email_id,
            action,
            note
        ])

# =====================
# MAIN
# =====================

def main():
    """Interactive approval mode (manual testing)"""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python gmail_send_reply.py <email_id> <approve|skip>")
        print("\nExample:")
        print("  python gmail_send_reply.py 20260203__abc123 approve")
        sys.exit(1)
    
    email_id = sys.argv[1]
    action = sys.argv[2]
    
    draft_file = DRAFTS_DIR / f"{email_id}_draft.json"
    
    if not draft_file.exists():
        print(f"Draft file not found: {draft_file}")
        sys.exit(1)
    
    if process_approved_draft(draft_file, action):
        print("✅ Processed successfully")
    else:
        print("❌ Processing failed")

if __name__ == "__main__":
    main()

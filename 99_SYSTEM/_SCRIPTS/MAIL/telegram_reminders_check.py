#!/usr/bin/env python3
"""
Check 2-hour reminders for telegram drafts.
Run this periodically (e.g., every 30 minutes) to send reminders.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib import request, parse

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
STATE_FILE = ROOT / "00_INBOX" / "_ROUTER_LOGS" / "telegram_reminders.json"
DRAFTS_DIR = ROOT / "00_INBOX" / "_DRAFTS"

SECRETS_DIR = ROOT / "99_SYSTEM" / "_SECRETS"
TOKEN_FILE = SECRETS_DIR / "telegram_bot_token.txt"
CHAT_FILE = SECRETS_DIR / "telegram_chat_id.txt"


def send_telegram(token: str, chat_id: str, text: str):
    """Send Telegram message"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        with request.urlopen(request.Request(url, data=data), timeout=20) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"Telegram error: {e}")
        raise


def load_reminders() -> dict:
    """Load reminder state"""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    return {"pending": {}}  # {draft_filename: created_timestamp}


def save_reminders(data: dict):
    """Save reminder state"""
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def main():
    # Load tokens
    token = TOKEN_FILE.read_text().strip()
    chat_id = CHAT_FILE.read_text().strip()
    
    # Load reminders state
    reminders = load_reminders()
    pending = reminders.get("pending", {})
    
    # Check each draft
    to_remove = []
    now = datetime.now(timezone.utc)
    
    for draft_file, created_str in list(pending.items()):
        draft_path = DRAFTS_DIR / draft_file
        
        # If draft deleted → remove from pending
        if not draft_path.exists():
            to_remove.append(draft_file)
            continue
        
        # Parse created time
        try:
            created = datetime.fromisoformat(created_str)
        except:
            to_remove.append(draft_file)
            continue
        
        # Check if 2+ hours passed
        elapsed = now - created
        if elapsed >= timedelta(hours=2):
            # Send reminder
            subject = draft_file.replace('_draft.txt', '').replace('_', ' ')
            msg = f"""⏰ REMINDER (2 hours):
            
Draft still pending:
{subject}

Action:
- ✏️ Edit & send reply
- 🗑️ Delete draft (closes topic + stops reminders)

Draft: {draft_path}"""
            
            try:
                send_telegram(token, chat_id, msg)
                print(f"[REMINDER] Sent for: {draft_file}")
                # Update timestamp to avoid re-sending
                created = datetime.now(timezone.utc)
                pending[draft_file] = created.isoformat()
            except Exception as e:
                print(f"[ERROR] Failed to send reminder for {draft_file}: {e}")
    
    # Remove deleted drafts from state
    for draft_file in to_remove:
        del pending[draft_file]
        print(f"[CLEANUP] Removed from reminders: {draft_file}")
    
    # Save updated state
    reminders["pending"] = pending
    save_reminders(reminders)
    
    print(f"Reminders check done. Pending: {len(pending)}")


if __name__ == "__main__":
    main()

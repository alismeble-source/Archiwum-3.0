#!/usr/bin/env python3
"""
Telegram Approval Listener
Monitors Telegram messages for reactions (✅/❌) and triggers email sending.

Workflow:
1. ai_responder.py sends draft with unique email_id
2. You react with ✅ (approve) or ❌ (skip)
3. This script detects reaction
4. Calls gmail_send_reply.py to send or skip
"""

import json
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from urllib import request, parse

# =====================
# CONFIG
# =====================

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")

SECRETS_DIR = ROOT / "99_SYSTEM" / "_SECRETS"
TELEGRAM_TOKEN_FILE = SECRETS_DIR / "telegram_bot_token.txt"
TELEGRAM_CHAT_FILE = SECRETS_DIR / "telegram_chat_id.txt"

APPROVAL_STATE_FILE = ROOT / "00_INBOX" / "_ROUTER_LOGS" / "telegram_approval_state.json"
LOG_DIR = ROOT / "00_INBOX" / "_ROUTER_LOGS"

MAIL_SCRIPTS = ROOT / "99_SYSTEM" / "_SCRIPTS" / "MAIL"

DRY_RUN = False
AUTO_SEND = False  # ⚠️ Set to True to auto-send emails on ✅ reaction

# =====================
# TELEGRAM
# =====================

def get_telegram_credentials() -> tuple:
    """Load Telegram credentials"""
    token = TELEGRAM_TOKEN_FILE.read_text(encoding="utf-8").strip()
    chat_id = TELEGRAM_CHAT_FILE.read_text(encoding="utf-8").strip()
    return token, chat_id

def get_telegram_updates(token: str, offset: int = 0) -> list:
    """Get updates from Telegram bot"""
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = parse.urlencode({"offset": offset, "allowed_updates": ["message_reaction"]})
        req = request.Request(f"{url}?{params}")
        
        with request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
            if data.get("ok"):
                return data.get("result", [])
            else:
                print(f"Telegram error: {data.get('description')}")
                return []
    except Exception as e:
        print(f"Error getting Telegram updates: {e}")
        return []

def parse_email_id_from_message(message: str) -> str:
    """Extract email_id from message (format: Original email ID: 20260203__abc123)"""
    match = re.search(r"Original email ID: (\S+)", message)
    if match:
        return match.group(1)
    return None

def get_message_reactions(update: dict) -> list:
    """Extract emoji reactions from update"""
    if "message_reaction" in update:
        reactions = update["message_reaction"].get("new_reaction", [])
        return [r.get("emoji") for r in reactions if r.get("emoji")]
    return []

def load_approval_state() -> dict:
    """Load state of processed approvals"""
    if not APPROVAL_STATE_FILE.exists():
        return {}
    
    try:
        return json.loads(APPROVAL_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_approval_state(state: dict):
    """Save approval state"""
    APPROVAL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    APPROVAL_STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

# =====================
# PROCESS REACTIONS
# =====================

def process_reaction(email_id: str, emoji: str, state: dict) -> bool:
    """Process reaction: ✅ approve, ❌ skip"""
    
    state_key = f"{email_id}_{emoji}"
    
    # Check if already processed
    if state_key in state:
        print(f"Already processed: {email_id} with {emoji}")
        return False
    
    # Map emoji to action
    if emoji == "✅":
        action = "approve"
    elif emoji == "❌":
        action = "skip"
    else:
        print(f"Unknown emoji: {emoji}")
        return False
    
    print(f"Processing: {email_id} → {action}")
    
    # Check AUTO_SEND flag
    if not AUTO_SEND:
        print(f"⚠️ AUTO_SEND disabled. Reaction logged but NOT sending email.")
        print(f"   To enable auto-send: Set AUTO_SEND = True in script config")
        state[state_key] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "status": "logged_only"
        }
        return True
    
    # Call gmail_send_reply.py
    script_path = MAIL_SCRIPTS / "gmail_send_reply.py"
    
    if not script_path.exists():
        print(f"Script not found: {script_path}")
        return False
    
    if DRY_RUN:
        print(f"[DRY_RUN] Would execute: python {script_path} {email_id} {action}")
        state[state_key] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "status": "dry_run"
        }
    else:
        try:
            result = subprocess.run(
                ["python", str(script_path), email_id, action],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print(f"✅ Success: {email_id} {action}")
                state[state_key] = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": action,
                    "status": "success"
                }
            else:
                print(f"❌ Failed: {result.stderr}")
                state[state_key] = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": action,
                    "status": "error",
                    "error": result.stderr[:200]
                }
        except Exception as e:
            print(f"Error executing script: {e}")
            state[state_key] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "status": "error",
                "error": str(e)[:200]
            }
    
    return True

def main():
    """Main listener loop"""
    
    token, chat_id = get_telegram_credentials()
    state = load_approval_state()
    
    print(f"Starting Telegram approval listener (chat_id: {chat_id})")
    print("Monitoring for ✅ (approve) and ❌ (skip) reactions...")
    print()
    
    offset = 0
    
    while True:
        try:
            updates = get_telegram_updates(token, offset)
            
            if not updates:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] No updates")
            else:
                for update in updates:
                    update_id = update.get("update_id")
                    offset = max(offset, update_id + 1)
                    
                    # Check for message reactions
                    reactions = get_message_reactions(update)
                    
                    if reactions:
                        # Get message to extract email_id
                        message = update.get("message", {})
                        text = message.get("text", "")
                        email_id = parse_email_id_from_message(text)
                        
                        if email_id:
                            for emoji in reactions:
                                process_reaction(email_id, emoji, state)
                        else:
                            print(f"Could not extract email_id from message")
            
            # Save state
            save_approval_state(state)
            
            # Sleep before next check (Telegram long polling)
            import time
            time.sleep(5)
        
        except KeyboardInterrupt:
            print("\nListener stopped")
            save_approval_state(state)
            break
        except Exception as e:
            print(f"Error in listener: {e}")
            import time
            time.sleep(5)

if __name__ == "__main__":
    main()

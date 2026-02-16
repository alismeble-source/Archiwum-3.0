#!/usr/bin/env python3
"""
AI Auto-Responder for AlisMeble
Analyzes client inquiries and generates draft responses based on business philosophy.

Workflow:
1. Read email from CASES/_INBOX (or routed folders)
2. Classify: tire-kicker vs serious client
3. Generate draft response per AI_RESPONDER_PROMPT
4. Send draft to Telegram for approval
5. After approval: queue for sending to client
"""

import json
import re
import csv
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

# AI/LLM integration
try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

# PDF extraction
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# =====================
# CONFIG
# =====================

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")

CASES_INBOX = ROOT / "CASES" / "_INBOX"
RESPONDER_QUEUE = ROOT / "00_INBOX" / "_RESPONDER_QUEUE"
DRAFTS_DIR = ROOT / "00_INBOX" / "_DRAFTS"
LOG_DIR = ROOT / "00_INBOX" / "_ROUTER_LOGS"

SECRETS_DIR = ROOT / "99_SYSTEM" / "_SECRETS"
CLAUDE_KEY_FILE = SECRETS_DIR / "claude_api_key.txt"
TELEGRAM_TOKEN_FILE = SECRETS_DIR / "telegram_bot_token.txt"
TELEGRAM_CHAT_FILE = SECRETS_DIR / "telegram_chat_id.txt"

RESPONDER_PROMPT_FILE = ROOT / "CORE" / "AI_RESPONDER_PROMPT.md"
RESPONDER_LOG = LOG_DIR / "responder_log.csv"

STATE_FILE = RESPONDER_QUEUE / "state.json"

# Behavior
DRY_RUN = False  # set True to test without sending
MAX_EMAILS_PER_RUN = 20

# =====================
# HELPERS
# =====================

def ensure_dirs():
    for p in [RESPONDER_QUEUE, DRAFTS_DIR, LOG_DIR]:
        p.mkdir(parents=True, exist_ok=True)

def load_prompt() -> str:
    """Load AI responder system prompt"""
    if not RESPONDER_PROMPT_FILE.exists():
        raise FileNotFoundError(f"Prompt file not found: {RESPONDER_PROMPT_FILE}")
    return RESPONDER_PROMPT_FILE.read_text(encoding="utf-8")

def get_claude_api_key() -> str:
    """Load Claude API key from secrets"""
    if not CLAUDE_KEY_FILE.exists():
        raise FileNotFoundError(f"Claude key file not found: {CLAUDE_KEY_FILE}")
    return CLAUDE_KEY_FILE.read_text(encoding="utf-8").strip()

def get_telegram_credentials() -> Tuple[str, str]:
    """Load Telegram bot token and chat ID"""
    if not TELEGRAM_TOKEN_FILE.exists() or not TELEGRAM_CHAT_FILE.exists():
        raise FileNotFoundError("Telegram credentials missing")
    token = TELEGRAM_TOKEN_FILE.read_text(encoding="utf-8").strip()
    chat_id = TELEGRAM_CHAT_FILE.read_text(encoding="utf-8").strip()
    return token, chat_id

def extract_text_from_email(meta_json: Path) -> Tuple[str, str, str]:
    """Extract subject, from, and body from .meta.json"""
    try:
        meta = json.loads(meta_json.read_text(encoding="utf-8"))
        subject = meta.get("subject", "No subject")
        from_addr = meta.get("from", "Unknown sender")
        body = meta.get("body", "")
        return subject, from_addr, body
    except Exception as e:
        return f"Error: {e}", "", ""

def extract_text_from_attachments(meta_json: Path, max_chars: int = 2000) -> str:
    """Extract text from PDF attachments if present"""
    if not PDF_AVAILABLE:
        return ""
    
    try:
        meta = json.loads(meta_json.read_text(encoding="utf-8"))
        attachment_files = meta.get("attachment_files", [])
        
        text = ""
        for filename in attachment_files[:2]:  # Max 2 files
            if filename.lower().endswith(".pdf"):
                pdf_path = meta_json.parent / filename
                if pdf_path.exists():
                    with pdfplumber.open(pdf_path) as pdf:
                        for page in pdf.pages[:1]:  # First page only
                            text += page.extract_text() or ""
                            if len(text) > max_chars:
                                return text[:max_chars]
        return text[:max_chars]
    except Exception:
        return ""

def generate_ai_response(client_message: str, prompt: str) -> Dict:
    """
    Call Claude API to generate response draft
    Returns: {
        "client_type": "tire_kicker" | "serious",
        "confidence": 0.0-1.0,
        "reasoning": "...",
        "recommended_action": "send_range" | "send_detailed" | "ignore",
        "draft_response_PL": "...",
        "estimated_budget": "...",
        "next_step": "..."
    }
    """
    if not CLAUDE_AVAILABLE:
        return {
            "client_type": "unknown",
            "confidence": 0.0,
            "reasoning": "Claude not available",
            "recommended_action": "manual_review",
            "draft_response_PL": "[Manual review required - Claude SDK not installed]",
            "estimated_budget": "unknown",
            "next_step": "Review in Telegram"
        }
    
    try:
        api_key = get_claude_api_key()
        client = anthropic.Anthropic(api_key=api_key)
        
        system_message = prompt
        user_message = f"Analyze this client inquiry:\n\n{client_message}"
        
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1500,
            messages=[
                {"role": "user", "content": user_message}
            ],
            system=system_message
        )
        
        # Parse response as JSON
        response_text = response.content[0].text
        
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result
        else:
            # Fallback: return as text
            return {
                "client_type": "unknown",
                "confidence": 0.5,
                "reasoning": "Could not parse structured response",
                "recommended_action": "manual_review",
                "draft_response_PL": response_text,
                "estimated_budget": "unknown",
                "next_step": "Review in Telegram"
            }
    except Exception as e:
        return {
            "client_type": "error",
            "confidence": 0.0,
            "reasoning": f"API error: {str(e)}",
            "recommended_action": "manual_review",
            "draft_response_PL": f"[Error generating response: {str(e)}]",
            "estimated_budget": "unknown",
            "next_step": "Review in Telegram"
        }

def send_telegram_notification(token: str, chat_id: str, message: str, parse_mode: str = "HTML") -> bool:
    """Send message to Telegram"""
    if DRY_RUN:
        print(f"[DRY_RUN] Would send to Telegram:\n{message}")
        return True
    
    try:
        from urllib import request, parse
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = parse.urlencode({
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode
        }).encode("utf-8")
        
        req = request.Request(url, data=data)
        with request.urlopen(req, timeout=10) as response:
            return response.status == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def log_responder_action(email_from: str, subject: str, action: str, client_type: str, confidence: float):
    """Log action to CSV"""
    RESPONDER_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    with open(RESPONDER_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            email_from,
            subject,
            action,
            client_type,
            confidence
        ])

# =====================
# MAIN WORKFLOW
# =====================

def process_email(meta_json_path: Path, prompt: str) -> bool:
    """
    Process single email:
    1. Extract content
    2. Generate AI response
    3. Send draft to Telegram
    4. Queue for approval
    """
    
    try:
        # Extract email content
        subject, from_addr, body = extract_text_from_email(meta_json_path)
        attachment_text = extract_text_from_attachments(meta_json_path)
        
        # Combine for AI analysis
        full_message = f"""
Subject: {subject}
From: {from_addr}

Body:
{body}

Attachments content (if any):
{attachment_text}
"""
        
        # Generate AI response
        ai_result = generate_ai_response(full_message, prompt)
        
        # Log the action
        log_responder_action(
            from_addr,
            subject,
            ai_result.get("recommended_action", "unknown"),
            ai_result.get("client_type", "unknown"),
            ai_result.get("confidence", 0.0)
        )
        
        # Prepare Telegram notification
        telegram_message = f"""
🤖 <b>New Client Inquiry</b>

<b>From:</b> {from_addr}
<b>Subject:</b> {subject}

<b>Classification:</b> {ai_result.get('client_type')} (confidence: {ai_result.get('confidence', 0.0):.1%})

<b>Reasoning:</b> {ai_result.get('reasoning', 'N/A')}

<b>Budget estimate:</b> {ai_result.get('estimated_budget', 'unknown')}

<b>Draft Response:</b>
{ai_result.get('draft_response_PL', '[No response generated]')}

<b>Next step:</b> {ai_result.get('next_step', 'Manual review')}

---
React with ✅ to approve and send, or ❌ to skip.
Original email ID: {meta_json_path.stem}
"""
        
        # Send to Telegram
        token, chat_id = get_telegram_credentials()
        send_telegram_notification(token, chat_id, telegram_message, parse_mode="HTML")
        
        # Save draft for reference
        draft_file = DRAFTS_DIR / f"{meta_json_path.stem}_draft.json"
        draft_file.write_text(json.dumps(ai_result, indent=2, ensure_ascii=False), encoding="utf-8")
        
        return True
    
    except Exception as e:
        print(f"Error processing {meta_json_path}: {e}")
        return False

def main():
    """Main responder loop"""
    ensure_dirs()
    
    # Load prompt
    prompt = load_prompt()
    
    # Find unprocessed emails in CASES/_INBOX (look for .meta.json files)
    meta_files = sorted(CASES_INBOX.glob("*.meta.json"))[:MAX_EMAILS_PER_RUN]
    
    if not meta_files:
        print("No emails to process")
        return
    
    print(f"Processing {len(meta_files)} emails...")
    
    processed = 0
    for meta_file in meta_files:
        if process_email(meta_file, prompt):
            processed += 1
    
    print(f"Processed {processed}/{len(meta_files)} emails")

if __name__ == "__main__":
    main()

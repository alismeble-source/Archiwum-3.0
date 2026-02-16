#!/usr/bin/env python3
"""
Sync Gmail emails to Google Calendar:
- Major/minor projects (wyceny) → deadline reminders
- High/medium risk → follow-up reminders
- Faktury → payment deadline reminders
"""

import csv
import json
import re
import time
import os
from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
ROUTER_LOG = ROOT / "00_INBOX" / "_ROUTER_LOGS" / "router_log.csv"
SECRETS_DIR = ROOT / "99_SYSTEM" / "_SECRETS" / "gmail"
TOKEN_FILE = SECRETS_DIR / "token.json"
CREDS_FILE = SECRETS_DIR / "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/calendar']

DEST_DIRS = {
    "KLIENTS": ROOT / "02_KLIENCI" / "_INBOX",
    "FIRMA": ROOT / "01_FIRMA",
    "CAR": ROOT / "04_CAR",
    "REVIEW": ROOT / "_REVIEW",
}


def get_calendar_service(max_retries: int = 3):
    """OAuth2 flow for Google Calendar API (with retry logic)"""
    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception as e:
            print(f"  Warning: Failed to load token: {e}")
            creds = None
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"  Warning: Token refresh failed: {e}")
                creds = None
        
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        
        tmp_token = TOKEN_FILE.parent / f"{TOKEN_FILE.name}.tmp"
        try:
            tmp_token.write_text(creds.to_json(), encoding='utf-8')
            os.replace(str(tmp_token), str(TOKEN_FILE))
        except Exception as e:
            print(f"  Warning: Failed to save token: {e}")
    
    for attempt in range(max_retries):
        try:
            service = build('calendar', 'v3', credentials=creds, cache_discovery=False)
            return service
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"  Retry {attempt+1}/{max_retries}: {type(e).__name__}")
                time.sleep(2 ** attempt)
            else:
                raise


def parse_deadline(subject: str, body_preview: str) -> datetime | None:
    """Extract deadline from email text (Polish format)"""
    text = f"{subject} {body_preview}".lower()
    
    # Patterns: "do 15.02", "termin: 20 lutego", "deadline 2026-02-15"
    patterns = [
        r'(?:do|termin|deadline|płatność do)[:\s]+(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{4}))?',
        r'(\d{1,2})\s+(stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia)(?:\s+(\d{4}))?',
    ]
    
    months_pl = {
        'stycznia': 1, 'lutego': 2, 'marca': 3, 'kwietnia': 4, 'maja': 5, 'czerwca': 6,
        'lipca': 7, 'sierpnia': 8, 'września': 9, 'października': 10, 'listopada': 11, 'grudnia': 12
    }
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            if len(groups) == 3 and groups[1] in months_pl:
                # "15 lutego 2026"
                day = int(groups[0])
                month = months_pl[groups[1]]
                year = int(groups[2]) if groups[2] else datetime.now().year
            else:
                # "15.02.2026" or "15.02"
                day = int(groups[0])
                month = int(groups[1])
                year = int(groups[2]) if groups[2] else datetime.now().year
            
            try:
                return datetime(year, month, day)
            except ValueError:
                continue
    
    return None


def load_meta(meta_name: str, decision: str) -> dict:
    """Load metadata from .meta.json file"""
    base = DEST_DIRS.get(decision)
    if not base:
        return {}
    
    meta_path = base / meta_name
    if not meta_path.exists():
        return {}
    
    try:
        return json.loads(meta_path.read_text(encoding='utf-8'))
    except:
        return {}


def create_or_update_event(service, email_id: str, title: str, due_date: datetime, 
                           event_type: str, notes: str = "", max_retries: int = 3):
    """Create or update calendar event (with retry logic)"""
    
    event_body = {
        'summary': f"[{event_type}] {title[:100]}",
        'description': f"Email ID: {email_id}\n{notes}",
        'start': {'date': due_date.strftime('%Y-%m-%d')},
        'end': {'date': due_date.strftime('%Y-%m-%d')},
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},
                {'method': 'popup', 'minutes': 60},
            ],
        },
    }
    
    events = None
    for attempt in range(max_retries):
        try:
            events = service.events().list(
                calendarId='primary',
                q=email_id,
                singleEvents=True,
                maxResults=1
            ).execute()
            break
        except HttpError as e:
            if attempt < max_retries - 1:
                print(f"  Retry list {attempt+1}/{max_retries}: {e.resp.status}")
                time.sleep(2 ** attempt)
            else:
                print(f"  Error: Failed to list events: {e}")
                return 'failed'
    
    if events and events.get('items'):
        event_id = events['items'][0]['id']
        for attempt in range(max_retries):
            try:
                service.events().update(
                    calendarId='primary',
                    eventId=event_id,
                    body=event_body
                ).execute()
                return 'updated'
            except HttpError as e:
                if attempt < max_retries - 1:
                    print(f"  Retry update {attempt+1}/{max_retries}: {e.resp.status}")
                    time.sleep(2 ** attempt)
                else:
                    print(f"  Error: Failed to update event: {e}")
                    return 'failed'
    else:
        for attempt in range(max_retries):
            try:
                service.events().insert(calendarId='primary', body=event_body).execute()
                return 'created'
            except HttpError as e:
                if attempt < max_retries - 1:
                    print(f"  Retry insert {attempt+1}/{max_retries}: {e.resp.status}")
                    time.sleep(2 ** attempt)
                else:
                    print(f"  Error: Failed to create event: {e}")
                    return 'failed'
    
    return 'failed'


def main():
    if not ROUTER_LOG.exists():
        print(f"Router log not found: {ROUTER_LOG}")
        return
    
    print("Initializing Google Calendar service...")
    try:
        service = get_calendar_service()
    except Exception as e:
        print(f"ERROR: Failed to initialize Calendar service: {e}")
        return
    
    try:
        with ROUTER_LOG.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"ERROR: Failed to read router log: {e}")
        return
    
    if not rows:
        print("No entries in router log")
        return
    
    active_email_ids = set()
    created = 0
    updated = 0
    skipped = 0
    
    for row in rows[-100:]:  # Last 100 entries
        project_type = row.get('project_type', '')
        payment_risk = row.get('payment_risk', '')
        decision = row.get('decision', '')
        subject = row.get('subject', '')
        meta_name = row.get('meta', '')
        from_addr = row.get('from', '')
        ts_utc = row.get('ts_utc', '')
        
        # Filter: only major/minor projects OR high/medium risk
        if project_type not in ('major', 'minor') and payment_risk not in ('high', 'medium'):
            continue
        
        # Load metadata
        meta = load_meta(meta_name, decision)
        body_preview = meta.get('body_preview', '')[:500]
        email_id = meta.get('gmail_id', ts_utc)
        active_email_ids.add(email_id)
        
        # Try to parse deadline
        deadline = parse_deadline(subject, body_preview)
        
        if not deadline:
            # Default: 7 days from email date (for high-risk follow-ups)
            if payment_risk in ('high', 'medium'):
                try:
                    email_date = datetime.fromisoformat(ts_utc.replace('Z', '+00:00'))
                    deadline = email_date + timedelta(days=7)
                except:
                    skipped += 1
                    continue
            else:
                skipped += 1
                continue
        
        # Determine event type
        if 'faktura' in subject.lower() or 'invoice' in subject.lower():
            event_type = 'PAYMENT'
        elif payment_risk in ('high', 'medium'):
            event_type = 'FOLLOW-UP'
        else:
            event_type = 'WYCENA'
        
        # Create/update calendar event
        notes = f"From: {from_addr}\nRisk: {payment_risk}\nType: {project_type}"
        
        status = create_or_update_event(service, email_id, subject, deadline, event_type, notes)
        
        if status == 'created':
            created += 1
        elif status == 'updated':
            updated += 1
    
    # CLEANUP: Delete old events (created by this script, no longer in router log)
    deleted = 0
    cutoff_date = (datetime.now() - timedelta(days=7)).isoformat() + 'Z'
    
    events = service.events().list(
        calendarId='primary',
        timeMin=cutoff_date,
        maxResults=100,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    for event in events.get('items', []):
        description = event.get('description', '')
        summary = event.get('summary', '')
        
        # Only delete events created by this script (contain "Email ID:")
        if 'Email ID:' not in description:
            continue
        
        # Extract email ID from description
        match = re.search(r'Email ID:\s*(\S+)', description)
        if not match:
            continue
        
        event_email_id = match.group(1)
        
        # Delete if not in active emails OR event is for old wyceny/follow-ups
        if event_email_id not in active_email_ids:
            # Only delete WYCENA/FOLLOW-UP events (keep PAYMENT events from CSV)
            if any(tag in summary for tag in ['[WYCENA]', '[FOLLOW-UP]']):
                service.events().delete(calendarId='primary', eventId=event['id']).execute()
                deleted += 1
    
    print(f"DONE. created={created} updated={updated} skipped={skipped} deleted={deleted}")


if __name__ == "__main__":
    main()

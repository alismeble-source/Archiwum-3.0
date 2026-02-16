#!/usr/bin/env python3
"""
Delete recurring Google Calendar events (Focus time, Lunch, etc.)
"""

from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
SECRETS_DIR = ROOT / "99_SYSTEM" / "_SECRETS" / "gmail"
TOKEN_FILE = SECRETS_DIR / "token.json"
CREDS_FILE = SECRETS_DIR / "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Patterns to delete (case-insensitive)
DELETE_PATTERNS = [
    'focus time',
    'lunch',
    'обед',
    'фокус'
]


def get_calendar_service():
    """OAuth2 flow for Google Calendar API"""
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding='utf-8')
    
    return build('calendar', 'v3', credentials=creds)


def main():
    service = get_calendar_service()
    
    # Get all events (including recurring)
    events = service.events().list(
        calendarId='primary',
        maxResults=250,
        singleEvents=False  # Important: get recurring event masters
    ).execute()
    
    deleted_count = 0
    
    for event in events.get('items', []):
        summary = event.get('summary', '').lower()
        event_id = event.get('id')
        recurrence = event.get('recurrence', [])
        
        # Check if summary matches any delete pattern
        should_delete = any(pattern in summary for pattern in DELETE_PATTERNS)
        
        if should_delete:
            try:
                # Delete recurring event (master)
                service.events().delete(calendarId='primary', eventId=event_id).execute()
                # Safe print (ASCII only)
                title = ''.join(c if ord(c) < 128 else '?' for c in event.get('summary', 'Unknown'))
                print(f"[OK] Deleted: {title}")
                deleted_count += 1
            except Exception as e:
                title = ''.join(c if ord(c) < 128 else '?' for c in event.get('summary', 'Unknown'))
                print(f"[FAIL] {title}: {str(e)[:50]}")
    
    print(f"\nTotal deleted: {deleted_count} recurring events")


if __name__ == "__main__":
    main()

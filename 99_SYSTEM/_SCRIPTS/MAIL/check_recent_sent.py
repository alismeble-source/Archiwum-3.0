"""Quick check: recent Gmail sent emails"""
from pathlib import Path
import sys

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
sys.path.insert(0, str(ROOT / "99_SYSTEM" / "_SCRIPTS" / "MAIL"))

try:
    from gmail_send_reply import build_gmail_service
    
    service = build_gmail_service()
    result = service.users().messages().list(
        userId='me',
        labelIds=['SENT'],
        maxResults=10
    ).execute()
    
    messages = result.get('messages', [])
    print(f"\nLast {len(messages)} sent emails:")
    print("=" * 80)
    
    for msg in messages:
        full = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='metadata',
            metadataHeaders=['From', 'To', 'Subject', 'Date']
        ).execute()
        
        headers = {h['name']: h['value'] for h in full['payload']['headers']}
        
        print(f"\nDate: {headers.get('Date')}")
        print(f"To: {headers.get('To')}")
        print(f"Subject: {headers.get('Subject')}")
        print("-" * 80)
        
except Exception as e:
    print(f"Error: {e}")

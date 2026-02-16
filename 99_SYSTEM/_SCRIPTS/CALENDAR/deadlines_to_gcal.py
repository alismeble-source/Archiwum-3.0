import csv, os, hashlib, datetime as dt
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
CSV_PATH = ROOT / r"FINANCE\_CALENDAR\DEADLINES.csv"
STATE_DIR = ROOT / r"FINANCE\_CALENDAR\_STATE"
STATE_DIR.mkdir(parents=True, exist_ok=True)

# Put your OAuth client secret JSON here (downloaded from Google Cloud Console)
CLIENT_SECRET_JSON = Path(os.environ.get("GCAL_CLIENT_SECRET", str(ROOT / r"99_SYSTEM\_SECRETS\credentials.json")))
TOKEN_JSON = STATE_DIR / "token.json"

# Calendar ID: "primary" or конкретный календарь
CALENDAR_ID = os.environ.get("GCAL_CALENDAR_ID", "primary")

def stable_uid(type_, title, due_date, case_id):
    s = f"{type_}|{title}|{due_date}|{case_id}".encode("utf-8")
    return hashlib.sha1(s).hexdigest()  # stable

def get_service():
    creds = None
    if TOKEN_JSON.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_JSON), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_JSON.exists():
                raise FileNotFoundError(f"Missing client secret JSON: {CLIENT_SECRET_JSON}")
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_JSON), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_JSON.write_text(creds.to_json(), encoding="utf-8")
    return build("calendar", "v3", credentials=creds)

def parse_date(s):
    # YYYY-MM-DD
    return dt.datetime.strptime(s.strip(), "%Y-%m-%d").date()

def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing CSV: {CSV_PATH}")

    service = get_service()

    created = updated = skipped = 0

    with CSV_PATH.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for r in rows:
        type_ = (r.get("TYPE") or "").strip()
        title = (r.get("TITLE") or "").strip()
        due   = (r.get("DUE_DATE") or "").strip()
        amt   = (r.get("AMOUNT") or "").strip()
        filep = (r.get("FILE_PATH") or "").strip()
        case  = (r.get("CASE_ID") or "").strip()
        notes = (r.get("NOTES") or "").strip()

        if not type_ or not title or not due:
            skipped += 1
            continue

        d = parse_date(due)
        uid = stable_uid(type_, title, due, case)

        summary = f"{type_} | {title}"
        if amt and amt != "0":
            summary += f" | {amt} PLN"

        description = "\n".join([
            f"TYPE: {type_}",
            f"DUE: {due}",
            f"AMOUNT: {amt}",
            f"CASE: {case}",
            f"FILE: {filep}",
            f"NOTES: {notes}",
            f"UID: {uid}",
        ])

        # We store per-uid event id mapping to avoid duplicates
        map_file = STATE_DIR / f"map_{uid}.txt"
        event_id = map_file.read_text(encoding="utf-8").strip() if map_file.exists() else ""

        body = {
            "summary": summary,
            "description": description,
            "start": {"date": d.isoformat()},
            "end": {"date": d.isoformat()},
            # Reminders: one day (email) and one hour (popup)
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 1440},
                    {"method": "popup", "minutes": 60}
                ]
            },
        }

        try:
            if event_id:
                # update existing
                service.events().update(calendarId=CALENDAR_ID, eventId=event_id, body=body).execute()
                updated += 1
            else:
                ev = service.events().insert(calendarId=CALENDAR_ID, body=body).execute()
                event_id = ev["id"]
                map_file.write_text(event_id, encoding="utf-8")
                created += 1
        except Exception as e:
            # If stored event_id not found anymore -> recreate
            if "Not Found" in str(e) or "404" in str(e):
                ev = service.events().insert(calendarId=CALENDAR_ID, body=body).execute()
                event_id = ev["id"]
                map_file.write_text(event_id, encoding="utf-8")
                created += 1
            else:
                raise

    print(f"DONE. created={created} updated={updated} skipped={skipped} csv={CSV_PATH}")

if __name__ == "__main__":
    main()


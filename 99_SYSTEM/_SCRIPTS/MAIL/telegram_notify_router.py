"""
Send Telegram notifications with AI-based draft replies after routing.
Reads router_log.csv and sends only new entries (state file).
"""

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, parse

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
LOG_CSV = ROOT / "00_INBOX" / "_ROUTER_LOGS" / "router_log.csv"
STATE_FILE = ROOT / "00_INBOX" / "_ROUTER_LOGS" / "telegram_notify_state.json"
REMINDERS_FILE = ROOT / "00_INBOX" / "_ROUTER_LOGS" / "telegram_reminders.json"  # Persistent reminders
DRAFTS_DIR = ROOT / "00_INBOX" / "_DRAFTS"

SECRETS_DIR = ROOT / "99_SYSTEM" / "_SECRETS"
TOKEN_FILE = SECRETS_DIR / "telegram_bot_token.txt"
CHAT_FILE = SECRETS_DIR / "telegram_chat_id.txt"

CASES_DIR = ROOT / "CASES"
DEST_DIRS = {
    "KLIENTS": CASES_DIR / "01_KLIENTS" / "_INBOX",
    "FIRMA": CASES_DIR / "02_FIRMA" / "_INBOX",
    "CAR": CASES_DIR / "03_CAR" / "_INBOX",
    "REVIEW": CASES_DIR / "_REVIEW",
}


def slugify(text: str, max_len: int = 60) -> str:
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9\-_. ]+", "", t)
    t = re.sub(r"\s+", "_", t).strip("_")
    return t[:max_len] if t else "no_subject"


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"sent": set(), "reminders": {}}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return {
            "sent": set(data.get("sent", [])),
            "reminders": data.get("reminders", {}),
        }
    except Exception:
        return {"sent": set(), "reminders": {}}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(
            {
                "sent": sorted(state.get("sent", set())),
                "reminders": state.get("reminders", {}),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def read_secret(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def send_telegram(token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = request.Request(url, data=data)
    with request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8")


def find_meta(meta_name: str, decision: str) -> Path | None:
    base = DEST_DIRS.get(decision)
    if not base:
        return None
    meta_path = base / meta_name
    if meta_path.exists():
        return meta_path
    return None


def build_draft(subject: str, from_addr: str, evaluation: dict) -> str:
    project_type = evaluation.get("project_type", "unknown")
    quality = evaluation.get("quality", "unknown")

    if project_type == "administrative":
        return (
            "Dzień dobry,\n"
            "potwierdzam otrzymanie wiadomości.\n"
            "W razie potrzeby doprecyzuję dane.\n\n"
            "Pozdrawiam,\n"
            "AlisMeble"
        )

    if project_type in ("major", "minor", "consultation"):
        questions = (
            "Proszę o krótkie informacje:\n"
            "1) Lokalizacja montażu\n"
            "2) Wymiary / rysunek / projekt\n"
            "3) Materiał / kolor / styl\n"
            "4) Termin realizacji\n"
        )
        if quality == "vague":
            return (
                "Dzień dobry, dziękuję za wiadomość.\n"
                "Aby przygotować wycenę, potrzebuję kilku danych:\n"
                f"{questions}\n"
                "Pozdrawiam,\n"
                "AlisMeble"
            )
        return (
            "Dzień dobry, dziękuję za zapytanie.\n"
            "Na podstawie przesłanych informacji mogę przygotować wstępną wycenę.\n"
            "Proszę jeszcze o:\n"
            f"{questions}\n"
            "Pozdrawiam,\n"
            "AlisMeble"
        )

    return (
        "Dzień dobry, dziękuję za wiadomość.\n"
        "Wrócę z odpowiedzią najszybciej jak to możliwe.\n\n"
        "Pozdrawiam,\n"
        "AlisMeble"
    )


def main():
    token = read_secret(TOKEN_FILE)
    chat_id = read_secret(CHAT_FILE)
    if not token or not chat_id:
        print("Telegram not configured. Missing token or chat_id.")
        return

    if not LOG_CSV.exists():
        print("router_log.csv not found. Nothing to notify.")
        return

    state = load_state()
    sent_ids = state.get("sent", set())
    reminders = state.get("reminders", {})
    new_sent = set(sent_ids)

    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Sync with persistent reminders file
    persistent_reminders = {}
    if REMINDERS_FILE.exists():
        persistent_reminders = json.loads(REMINDERS_FILE.read_text(encoding='utf-8')).get("pending", {})

    with LOG_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for row in rows[-50:]:
        uid = f"{row.get('ts_utc')}|{row.get('file')}|{row.get('meta')}"
        if uid in sent_ids:
            continue

        decision = row.get("decision", "")
        meta_name = row.get("meta", "")
        meta_path = find_meta(meta_name, decision)

        subject = row.get("subject", "")
        from_addr = row.get("from", "")

        evaluation = {
            "payment_risk": row.get("payment_risk", "n/a"),
            "project_type": row.get("project_type", "unknown"),
            "urgency": row.get("urgency", "normal"),
            "quality": row.get("quality", "unknown"),
        }

        # FILTER: Skip administrative spam (banks, payments, confirmations)
        if evaluation.get("project_type") == "administrative":
            continue
        
        # FILTER: Only major/minor projects OR high/medium risk
        is_risky = evaluation.get("payment_risk") in ("high", "medium")
        is_project = evaluation.get("project_type") in ("major", "minor")
        
        if not (is_risky or is_project):
            continue

        draft_text = build_draft(subject, from_addr, evaluation)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        draft_name = f"{stamp}__{slugify(subject)}.txt"
        draft_path = DRAFTS_DIR / draft_name
        draft_path.write_text(draft_text, encoding="utf-8")

        msg = (
            "📬 New client message\n"
            f"Decision: {decision}\n"
            f"From: {from_addr}\n"
            f"Subject: {subject}\n"
            f"Risk: {evaluation.get('payment_risk')} | Type: {evaluation.get('project_type')} | Quality: {evaluation.get('quality')}\n\n"
            "Draft reply saved:\n"
            f"{draft_path}\n\n"
            "Tip: usuń plik draftu, jeśli temat zamknięty (stop reminder).\n"
        )

        try:
            send_telegram(token, chat_id, msg)
            new_sent.add(uid)
            reminders[draft_name] = {
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "draft_path": str(draft_path),
                "notified": False,
            }
        except Exception as e:
            print(f"Telegram send failed: {e}")
            break

    # Reminders: send after 2 hours if draft still exists and not notified
    now = datetime.now(timezone.utc)
    for draft_name, info in list(reminders.items()):
        try:
            draft_path = Path(info.get("draft_path", ""))
            created = datetime.fromisoformat(info.get("created_utc"))
            age_hours = (now - created).total_seconds() / 3600.0

            if info.get("notified"):
                continue
            if age_hours < 2:
                continue
            if not draft_path.exists():
                # Draft deleted = handled
                info["notified"] = True
                continue

            reminder_msg = (
                "⏰ Reminder: draft waiting\n"
                f"Plik: {draft_path.name}\n"
                f"Ścieżka: {draft_path}\n"
                "Jeśli temat zamknięty — usuń plik draftu, aby zatrzymać przypomnienia."
            )
            send_telegram(token, chat_id, reminder_msg)
            info["notified"] = True
        except Exception as e:
            print(f"Reminder failed: {e}")

    state["sent"] = new_sent
    state["reminders"] = reminders
    save_state(state)
    
    # Sync reminders to persistent file
    persistent_data = {"pending": {}}
    for draft_name, info in reminders.items():
        draft_path = Path(info.get("draft_path", ""))
        if draft_path.exists():  # Only keep if draft still exists
            persistent_data["pending"][draft_name] = info.get("created_utc")
    REMINDERS_FILE.write_text(json.dumps(persistent_data, indent=2), encoding='utf-8')
    
    print("Telegram notifications done.")


if __name__ == "__main__":
    main()

"""
ALIS | CONTROL CENTER — v2.0 (Telegram Dashboard)

Goal (non-technical):
- One message = one dashboard (tiles).
- Real numbers from logs/CSV, not "random text".
- Fast and non-blocking on Dropbox.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# Paths / Config
# =========================
ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")

SECRETS = ROOT / "99_SYSTEM" / "_SECRETS"
TOKEN_FILE = SECRETS / "telegram_bot_token.txt"
CHAT_ID_FILE = SECRETS / "telegram_chat_id.txt"

LOG_DIR = ROOT / "00_INBOX" / "_ROUTER_LOGS"
PIPELINE_LOG = LOG_DIR / "pipeline_run.log"
PIPELINE_ERRORS = LOG_DIR / "pipeline_errors.jsonl"
ROUTER_LOG = LOG_DIR / "router_log.csv"

PAYMENTS_CSV = ROOT / "FINANCE" / "PAYMENTS.csv"
CLIENT_QUOTES_CSV = ROOT / "FINANCE" / "CLIENT_QUOTES.csv"
FINANCE_DOCS = ROOT / "FINANCE" / "DOCS"

CASES = ROOT / "CASES"
DIR_INBOX = CASES / "_INBOX"
DIR_KLIENTS = CASES / "01_KLIENTS" / "_INBOX"
DIR_FIRMA = CASES / "02_FIRMA" / "_INBOX"
DIR_CAR = CASES / "03_CAR" / "_INBOX"
DIR_REVIEW = CASES / "_REVIEW"

UI_STATE_FILE = LOG_DIR / "telegram_ui_state.json"
QUOTES_DRAFTS_FILE = LOG_DIR / "quotes_drafts.json"
RUNTIME_LOG = LOG_DIR / "telegram_dashboard_runtime.log"

MAIL_PIPELINE_PS1 = ROOT / "99_SYSTEM" / "_SCRIPTS" / "MAIL" / "run_mail_pipeline.ps1"

WINDOW_DAYS = 7
MAX_LIST = 10
NOTIFY_INTERVAL_MIN = 15
MSG_LIMIT = 3900
SLA_NOTIFY_DAYS = (7, 3, 1)
SLA_NOTIFY_MAX_PER_TICK = 8
QUOTES_BOOTSTRAP_DAYS = 30
QUOTES_BOOTSTRAP_LIMIT = 500
QUOTE_STATUS_ALLOWED = {"open", "sent", "won", "lost", "expired"}
SELFTEST_HOUR_LOCAL = 3

PIPELINE_RUN_LOCK = asyncio.Lock()

QUOTES_EXCLUDE_FROM_SUBSTRINGS = [
    # Supplier / operational emails that are not "wycena"
    "centrum.meble.pl",
    "centrum@meble.pl",
]
QUOTES_EXCLUDE_SUBJECT_SUBSTRINGS = [
    "instrukcje do zamówienia",
    "instrukcje do zamowienia",
]

INVOICES_IT_RECEIPT_SUBJECT_SUBSTRINGS = [
    "receipt from anthropic",
    "receipt from openai",
    "receipt from github",
    "github copilot",
    "copilot pro",
    "openai invoice",
    "anthropic invoice",
]


# =========================
# Small utilities
# =========================

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _log_runtime(message: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        with RUNTIME_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{ts} {message}\n")
    except Exception:
        pass


def _fit_message(text: str, limit: int = MSG_LIMIT) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    tail = "\n\n[...message trimmed for Telegram limit...]"
    return t[: max(0, limit - len(tail))] + tail


def _file_mtime_utc(path: Path) -> str:
    try:
        if not path.exists():
            return "n/a"
        dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return "n/a"


def _parse_deadline_date(s: str) -> Optional[datetime.date]:
    try:
        return datetime.strptime((s or "").strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _payment_row_id(row: dict) -> str:
    explicit = (
        (row.get("id") or "").strip()
        or (row.get("payment_id") or "").strip()
        or (row.get("uuid") or "").strip()
    )
    if explicit:
        return explicit
    base = "|".join(
        [
            (row.get("name") or "").strip().lower(),
            (row.get("amount") or "").strip().lower(),
            (row.get("deadline") or "").strip(),
            (row.get("type") or "").strip().lower(),
        ]
    )
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _payment_sla_stage(days_left: int) -> Optional[str]:
    if days_left < 0:
        return "OVERDUE"
    if days_left in SLA_NOTIFY_DAYS:
        return f"D{days_left}"
    return None


def _payment_sla_events() -> list[dict]:
    today = datetime.now().date()
    events: list[dict] = []
    for row in _payments_pending():
        deadline = _parse_deadline_date(row.get("deadline") or "")
        if not deadline:
            continue
        days_left = (deadline - today).days
        stage = _payment_sla_stage(days_left)
        if not stage:
            continue
        events.append(
            {
                "payment_id": _payment_row_id(row),
                "stage": stage,
                "days_left": days_left,
                "deadline": deadline.isoformat(),
                "name": (row.get("name") or "").strip() or "Без названия",
                "amount": (row.get("amount") or "").strip() or "n/a",
            }
        )
    events.sort(key=lambda e: (e["days_left"], e["deadline"], e["name"]))
    return events


def _normalize_quote_row(row: dict, fallback_id: str = "") -> dict:
    out = {h: (row.get(h, "") if isinstance(row, dict) else "") for h in _csv_headers_quotes()}

    if not (out.get("quote_id") or "").strip():
        out["quote_id"] = fallback_id or f"AUTO-{_utcnow().strftime('%Y%m%d%H%M%S')}"
    out["quote_id"] = str(out.get("quote_id") or "").strip()[:64]

    client = str(out.get("client") or "").strip()
    out["client"] = client if client else "Unknown"

    subject = str(out.get("subject") or out.get("email_subject") or "").strip()
    out["subject"] = (subject if subject else "(no subject)")[:200]

    status = str(out.get("status") or "").strip().lower()
    out["status"] = status if status in QUOTE_STATUS_ALLOWED else "open"

    curr = str(out.get("currency") or "").strip().upper()
    out["currency"] = curr[:8] if curr else "PLN"

    for k in ("date", "due_date"):
        v = str(out.get(k) or "").strip()
        d = _parse_deadline_date(v)
        out[k] = d.isoformat() if d else ""

    out["amount"] = str(out.get("amount") or "").strip()[:32]
    out["email_from"] = str(out.get("email_from") or "").strip()[:200]
    out["email_subject"] = str(out.get("email_subject") or "").strip()[:200]
    out["notes"] = str(out.get("notes") or "").strip()[:400]
    return out


def _parse_amount_number(raw: str) -> Optional[float]:
    s = (raw or "").strip().lower()
    if not s:
        return None
    for token in ("zł", "zl", "pln", "eur", "€"):
        s = s.replace(token, "")
    s = s.replace("\u00a0", " ").strip()
    s = s.replace(" ", "")
    if "," in s and "." not in s:
        parts = s.split(",")
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            # 1,200 -> 1200
            s = "".join(parts)
        else:
            # 1200,50 -> 1200.50
            s = s.replace(",", ".")
    elif "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # 1.200,50 -> 1200.50
            s = s.replace(".", "")
            s = s.replace(",", ".")
        else:
            # 1,200.50 -> 1200.50
            s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return None


def _fmt_amount(amount: float) -> str:
    if int(amount) == amount:
        return str(int(amount))
    return f"{amount:.2f}"


def _quotes_rows_safe() -> tuple[list[dict], Optional[str]]:
    if not CLIENT_QUOTES_CSV.exists():
        return ([], None)
    rows: list[dict] = []
    try:
        with CLIENT_QUOTES_CSV.open("r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            idx = 0
            for row in reader:
                idx += 1
                rows.append(_normalize_quote_row(row, fallback_id=f"LEGACY-{idx:04d}"))
        return (rows, None)
    except Exception as e:
        return ([], f"{type(e).__name__}: {e}")


def _quotes_missing_amount_count(rows: Optional[list[dict]] = None) -> int:
    data = rows if rows is not None else _client_quotes()
    n = 0
    for r in data:
        status = (r.get("status") or "").strip().lower()
        if status != "open":
            continue
        if _parse_amount_number(str(r.get("amount") or "")) is None:
            n += 1
    return n


def _health_snapshot() -> dict:
    status, ts = _pipeline_last_status()
    now = _utcnow()
    pipeline_age_min: Optional[int] = None
    ts_dt = _parse_iso_utc(ts or "")
    if ts_dt:
        pipeline_age_min = int((now - ts_dt).total_seconds() // 60)

    err = _latest_pipeline_error()
    err_age_min: Optional[int] = None
    err_dt = None
    raw = err.get("raw", "") or ""
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                err_dt = _parse_iso_utc(str(obj.get("ts_utc") or ""))
        except Exception:
            err_dt = None
    if err_dt:
        err_age_min = int((now - err_dt).total_seconds() // 60)

    return {
        "pipeline_status": status,
        "pipeline_ts": ts or "n/a",
        "pipeline_age_min": pipeline_age_min,
        "last_error_stage": err.get("stage") or "n/a",
        "last_error_code": err.get("code") or "n/a",
        "last_error_age_min": err_age_min,
        "payments_pending": len(_payments_pending()),
        "quotes_rows": len(_client_quotes()),
        "quotes_missing_amount": _quotes_missing_amount_count(),
        "router_rows_window": _count_routed("KLIENTS") + _count_routed("FIRMA"),
        "cache_entries": len(_CACHE),
        "pipeline_running": PIPELINE_RUN_LOCK.locked(),
    }


def _selftest_text() -> str:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append((name, ok, detail))

    token = TOKEN_FILE.read_text(encoding="utf-8").strip() if TOKEN_FILE.exists() else ""
    check("token", bool(token), str(TOKEN_FILE))

    chat = CHAT_ID_FILE.read_text(encoding="utf-8").strip() if CHAT_ID_FILE.exists() else ""
    check("chat_id", chat.isdigit(), str(CHAT_ID_FILE))

    check("pipeline_log", PIPELINE_LOG.exists(), f"{PIPELINE_LOG} @ {_file_mtime_utc(PIPELINE_LOG)}")
    check("router_log", ROUTER_LOG.exists(), f"{ROUTER_LOG} @ {_file_mtime_utc(ROUTER_LOG)}")
    check("payments_csv", PAYMENTS_CSV.exists(), f"{PAYMENTS_CSV} @ {_file_mtime_utc(PAYMENTS_CSV)}")
    check("quotes_csv", CLIENT_QUOTES_CSV.exists(), f"{CLIENT_QUOTES_CSV} @ {_file_mtime_utc(CLIENT_QUOTES_CSV)}")
    check("runtime_log", RUNTIME_LOG.exists(), f"{RUNTIME_LOG} @ {_file_mtime_utc(RUNTIME_LOG)}")

    h = _health_snapshot()
    ok_count = sum(1 for _, ok, _ in checks if ok)
    lines = [
        "Ночной self-test (dry-run)",
        f"UTC: {_utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"Checks: {ok_count}/{len(checks)}",
        "",
    ]
    for name, ok, detail in checks:
        lines.append(f"{'OK' if ok else 'FAIL'} {name}: {detail}")
    lines += [
        "",
        f"Pipeline: {h['pipeline_status']} | age_min={h['pipeline_age_min'] if h['pipeline_age_min'] is not None else 'n/a'}",
        f"Pending payments: {h['payments_pending']} | quotes rows: {h['quotes_rows']} | quotes_missing_amount: {h['quotes_missing_amount']}",
        f"Cache entries: {h['cache_entries']} | pipeline_running: {h['pipeline_running']}",
    ]
    return _fit_message("\n".join(lines))


def _parse_iso_utc(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        # Handles "2026-02-10T17:42:43Z" and "+00:00"
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _read_text(path: Path, max_bytes: int = 512_000) -> str:
    if not path.exists():
        return ""
    try:
        data = path.read_bytes()
        if len(data) > max_bytes:
            data = data[-max_bytes:]
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_chat_state(chat_id: int) -> dict:
    all_state = _load_json(UI_STATE_FILE)
    return all_state.get(str(chat_id), {}) if isinstance(all_state, dict) else {}


def _set_chat_state(chat_id: int, patch: dict) -> None:
    all_state = _load_json(UI_STATE_FILE)
    if not isinstance(all_state, dict):
        all_state = {}
    cur = all_state.get(str(chat_id), {})
    if not isinstance(cur, dict):
        cur = {}
    cur.update(patch)
    all_state[str(chat_id)] = cur
    _save_json(UI_STATE_FILE, all_state)


def _notify_enabled(chat_id: int) -> bool:
    state = _get_chat_state(chat_id)
    val = state.get("notify_enabled")
    if isinstance(val, bool):
        return val
    return True


def _csv_headers_quotes() -> list[str]:
    return [
        "quote_id",
        "client",
        "subject",
        "amount",
        "currency",
        "date",
        "status",
        "due_date",
        "email_from",
        "email_subject",
        "notes",
    ]


def _ensure_quotes_csv() -> None:
    CLIENT_QUOTES_CSV.parent.mkdir(parents=True, exist_ok=True)
    if CLIENT_QUOTES_CSV.exists() and CLIENT_QUOTES_CSV.stat().st_size > 0:
        return
    with CLIENT_QUOTES_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_csv_headers_quotes())
        writer.writeheader()


def _is_authorized(update: Update) -> bool:
    try:
        authorized = CHAT_ID_FILE.read_text(encoding="utf-8").strip()
        return str(update.effective_chat.id) == authorized
    except Exception:
        return False


# =========================
# Cache (30–60 seconds)
# =========================

@dataclass
class _CacheEntry:
    ts: float
    value: Any


_CACHE: dict[str, _CacheEntry] = {}


def _cache_get(key: str, ttl_s: float, fn):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and (now - hit.ts) <= ttl_s:
        return hit.value
    val = fn()
    _CACHE[key] = _CacheEntry(ts=now, value=val)
    return val


def _invalidate_runtime_cache() -> None:
    keys = [
        "router_rows",
        "payments_pending",
        "client_quotes",
        "finance_pdf_counts",
    ]
    for k in keys:
        _CACHE.pop(k, None)


# =========================
# Data sources
# =========================

def _row_subject(row: dict) -> str:
    return (row.get("subject") or "").strip()


def _row_from(row: dict) -> str:
    return (row.get("from") or "").strip()


def _subject_l(row: dict) -> str:
    return _row_subject(row).lower()


def _from_l(row: dict) -> str:
    return _row_from(row).lower()


def _dedup_rows(rows: list[dict], key_fn) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        k = key_fn(r)
        if not k:
            continue
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def _is_quote_candidate(row: dict) -> bool:
    # Plan rule: KLIENTS in last 7 days, with simple exclusions (avoid spam).
    if (row.get("decision") or "").upper() != "KLIENTS":
        return False
    if not _in_window(row.get("ts_utc") or ""):
        return False
    s = _subject_l(row)
    f = _from_l(row)
    if any(x in f for x in QUOTES_EXCLUDE_FROM_SUBSTRINGS):
        return False
    if any(x in s for x in QUOTES_EXCLUDE_SUBJECT_SUBSTRINGS):
        return False
    return True


def _is_it_receipt(row: dict) -> bool:
    s = _subject_l(row)
    return any(x in s for x in INVOICES_IT_RECEIPT_SUBJECT_SUBSTRINGS)


def _invoice_rows_window() -> list[dict]:
    rows = _router_rows()
    items = [r for r in rows if (r.get("decision") or "").upper() == "FIRMA" and _in_window(r.get("ts_utc") or "")]
    items.sort(key=lambda r: (r.get("ts_utc") or ""), reverse=True)
    return items


def _quotes_rows_window() -> list[dict]:
    rows = _router_rows()
    items = [r for r in rows if _is_quote_candidate(r)]
    items.sort(key=lambda r: (r.get("ts_utc") or ""), reverse=True)
    # de-dup by subject+from to avoid spam from the same sender
    items = _dedup_rows(items, lambda r: f"{_subject_l(r)}|{_from_l(r)}")
    return items


def _router_rows() -> list[dict]:
    def _load():
        if not ROUTER_LOG.exists():
            return []
        try:
            with ROUTER_LOG.open("r", encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.DictReader(f)
                return list(reader)
        except Exception:
            return []

    return _cache_get("router_rows", 30.0, _load)


def _window_start() -> datetime:
    return _utcnow() - timedelta(days=WINDOW_DAYS)


def _in_window(ts_utc: str) -> bool:
    dt = _parse_iso_utc(ts_utc)
    if not dt:
        return False
    return dt >= _window_start()


def _count_routed(decision: str) -> int:
    d = (decision or "").upper()
    rows = _router_rows()
    return sum(1 for r in rows if (r.get("decision") or "").upper() == d and _in_window(r.get("ts_utc") or ""))


def _list_routed(decision: str, limit: int = MAX_LIST) -> list[dict]:
    d = (decision or "").upper()
    rows = _router_rows()
    items = [r for r in rows if (r.get("decision") or "").upper() == d and _in_window(r.get("ts_utc") or "")]
    # Sort by ts_utc descending (string ISO in UTC should sort lexicographically)
    items.sort(key=lambda r: (r.get("ts_utc") or ""), reverse=True)
    return items[:limit]


def _payments_pending() -> list[dict]:
    def _load():
        out: list[dict] = []
        if not PAYMENTS_CSV.exists():
            return out
        try:
            with PAYMENTS_CSV.open("r", encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row.get("status") or "").strip().lower() == "pending":
                        out.append(row)
        except Exception:
            return out
        return out

    return _cache_get("payments_pending", 15.0, _load)


def _client_quotes() -> list[dict]:
    """
    Source of truth for quote amounts/statuses.
    Expected columns:
    quote_id,client,subject,amount,currency,date,status,due_date,email_from,email_subject,notes
    """
    def _load():
        out, err = _quotes_rows_safe()
        if err:
            _log_runtime(f"client_quotes read error: {err}")
            return []
        return out

    return _cache_get("client_quotes", 20.0, _load)


def _quotes_stats_from_csv() -> dict:
    rows = _client_quotes()
    if not rows:
        return {"total": 0, "open": 0, "sent": 0, "won": 0, "lost": 0, "expired": 0, "unknown": 0}

    counters = {"total": len(rows), "open": 0, "sent": 0, "won": 0, "lost": 0, "expired": 0, "unknown": 0}
    for r in rows:
        status = (r.get("status") or "").strip().lower()
        if status in counters:
            counters[status] += 1
        else:
            counters["unknown"] += 1
    return counters


def _payables_stats() -> tuple[int, int, int, list[str]]:
    """(total, overdue, due_3, top_lines)"""
    rows = _payments_pending()
    today = datetime.now().date()

    parsed: list[tuple[datetime.date, dict]] = []
    for r in rows:
        try:
            d = datetime.strptime((r.get("deadline") or "").strip(), "%Y-%m-%d").date()
        except Exception:
            continue
        parsed.append((d, r))
    parsed.sort(key=lambda x: x[0])

    overdue = 0
    due_3 = 0
    for d, _ in parsed:
        days_left = (d - today).days
        if days_left < 0:
            overdue += 1
        if days_left <= 3:
            due_3 += 1

    lines: list[str] = []
    for d, r in parsed[:5]:
        days_left = (d - today).days
        icon = "🔴" if days_left < 0 else ("⚠️" if days_left <= 3 else "✅")
        name = (r.get("name") or "").strip()
        amount = (r.get("amount") or "").strip()
        if amount and amount not in {"do wyliczenia", "tbd", "TBD"}:
            amount = f"{amount} zł"
        lines.append(f"{icon} {name}: {amount} ({d.isoformat()})")

    return (len(parsed), overdue, due_3, lines)


def _count_pdfs(path: Path) -> int:
    def _do():
        if not path.exists():
            return 0
        n = 0
        for p in path.rglob("*.pdf"):
            if p.is_file() and p.name.lower() != "desktop.ini":
                n += 1
        return n

    # finance trees may be larger; cache a bit more
    return _cache_get(f"pdfs:{str(path)}", 60.0, _do)


def _finance_pdf_counts() -> dict[str, int]:
    def _do():
        return {
            "issued": _count_pdfs(FINANCE_DOCS / "FAKTURY" / "ISSUED"),
            "received": _count_pdfs(FINANCE_DOCS / "FAKTURY" / "RECEIVED"),
            "zus": _count_pdfs(FINANCE_DOCS / "ZUS"),
            "vat": _count_pdfs(FINANCE_DOCS / "VAT"),
            "leasing": _count_pdfs(FINANCE_DOCS / "LEASING"),
            "rachunki": _count_pdfs(FINANCE_DOCS / "RACHUNKI"),
        }

    return _cache_get("finance_pdf_counts", 60.0, _do)


def _pipeline_last_status() -> tuple[str, Optional[str]]:
    """
    Returns (status, ts_utc_str)
    status in: OK / ERROR / NEVER / UNKNOWN
    """
    text = _read_text(PIPELINE_LOG)
    if not text.strip():
        return ("NEVER", None)

    lines = text.splitlines()
    last_utc = None
    for line in reversed(lines[-500:]):
        if line.strip().startswith("UTC: "):
            last_utc = line.strip().replace("UTC: ", "").strip()
            break

    for line in reversed(lines[-500:]):
        if "MAIL PIPELINE DONE" in line:
            return ("OK", last_utc)
        if "PIPELINE ERROR" in line:
            return ("ERROR", last_utc)

    try:
        ts = datetime.fromtimestamp(PIPELINE_LOG.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        ts = None
    return ("UNKNOWN", ts)


def _pipeline_last_imported_count() -> Optional[int]:
    """
    Best-effort: parse last "Imported: N attachment(s)." from pipeline log.
    """
    text = _read_text(PIPELINE_LOG)
    if not text.strip():
        return None
    lines = text.splitlines()
    for line in reversed(lines[-800:]):
        line = line.strip()
        if line.startswith("Imported:") and "attachment" in line:
            # Imported: 12 attachment(s). Saved to: ...
            try:
                n = int(line.split("Imported:", 1)[1].strip().split(" ", 1)[0])
                return n
            except Exception:
                return None
    return None


def _pipeline_last_start_dt_utc() -> Optional[datetime]:
    """Parse last 'UTC: ...Z' from pipeline log into datetime (UTC)."""
    status, ts = _pipeline_last_status()
    dt = _parse_iso_utc(ts or "")
    return dt


def _count_routed_since(dt_utc: Optional[datetime]) -> Optional[int]:
    """Count router_log rows with ts_utc >= dt_utc (best-effort)."""
    if not dt_utc:
        return None
    rows = _router_rows()
    n = 0
    for r in rows:
        dt = _parse_iso_utc(r.get("ts_utc") or "")
        if dt and dt >= dt_utc:
            n += 1
    return n


def _risk_report_data() -> dict:
    """
    Risk report from real sources only:
    - PAYMENTS.csv (deadlines)
    - router_log.csv (quality/payment_risk flags, last WINDOW_DAYS)
    """
    total, overdue, due_3, top = _payables_stats()
    rows = _router_rows()
    risk_rows = [
        r for r in rows
        if _in_window(r.get("ts_utc") or "")
        and (
            (r.get("payment_risk") or "").lower() in {"high", "medium"}
            or (r.get("quality") or "").lower() in {"vague"}
        )
    ]
    risk_rows.sort(key=lambda r: (r.get("ts_utc") or ""), reverse=True)
    return {
        "pay_total": total,
        "pay_overdue": overdue,
        "pay_due3": due_3,
        "pay_top": top,
        "mail_risks": risk_rows[:10],
    }


def _latest_pipeline_error() -> dict:
    """
    Returns {"raw": str, "stage": str, "code": str, "message": str}
    or empty fields if no errors.
    """
    text = _read_text(PIPELINE_ERRORS, 120_000)
    if not text.strip():
        return {"raw": "", "stage": "", "code": "", "message": ""}
    raw = text.splitlines()[-1].strip()
    if not raw:
        return {"raw": "", "stage": "", "code": "", "message": ""}
    try:
        obj = json.loads(raw)
    except Exception:
        obj = {}
    if isinstance(obj, dict):
        return {
            "raw": raw,
            "stage": str(obj.get("stage") or ""),
            "code": str(obj.get("exit_code") or ""),
            "message": str(obj.get("message") or ""),
        }
    return {"raw": raw, "stage": "", "code": "", "message": ""}


def _risk_signature(data: dict) -> str:
    pay_top = data.get("pay_top") or []
    top = "|".join(pay_top[:3]) if isinstance(pay_top, list) else ""
    return (
        f"overdue={data.get('pay_overdue', 0)};"
        f"due3={data.get('pay_due3', 0)};"
        f"mail={len(data.get('mail_risks') or [])};"
        f"top={top}"
    )


def _extract_money_hint(text: str) -> Optional[str]:
    """
    Best-effort money extraction from subject lines (e.g. 1200 zl / 1 200 PLN).
    Returns normalized string or None.
    """
    import re
    t = (text or "").lower()
    m = re.search(r"(\d[\d\s]{1,10})(?:zł|zl|pln|eur|€)", t)
    if not m:
        return None
    raw = re.sub(r"\s+", "", m.group(1))
    return raw


def _ai_answer(question: str) -> str:
    """
    Lightweight local AI assistant (rule-based), grounded in real project data.
    No fabricated metrics.
    """
    q = (question or "").strip().lower()
    if not q:
        return "Задай вопрос, например: 'откуда цифры по рискам', 'что по выценам', 'что по оплатам'."

    summary = _build_dashboard_summary()
    risk = _risk_report_data()
    quotes = _quotes_rows_window()[:MAX_LIST]
    qstats = _quotes_stats_from_csv()
    qrows = _client_quotes()
    inv = [r for r in _invoice_rows_window() if not _is_it_receipt(r)][:MAX_LIST]

    if any(x in q for x in ["риск", "риски", "risk"]):
        lines = [
            "Риски (реальные источники):",
            f"• PAYMENTS.csv: всего {risk['pay_total']}, просрочено {risk['pay_overdue']}, <=3 дня {risk['pay_due3']}",
            f"• router_log.csv: риск-писем {len(risk['mail_risks'])} за {WINDOW_DAYS} дней",
            "• Источник цифр: `FINANCE/PAYMENTS.csv` и `00_INBOX/_ROUTER_LOGS/router_log.csv`",
        ]
        return "\n".join(lines)

    if any(x in q for x in ["оплат", "к оплате", "pay"]):
        lines = [f"К оплате: {summary['pay_total']} (просрочено {summary['pay_overdue']}, <=3 дня {summary['pay_due3']})", "Топ-5:"]
        top = risk["pay_top"] or ["(пусто)"]
        lines.extend([f"• {x}" for x in top])
        lines.append("Источник: `FINANCE/PAYMENTS.csv`.")
        return "\n".join(lines)

    if any(x in q for x in ["выцен", "клиент", "quotes", "klients"]):
        lines = [f"Выцены: {summary['quotes']} новых за {WINDOW_DAYS} дней.", "Последние из почты:"]
        if not quotes:
            lines.append("• (пусто)")
        else:
            for r in quotes[:5]:
                subj = (r.get("subject") or r.get("file") or "").strip()
                if len(subj) > 70:
                    subj = subj[:67] + "..."
                money = _extract_money_hint(subj) or "без суммы"
                lines.append(f"• {subj} [{money}]")
        if qrows:
            lines += [
                "",
                f"CRM выцен (CLIENT_QUOTES.csv): всего {qstats['total']}, open {qstats['open']}, won {qstats['won']}, lost {qstats['lost']}",
            ]
        else:
            lines += [
                "",
                "Для точного «кому сколько выценил» заполняй `FINANCE/CLIENT_QUOTES.csv`.",
            ]
        lines.append("Источник: `router_log.csv` + `FINANCE/CLIENT_QUOTES.csv`.")
        return "\n".join(lines)

    if any(x in q for x in ["фактур", "бух", "invoice", "zus", "vat"]):
        c = _finance_pdf_counts()
        lines = [
            f"Бухгалтерия: {summary['inv']} новых FIRMA за {WINDOW_DAYS} дней.",
            f"FINANCE/DOCS(PDF): issued {c['issued']}, received {c['received']}, ZUS {c['zus']}, VAT {c['vat']}, Leasing {c['leasing']}, Rachunki {c['rachunki']}",
        ]
        if inv:
            lines.append("Последние входящие:")
            for r in inv[:5]:
                subj = (r.get("subject") or r.get("file") or "").strip()
                if len(subj) > 70:
                    subj = subj[:67] + "..."
                lines.append(f"• {subj}")
        lines.append("Источник: `router_log.csv` + `FINANCE/DOCS`.")
        return "\n".join(lines)

    if any(x in q for x in ["почт", "pipeline", "пайп", "импорт"]):
        return (
            f"Почта/пайплайн: {summary['status']} (UTC {summary['ts']}).\n"
            f"Импорт: +{summary['imported'] if summary['imported'] is not None else 'n/a'}\n"
            f"Разложено: {summary['routed_last_run'] if summary['routed_last_run'] is not None else 'n/a'}\n"
            "Источники: `pipeline_run.log`, `router_log.csv`."
        )

    return (
        "Могу ответить по 5 блокам: почта, риски, оплаты, выцены, бухгалтерия.\n"
        "Пример: 'откуда цифры по рискам' или 'что по выценам за 7 дней'."
    )


# =========================
# UI rendering
# =========================

def _tile(text: str, cb: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=cb)


def _dashboard_keyboard(summary: dict) -> InlineKeyboardMarkup:
    """
    6 tiles: Mail, Payables, Quotes, Invoices, Search, Status
    """
    mail_badge = summary.get("mail_badge", "")
    pay_badge = summary.get("pay_badge", "")
    quotes_badge = summary.get("quotes_badge", "")
    inv_badge = summary.get("inv_badge", "")

    return InlineKeyboardMarkup(
        [
            [_tile(f"📩 Почта {mail_badge}", "mail"), _tile(f"💸 К оплате {pay_badge}", "payables")],
            [_tile(f"🤝 Выцены {quotes_badge}", "quotes"), _tile(f"📄 Бух {inv_badge}", "invoices")],
            [_tile("🔎 Поиск", "search"), _tile("⚙️ Статус", "status")],
            [_tile("AI", "ai_open"), _tile("Уведомления", "notify_menu")],
        ]
    )


def _build_dashboard_summary() -> dict:
    status, ts = _pipeline_last_status()
    imported = _pipeline_last_imported_count()
    last_start_dt = _pipeline_last_start_dt_utc()
    routed_last_run = _count_routed_since(last_start_dt)

    total, overdue, due_3, _ = _payables_stats()
    quotes = len(_quotes_rows_window())
    inv_rows = _invoice_rows_window()
    it_receipts = sum(1 for r in inv_rows if _is_it_receipt(r))
    inv = max(0, len(inv_rows) - it_receipts)
    qstats = _quotes_stats_from_csv()

    mail_badge = {"OK": "✅", "ERROR": "🔴", "NEVER": "⚪", "UNKNOWN": "🟡"}.get(status, "🟡")
    if imported is not None:
        mail_badge += f" +{imported}"
    if routed_last_run is not None:
        mail_badge += f"/{routed_last_run}"

    pay_badge = f"{total}"
    if overdue or due_3:
        pay_badge += f" ({overdue}/{due_3})"  # overdue / <=3d

    return {
        "status": status,
        "ts": ts or "—",
        "imported": imported,
        "routed_last_run": routed_last_run,
        "pay_total": total,
        "pay_overdue": overdue,
        "pay_due3": due_3,
        "quotes": quotes,
        "quotes_open": qstats["open"],
        "inv": inv,
        "it_receipts": it_receipts,
        "mail_badge": mail_badge,
        "pay_badge": pay_badge,
        "quotes_badge": f"{quotes}",
        "inv_badge": f"{inv}",
    }


def build_dashboard_text() -> str:
    s = _build_dashboard_summary()
    status_badge = {"OK": "OK", "ERROR": "ERROR", "NEVER": "NEVER", "UNKNOWN": "UNKNOWN"}.get(
        s["status"], "UNKNOWN"
    )

    lines = [
        "🧭 ALIS | Archiwum 3.0",
        "====================",
        f"📩 Почта: {status_badge} | UTC: {s['ts']}",
    ]
    if s["imported"] is not None:
        lines.append(f"📥 Импорт: +{s['imported']} вложений")
    if s.get("routed_last_run") is not None:
        lines.append(f"📦 Маршрутизация: {s['routed_last_run']} файлов")

    lines += [
        "",
        f"💸 К оплате: {s['pay_total']} | просрочено {s['pay_overdue']} | <=3 дн {s['pay_due3']}",
        f"🤝 Клиенты/выцены: {s['quotes']} новых за {WINDOW_DAYS} дн",
        f"📄 Фактуры/бух: {s['inv']} новых за {WINDOW_DAYS} дн",
    ]
    if s.get("quotes_open", 0) > 0:
        lines.append(f"📌 Выцены в работе (CRM): {s['quotes_open']}")

    lines += [
        "",
        "🧾 Источники: router_log.csv | PAYMENTS.csv | FINANCE/DOCS",
        f"UTC: router={_file_mtime_utc(ROUTER_LOG)}, payments={_file_mtime_utc(PAYMENTS_CSV)}",
    ]
    return _fit_message("\n".join(lines))

# =========================
# Screens (all edit the same message)
# =========================

async def _edit(query, text: str, keyboard: Optional[InlineKeyboardMarkup] = None) -> None:
    safe_text = _fit_message(text)
    try:
        await query.edit_message_text(safe_text, reply_markup=keyboard)
    except Exception as e:
        msg = str(e).lower()
        if "message is not modified" in msg:
            return
        _log_runtime(f"_edit failed: {type(e).__name__}: {e}")
        try:
            await query.edit_message_text(safe_text)
        except Exception as e2:
            _log_runtime(f"_edit fallback failed: {type(e2).__name__}: {e2}")

async def show_dashboard(query) -> None:
    text = await asyncio.to_thread(build_dashboard_text)
    summary = await asyncio.to_thread(_build_dashboard_summary)
    await _edit(query, text, _dashboard_keyboard(summary))


def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[_tile("🏠 Панель", "dashboard")]])


def _back_with_ai_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_tile("AI вопрос", "ai_open")],
            [_tile("Уведомления", "notify_menu")],
            [_tile("🏠 Панель", "dashboard")],
        ]
    )


async def show_mail(query) -> None:
    status, ts = await asyncio.to_thread(_pipeline_last_status)
    imported = await asyncio.to_thread(_pipeline_last_imported_count)
    msg = [
        "📩 Почта / Пайплайн",
        "",
        f"Статус: {status}",
        f"Время (UTC): {ts or '—'}",
    ]
    if imported is not None:
        msg.append(f"Импортировано вложений (последний запуск): {imported}")
    msg.append("")
    msg.append("Действие: запустить обновление (импорт + сортировка).")
    msg.append(f"Источник: pipeline_run.log UTC={_file_mtime_utc(PIPELINE_LOG)}")

    kb = InlineKeyboardMarkup(
        [
            [_tile("▶️ Запустить пайплайн", "mail_run")],
            [_tile("🏠 Панель", "dashboard")],
        ]
    )
    await _edit(query, "\n".join(msg), kb)


async def run_pipeline(query) -> None:
    if PIPELINE_RUN_LOCK.locked():
        await _edit(
            query,
            "Пайплайн уже выполняется. Подожди завершения текущего запуска.",
            _back_kb(),
        )
        return

    def _run() -> tuple[int, str, str]:
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(MAIL_PIPELINE_PS1)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return (r.returncode, r.stdout or "", r.stderr or "")
        except subprocess.TimeoutExpired:
            return (124, "", "Timeout (120s)")
        except Exception as e:
            return (1, "", f"{type(e).__name__}: {e}")

    await _edit(query, "⏳ Запускаю пайплайн... (до 120 сек)", _back_kb())
    async with PIPELINE_RUN_LOCK:
        rc, out, err = await asyncio.to_thread(_run)
        _invalidate_runtime_cache()

    _log_runtime(f"pipeline rc={rc}")
    if rc == 0:
        await show_dashboard(query)
        return

    tail = (err.strip() or out.strip() or "Неизвестная ошибка")[-1500:]
    await _edit(query, f"Ошибка пайплайна (код {rc})\n\n{tail}", _back_kb())


async def show_payables(query) -> None:
    total, overdue, due_3, top = await asyncio.to_thread(_payables_stats)
    lines = [
        "💸 К оплате",
        "",
        f"Всего: {total} | Просрочено: {overdue} | ≤3 дня: {due_3}",
        "",
        "Ближайшие 5:",
    ]
    if not top:
        lines.append("• (пусто)")
    else:
        lines.extend([f"• {x}" for x in top])
    lines += [
        "",
        "Источник: `FINANCE/PAYMENTS.csv` (status=pending, deadline).",
        f"Обновлен (UTC): {_file_mtime_utc(PAYMENTS_CSV)}",
    ]
    kb = InlineKeyboardMarkup(
        [
            [_tile("⚠️ Отчёт рисков", "risk_report")],
            [_tile("🤖 AI вопрос", "ai_open")],
            [_tile("🏠 Панель", "dashboard")],
        ]
    )
    await _edit(query, "\n".join(lines), kb)


async def show_quotes(query) -> None:
    bootstrap = await asyncio.to_thread(_bootstrap_quotes_if_empty, QUOTES_BOOTSTRAP_DAYS)
    items = await asyncio.to_thread(_quotes_rows_window)
    items = items[:MAX_LIST]

    state = _get_chat_state(query.message.chat_id)
    last_seen = (state.get("quotes_last_seen_ts") or "").strip()

    lines = [f"🤝 Клиенты / Выцены (за {WINDOW_DAYS} дней)", ""]
    if not items:
        lines.append("(пока пусто)")
    else:
        for r in items:
            ts = (r.get("ts_utc") or "").strip()
            subj = (r.get("subject") or "").strip() or (r.get("file") or "").strip()
            frm = (r.get("from") or "").strip()
            if len(subj) > 64:
                subj = subj[:61] + "..."
            new = "🆕 " if last_seen and ts and ts > last_seen else ""
            lines.append(f"• {new}{subj}")
            if frm:
                lines.append(f"  от: {frm[:80]}")

        newest = max(((r.get("ts_utc") or "").strip() for r in items), default="")
        if newest:
            _set_chat_state(query.message.chat_id, {"quotes_last_seen_ts": newest})

    lines += [
        "",
        "Примечание: системные письма поставщиков (типа 'Instrukcje do zamówienia') скрыты.",
        "Источник: `router_log.csv` (decision=KLIENTS, 7 дней).",
        f"Обновлен (UTC): {_file_mtime_utc(ROUTER_LOG)}",
    ]
    if bootstrap.get("attempted"):
        lines += [
            "",
            f"Автозаполнение CLIENT_QUOTES: добавлено {bootstrap.get('added', 0)} строк (окно {QUOTES_BOOTSTRAP_DAYS} дней).",
        ]
    elif str(bootstrap.get("reason", "")).startswith("csv_error:"):
        lines += ["", f"CLIENT_QUOTES warning: {bootstrap.get('reason')}"]
    kb = InlineKeyboardMarkup(
        [
            [_tile("💼 Отчёт по выценам", "quotes_report")],
            [_tile("🤖 AI вопрос", "ai_open")],
            [_tile("🏠 Панель", "dashboard")],
        ]
    )
    await _edit(query, "\n".join(lines), kb)


def _quotes_report_text() -> str:
    rows, err = _quotes_rows_safe()
    if err:
        return (
            "💼 Отчёт по выценам\n\n"
            "Ошибка чтения CLIENT_QUOTES.csv.\n"
            f"Файл: {CLIENT_QUOTES_CSV}\n"
            f"Диагностика: {err}"
        )
    if not rows:
        return (
            "💼 Отчёт по выценам\n\n"
            "CLIENT_QUOTES.csv пуст.\n"
            "Открой «Клиенты/Выцены» или «Отчёт по выценам» повторно: бот выполнит автозаполнение."
        )

    stats = _quotes_stats_from_csv()

    def _date_key(r: dict) -> str:
        return (r.get("date") or "").strip()

    rows_sorted = sorted(rows, key=_date_key, reverse=True)
    by_client: dict[str, dict[str, Any]] = {}
    missing: list[dict] = []

    for r in rows:
        client = (r.get("client") or "").strip() or "Unknown"
        cur = (r.get("currency") or "").strip() or "PLN"
        st = (r.get("status") or "").strip().lower()
        amount_val = _parse_amount_number(str(r.get("amount") or ""))

        c = by_client.setdefault(client, {"sum": 0.0, "count": 0, "open": 0, "currency": cur})
        c["count"] += 1
        if st == "open":
            c["open"] += 1
        if amount_val is not None:
            c["sum"] += amount_val

        if amount_val is None:
            missing.append(r)

    client_rows = sorted(by_client.items(), key=lambda kv: (kv[1]["sum"], kv[1]["count"]), reverse=True)

    lines = [
        "💼 Отчёт по выценам (по клиентам)",
        "",
        f"Итоги: всего {stats['total']} | open {stats['open']} | sent {stats['sent']} | won {stats['won']} | lost {stats['lost']} | expired {stats['expired']}",
        "",
        "Топ клиентов (до 10):",
    ]

    if not client_rows:
        lines.append("• (пусто)")
    else:
        for client, data in client_rows[:10]:
            lines.append(
                f"• {client}: сумма {_fmt_amount(float(data['sum']))} {data['currency']} | кол-во {data['count']} | open {data['open']}"
            )

    lines += ["", "Требуют заполнения суммы (до 10):"]
    if not missing:
        lines.append("• (нет)")
    else:
        missing_sorted = sorted(missing, key=_date_key, reverse=True)
        for r in missing_sorted[:10]:
            client = (r.get("client") or "").strip() or "Unknown"
            date = (r.get("date") or "").strip() or "—"
            subj = (r.get("subject") or "").strip() or "—"
            if len(subj) > 60:
                subj = subj[:57] + "..."
            lines.append(f"• {client} | {date} | {subj}")

    lines += ["", "Последние сделки (до 10):"]
    for r in rows_sorted[:10]:
        client = (r.get("client") or "").strip() or "Unknown"
        amount_raw = (r.get("amount") or "").strip()
        amount_val = _parse_amount_number(amount_raw)
        amount_txt = _fmt_amount(amount_val) if amount_val is not None else "—"
        curr = (r.get("currency") or "").strip() or "PLN"
        date = (r.get("date") or "").strip() or "—"
        st = (r.get("status") or "").strip() or "unknown"
        lines.append(f"• {client}: {amount_txt} {curr} [{st}] ({date})")

    lines += [
        "",
        "Источник: `FINANCE/CLIENT_QUOTES.csv`.",
        f"Обновлен (UTC): {_file_mtime_utc(CLIENT_QUOTES_CSV)}",
    ]
    return _fit_message("\n".join(lines))


def _quote_row_key(email_from: str, email_subject: str) -> str:
    return f"{(email_from or '').strip().lower()}|{(email_subject or '').strip().lower()}"


def _existing_quote_keys() -> set[str]:
    rows = _client_quotes()
    keys: set[str] = set()
    for r in rows:
        keys.add(_quote_row_key(r.get("email_from", ""), r.get("email_subject", "")))
    return keys


def _build_quote_drafts_from_router(limit: int = 30, days_window: int = WINDOW_DAYS) -> dict:
    """
    Create draft quote rows from KLIENTS mail in the given window.
    Amount is unknown by default -> empty.
    """
    window_start = _utcnow() - timedelta(days=days_window)
    rows = _router_rows()
    items = [
        r for r in rows
        if (r.get("decision") or "").upper() == "KLIENTS"
        and (_parse_iso_utc(r.get("ts_utc") or "") or datetime.min.replace(tzinfo=timezone.utc)) >= window_start
    ]
    items.sort(key=lambda r: (r.get("ts_utc") or ""), reverse=True)
    items = items[:limit]
    existing = _existing_quote_keys()
    drafts: list[dict] = []

    # sequence for quote_id per current date
    today = datetime.now().strftime("%Y%m%d")
    seq = 1

    for r in items:
        email_from = (r.get("from") or "").strip()
        email_subject = (r.get("subject") or r.get("file") or "").strip()
        if not email_subject:
            continue

        k = _quote_row_key(email_from, email_subject)
        if k in existing:
            continue
        if any(_quote_row_key(d["email_from"], d["email_subject"]) == k for d in drafts):
            continue

        ts = _parse_iso_utc(r.get("ts_utc") or "")
        date = ts.date().isoformat() if ts else datetime.now().date().isoformat()
        client = email_from.split("<")[0].strip().strip('"') if email_from else "Unknown"
        if not client:
            client = "Unknown"

        draft = {
            "quote_id": f"AUTO-{today}-{seq:03d}",
            "client": client,
            "subject": email_subject[:120],
            "amount": "",
            "currency": "PLN",
            "date": date,
            "status": "open",
            "due_date": "",
            "email_from": email_from[:200],
            "email_subject": email_subject[:200],
            "notes": "auto-draft from router",
        }
        drafts.append(draft)
        seq += 1

    payload = {
        "created_utc": _utcnow().isoformat(),
        "count": len(drafts),
        "rows": drafts,
    }
    _save_json(QUOTES_DRAFTS_FILE, payload)
    return payload


def _apply_quote_drafts_to_csv() -> dict:
    payload = _load_json(QUOTES_DRAFTS_FILE)
    rows = payload.get("rows", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []

    _ensure_quotes_csv()
    existing = _existing_quote_keys()

    to_write: list[dict] = []
    seq = 0
    for r in rows:
        k = _quote_row_key(r.get("email_from", ""), r.get("email_subject", ""))
        if not k or k in existing:
            continue
        # enforce schema
        seq += 1
        row = _normalize_quote_row(r, fallback_id=f"DRAFT-{_utcnow().strftime('%Y%m%d')}-{seq:03d}")
        to_write.append(row)
        existing.add(k)

    if to_write:
        with CLIENT_QUOTES_CSV.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_csv_headers_quotes())
            for r in to_write:
                writer.writerow(r)

    # invalidate related cache
    _CACHE.pop("client_quotes", None)
    _CACHE.pop("router_rows", None)

    return {"draft_rows": len(rows), "added": len(to_write)}


def _bootstrap_quotes_if_empty(days_window: int = QUOTES_BOOTSTRAP_DAYS) -> dict:
    """
    Auto-seed CLIENT_QUOTES.csv from router_log when it is empty.
    Returns: {"attempted": bool, "added": int, "draft_rows": int, "reason": str}
    """
    _ensure_quotes_csv()
    rows, err = _quotes_rows_safe()
    if err:
        return {"attempted": False, "added": 0, "draft_rows": 0, "reason": f"csv_error: {err}"}
    if rows:
        return {"attempted": False, "added": 0, "draft_rows": 0, "reason": "already_has_rows"}

    payload = _build_quote_drafts_from_router(limit=QUOTES_BOOTSTRAP_LIMIT, days_window=days_window)
    res = _apply_quote_drafts_to_csv()
    return {
        "attempted": True,
        "added": int(res.get("added", 0)),
        "draft_rows": int(payload.get("count", 0)),
        "reason": "bootstrapped",
    }


async def show_quotes_report(query) -> None:
    bootstrap = await asyncio.to_thread(_bootstrap_quotes_if_empty, QUOTES_BOOTSTRAP_DAYS)
    text = await asyncio.to_thread(_quotes_report_text)
    if bootstrap.get("attempted"):
        text = (
            f"Автозаполнение CLIENT_QUOTES: добавлено {bootstrap.get('added', 0)} строк "
            f"(кандидатов {bootstrap.get('draft_rows', 0)}, окно {QUOTES_BOOTSTRAP_DAYS} дней).\n\n"
            + text
        )
    elif str(bootstrap.get("reason", "")).startswith("csv_error:"):
        text = f"CLIENT_QUOTES warning: {bootstrap.get('reason')}\n\n{text}"
    kb = InlineKeyboardMarkup(
        [
            [_tile("⚡ Авто-черновик выцен", "quotes_draft_generate")],
            [_tile("✅ Применить в CLIENT_QUOTES", "quotes_draft_apply")],
            [_tile("🤖 AI вопрос", "ai_open")],
            [_tile("🏠 Панель", "dashboard")],
        ]
    )
    await _edit(query, text, kb)


async def generate_quotes_draft(query) -> None:
    payload = await asyncio.to_thread(_build_quote_drafts_from_router, 30, QUOTES_BOOTSTRAP_DAYS)
    rows = payload.get("rows", []) if isinstance(payload, dict) else []
    lines = [
        "⚡ Черновик выцен сформирован",
        "",
        f"Найдено кандидатов: {payload.get('count', 0)}",
        f"Файл: {QUOTES_DRAFTS_FILE}",
        "",
        "Первые 10 кандидатов:",
    ]
    if not rows:
        lines.append("• (новых кандидатов нет)")
    else:
        for r in rows[:10]:
            lines.append(f"• {r.get('client','—')}: {r.get('subject','—')}")
    lines += [
        "",
        "Далее нажми: `✅ Применить в CLIENT_QUOTES`.",
    ]
    kb = InlineKeyboardMarkup(
        [
            [_tile("✅ Применить в CLIENT_QUOTES", "quotes_draft_apply")],
            [_tile("💼 Отчёт по выценам", "quotes_report")],
            [_tile("🏠 Панель", "dashboard")],
        ]
    )
    await _edit(query, "\n".join(lines), kb)


async def apply_quotes_draft(query) -> None:
    res = await asyncio.to_thread(_apply_quote_drafts_to_csv)
    lines = [
        "✅ Черновик применён",
        "",
        f"Строк в черновике: {res.get('draft_rows', 0)}",
        f"Добавлено в CLIENT_QUOTES.csv: {res.get('added', 0)}",
        "",
        f"Файл: {CLIENT_QUOTES_CSV}",
    ]
    kb = InlineKeyboardMarkup(
        [
            [_tile("💼 Отчёт по выценам", "quotes_report")],
            [_tile("🏠 Панель", "dashboard")],
        ]
    )
    await _edit(query, "\n".join(lines), kb)


async def show_invoices(query) -> None:
    inv_rows = await asyncio.to_thread(_invoice_rows_window)
    it_rows = [r for r in inv_rows if _is_it_receipt(r)]
    biz_rows = [r for r in inv_rows if not _is_it_receipt(r)]
    items = biz_rows[:MAX_LIST]
    counts = await asyncio.to_thread(_finance_pdf_counts)

    state = _get_chat_state(query.message.chat_id)
    last_seen = (state.get("inv_last_seen_ts") or "").strip()

    lines = [f"📄 Фактуры / Бухгалтерия (за {WINDOW_DAYS} дней)", ""]
    lines += [
        "FINANCE/DOCS (PDF):",
        f"• Faktury: issued {counts['issued']}, received {counts['received']}",
        f"• ZUS {counts['zus']} | VAT {counts['vat']} | Leasing {counts['leasing']} | Rachunki {counts['rachunki']}",
        "",
        "Последние 10 входящих (FIRMA):",
    ]

    if not items:
        lines.append("• (пока пусто)")
    else:
        for r in items:
            ts = (r.get("ts_utc") or "").strip()
            subj = (r.get("subject") or "").strip() or (r.get("file") or "").strip()
            if len(subj) > 64:
                subj = subj[:61] + "..."
            new = "🆕 " if last_seen and ts and ts > last_seen else ""
            lines.append(f"• {new}{subj}")

        newest = max(((r.get("ts_utc") or "").strip() for r in items), default="")
        if newest:
            _set_chat_state(query.message.chat_id, {"inv_last_seen_ts": newest})

    if it_rows:
        lines += ["", f"🧾 IT‑чеки (скрыто): {len(it_rows)} (Anthropic/OpenAI/GitHub и т.п.)"]
    lines += [
        "",
        "Источник: `router_log.csv` (FIRMA) + `FINANCE/DOCS/*.pdf`.",
        f"router_log UTC: {_file_mtime_utc(ROUTER_LOG)}",
        f"FINANCE/DOCS UTC: {_file_mtime_utc(FINANCE_DOCS)}",
    ]
    await _edit(query, "\n".join(lines), _back_with_ai_kb())


async def show_status(query) -> None:
    status, ts = await asyncio.to_thread(_pipeline_last_status)
    last_err_text = await asyncio.to_thread(_read_text, PIPELINE_ERRORS, 120_000)
    has_err = bool(last_err_text.strip())

    lines = [
        "⚙️ Статус системы",
        "",
        f"Пайплайн: {status}",
        f"Время (UTC): {ts or '—'}",
        "",
        f"Логи: {LOG_DIR}",
        f"pipeline_run.log UTC: {_file_mtime_utc(PIPELINE_LOG)}",
        f"pipeline_errors.jsonl UTC: {_file_mtime_utc(PIPELINE_ERRORS)}",
        f"Ошибки: {'есть' if has_err else '—'}",
    ]
    if has_err:
        raw = last_err_text.splitlines()[-1].strip()
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {}

        if isinstance(obj, dict) and obj:
            stage = (obj.get("stage") or "").strip() or "UNKNOWN"
            msg = (obj.get("message") or "").strip()
            code = str(obj.get("exit_code") or "").strip()
            # Backward-compat: older logs used this wording.
            if "iCloud stage failed" in msg:
                msg = msg.replace("IMPORT iCloud stage failed", "IMPORT_GMAIL stage failed")
            short = msg[:240] + ("…" if len(msg) > 240 else "")
            lines += ["", f"Последняя ошибка: {stage} (код {code or '—'})", short]
        else:
            raw = raw[:600]
            if raw:
                lines += ["", f"Последняя ошибка (строка): {raw}"]
    await _edit(query, "\n".join(lines), _back_with_ai_kb())


async def show_risk_report(query) -> None:
    data = await asyncio.to_thread(_risk_report_data)
    lines = [
        "⚠️ Отчёт рисков",
        "",
        f"Платежи: всего {data['pay_total']}, просрочено {data['pay_overdue']}, <=3 дня {data['pay_due3']}",
        "",
        "Ближайшие платежи:",
    ]
    top = data["pay_top"] or ["(пусто)"]
    lines.extend([f"• {x}" for x in top[:5]])
    lines += ["", f"Email-риски (router_log, {WINDOW_DAYS} дней): {len(data['mail_risks'])}"]
    for r in data["mail_risks"][:5]:
        subj = (r.get("subject") or r.get("file") or "").strip()
        if len(subj) > 70:
            subj = subj[:67] + "..."
        pr = (r.get("payment_risk") or "n/a").lower()
        q = (r.get("quality") or "n/a").lower()
        lines.append(f"• {subj} [risk={pr}, quality={q}]")
    lines += [
        "",
        "Источник цифр:",
        "• `FINANCE/PAYMENTS.csv`",
        "• `00_INBOX/_ROUTER_LOGS/router_log.csv`",
        f"• UTC: payments={_file_mtime_utc(PAYMENTS_CSV)}, router={_file_mtime_utc(ROUTER_LOG)}",
    ]
    await _edit(query, "\n".join(lines), _back_with_ai_kb())


async def show_notify_menu(query) -> None:
    chat_id = query.message.chat_id
    enabled = _notify_enabled(chat_id)
    err = await asyncio.to_thread(_latest_pipeline_error)
    risk = await asyncio.to_thread(_risk_report_data)
    sig = _risk_signature(risk)
    missing_quotes = await asyncio.to_thread(_quotes_missing_amount_count)
    state = _get_chat_state(chat_id)
    last_risk = str(state.get("notify_last_risk_sig") or "")
    last_err = str(state.get("notify_last_error_raw") or "")
    sla_events = await asyncio.to_thread(_payment_sla_events)

    lines = [
        "Уведомления",
        "",
        f"Статус: {'ON' if enabled else 'OFF'}",
        f"Интервал проверки: {NOTIFY_INTERVAL_MIN} мин",
        f"Текущий риск: overdue={risk['pay_overdue']}, <=3d={risk['pay_due3']}, mail={len(risk['mail_risks'])}",
        f"SLA платежи (T-7/T-3/T-1/overdue): {len(sla_events)}",
        f"Выцены без суммы (open): {missing_quotes}",
        f"Ночной self-test: каждый день в {SELFTEST_HOUR_LOCAL:02d}:00 local",
        f"Последняя ошибка в логе: {'есть' if err.get('raw') else 'нет'}",
    ]
    if last_risk:
        lines.append("Последний отправленный risk-sig: есть")
    if last_err:
        lines.append("Последняя отправленная ошибка: есть")

    kb = InlineKeyboardMarkup(
        [
            [_tile("Включить", "notify_on"), _tile("Выключить", "notify_off")],
            [_tile("Тест уведомления", "notify_test"), _tile("⚠️ Отчёт рисков", "risk_report")],
            [_tile("🏠 Панель", "dashboard")],
        ]
    )
    await _edit(query, "\n".join(lines), kb)


async def notify_toggle(query, enabled: bool) -> None:
    chat_id = query.message.chat_id
    _set_chat_state(chat_id, {"notify_enabled": enabled})
    msg = "Уведомления включены." if enabled else "Уведомления выключены."
    kb = InlineKeyboardMarkup(
        [
            [_tile("Уведомления", "notify_menu")],
            [_tile("🏠 Панель", "dashboard")],
        ]
    )
    await _edit(query, msg, kb)


async def notify_test(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = query.message.chat_id
    text = (
        "Тест уведомления\n"
        f"UTC: {_utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        "Если это сообщение пришло, канал уведомлений работает."
    )
    await context.bot.send_message(chat_id=chat_id, text=text)
    await _edit(query, "Тест отправлен.", _back_with_ai_kb())


async def _notification_tick(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Background notifier:
    - sends when error line changes
    - sends when risk signature changes and risk is non-zero
    """
    try:
        try:
            chat_id = int(CHAT_ID_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            return

        if not _notify_enabled(chat_id):
            return

        state = _get_chat_state(chat_id)

        # 1) Pipeline error notifications
        err = _latest_pipeline_error()
        raw = err.get("raw", "")
        last_raw = str(state.get("notify_last_error_raw") or "")
        if raw and raw != last_raw:
            stage = err.get("stage", "") or "UNKNOWN"
            code = err.get("code", "") or "—"
            msg = (err.get("message", "") or "").strip()
            if "iCloud stage failed" in msg:
                msg = msg.replace("IMPORT iCloud stage failed", "IMPORT_GMAIL stage failed")
            notify_text = (
                "Уведомление: ошибка пайплайна\n"
                f"Stage: {stage}\n"
                f"Code: {code}\n"
                f"Message: {msg[:280]}"
            )
            await context.bot.send_message(chat_id=chat_id, text=_fit_message(notify_text))
            _set_chat_state(chat_id, {"notify_last_error_raw": raw})

        # 2) Risk profile notifications (only when there is actual risk)
        risk = _risk_report_data()
        has_risk = bool(
            risk.get("pay_overdue", 0) > 0
            or risk.get("pay_due3", 0) > 0
            or len(risk.get("mail_risks") or []) > 0
        )
        sig = _risk_signature(risk)
        last_sig = str(state.get("notify_last_risk_sig") or "")
        if has_risk and sig != last_sig:
            top = risk.get("pay_top") or []
            top_line = top[0] if top else "(нет)"
            notify_text = (
                "Уведомление: изменение рисков\n"
                f"Платежи: просрочено {risk['pay_overdue']}, <=3 дня {risk['pay_due3']}\n"
                f"Email-риски: {len(risk['mail_risks'])}\n"
                f"Ближайший: {top_line}"
            )
            await context.bot.send_message(chat_id=chat_id, text=_fit_message(notify_text))
            _set_chat_state(chat_id, {"notify_last_risk_sig": sig})

        # 3) SLA payment reminders (T-7/T-3/T-1/overdue), dedup by payment_id+stage.
        events = _payment_sla_events()
        sent = state.get("notify_payment_alerts", {})
        if not isinstance(sent, dict):
            sent = {}
        new_events: list[dict] = []
        for e in events:
            event_key = f"{e['payment_id']}|{e['stage']}"
            if event_key in sent:
                continue
            new_events.append(e)
            sent[event_key] = _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        if new_events:
            for e in new_events[:SLA_NOTIFY_MAX_PER_TICK]:
                if e["stage"] == "OVERDUE":
                    stage_text = f"ПРОСРОЧЕНО {abs(e['days_left'])} дн"
                else:
                    stage_text = f"T-{e['days_left']} дн"
                txt = (
                    "SLA-уведомление по оплате\n"
                    f"{e['name']}\n"
                    f"Срок: {e['deadline']} ({stage_text})\n"
                    f"Сумма: {e['amount']}\n"
                    f"id: {e['payment_id']}"
                )
                await context.bot.send_message(chat_id=chat_id, text=_fit_message(txt))
            if len(new_events) > SLA_NOTIFY_MAX_PER_TICK:
                rest = len(new_events) - SLA_NOTIFY_MAX_PER_TICK
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"SLA: еще {rest} уведомлений не отправлено в этом цикле (анти-спам лимит).",
                )

            # Keep state compact
            if len(sent) > 1200:
                keys = list(sent.keys())
                for k in keys[: len(sent) - 800]:
                    sent.pop(k, None)
            _set_chat_state(chat_id, {"notify_payment_alerts": sent})

        # 4) Daily reminder: open quotes without amount (no more than once/day)
        quote_rows = _client_quotes()
        missing_count = _quotes_missing_amount_count(quote_rows)
        if missing_count > 0:
            day_key = _utcnow().strftime("%Y-%m-%d")
            last_day = str(state.get("notify_quotes_missing_date") or "")
            if day_key != last_day:
                sample_clients: list[str] = []
                for r in quote_rows:
                    st = (r.get("status") or "").strip().lower()
                    if st != "open":
                        continue
                    if _parse_amount_number(str(r.get("amount") or "")) is not None:
                        continue
                    client = (r.get("client") or "").strip() or "Unknown"
                    if client not in sample_clients:
                        sample_clients.append(client)
                    if len(sample_clients) >= 5:
                        break
                sample = ", ".join(sample_clients) if sample_clients else "n/a"
                txt = (
                    "Напоминание по выценам\n"
                    f"Открытых выцен без суммы: {missing_count}\n"
                    f"Примеры клиентов: {sample}\n"
                    "Источник: FINANCE/CLIENT_QUOTES.csv"
                )
                await context.bot.send_message(chat_id=chat_id, text=_fit_message(txt))
                _set_chat_state(chat_id, {"notify_quotes_missing_date": day_key})
    except Exception as e:
        _log_runtime(f"notification tick error: {type(e).__name__}: {e}")


async def _nightly_selftest_tick(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        try:
            chat_id = int(CHAT_ID_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            return

        if not _notify_enabled(chat_id):
            return

        now_local = datetime.now().astimezone()
        if now_local.hour != SELFTEST_HOUR_LOCAL:
            return

        day_key = now_local.strftime("%Y-%m-%d")
        state = _get_chat_state(chat_id)
        if str(state.get("selftest_last_date") or "") == day_key:
            return

        txt = _selftest_text()
        await context.bot.send_message(chat_id=chat_id, text=_fit_message(txt))
        _set_chat_state(chat_id, {"selftest_last_date": day_key})
    except Exception as e:
        _log_runtime(f"nightly selftest tick error: {type(e).__name__}: {e}")


async def open_ai_mode(query) -> None:
    chat_id = query.message.chat_id
    msg_id = query.message.message_id
    _set_chat_state(chat_id, {"mode": "ai", "dashboard_message_id": msg_id})
    await _edit(
        query,
        "🤖 AI режим\n\nНапиши вопрос:\n"
        "• откуда цифры по рискам\n"
        "• что по оплатам\n"
        "• что по выценам\n"
        "• что по бухгалтерии\n\n"
        "AI отвечает только по реальным данным из логов/CSV.",
        _back_kb(),
    )


def _search_fast(query_text: str, max_results: int = 10, max_seconds: float = 2.0) -> list[tuple[str, bool]]:
    query_text = (query_text or "").strip().lower()
    if not query_text:
        return []

    start = time.time()
    roots = [ROOT / "CASES", ROOT / "FINANCE", ROOT / "00_INBOX" / "_DRAFTS"]

    results: list[tuple[str, bool]] = []
    for r in roots:
        if not r.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(r):
            if (time.time() - start) > max_seconds:
                return results

            base = os.path.basename(dirpath).lower()
            if query_text in base:
                results.append((str(Path(dirpath).relative_to(ROOT)), True))
                if len(results) >= max_results:
                    return results

            for fn in filenames:
                if query_text in fn.lower():
                    results.append((str((Path(dirpath) / fn).relative_to(ROOT)), False))
                    if len(results) >= max_results:
                        return results
    return results


async def show_search_prompt(query) -> None:
    chat_id = query.message.chat_id
    msg_id = query.message.message_id
    _set_chat_state(chat_id, {"mode": "search", "dashboard_message_id": msg_id})
    await _edit(query, "🔎 Поиск\n\nНапиши текст (например: `BMW`, `faktura`, `Monika`).", _back_kb())


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return

    chat_id = update.effective_chat.id
    state = _get_chat_state(chat_id)
    mode = state.get("mode")
    if mode not in {"search", "ai"}:
        return

    dash_id = state.get("dashboard_message_id")
    if not isinstance(dash_id, int):
        return

    q = (update.message.text or "").strip()
    if mode == "search":
        results = await asyncio.to_thread(_search_fast, q, 10, 2.0)
        if not results:
            text = f"🔎 Поиск: {q}\n\n(ничего не найдено)"
        else:
            lines = [f"🔎 Поиск: {q}", ""]
            for rel, is_dir in results:
                icon = "📁" if is_dir else "📄"
                lines.append(f"{icon} {rel}")
            text = "\n".join(lines)
        # reset mode
        _set_chat_state(chat_id, {"mode": None})
        kb = _back_kb()
    else:
        text = await asyncio.to_thread(_ai_answer, q)
        kb = _back_with_ai_kb()

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=dash_id,
            text=_fit_message(text),
            reply_markup=kb,
        )
    except Exception:
        # If edit fails (message deleted), just do nothing.
        _log_runtime("handle_text: failed to edit dashboard message")
        return


# =========================
# Operational commands
# =========================

def _health_text(context: ContextTypes.DEFAULT_TYPE, chat_id: Optional[int] = None) -> str:
    h = _health_snapshot()
    queue_depth = "n/a"
    try:
        uq = getattr(context.application, "update_queue", None)
        if uq is not None and hasattr(uq, "qsize"):
            queue_depth = str(uq.qsize())
    except Exception:
        queue_depth = "n/a"

    notify = "n/a"
    if isinstance(chat_id, int):
        notify = "ON" if _notify_enabled(chat_id) else "OFF"

    lines = [
        "Health report",
        f"UTC: {_utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        f"pipeline_status: {h['pipeline_status']}",
        f"pipeline_ts: {h['pipeline_ts']}",
        f"pipeline_age_min: {h['pipeline_age_min'] if h['pipeline_age_min'] is not None else 'n/a'}",
        f"last_error_stage: {h['last_error_stage']}",
        f"last_error_code: {h['last_error_code']}",
        f"last_error_age_min: {h['last_error_age_min'] if h['last_error_age_min'] is not None else 'n/a'}",
        f"payments_pending: {h['payments_pending']}",
        f"quotes_rows: {h['quotes_rows']}",
        f"quotes_missing_amount: {h['quotes_missing_amount']}",
        f"router_rows_window: {h['router_rows_window']}",
        f"notify: {notify}",
        f"pipeline_running: {h['pipeline_running']}",
        f"queue_depth: {queue_depth}",
        f"cache_entries: {h['cache_entries']}",
    ]
    return _fit_message("\n".join(lines))


async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    text = _health_text(context, update.effective_chat.id)
    await update.message.reply_text(text)


async def cmd_selftest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    text = await asyncio.to_thread(_selftest_text)
    await update.message.reply_text(text)


# =========================
# Handlers
# =========================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await update.message.reply_text("⛔ Доступ запрещен")
        return

    # Prefer editing the existing dashboard message (no spam).
    chat_id = update.effective_chat.id
    state = _get_chat_state(chat_id)
    existing_id = state.get("dashboard_message_id")

    text = await asyncio.to_thread(build_dashboard_text)
    summary = await asyncio.to_thread(_build_dashboard_summary)
    kb = _dashboard_keyboard(summary)

    if isinstance(existing_id, int):
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=existing_id,
                text=text,
                reply_markup=kb,
            )
            _set_chat_state(chat_id, {"mode": None})
            return
        except Exception:
            pass

    # Fallback: send a new dashboard message and store its message_id.
    msg = await update.message.reply_text(text, reply_markup=kb)
    _set_chat_state(chat_id, {"dashboard_message_id": msg.message_id, "mode": None})


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    if not _is_authorized(update):
        await _edit(query, "⛔ Доступ запрещен", None)
        return

    cb = query.data or ""
    try:
        if cb == "dashboard":
            await show_dashboard(query)
        elif cb == "mail":
            await show_mail(query)
        elif cb == "mail_run":
            await run_pipeline(query)
        elif cb == "payables":
            await show_payables(query)
        elif cb == "risk_report":
            await show_risk_report(query)
        elif cb == "quotes":
            await show_quotes(query)
        elif cb == "quotes_report":
            await show_quotes_report(query)
        elif cb == "quotes_draft_generate":
            await generate_quotes_draft(query)
        elif cb == "quotes_draft_apply":
            await apply_quotes_draft(query)
        elif cb == "invoices":
            await show_invoices(query)
        elif cb == "search":
            await show_search_prompt(query)
        elif cb == "ai_open":
            await open_ai_mode(query)
        elif cb == "notify_menu":
            await show_notify_menu(query)
        elif cb == "notify_on":
            await notify_toggle(query, True)
        elif cb == "notify_off":
            await notify_toggle(query, False)
        elif cb == "notify_test":
            await notify_test(query, context)
        elif cb == "status":
            await show_status(query)
        else:
            await show_dashboard(query)
    except Exception as e:
        _log_runtime(f"callback '{cb}' failed: {type(e).__name__}: {e}")
        await _edit(query, "Ошибка интерфейса. Нажми «Панель» и повтори.", _back_kb())


def main() -> None:
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()

    application = Application.builder().token(token).concurrent_updates(False).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("health", cmd_health))
    application.add_handler(CommandHandler("selftest", cmd_selftest))
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Background notifications for one authorized chat.
    if application.job_queue is not None:
        application.job_queue.run_repeating(_notification_tick, interval=NOTIFY_INTERVAL_MIN * 60, first=30)
        application.job_queue.run_repeating(_nightly_selftest_tick, interval=1800, first=120)

    _log_runtime("bot start")
    print("[OK] Telegram dashboard bot running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()

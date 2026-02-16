import os
import csv
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

# AI Client Evaluator
try:
    from client_evaluator import evaluate_client_email
    EVALUATOR_AVAILABLE = True
except ImportError:
    EVALUATOR_AVAILABLE = False
    def evaluate_client_email(subject, body):
        return {'payment_risk': 'n/a', 'project_type': 'unknown', 'urgency': 'normal', 'quality': 'unknown'}

# PDF support
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# -----------------------------
# CONFIG
# -----------------------------
ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")

SRC_DIR = ROOT / "CASES" / "_INBOX"
REVIEW_DIR = ROOT / "CASES" / "_REVIEW"

DST_KLIENTS = ROOT / "CASES" / "01_KLIENTS" / "_INBOX"
DST_FIRMA   = ROOT / "CASES" / "02_FIRMA" / "_INBOX"
DST_CAR     = ROOT / "CASES" / "03_CAR" / "_INBOX"
LOG_DIR = ROOT / "00_INBOX" / "_ROUTER_LOGS"
LOG_CSV = LOG_DIR / "router_log.csv"

DRY_RUN = False  # True = только показать, без переносов


# -----------------------------
# SIMPLE HEURISTICS (NO "YOUR RULES")
# -----------------------------
# Мы не "угадываем клиента". Мы делаем только грубую сортировку:
# - CAR: если видно авто-ключи
# - FIRMA: если видно ZUS/US/фактуры/банки/контракты и т.п.
# - KLIENTS: если видно слова типа kuchnia/szafa/umowa/dom/adres и т.п.
# Всё остальное -> REVIEW

CAR_KEYS = {
    "bmw", "vin", "oc", "ac", "polisa", "ubezpiec", "koliz", "szkoda", "warsztat",
    "przegl", "diagn", "ista", "inpa", "car", "auto", "rejestr", "dowod rejestr",
}
FIRMA_KEYS = {
    "zus", "pue", "us", "vat", "pit", "cit", "faktura", "rachunek", "invoice", "ksef",
    "ksieg", "umowa", "kontrakt", "leasing", "mbank", "pekao", "revolut", "bank",
    "skladka", "podatek", "firma", "dzialaln",
    # Financial docs (added 2026-02-03)
    "jpk", "zusdra", "zusrca", "vat-7", "deklaracja", "wyciąg", "przelewy",
    "powiadomienie o wystawieniu", "potwierdzenie płatności", "upo", "e-deklaracje",
}
KLIENTS_KEYS = {
    "kuchnia", "szafa", "zabud", "meble", "pomiar", "wycena", "oferta", "projekt",
    "dom", "mieszkanie", "legionowo", "warszawa", "front", "blat", "gola",
}

# приоритет: CAR > FIRMA > KLIENTS (чтобы не сыпалось в клиентов всё подряд)
def classify(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in CAR_KEYS):
        return "CAR"
    if any(k in t for k in FIRMA_KEYS):
        return "FIRMA"
    if any(k in t for k in KLIENTS_KEYS):
        return "KLIENTS"
    return "REVIEW"


# -----------------------------
# HELPERS
# -----------------------------

def extract_text_from_pdf(pdf_path: Path, max_chars: int = 1000) -> str:
    """Extract text from PDF file (first page + limit)"""
    if not PDF_AVAILABLE or pdf_path.suffix.lower() != ".pdf":
        return ""
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            # Extract from first 2 pages max
            for page_num, page in enumerate(pdf.pages[:2]):
                text += page.extract_text() or ""
                if len(text) > max_chars:
                    break
            return text[:max_chars]
    except Exception as e:
        return f"[PDF read error: {type(e).__name__}]"


def ensure_dirs():
    for p in [SRC_DIR, REVIEW_DIR, DST_KLIENTS, DST_FIRMA, DST_CAR, LOG_DIR]:
        p.mkdir(parents=True, exist_ok=True)

def write_log(row: dict):
    exists = LOG_CSV.exists()
    with LOG_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            w.writeheader()
        w.writerow(row)

def move_pair(file_path: Path, meta_path: Path, dst_dir: Path):
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_file = dst_dir / file_path.name
    dst_meta = dst_dir / meta_path.name

    # защита от перезаписи
    if dst_file.exists() or dst_meta.exists():
        # если уже есть — в REVIEW (чтобы не затереть)
        return False, "COLLISION_EXISTS"

    if DRY_RUN:
        return True, "DRY_RUN"

    shutil.move(str(file_path), str(dst_file))
    shutil.move(str(meta_path), str(dst_meta))
    return True, "MOVED"

def main():
    ensure_dirs()

    # берём только meta.json и ищем парный файл
    metas = sorted(SRC_DIR.glob("*.meta.json"))

    if not metas:
        print("Router: nothing to do in", SRC_DIR)
        return

    for meta_path in metas:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            # битый meta -> REVIEW
            meta = {}

        saved_filename = meta.get("saved_filename") or meta_path.name.replace(".meta.json", "")
        file_path = SRC_DIR / saved_filename

        # если файл отсутствует — REVIEW (но meta перенесём)
        if not file_path.exists():
            decision = "REVIEW"
            # Переносим только meta-файл в REVIEW (без попытки move_pair с двух одинаковых аргументов)
            dst_meta = REVIEW_DIR / meta_path.name
            try:
                if DRY_RUN:
                    status = "DRY_RUN"
                else:
                    # защититься от перезаписи: если уже есть, добавим таймстамп
                    if dst_meta.exists():
                        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                        dst_meta = REVIEW_DIR / f"{meta_path.stem}_{stamp}{meta_path.suffix}"
                    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(meta_path), str(dst_meta))
                    status = "META_MOVED_TO_REVIEW"
            except Exception as e:
                status = f"META_MOVE_ERR:{type(e).__name__}"
            write_log({
                "ts_utc": datetime.now(timezone.utc).isoformat(),
                "decision": decision,
                "status": status,
                "file": saved_filename,
                "meta": dst_meta.name,
                "from": (meta.get("from") or "")[:200],
                "subject": (meta.get("subject") or "")[:200],
                "payment_risk": "n/a",
                "project_type": "unknown",
                "urgency": "normal",
                "quality": "unknown",
            })
            continue

        # классификация по объединённому тексту
        text = " | ".join([
            file_path.name,
            meta.get("subject", ""),
            meta.get("from", ""),
            meta.get("original_filename", ""),
        ])

        # AI Evaluation (if available)
        evaluation = {'payment_risk': 'n/a', 'project_type': 'unknown', 'urgency': 'normal', 'quality': 'unknown'}
        if EVALUATOR_AVAILABLE:
            try:
                subject = meta.get("subject", "")
                # Try to read file preview for body (max 1000 chars)
                body_preview = ""
                try:
                    if file_path.suffix.lower() in [".txt", ".md", ".eml"]:
                        body_preview = file_path.read_text(encoding='utf-8', errors='ignore')[:1000]
                    elif file_path.suffix.lower() == ".pdf":
                        body_preview = extract_text_from_pdf(file_path, max_chars=1000)
                except:
                    pass
                evaluation = evaluate_client_email(subject, body_preview)
            except Exception as e:
                evaluation['_error'] = str(e)

        decision = classify(text)
        
        # Override: high risk or vague → REVIEW
        if evaluation.get('payment_risk') == 'high' or evaluation.get('quality') == 'vague':
            decision = "REVIEW"

        if decision == "CAR":
            dst = DST_CAR
        elif decision == "FIRMA":
            dst = DST_FIRMA
        elif decision == "KLIENTS":
            dst = DST_KLIENTS
        else:
            dst = REVIEW_DIR

        ok, status = move_pair(file_path, meta_path, dst)

        # если коллизия — отправляем в REVIEW, чтобы не затереть
        if not ok and status == "COLLISION_EXISTS":
            dst = REVIEW_DIR
            ok2, status2 = move_pair(file_path, meta_path, dst)
            status = f"COLLISION_TO_REVIEW:{status2}"
            decision = "REVIEW"

        write_log({
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
            "status": status,
            "file": file_path.name,
            "meta": meta_path.name,
            "from": (meta.get("from") or "")[:200],
            "subject": (meta.get("subject") or "")[:200],
            "payment_risk": evaluation.get('payment_risk', 'n/a'),
            "project_type": evaluation.get('project_type', 'unknown'),
            "urgency": evaluation.get('urgency', 'normal'),
            "quality": evaluation.get('quality', 'unknown'),
        })

    print("Router done.")

if __name__ == "__main__":
    main()

"""
organize_finance_docs.py - Financial document organizer

Scans FINANCE_DOCS/_INBOX and organizes documents:
- ZUS (social insurance): deklaracje, UPO, potwierdzenia
- VAT: JPK-V7M, deklaracje VAT-7, VAT-UE
- PIT: roczne zeznania podatkowe
- FAKTURY_ISSUED: faktury sprzedaży (FV) wystawione przez ciebie
- FAKTURY_RECEIVED: faktury zakupowe (otrzymane od dostawców)
- RACHUNKI: wyciągi bankowe, przelewy
- ZAKUPY: potwierdzenia zakupów (Allegro, sklepy)

Output structure:
FINANCE/DOCS/{TYPE}/YYYY/MM/YYYYMMDD_TYPE_FILENAME.ext
"""

import re
import shutil
from pathlib import Path
from datetime import datetime
import json

# === CONFIG ===
ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
INBOX = ROOT / "FINANCE_DOCS" / "_INBOX"
FINANCE_DOCS = ROOT / "FINANCE" / "DOCS"

LOG_FILE = ROOT / "99_SYSTEM" / "_LOGS" / "finance_organize_log.csv"

# === CLASSIFICATION KEYWORDS ===
PATTERNS = {
    "ZUS": {
        "keywords": ["zus", "zusdra", "zusrca", "społeczne ubezpieczenie", "social insurance", "upo"],
        "dest": "ZUS"
    },
    "VAT": {
        "keywords": ["jpk", "vat-7", "vat-ue", "vat7", "vatue", "vatr", "podatek vat"],
        "dest": "VAT"
    },
    "PIT": {
        "keywords": ["pit-36", "pit-11", "pit36", "pit11", "zeznanie roczne", "epit"],
        "dest": "PIT"
    },
    "FAKTURA_ISSUED": {
        "keywords": ["faktura sprzedaży", "fv", "fs", "invoice", "faktura nr", "fs-", "fs_"],
        "exclude": ["otrzymałeś", "kupiłeś", "zapłaciłeś", "zamówienie", "biblioteczka"],
        "dest": "FAKTURY/ISSUED"
    },
    "FAKTURA_RECEIVED": {
        "keywords": ["faktura", "otrzymałeś fakturę", "kupiłeś i zapłaciłeś", 
                     "biblioteczka realizacja", "formanufaktura"],
        "exclude": ["sprzedaży", "fs-", "fs_", "fv"],
        "dest": "FAKTURY/RECEIVED"
    },
    "RACHUNEK": {
        "keywords": ["wyciąg", "rachunek", "historia operacji", "przelewy", "bank",
                     "energia elektryczna", "najem lokalu", "czynsz", "prąd", "gaz", 
                     "woda", "opłaty", "rachunki"],
        "dest": "RACHUNKI"
    },
    "ZAKUP": {
        "keywords": ["kupiłeś", "zamówienie", "potwierdzenie zakupu", "allegro",
                     "kupiles", "zapłaciłeś"],
        "dest": "ZAKUPY"
    }
}


def sanitize_filename(name: str) -> str:
    """Remove unsafe characters"""
    # Remove emoji, special chars
    name = re.sub(r'[^\w\s\-_\.]', '', name)
    # Replace spaces with underscores
    name = name.replace(' ', '_')
    # Remove multiple underscores
    name = re.sub(r'_+', '_', name)
    return name[:200]  # Max length


def extract_date_from_filename(filename: str) -> str | None:
    """
    Extract YYYYMMDD from filename patterns:
    - 20260111__19bab3a5__filename.pdf
    - Deklaracja_JPKV7M_2025_09.pdf
    - invoice_42_06_2024.pdf
    """
    # Pattern 1: email format YYYYMMDD__msgid__
    match = re.search(r'(\d{8})__[a-f0-9]+__', filename)
    if match:
        return match.group(1)
    
    # Pattern 2: YYYY_MM or YYYY-MM
    match = re.search(r'(\d{4})[-_](\d{2})', filename)
    if match:
        year, month = match.groups()
        return f"{year}{month}01"  # First day of month
    
    # Pattern 3: DD_MM_YYYY or MM_YYYY
    match = re.search(r'(\d{2})_(\d{2})_(\d{4})', filename)
    if match:
        day, month, year = match.groups()
        return f"{year}{month}{day}"
    
    return None


def classify_document(filepath: Path) -> str | None:
    """
    Classify document based on filename and content.
    Returns: TYPE key from PATTERNS or None
    """
    filename_lower = filepath.name.lower()
    
    for doc_type, config in PATTERNS.items():
        # Check keywords
        has_keyword = any(kw in filename_lower for kw in config["keywords"])
        
        # Check exclusions
        has_exclusion = False
        if "exclude" in config:
            has_exclusion = any(ex in filename_lower for ex in config["exclude"])
        
        if has_keyword and not has_exclusion:
            return doc_type
    
    return None


def organize_file(filepath: Path, doc_type: str, dry_run: bool = False) -> dict:
    """
    Move file to organized structure: FINANCE/DOCS/{TYPE}/YYYY/MM/YYYYMMDD_TYPE_FILENAME.ext
    Returns: dict with status
    """
    config = PATTERNS[doc_type]
    dest_base = FINANCE_DOCS / config["dest"]
    
    # Extract date
    date_str = extract_date_from_filename(filepath.name)
    if not date_str:
        # Fallback to file mtime
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
        date_str = mtime.strftime("%Y%m%d")
    
    # Parse YYYY/MM
    year = date_str[:4]
    month = date_str[4:6]
    
    # Destination folder
    dest_folder = dest_base / year / month
    
    # New filename: YYYYMMDD_TYPE_sanitized.ext
    sanitized_name = sanitize_filename(filepath.stem)
    new_name = f"{date_str}_{doc_type}_{sanitized_name}{filepath.suffix}"
    dest_path = dest_folder / new_name
    
    # Check if already exists
    if dest_path.exists():
        return {
            "source": str(filepath),
            "dest": str(dest_path),
            "type": doc_type,
            "status": "SKIP_EXISTS",
            "date": date_str
        }
    
    if not dry_run:
        dest_folder.mkdir(parents=True, exist_ok=True)
        shutil.move(str(filepath), str(dest_path))
        status = "MOVED"
    else:
        status = "DRY_RUN"
    
    return {
        "source": str(filepath),
        "dest": str(dest_path),
        "type": doc_type,
        "status": status,
        "date": date_str
    }


def scan_and_organize(dry_run: bool = True):
    """
    Main function: scan INBOX and organize
    """
    if not INBOX.exists():
        print(f"❌ INBOX not found: {INBOX}")
        return
    
    results = []
    
    # Find all PDF/XLSX files recursively
    for ext in ["*.pdf", "*.xlsx", "*.xml"]:
        for filepath in INBOX.rglob(ext):
            # Skip meta.json files
            if filepath.name.endswith(".meta.json"):
                continue
            
            # Classify
            doc_type = classify_document(filepath)
            
            if doc_type:
                result = organize_file(filepath, doc_type, dry_run=dry_run)
                results.append(result)
                
                status_icon = "📄" if result["status"] == "DRY_RUN" else "✅"
                print(f"{status_icon} {doc_type:20} {filepath.name[:60]}")
            else:
                print(f"⚠️  UNCLASSIFIED: {filepath.name[:60]}")
                results.append({
                    "source": str(filepath),
                    "dest": "",
                    "type": "UNKNOWN",
                    "status": "SKIP_UNCLASSIFIED",
                    "date": ""
                })
    
    # Summary
    print("\n" + "="*80)
    print("📊 SUMMARY:")
    by_type = {}
    by_status = {}
    
    for r in results:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    
    print("\nBy Type:")
    for t, count in sorted(by_type.items()):
        print(f"  {t:20} {count:3}")
    
    print("\nBy Status:")
    for s, count in sorted(by_status.items()):
        print(f"  {s:20} {count:3}")
    
    # Save log
    if not dry_run and results:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        import csv
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "source", "dest", "type", "status", "date"])
            if LOG_FILE.stat().st_size == 0:
                writer.writeheader()
            
            for r in results:
                writer.writerow({
                    "timestamp": datetime.now().isoformat(),
                    **r
                })
        
        print(f"\n✅ Log saved: {LOG_FILE}")
    
    return results


if __name__ == "__main__":
    import sys
    
    # Windows console fix
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    
    print("🔍 FINANCE DOCS ORGANIZER")
    print(f"📂 Source: {INBOX}")
    print(f"📂 Destination: {FINANCE_DOCS}")
    print(f"🧪 Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will move files)'}")
    print("="*80 + "\n")
    
    results = scan_and_organize(dry_run=dry_run)
    
    if dry_run:
        print("\n💡 To execute: python organize_finance_docs.py --run")

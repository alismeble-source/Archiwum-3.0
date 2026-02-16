"""
show_finance_summary.py - Quick finance overview

Shows:
- Organized files by type (count + dates)
- Upcoming deadlines from DEADLINES.csv
- Unprocessed files in _INBOX
"""

from pathlib import Path
from datetime import datetime, timedelta
import csv

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
FINANCE_DOCS = ROOT / "FINANCE" / "DOCS"
INBOX = ROOT / "FINANCE_DOCS" / "_INBOX"
DEADLINES_CSV = ROOT / "FINANCE" / "_CALENDAR" / "DEADLINES.csv"

def count_files_by_type():
    """Count organized files"""
    print("=" * 80)
    print("📊 ORGANIZED FINANCE DOCS")
    print("=" * 80)
    
    for doc_type in ["ZUS", "VAT", "PIT", "FAKTURY", "RACHUNKI", "ZAKUPY"]:
        type_path = FINANCE_DOCS / doc_type
        if type_path.exists():
            files = list(type_path.rglob("*.pdf")) + list(type_path.rglob("*.xml"))
            if files:
                # Find newest and oldest
                files_sorted = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
                newest = datetime.fromtimestamp(files_sorted[0].stat().st_mtime)
                oldest = datetime.fromtimestamp(files_sorted[-1].stat().st_mtime)
                
                print(f"\n{doc_type:15} {len(files):3} files")
                print(f"                Newest: {newest.strftime('%Y-%m-%d')}")
                print(f"                Oldest: {oldest.strftime('%Y-%m-%d')}")
                
                # Show subfolder breakdown for FAKTURY
                if doc_type == "FAKTURY":
                    issued = len(list((type_path / "ISSUED").rglob("*.pdf")))
                    received = len(list((type_path / "RECEIVED").rglob("*.pdf")))
                    print(f"                  ├─ ISSUED: {issued}")
                    print(f"                  └─ RECEIVED: {received}")


def show_deadlines():
    """Show upcoming deadlines"""
    print("\n" + "=" * 80)
    print("📅 UPCOMING DEADLINES")
    print("=" * 80)
    
    if not DEADLINES_CSV.exists():
        print("⚠️  No DEADLINES.csv found")
        return
    
    with open(DEADLINES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        deadlines = list(reader)
    
    today = datetime.now().date()
    
    for dl in deadlines:
        due_date_str = dl.get("DUE_DATE", "")
        if not due_date_str:
            continue
        
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        
        days_left = (due_date - today).days
        
        if days_left < 0:
            status = f"❌ OVERDUE {abs(days_left)} days"
        elif days_left == 0:
            status = "🔴 TODAY"
        elif days_left <= 7:
            status = f"⚠️  {days_left} days"
        elif days_left <= 30:
            status = f"✅ {days_left} days"
        else:
            continue  # Skip far future
        
        print(f"\n{status:20} {dl['TITLE']}")
        print(f"                     Due: {due_date_str}")
        if dl.get("FILE_PATH"):
            print(f"                     Path: {dl['FILE_PATH']}")


def show_unprocessed():
    """Count unprocessed files in INBOX"""
    print("\n" + "=" * 80)
    print("📥 UNPROCESSED FILES (INBOX)")
    print("=" * 80)
    
    if not INBOX.exists():
        print("✅ INBOX empty or doesn't exist")
        return
    
    pdf_files = list(INBOX.rglob("*.pdf"))
    xlsx_files = list(INBOX.rglob("*.xlsx"))
    xml_files = list(INBOX.rglob("*.xml"))
    
    total = len(pdf_files) + len(xlsx_files) + len(xml_files)
    
    print(f"\nTotal unprocessed: {total}")
    print(f"  PDF:  {len(pdf_files)}")
    print(f"  XLSX: {len(xlsx_files)}")
    print(f"  XML:  {len(xml_files)}")
    
    if total > 0:
        print(f"\n💡 Run: python organize_finance_docs.py --run")


if __name__ == "__main__":
    # Ensure UTF-8 output for Windows PowerShell
    import sys
    if sys.platform == 'win32':
        import codecs
        sys.stdout.reconfigure(encoding='utf-8')
    
    count_files_by_type()
    show_deadlines()
    show_unprocessed()
    
    print("\n" + "=" * 80)

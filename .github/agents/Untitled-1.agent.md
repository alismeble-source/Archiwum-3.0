import os
import hashlib
from pathlib import Path
from collections import defaultdict
import csv
from datetime import datetime

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
CASES = ROOT / "CASES"
REPORT_DIR = ROOT / "00_INBOX" / "_ROUTER_LOGS"
REPORT_FILE = REPORT_DIR / f"duplicates_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    sha_map = defaultdict(list)
    total_files = 0
    
    print("Scanning files in CASES...")
    for file_path in CASES.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.name.endswith(".meta.json") or ".bak" in file_path.name:
            continue
        
        total_files += 1
        if total_files % 100 == 0:
            print(f"  Scanned: {total_files}...")
        
        sha = sha1_file(file_path)
        if sha:
            sha_map[sha].append(file_path)
    
    duplicates = {sha: paths for sha, paths in sha_map.items() if len(paths) > 1}
    
    with REPORT_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["SHA1", "Count", "Size (bytes)", "Files"])
        
        for sha, paths in sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True):
            size = paths[0].stat().st_size if paths[0].exists() else 0
            file_list = " | ".join([str(p.relative_to(ROOT)) for p in paths])
            w.writerow([sha, len(paths), size, file_list])
    
    print(f"\n✓ Total files scanned: {total_files}")
    print(f"✓ Duplicate groups found: {len(duplicates)}")
    print(f"✓ Report saved: {REPORT_FILE.name}")

if __name__ == "__main__":
    main()
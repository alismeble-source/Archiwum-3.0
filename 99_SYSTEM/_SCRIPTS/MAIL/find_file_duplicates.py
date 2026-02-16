#!/usr/bin/env python3
"""
Find duplicate files by SHA256 hash + file size.
Detects true duplicates (same content, different filenames).
"""

import hashlib
import csv
from datetime import datetime
from pathlib import Path
from collections import defaultdict

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
SEARCH_DIRS = [
    ROOT / "02_KLIENCI",
    ROOT / "01_FIRMA",
    ROOT / "04_CAR",
    ROOT / "_REVIEW",
    ROOT / "CASES",
]

REPORT_DIR = ROOT / "00_INBOX" / "_ROUTER_LOGS"
REPORT_FILE = REPORT_DIR / f"duplicates_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# Skip files
SKIP_EXTENSIONS = {'.meta.json', '.lock', '.tmp'}
MIN_FILE_SIZE = 1024  # Ignore files < 1KB


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        return f"ERROR:{type(e).__name__}"


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Scanning for duplicates...")
    hashes = defaultdict(list)  # {hash: [(file_path, size, hash_str), ...]}
    
    total_files = 0
    total_size = 0
    
    # Scan all files
    for search_dir in SEARCH_DIRS:
        if not search_dir.exists():
            continue
        
        for file_path in search_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Skip certain files
            if file_path.suffix in SKIP_EXTENSIONS:
                continue
            
            file_size = file_path.stat().st_size
            if file_size < MIN_FILE_SIZE:
                continue
            
            # Calculate hash
            file_hash = calculate_sha256(file_path)
            if file_hash.startswith("ERROR:"):
                print(f"[ERROR] {file_path}: {file_hash}")
                continue
            
            hashes[file_hash].append((file_path, file_size))
            total_files += 1
            total_size += file_size
    
    # Find duplicates
    duplicates = {k: v for k, v in hashes.items() if len(v) > 1}
    
    print(f"Scanned: {total_files} files ({total_size / 1024 / 1024:.1f} MB)")
    print(f"Found {len(duplicates)} duplicate groups\n")
    
    # Write report
    with REPORT_FILE.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['hash', 'size_bytes', 'file_count', 'file_path'])
        
        for file_hash, files in sorted(duplicates.items()):
            size = files[0][1]
            for file_path, _ in files:
                writer.writerow([file_hash, size, len(files), str(file_path)])
    
    # Print summary
    print("=== DUPLICATE GROUPS ===\n")
    for file_hash, files in sorted(duplicates.items()):
        size_mb = files[0][1] / 1024 / 1024
        print(f"Hash: {file_hash[:16]}...")
        print(f"Size: {size_mb:.2f} MB | Count: {len(files)}")
        for file_path, _ in files:
            print(f"  - {file_path}")
        print()
    
    print(f"Report saved: {REPORT_FILE}")
    print(f"Total duplicate data: {sum(len(v) * v[0][1] for v in duplicates.values()) / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()

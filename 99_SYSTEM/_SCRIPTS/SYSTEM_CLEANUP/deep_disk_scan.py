#!/usr/bin/env python3
"""
Deep disk space audit - find ALL folders taking space on C: drive.
Shows where 300 GB is hiding.
"""

import os
from pathlib import Path
from datetime import datetime

REPORT_DIR = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0\00_INBOX\_PHOTO_DEDUP")


def get_folder_size(folder_path: Path) -> int:
    """Get total size of folder (recursive)"""
    try:
        total = 0
        for entry in folder_path.rglob("*"):
            try:
                if entry.is_file() and not entry.is_symlink():
                    total += entry.stat().st_size
            except (PermissionError, OSError):
                pass
        return total
    except (PermissionError, OSError):
        return 0


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:>8.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:>8.2f} PB"


def scan_all_folders():
    """Deep scan of C: drive - find all folders with their sizes"""
    print("="*100)
    print("  DEEP DISK SCAN - Finding where 300 GB is hiding")
    print("="*100)
    print("\nScanning all folders on C: drive (this may take 5-10 minutes)...\n")
    
    # Skip system folders
    skip_list = {
        'System Volume Information', '$Recycle.Bin', 'ProgramData', 
        'Program Files', 'Program Files (x86)', 'Windows', 'Recovery',
        'PerfLogs', '$RECYCLE.BIN'
    }
    
    folder_sizes = {}
    scanned = 0
    
    try:
        for root, dirs, files in os.walk("C:\\", topdown=True):
            # Skip protected/system folders
            dirs[:] = [d for d in dirs if d not in skip_list]
            
            try:
                folder_path = Path(root)
                size = sum(
                    os.path.getsize(os.path.join(root, f))
                    for f in files
                    if os.path.isfile(os.path.join(root, f))
                )
                
                if size > 0:
                    folder_sizes[root] = size
                
                scanned += 1
                if scanned % 500 == 0:
                    print(f"  Scanned: {scanned} folders... Found: {len(folder_sizes)} with data")
            
            except (PermissionError, OSError):
                pass
    
    except (PermissionError, OSError):
        pass
    
    print(f"\n  Total scanned: {scanned} folders")
    print(f"  Folders with data: {len(folder_sizes)}")
    
    return folder_sizes


def main():
    folder_sizes = scan_all_folders()
    
    # Sort by size
    sorted_folders = sorted(folder_sizes.items(), key=lambda x: x[1], reverse=True)
    
    print("\n" + "="*100)
    print("  TOP 50 LARGEST FOLDERS")
    print("="*100)
    print(f"{'Rank':<6} {'Size':<15} {'Path':<80}")
    print("-" * 100)
    
    total_size = 0
    for i, (path, size) in enumerate(sorted_folders[:50], 1):
        total_size += size
        print(f"{i:<6} {format_size(size):<15} {path:<80}")
    
    print("\n" + "="*100)
    print(f"Total size (top 50): {format_size(total_size)}")
    print("="*100)
    
    # Generate report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORT_DIR / f"DISK_DEEP_SCAN_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("="*100 + "\n")
        f.write("  DISK DEEP SCAN - ALL FOLDERS\n")
        f.write("="*100 + "\n\n")
        
        f.write(f"{'Rank':<6} {'Size':<15} {'Path':<80}\n")
        f.write("-" * 100 + "\n")
        
        grand_total = 0
        for i, (path, size) in enumerate(sorted_folders, 1):
            grand_total += size
            f.write(f"{i:<6} {format_size(size):<15} {path:<80}\n")
        
        f.write("\n" + "="*100 + "\n")
        f.write(f"GRAND TOTAL: {format_size(grand_total)}\n")
        f.write("="*100 + "\n")
    
    print(f"\nFull report saved: {report_file}\n")


if __name__ == "__main__":
    main()

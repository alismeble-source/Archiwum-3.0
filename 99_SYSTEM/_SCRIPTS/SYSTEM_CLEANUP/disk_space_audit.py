#!/usr/bin/env python3
"""
Comprehensive disk cleanup audit - find what's eating 300 GB.
Shows largest folders, temp files, caches, duplicates, etc.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict

REPORT_DIR = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0\00_INBOX\_PHOTO_DEDUP")


def get_folder_size(folder_path: Path, max_depth=None, current_depth=0) -> int:
    """Get total size of folder (recursive)"""
    try:
        total = 0
        for entry in folder_path.iterdir():
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir() and (max_depth is None or current_depth < max_depth):
                    total += get_folder_size(entry, max_depth, current_depth + 1)
            except (PermissionError, OSError):
                continue
        return total
    except (PermissionError, OSError):
        return 0


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def scan_root_folders():
    """Scan C: drive root folders"""
    print("="*80)
    print("  DISK CLEANUP AUDIT - Finding 300 GB")
    print("="*80)
    print("\nScanning C: drive root folders...\n")
    
    folders = {}
    
    try:
        for entry in Path("C:\\").iterdir():
            if not entry.is_dir():
                continue
            
            # Skip protected folders
            skip = ['System Volume Information', '$Recycle.Bin', 'ProgramData', 
                    'Program Files', 'Program Files (x86)', 'Windows', 'Recovery']
            
            if entry.name in skip:
                continue
            
            try:
                size = get_folder_size(entry, max_depth=1)
                folders[entry.name] = size
                print(f"  {entry.name:<40} {format_size(size):>15}")
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    
    return folders


def scan_user_appdata():
    """Scan user AppData for caches"""
    print("\n" + "="*80)
    print("  APPDATA ANALYSIS (Caches, Temp)")
    print("="*80)
    print("\nScanning C:\\Users\\alimg\\AppData\\...\n")
    
    appdata_dirs = {}
    user_path = Path(r"C:\Users\alimg\AppData")
    
    if user_path.exists():
        for item in [user_path / "Local", user_path / "Roaming", user_path / "LocalLow"]:
            if item.exists():
                try:
                    # Top-level subfolders
                    for entry in item.iterdir():
                        if entry.is_dir():
                            try:
                                size = get_folder_size(entry, max_depth=2)
                                appdata_dirs[f"{item.name}/{entry.name}"] = size
                            except:
                                pass
                except PermissionError:
                    pass
    
    # Sort and show top 15
    sorted_dirs = sorted(appdata_dirs.items(), key=lambda x: x[1], reverse=True)
    for path, size in sorted_dirs[:15]:
        print(f"  {path:<50} {format_size(size):>15}")
    
    return appdata_dirs


def find_temp_files():
    """Find temporary files and caches"""
    print("\n" + "="*80)
    print("  TEMP FILES & CACHES")
    print("="*80)
    print("\nFinding cleanup candidates...\n")
    
    cleanup_paths = [
        (r"C:\Windows\Temp", "Windows Temp"),
        (r"C:\Users\alimg\AppData\Local\Temp", "User Temp"),
        (r"C:\Users\alimg\AppData\Local\Microsoft\Windows\INetCache", "Internet Cache"),
        (r"C:\Temp", "C:\\Temp"),
        (r"C:\Users\alimg\Downloads", "Downloads (old)"),
        (r"C:\Users\alimg\AppData\Local\Google\Chrome\User Data\Default\Cache", "Chrome Cache"),
        (r"C:\Users\alimg\AppData\Local\Mozilla\Firefox", "Firefox Cache"),
        (r"C:\Users\alimg\AppData\Local\pip\http", "PIP Cache"),
    ]
    
    candidates = {}
    for path_str, desc in cleanup_paths:
        path = Path(path_str)
        if path.exists():
            try:
                size = get_folder_size(path, max_depth=2)
                if size > 0:
                    candidates[desc] = (path, size)
                    print(f"  {desc:<40} {format_size(size):>15}")
            except:
                pass
    
    return candidates


def find_large_files():
    """Find largest files in user folder"""
    print("\n" + "="*80)
    print("  LARGEST FILES (in user folder)")
    print("="*80)
    print("\nScanning for files > 100 MB...\n")
    
    user_path = Path(r"C:\Users\alimg")
    large_files = []
    
    try:
        for file_path in user_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            try:
                size = file_path.stat().st_size
                if size > 100 * 1024 * 1024:  # 100 MB
                    large_files.append((size, file_path))
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    
    large_files.sort(reverse=True)
    
    for size, path in large_files[:20]:
        print(f"  {str(path):<60} {format_size(size):>12}")
    
    return large_files


def generate_cleanup_report(folders, appdata, cleanup_candidates, large_files):
    """Generate cleanup report"""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    report_file = REPORT_DIR / f"DISK_CLEANUP_PLAN_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    # Calculate totals
    total_root = sum(folders.values())
    total_appdata = sum(appdata.values())
    total_cleanup = sum(size for _, size in cleanup_candidates.values())
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("  DISK CLEANUP ACTION PLAN\n")
        f.write("="*80 + "\n\n")
        
        f.write(f"Report: {datetime.now().isoformat()}\n\n")
        
        f.write("QUICK CLEANUP (Safe to delete):\n")
        f.write("-" * 80 + "\n")
        f.write(f"1. Windows Temp files:              Can free ~1-5 GB\n")
        f.write(f"   Path: C:\\Windows\\Temp\n")
        f.write(f"   Command: rmdir /s /q C:\\Windows\\Temp && mkdir C:\\Windows\\Temp\n\n")
        
        f.write(f"2. User Temp files:                 Can free ~1-10 GB\n")
        f.write(f"   Path: C:\\Users\\alimg\\AppData\\Local\\Temp\n")
        f.write(f"   Command: rmdir /s /q C:\\Users\\alimg\\AppData\\Local\\Temp && mkdir C:\\Users\\alimg\\AppData\\Local\\Temp\n\n")
        
        f.write(f"3. Browser Caches:                  Can free ~2-5 GB\n")
        f.write(f"   Chrome: C:\\Users\\alimg\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cache\n")
        f.write(f"   Firefox: C:\\Users\\alimg\\AppData\\Local\\Mozilla\\Firefox\n\n")
        
        f.write(f"4. PIP Python Cache:                Can free ~0.5-1 GB\n")
        f.write(f"   Path: C:\\Users\\alimg\\AppData\\Local\\pip\\http\n\n")
        
        f.write("FOLDER SIZE BREAKDOWN:\n")
        f.write("-" * 80 + "\n")
        for folder, size in sorted(folders.items(), key=lambda x: x[1], reverse=True):
            pct = (size / (total_root + 1)) * 100
            f.write(f"  {folder:<40} {format_size(size):>15} ({pct:>5.1f}%)\n")
        f.write(f"\n  Total (root): {format_size(total_root)}\n\n")
        
        f.write("CLEANUP CANDIDATES:\n")
        f.write("-" * 80 + "\n")
        for desc, (path, size) in sorted(cleanup_candidates.items(), key=lambda x: x[1][1], reverse=True):
            f.write(f"  {desc:<40} {format_size(size):>15}\n")
            f.write(f"    Path: {path}\n")
        f.write(f"\n  Total can free: {format_size(total_cleanup)}\n\n")
        
        f.write("LARGEST FILES:\n")
        f.write("-" * 80 + "\n")
        for size, path in large_files[:20]:
            f.write(f"  {str(path):<60} {format_size(size):>12}\n")
    
    return report_file


def main():
    folders = scan_root_folders()
    appdata = scan_user_appdata()
    candidates = find_temp_files()
    large_files = find_large_files()
    
    report_file = generate_cleanup_report(folders, appdata, candidates, large_files)
    
    print("\n" + "="*80)
    print("  CLEANUP PLAN SAVED")
    print("="*80)
    print(f"\nReport: {report_file}\n")
    
    print("RECOMMENDED CLEANUP (in order):")
    print("1. Clear Temp files (1-10 GB)")
    print("2. Clear Browser caches (2-5 GB)")
    print("3. Review large files (20+ GB files)")
    print("4. Delete old downloads")
    print("5. Uninstall unused programs (Control Panel)")
    print()


if __name__ == "__main__":
    main()

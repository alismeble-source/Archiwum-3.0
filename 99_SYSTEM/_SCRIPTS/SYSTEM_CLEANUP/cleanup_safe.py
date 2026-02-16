#!/usr/bin/env python3
"""
Safe cleanup script - remove temp files and caches (NON-DESTRUCTIVE).
Generates list of files to delete before actually deleting.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta

REPORT_DIR = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0\00_INBOX\_PHOTO_DEDUP")


def cleanup_temp_files(dry_run=True):
    """Clean temporary files"""
    cleanup_paths = [
        Path(r"C:\Users\alimg\AppData\Local\Temp"),
        Path(r"C:\Temp"),
        Path(r"C:\Windows\Temp"),
    ]
    
    deleted = 0
    freed = 0
    
    print("\n" + "="*80)
    print("  TEMPORARY FILES CLEANUP")
    print("="*80)
    
    for temp_dir in cleanup_paths:
        if not temp_dir.exists():
            continue
        
        print(f"\n  Scanning: {temp_dir}")
        
        for file_path in temp_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            try:
                size = file_path.stat().st_size
                freed += size
                
                if dry_run:
                    print(f"    [DRY] DELETE: {file_path.name} ({size / (1024*1024):.2f} MB)")
                else:
                    try:
                        file_path.unlink()
                        print(f"    ✓ DELETED: {file_path.name}")
                        deleted += 1
                    except Exception as e:
                        print(f"    ✗ FAILED: {file_path.name} - {e}")
            
            except (PermissionError, OSError):
                pass
    
    print(f"\n  Could delete: {deleted} files")
    print(f"  Could free: {freed / (1024**3):.2f} GB")
    
    return freed


def cleanup_caches(dry_run=True):
    """Clean browser and app caches"""
    cache_paths = [
        (Path(r"C:\Users\alimg\AppData\Local\Google\Chrome\User Data\Default\Cache"), "Chrome Cache"),
        (Path(r"C:\Users\alimg\AppData\Local\Mozilla\Firefox"), "Firefox Cache"),
        (Path(r"C:\Users\alimg\AppData\Local\pip"), "PIP Cache"),
    ]
    
    freed = 0
    
    print("\n" + "="*80)
    print("  CACHE CLEANUP")
    print("="*80)
    
    for cache_dir, name in cache_paths:
        if not cache_dir.exists():
            continue
        
        print(f"\n  Scanning: {name}")
        
        for file_path in cache_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            try:
                size = file_path.stat().st_size
                freed += size
                
                if dry_run:
                    print(f"    [DRY] DELETE: {file_path.name}")
                else:
                    try:
                        file_path.unlink()
                        deleted += 1
                    except:
                        pass
            
            except (PermissionError, OSError):
                pass
    
    print(f"\n  Could free: {freed / (1024**3):.2f} GB")
    return freed


def cleanup_old_downloads(days=30, dry_run=True):
    """Clean old downloads (> 30 days)"""
    download_dir = Path(r"C:\Users\alimg\Downloads")
    
    if not download_dir.exists():
        return 0
    
    print("\n" + "="*80)
    print(f"  OLD DOWNLOADS CLEANUP (older than {days} days)")
    print("="*80)
    
    cutoff_date = datetime.now() - timedelta(days=days)
    freed = 0
    deleted = 0
    
    for file_path in download_dir.iterdir():
        if not file_path.is_file():
            continue
        
        try:
            mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mod_time < cutoff_date:
                size = file_path.stat().st_size
                freed += size
                
                if dry_run:
                    print(f"  [DRY] DELETE: {file_path.name} ({size / (1024**2):.2f} MB) - {mod_time}")
                else:
                    try:
                        file_path.unlink()
                        deleted += 1
                    except:
                        pass
        
        except (PermissionError, OSError):
            pass
    
    print(f"\n  Could delete: {deleted} files")
    print(f"  Could free: {freed / (1024**3):.2f} GB")
    
    return freed


def main():
    print("="*80)
    print("  SAFE CLEANUP (DRY RUN - No files deleted yet)")
    print("="*80)
    
    temp_freed = cleanup_temp_files(dry_run=True)
    cache_freed = cleanup_caches(dry_run=True)
    downloads_freed = cleanup_old_downloads(days=30, dry_run=True)
    
    total_freed = temp_freed + cache_freed + downloads_freed
    
    print("\n" + "="*80)
    print(f"  TOTAL CAN FREE: {total_freed / (1024**3):.2f} GB")
    print("="*80)
    
    print("\nTo actually delete files, run with: python cleanup_safe.py --execute")
    print("(Do NOT run until you've reviewed the list above)")


if __name__ == "__main__":
    main()

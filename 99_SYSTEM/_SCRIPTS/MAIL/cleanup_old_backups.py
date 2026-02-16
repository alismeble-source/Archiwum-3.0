#!/usr/bin/env python3
"""
Cleanup old backup files (.bak_* and *.bak files).
Keeps only last N backups per file, deletes backups older than retention_days.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
STATE_DIR = ROOT / "00_INBOX" / "MAIL_RAW" / "_STATE"
LOG_DIR = ROOT / "00_INBOX" / "_ROUTER_LOGS"
CALENDAR_DIR = ROOT / "FINANCE" / "_CALENDAR" / "_STATE"

# Settings
RETENTION_DAYS = 14  # Keep backups younger than 14 days
MAX_BACKUPS_PER_FILE = 5  # Keep maximum 5 recent backups per file


def cleanup_backups(target_dir: Path, retention_days: int = RETENTION_DAYS):
    """Clean old backup files in directory"""
    if not target_dir.exists():
        return 0
    
    deleted_count = 0
    backups_by_base = defaultdict(list)
    
    # Group backups by base filename
    for backup_file in target_dir.glob("*"):
        if not backup_file.is_file():
            continue
        
        # Match patterns: file.bak_20260203_120000 or file.bak
        if '.bak_' in backup_file.name or backup_file.name.endswith('.bak'):
            # Extract base name (without timestamp)
            if '.bak_' in backup_file.name:
                base_name = backup_file.name.split('.bak_')[0]
                try:
                    # Extract timestamp from filename
                    timestamp_str = backup_file.name.split('.bak_')[1]
                    mtime = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                except:
                    mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
            else:
                base_name = backup_file.name.replace('.bak', '')
                mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
            
            backups_by_base[base_name].append((backup_file, mtime))
    
    # Process each base filename group
    now = datetime.now()
    for base_name, backups in backups_by_base.items():
        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x[1], reverse=True)
        
        for idx, (backup_path, mtime) in enumerate(backups):
            age_days = (now - mtime).days
            should_delete = False
            reason = ""
            
            # Rule 1: Older than retention period
            if age_days > retention_days:
                should_delete = True
                reason = f"older than {retention_days} days ({age_days} days old)"
            
            # Rule 2: More than MAX_BACKUPS_PER_FILE
            elif idx >= MAX_BACKUPS_PER_FILE:
                should_delete = True
                reason = f"exceeds max {MAX_BACKUPS_PER_FILE} backups (#{idx+1})"
            
            if should_delete:
                try:
                    backup_path.unlink()
                    print(f"[DELETE] {backup_path.name} ({reason})")
                    deleted_count += 1
                except Exception as e:
                    print(f"[ERROR] Failed to delete {backup_path.name}: {e}")
    
    return deleted_count


def main():
    print("=== BACKUP CLEANUP ===\n")
    
    total_deleted = 0
    
    # Cleanup state directory
    print(f"Scanning: {STATE_DIR}")
    deleted = cleanup_backups(STATE_DIR)
    total_deleted += deleted
    print(f"  Deleted: {deleted} backups\n")
    
    # Cleanup logs directory
    print(f"Scanning: {LOG_DIR}")
    deleted = cleanup_backups(LOG_DIR)
    total_deleted += deleted
    print(f"  Deleted: {deleted} backups\n")
    
    # Cleanup calendar directory
    print(f"Scanning: {CALENDAR_DIR}")
    deleted = cleanup_backups(CALENDAR_DIR)
    total_deleted += deleted
    print(f"  Deleted: {deleted} backups\n")
    
    print(f"Total deleted: {total_deleted} backup files")
    print(f"Retention policy: {RETENTION_DAYS} days, max {MAX_BACKUPS_PER_FILE} per file")


if __name__ == "__main__":
    main()

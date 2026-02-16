#!/usr/bin/env python3
"""
Atomic state file operations for synchronous pipeline execution.
Prevents race conditions and data corruption from concurrent writes.
"""

import os
import time
import tempfile
from pathlib import Path
from typing import Set


def atomic_read_lines(file_path: Path, max_retries: int = 3) -> list:
    """Atomically read file lines with retry logic"""
    for attempt in range(max_retries):
        try:
            if not file_path.exists():
                return []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except (IOError, OSError) as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)  # Wait 500ms before retry
            else:
                print(f"  ERROR: Failed to read {file_path.name} after {max_retries} retries: {e}")
                return []
    return []


def atomic_write_lines(file_path: Path, lines: list, max_retries: int = 3) -> bool:
    """Atomically write lines to file (temp + rename pattern)"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    for attempt in range(max_retries):
        try:
            # Write to temp file
            with tempfile.NamedTemporaryFile(
                mode='w', 
                dir=file_path.parent, 
                delete=False, 
                encoding='utf-8',
                suffix='.tmp'
            ) as tmp:
                tmp_path = tmp.name
                for line in sorted(set(lines)):  # Deduplicate + sort
                    tmp.write(line + '\n')
            
            # Atomic rename
            os.replace(tmp_path, str(file_path))
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
            else:
                print(f"  ERROR: Failed to write {file_path.name} after {max_retries} retries: {e}")
                # Cleanup temp file
                try:
                    os.remove(tmp_path)
                except:
                    pass
                return False
    
    return False


def append_line_atomic(file_path: Path, line: str, max_retries: int = 3) -> bool:
    """Atomically append single line to file"""
    if not line or not line.strip():
        return True
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    for attempt in range(max_retries):
        try:
            existing = atomic_read_lines(file_path, max_retries=1)
            if line.strip() in existing:
                return True  # Already present
            
            existing.append(line.strip())
            return atomic_write_lines(file_path, existing, max_retries=1)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5)
            else:
                print(f"  ERROR: Failed to append to {file_path.name}: {e}")
                return False
    
    return False


def acquire_lock(lock_path: Path, timeout_seconds: int = 30) -> bool:
    """Acquire lock file (spin-wait with timeout)"""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        try:
            # Try to create lock file exclusively
            with open(lock_path, 'x') as f:
                f.write(str(os.getpid()))
            return True
        except FileExistsError:
            time.sleep(0.1)  # Wait 100ms before retry
    
    print(f"  ERROR: Failed to acquire lock {lock_path.name} after {timeout_seconds}s")
    return False


def release_lock(lock_path: Path) -> bool:
    """Release lock file"""
    try:
        if lock_path.exists():
            os.remove(lock_path)
        return True
    except Exception as e:
        print(f"  ERROR: Failed to release lock: {e}")
        return False


# Example usage in scripts
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
    STATE_FILE = ROOT / "00_INBOX" / "MAIL_RAW" / "_STATE" / "test_state.txt"
    
    print("Testing atomic state file operations...")
    
    # Test append
    print("\n1. Appending lines...")
    append_line_atomic(STATE_FILE, "test_id_001")
    append_line_atomic(STATE_FILE, "test_id_002")
    
    # Test read
    print("2. Reading lines...")
    lines = atomic_read_lines(STATE_FILE)
    print(f"   Found {len(lines)} lines: {lines[:3]}...")
    
    # Test write
    print("3. Atomic write...")
    new_lines = ["new_001", "new_002", "new_003"]
    if atomic_write_lines(STATE_FILE, new_lines):
        print("   Write successful")
    
    # Cleanup
    STATE_FILE.unlink(missing_ok=True)
    print("\nTest complete!")

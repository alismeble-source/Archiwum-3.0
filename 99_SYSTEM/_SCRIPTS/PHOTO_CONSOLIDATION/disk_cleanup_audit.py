#!/usr/bin/env python3
"""
Complete disk cleanup: find all photos, duplicates, and wasted space.
Scans entire C: drive for photo clutter.
"""

import hashlib
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    EXIF_AVAILABLE = True
except ImportError:
    EXIF_AVAILABLE = False

PHOTO_EXTS = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.gif', '.bmp', '.tiff', '.raw', '.cr2', '.nef', '.webp'}
REPORT_DIR = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0\00_INBOX\_PHOTO_DEDUP")

# All photo sources to scan
SCAN_SOURCES = [
    Path(r"C:\Users\alimg\Dropbox"),  # Dropbox sync
    Path(r"C:\Users\alimg\iCloudDrive"),  # iCloud Drive
    Path(r"C:\Users\alimg\Мой диск (alismeble@gmail.com)"),  # Google Drive #1
    Path(r"C:\Users\alimg\Мой диск (alimgulov1992@gmail.com)"),  # Google Drive #2
    Path(r"C:\Users\alimg\Мой диск (slonskaula@gmail.com)"),  # Google Drive #3
    Path(r"C:\Google_foto"),  # Google Photos exports
]


def sha256_file(file_path: Path) -> str:
    """Compute SHA256 hash of file"""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        return ""


def scan_entire_disk():
    """Scan entire C: drive for photos"""
    print("="*70)
    print("  DISK CLEANUP AUDIT - ALL SOURCES")
    print("="*70)
    print("\nScanning all photo sources (Dropbox, iCloud, Google Drive x3)...\n")
    
    photos = {}  # {hash: [file_paths]}
    locations = defaultdict(int)  # {folder: count}
    scanned = 0
    errors = 0
    
    # Scan specific sources first
    for source_path in SCAN_SOURCES:
        if not source_path.exists():
            print(f"  Skipping (not found): {source_path.name}")
            continue
        
        print(f"  Scanning: {source_path.name}...")
        
        try:
            for file_path in source_path.rglob("*"):
                if not file_path.is_file():
                    continue
                
                if file_path.suffix.lower() not in PHOTO_EXTS:
                    continue
                
                scanned += 1
                if scanned % 500 == 0:
                    print(f"    Total scanned: {scanned} photos, unique hashes: {len(photos)}")
                
                try:
                    file_hash = sha256_file(file_path)
                    if file_hash:
                        if file_hash not in photos:
                            photos[file_hash] = []
                        photos[file_hash].append(file_path)
                        
                        # Track location
                        parts = file_path.parts
                        if len(parts) > 1:
                            # Get source folder name
                            source_name = source_path.name
                            locations[source_name] += 1
                except Exception as e:
                    errors += 1
        
        except PermissionError:
            print(f"    (Permission denied on some subfolders)")
    
    print(f"\n  Total scanned: {scanned} photos")
    print(f"  Unique hashes: {len(photos)}")
    print(f"  Errors: {errors}")
    
    return photos, locations, scanned


def analyze_duplicates(photos: dict):
    """Analyze duplicate patterns"""
    duplicates = {h: paths for h, paths in photos.items() if len(paths) > 1}
    
    print(f"\n{'='*70}")
    print(f"  DUPLICATE ANALYSIS")
    print(f"{'='*70}")
    
    total_waste = 0
    total_extra_copies = 0
    largest_dupes = []
    
    for file_hash, paths in duplicates.items():
        file_size = paths[0].stat().st_size
        waste = file_size * (len(paths) - 1)
        total_waste += waste
        total_extra_copies += len(paths) - 1
        
        largest_dupes.append((waste, file_hash, paths))
    
    largest_dupes.sort(reverse=True)
    
    print(f"\nFound {len(duplicates)} duplicate groups ({total_extra_copies} extra copies)")
    print(f"Wasted space: {total_waste / (1024**3):.2f} GB\n")
    
    print("Top 10 largest duplicate groups:")
    print(f"{'Size (MB)':<12} {'Copies':<8} {'File':<50}")
    print("-" * 70)
    
    for waste, file_hash, paths in largest_dupes[:10]:
        size_mb = waste / (1024**2)
        filename = paths[0].name[:50]
        print(f"{size_mb:>10.2f}  {len(paths):>6}x  {filename}")
    
    return duplicates, total_waste, largest_dupes


def analyze_locations(locations: dict, scanned: int):
    """Analyze where photos are stored"""
    print(f"\n{'='*70}")
    print(f"  STORAGE LOCATIONS")
    print(f"{'='*70}\n")
    
    print(f"{'Folder':<40} {'Count':<10} {'% of total':<10}")
    print("-" * 70)
    
    sorted_locs = sorted(locations.items(), key=lambda x: x[1], reverse=True)
    for folder, count in sorted_locs[:20]:
        pct = (count / scanned * 100) if scanned > 0 else 0
        print(f"{folder:<40} {count:<10} {pct:>6.1f}%")


def generate_cleanup_report(photos: dict, locations: dict, scanned: int, largest_dupes):
    """Generate comprehensive cleanup report"""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    report_file = REPORT_DIR / f"DISK_CLEANUP_AUDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    duplicates = {h: paths for h, paths in photos.items() if len(paths) > 1}
    total_waste = sum((paths[0].stat().st_size * (len(paths) - 1)) for paths in duplicates.values())
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("="*70 + "\n")
        f.write("  ARCHIWUM 3.0 - DISK CLEANUP AUDIT\n")
        f.write("="*70 + "\n\n")
        
        f.write(f"Scan date: {datetime.now().isoformat()}\n\n")
        
        f.write("SUMMARY\n")
        f.write("-" * 70 + "\n")
        f.write(f"Total photos found: {scanned}\n")
        f.write(f"Unique photos: {len(photos)}\n")
        f.write(f"Duplicate groups: {len(duplicates)}\n")
        f.write(f"Extra copies: {sum(len(p)-1 for p in duplicates.values())}\n")
        f.write(f"Wasted space: {total_waste / (1024**3):.2f} GB\n\n")
        
        f.write("TOP STORAGE LOCATIONS\n")
        f.write("-" * 70 + "\n")
        for folder, count in sorted(locations.items(), key=lambda x: x[1], reverse=True)[:15]:
            pct = (count / scanned * 100) if scanned > 0 else 0
            f.write(f"  {folder:<35} {count:>5} photos ({pct:>5.1f}%)\n")
        f.write("\n")
        
        f.write("LARGEST DUPLICATE GROUPS (by wasted space)\n")
        f.write("-" * 70 + "\n")
        for i, (waste, file_hash, paths) in enumerate(largest_dupes[:20], 1):
            size_mb = waste / (1024**2)
            f.write(f"\n{i}. {paths[0].name} ({size_mb:.1f} MB waste, {len(paths)} copies)\n")
            f.write(f"   Hash: {file_hash[:16]}...\n")
            for j, path in enumerate(paths, 1):
                f.write(f"   Copy {j}: {path}\n")
        f.write("\n")
        
        f.write("RECOMMENDED CLEANUP ACTIONS\n")
        f.write("-" * 70 + "\n")
        f.write(f"1. Free up {total_waste / (1024**3):.2f} GB by deleting extra copies\n")
        f.write(f"2. Priority folders to audit:\n")
        for folder, count in sorted(locations.items(), key=lambda x: x[1], reverse=True)[:5]:
            if count > 50:
                f.write(f"   - C:\\{folder}  ({count} photos)\n")
        f.write("\n")
        f.write("3. Keep: C:\\Users\\alimg\\Dropbox (WORKING STORAGE)\n")
        f.write("4. Delete: Other copies (after verification)\n")
        f.write("5. Upload unique to Google Photos\n")
    
    return report_file


def main():
    photos, locations, scanned = scan_entire_disk()
    
    if not photos:
        print("\nNo photos found!")
        return
    
    duplicates, total_waste, largest_dupes = analyze_duplicates(photos)
    analyze_locations(locations, scanned)
    
    report_file = generate_cleanup_report(photos, locations, scanned, largest_dupes)
    
    print(f"\n{'='*70}")
    print(f"  REPORT SAVED")
    print(f"{'='*70}")
    print(f"\nDetailed report: {report_file}\n")
    
    print("NEXT STEPS:")
    print("1. Review the report (shows all duplicates + locations)")
    print("2. Decide which copies to delete")
    print("3. Backup before deleting (use local external drive)")
    print("4. Delete extra copies from Dropbox/Google_foto/CASES")
    print("5. Keep only ONE copy per unique photo")
    print("6. Upload unique to Google Photos")
    print()


if __name__ == "__main__":
    main()

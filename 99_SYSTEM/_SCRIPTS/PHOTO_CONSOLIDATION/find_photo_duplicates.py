#!/usr/bin/env python3
"""
Photo deduplication across multiple cloud sources:
- iCloud Photos
- Google Drive/Photos
- Dropbox
- Local folders

Finds duplicates by SHA256 hash + EXIF metadata comparison.
"""

import hashlib
import json
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    EXIF_AVAILABLE = True
except ImportError:
    EXIF_AVAILABLE = False
    print("Warning: Pillow not installed. Install: pip install Pillow")

# Scan locations
SCAN_DIRS = [
    Path(r"C:\Users\alimg\Dropbox"),
    Path(r"C:\Google_foto"),  # Google Photos export
    Path(r"C:\CASES"),  # Additional photos location
    # Add iCloud path if needed: Path(r"C:\iCloud Photos"),
]

OUTPUT_DIR = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0\00_INBOX\_PHOTO_DEDUP")
REPORT_CSV = OUTPUT_DIR / f"photo_duplicates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
METADATA_CACHE = OUTPUT_DIR / "photo_metadata_cache.json"

# Photo extensions
PHOTO_EXTS = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.gif', '.bmp', '.tiff', '.raw', '.cr2', '.nef'}


def sha256_file(file_path: Path) -> str:
    """Compute SHA256 hash of file"""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"  Error hashing {file_path.name}: {e}")
        return ""


def get_exif_data(file_path: Path) -> dict:
    """Extract EXIF metadata from photo"""
    if not EXIF_AVAILABLE:
        return {}
    
    try:
        img = Image.open(file_path)
        exif_data = img._getexif()
        if not exif_data:
            return {}
        
        exif = {}
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            exif[tag] = str(value)
        
        return {
            'date_taken': exif.get('DateTime', ''),
            'camera': exif.get('Model', ''),
            'width': img.width,
            'height': img.height,
        }
    except Exception as e:
        return {}


def scan_photos(scan_dirs: list) -> dict:
    """Scan directories for photos, compute hashes + metadata"""
    print("Scanning for photos...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load cache if exists
    cache = {}
    if METADATA_CACHE.exists():
        try:
            cache = json.loads(METADATA_CACHE.read_text(encoding='utf-8'))
            print(f"  Loaded cache: {len(cache)} entries")
        except:
            cache = {}
    
    photos = {}  # {hash: [file_paths]}
    photo_metadata = {}  # {file_path: metadata}
    scanned = 0
    
    for base_dir in scan_dirs:
        if not base_dir.exists():
            print(f"  Skipping (not found): {base_dir}")
            continue
        
        print(f"\n  Scanning: {base_dir}")
        
        for file_path in base_dir.rglob('*'):
            if file_path.suffix.lower() not in PHOTO_EXTS:
                continue
            
            if not file_path.is_file():
                continue
            
            scanned += 1
            if scanned % 100 == 0:
                print(f"    Scanned: {scanned} photos...")
            
            # Check cache
            file_key = str(file_path)
            cached = cache.get(file_key)
            
            # Use cache if file unchanged (mtime + size match)
            if cached:
                stat = file_path.stat()
                if cached.get('mtime') == stat.st_mtime and cached.get('size') == stat.st_size:
                    file_hash = cached['hash']
                    photo_metadata[file_key] = cached.get('metadata', {})
                else:
                    # File changed, recompute
                    file_hash = sha256_file(file_path)
                    metadata = get_exif_data(file_path)
                    photo_metadata[file_key] = metadata
                    
                    # Update cache
                    cache[file_key] = {
                        'hash': file_hash,
                        'metadata': metadata,
                        'mtime': stat.st_mtime,
                        'size': stat.st_size,
                    }
            else:
                # New file
                file_hash = sha256_file(file_path)
                metadata = get_exif_data(file_path)
                photo_metadata[file_key] = metadata
                
                stat = file_path.stat()
                cache[file_key] = {
                    'hash': file_hash,
                    'metadata': metadata,
                    'mtime': stat.st_mtime,
                    'size': stat.st_size,
                }
            
            if file_hash:
                if file_hash not in photos:
                    photos[file_hash] = []
                photos[file_hash].append(file_path)
    
    # Save cache
    METADATA_CACHE.write_text(json.dumps(cache, indent=2), encoding='utf-8')
    print(f"\n  Total scanned: {scanned} photos")
    print(f"  Unique hashes: {len(photos)}")
    
    return photos, photo_metadata


def generate_report(photos: dict, metadata: dict):
    """Generate CSV report of duplicates"""
    print("\nGenerating duplicate report...")
    
    duplicates = {h: paths for h, paths in photos.items() if len(paths) > 1}
    
    if not duplicates:
        print("  No duplicates found!")
        return
    
    print(f"  Found {len(duplicates)} duplicate groups ({sum(len(p)-1 for p in duplicates.values())} extra copies)")
    
    # Write CSV
    with REPORT_CSV.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Hash', 'File_Count', 'Size_MB', 'Date_Taken', 'Camera', 'Resolution', 'Source', 'File_Path'])
        
        for file_hash, paths in sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True):
            size_mb = paths[0].stat().st_size / (1024 * 1024)
            
            for i, path in enumerate(paths):
                meta = metadata.get(str(path), {})
                source = "Dropbox" if "Dropbox" in str(path) else "Google Drive" if "Google" in str(path) else "iCloud" if "iCloud" in str(path) else "Other"
                resolution = f"{meta.get('width', '?')}x{meta.get('height', '?')}"
                
                writer.writerow([
                    file_hash[:12],
                    len(paths),
                    f"{size_mb:.2f}",
                    meta.get('date_taken', 'N/A'),
                    meta.get('camera', 'N/A'),
                    resolution,
                    source,
                    str(path)
                ])
    
    print(f"  Report saved: {REPORT_CSV}")
    
    # Summary stats
    total_waste = sum((len(paths) - 1) * paths[0].stat().st_size for paths in duplicates.values())
    print(f"\n  Wasted space: {total_waste / (1024**3):.2f} GB")
    
    # By source breakdown
    sources = defaultdict(int)
    for paths in duplicates.values():
        for path in paths[1:]:  # Count extra copies
            if "Dropbox" in str(path):
                sources['Dropbox'] += 1
            elif "Google" in str(path):
                sources['Google Drive'] += 1
            elif "iCloud" in str(path):
                sources['iCloud'] += 1
    
    print("\n  Duplicates by source:")
    for source, count in sources.items():
        print(f"    {source}: {count} extra copies")


def main():
    print("="*60)
    print("  Photo Deduplication Tool")
    print("="*60)
    
    photos, metadata = scan_photos(SCAN_DIRS)
    generate_report(photos, metadata)
    
    print("\n" + "="*60)
    print("  Done! Review report before deleting files.")
    print("="*60)


if __name__ == "__main__":
    main()

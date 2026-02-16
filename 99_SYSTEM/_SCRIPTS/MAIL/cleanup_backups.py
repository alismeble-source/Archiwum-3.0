from pathlib import Path

CAR_DIR = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0\04_CAR")

def main():
    bak_files = sorted(list(CAR_DIR.glob("*.bak_*")) + list(CAR_DIR.glob("*.bak")))
    
    if not bak_files:
        print("No backup files found.")
        return
    
    total_size = 0
    print(f"\nFound {len(bak_files)} backup files:\n")
    for f in bak_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        total_size += f.stat().st_size
        print(f"  {f.name:<50} {size_mb:>8.2f} MB")
    
    print(f"\nTotal size: {total_size / (1024 * 1024):.2f} MB")
    
    for f in bak_files:
        try:
            f.unlink()
            print(f"  ✓ {f.name}")
        except Exception as e:
            print(f"  ✗ {f.name}: {e}")
    print("\nCleanup complete.")

if __name__ == "__main__":
    main()

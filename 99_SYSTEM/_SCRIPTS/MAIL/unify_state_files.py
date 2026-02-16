from pathlib import Path

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
STATE_DIR = ROOT / "00_INBOX" / "MAIL_RAW" / "_STATE"

state_files = [
    ROOT / "04_CAR" / "gmail_icloud_processed_ids.txt",
    ROOT / "04_CAR" / "processed_ids.txt",
    ROOT / "04_CAR" / "icloud_export_processed_ids.txt",
    STATE_DIR / "gmail_icloud_processed_ids.txt",
    STATE_DIR / "processed_gmail_ids.txt",
]

def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    
    all_ids = set()
    
    print("Collecting processed IDs from:\n")
    for f in state_files:
        if f.exists():
            print(f"  ✓ {f.relative_to(ROOT)}")
            with f.open("r", encoding="utf-8", errors="ignore") as src:
                for line in src:
                    line = line.strip()
                    if line:
                        all_ids.add(line)
        else:
            print(f"  - {f.relative_to(ROOT)} (not found)")
    
    unified = STATE_DIR / "processed_gmail_all.txt"
    with unified.open("w", encoding="utf-8") as f:
        for mid in sorted(all_ids):
            f.write(mid + "\n")
    
    print(f"\n✓ Unified: {len(all_ids)} unique IDs")
    print(f"✓ Saved to: {unified.relative_to(ROOT)}")

if __name__ == "__main__":
    main()

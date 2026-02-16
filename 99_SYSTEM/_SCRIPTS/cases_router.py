import os, re, json, shutil, hashlib, datetime
from pathlib import Path

ROOT = r"C:\Users\alimg\Dropbox\Archiwum 3.0"
RULES_PATH = os.path.join(ROOT, "CASES", "_router_rules.json")

LOG_DIR = os.path.join(ROOT, "00_INBOX", "_ROUTER_LOGS")
STATE_DIR = os.path.join(ROOT, "00_INBOX", "MAIL_RAW", "_STATE")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(STATE_DIR, exist_ok=True)

STATE_FILE = os.path.join(STATE_DIR, "cases_router_processed_files.txt")
LOG_FILE   = os.path.join(LOG_DIR, f"CASES_ROUTER_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

def load_rules():
    with open(RULES_PATH, encoding="utf-8-sig") as f:
        return json.load(f)

def load_processed():
    if not os.path.exists(STATE_FILE):
        return set()
    return set([x.strip() for x in Path(STATE_FILE).read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()])

def save_processed(s):
    Path(STATE_FILE).write_text("\n".join(sorted(s)), encoding="utf-8")

def sha1_file(p):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def norm(s):
    return (s or "").lower()

def decide_target(rules, filename, meta):
    hay = " ".join([
        filename,
        meta.get("from",""),
        meta.get("subject",""),
        meta.get("orig_filename",""),
        meta.get("date",""),
        meta.get("source","")
    ])
    hay = norm(hay)

    for r in rules["rules"]:
        words = [norm(x) for x in (r.get("match_any") or [])]
        if any(w and w in hay for w in words):
            return r["target"], r["name"], "MATCH"
    return rules["defaults"]["review_folder"], "REVIEW", "NO_MATCH"

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def main(move=True):
    rules = load_rules()
    processed = load_processed()

    inbox = os.path.join(ROOT, rules["defaults"]["inbox_folder"].replace("/", os.sep))
    review = os.path.join(ROOT, rules["defaults"]["review_folder"].replace("/", os.sep))
    ensure_dir(inbox); ensure_dir(review)

    files = []
    for p in Path(inbox).iterdir():
        if p.is_file() and not p.name.endswith(".meta.json"):
            files.append(p)

    with open(LOG_FILE, "w", encoding="utf-8") as log:
        log.write("file,sha1,action,rule,target,final_path\n")

        for p in sorted(files, key=lambda x: x.name.lower()):
            key = str(p)
            if key in processed:
                continue

            meta_path = str(p) + ".meta.json"
            meta = {}
            if os.path.exists(meta_path):
                try:
                    meta = json.loads(Path(meta_path).read_text(encoding="utf-8", errors="ignore"))
                except:
                    meta = {}

            target_root_rel, rule_name, action = decide_target(rules, p.name, meta)
            target_root = os.path.join(ROOT, target_root_rel.replace("/", os.sep))
            ensure_dir(target_root)

            # Если цель — “ветка кейсов” (01_KLIENTS и т.д.), кладём в _INBOX этой ветки, чтобы не “угадать кейс”
            # Безопасно: сначала в ветку, потом руками/дальнейшим правилом в конкретный CASE_*
            if target_root_rel.startswith("CASES/01_KLIENTS") or target_root_rel.startswith("CASES/02_FIRMA") or target_root_rel.startswith("CASES/03_CAR"):
                out_dir = os.path.join(target_root, "_INBOX")
            else:
                out_dir = target_root

            ensure_dir(out_dir)

            # анти-дубликат в месте назначения по sha1
            h = sha1_file(str(p))
            out_path = os.path.join(out_dir, p.name)

            # если файл с тем же именем уже есть — добавим суффикс
            if os.path.exists(out_path):
                stem = p.stem
                suf = p.suffix
                out_path = os.path.join(out_dir, f"{stem}__DUP__{h[:8]}{suf}")

            if move:
                shutil.move(str(p), out_path)
                if os.path.exists(meta_path):
                    shutil.move(meta_path, out_path + ".meta.json")
                op = "MOVED"
            else:
                shutil.copy2(str(p), out_path)
                if os.path.exists(meta_path):
                    shutil.copy2(meta_path, out_path + ".meta.json")
                op = "COPIED"

            log.write(f'"{p}","{h}",{op},{rule_name},"{out_dir}","{out_path}"\n')
            processed.add(key)

    save_processed(processed)
    print(f"DONE. files_in_inbox={len(files)}")
    print(f"LOG:   {LOG_FILE}")
    print(f"STATE: {STATE_FILE}")

if __name__ == "__main__":
    # move=True безопасно, потому что всегда есть LOG+STATE
    # если хочешь сначала тест — поставь move=False
    main(move=True)

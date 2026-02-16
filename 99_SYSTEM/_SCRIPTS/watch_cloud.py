import json
import os
import time
from datetime import datetime, timezone

import dropbox


TOKEN_PATH = r"C:\Users\alimg\Dropbox\Archiwum 3.0\99_SYSTEM\_SECRETS\dropbox_token.txt"

# Что сканируем в облаке Dropbox
SCAN_ROOT = "/Archiwum 3.0"

# Куда пишем результат в Dropbox
OUT_STATE = "/Archiwum 3.0/00_INBOX/_ROUTER_LOGS/WATCH_CLOUD/state_cloud.json"
OUT_DIFF  = "/Archiwum 3.0/00_INBOX/_ROUTER_LOGS/WATCH_CLOUD/diff_cloud.txt"


def read_token(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        t = f.read().strip()
    if not t:
        raise RuntimeError("Token file is empty")
    return t


def list_all(dbx: dropbox.Dropbox, root: str):
    res = dbx.files_list_folder(root, recursive=True, include_deleted=False)
    entries = list(res.entries)
    while res.has_more:
        res = dbx.files_list_folder_continue(res.cursor)
        entries.extend(res.entries)
    return entries


def load_prev_paths(local_json_path: str) -> set[str]:
    if not os.path.exists(local_json_path):
        return set()
    with open(local_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # data ожидается в формате payload (см. ниже)
    items = data.get("items", [])
    return set(i["path"] for i in items if "path" in i)


def make_diff_text(prev: set[str], curr: set[str]) -> str:
    added = sorted(curr - prev)
    removed = sorted(prev - curr)

    lines = []
    for p in added:
        lines.append(f"+ {p}")
    for p in removed:
        lines.append(f"- {p}")
    return "\n".join(lines)


def upload_text(dbx: dropbox.Dropbox, dropbox_path: str, text: str):
    dbx.files_upload(
        text.encode("utf-8"),
        dropbox_path,
        mode=dropbox.files.WriteMode.overwrite
    )


def upload_json(dbx: dropbox.Dropbox, dropbox_path: str, obj: dict):
    data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    dbx.files_upload(
        data,
        dropbox_path,
        mode=dropbox.files.WriteMode.overwrite
    )


def main():
    print("START main")

    token = read_token(TOKEN_PATH)
    dbx = dropbox.Dropbox(token)

    t0 = time.time()
    entries = list_all(dbx, SCAN_ROOT)

    items = []
    for e in entries:
        if isinstance(e, dropbox.files.FolderMetadata):
            items.append({
                "path": e.path_display,
                "type": "dir",
            })
        elif isinstance(e, dropbox.files.FileMetadata):
            items.append({
                "path": e.path_display,
                "type": "file",
                "size": e.size,
                "client_modified": e.client_modified.replace(tzinfo=timezone.utc).isoformat(),
                "server_modified": e.server_modified.replace(tzinfo=timezone.utc).isoformat(),
            })

    payload = {
        "scan_root": SCAN_ROOT,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
        "elapsed_sec": round(time.time() - t0, 3),
    }

    # Локальные файлы (для diff)
    local_state = os.path.join(os.path.dirname(__file__), "state_cloud.json")

    prev_paths = load_prev_paths(local_state)
    curr_paths = set(i["path"] for i in items)

    diff_text = make_diff_text(prev_paths, curr_paths)

    # 1) Upload state (облако)
    upload_json(dbx, OUT_STATE, payload)

    # 2) Upload diff (облако)
    upload_text(dbx, OUT_DIFF, diff_text)

    # 3) Save local state (после диффа)
    with open(local_state, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"OK uploaded: {OUT_STATE} | items: {len(items)}")
    print(f"OK uploaded: {OUT_DIFF} | lines: {0 if not diff_text else len(diff_text.splitlines())}")

    print("END main")


if __name__ == "__main__":
    main()

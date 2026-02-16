from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SECRETS = ROOT / "99_SYSTEM" / "_SECRETS"
TOKEN_FILE = SECRETS / "telegram_bot_token.txt"
CHAT_ID_FILE = SECRETS / "telegram_chat_id.txt"

LOG_DIR = ROOT / "00_INBOX" / "_ROUTER_LOGS"
PIPELINE_LOG = LOG_DIR / "pipeline_run.log"
PIPELINE_ERRORS = LOG_DIR / "pipeline_errors.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def _last_error_line() -> str:
    if not PIPELINE_ERRORS.exists():
        return "нет"
    try:
        lines = PIPELINE_ERRORS.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        if not lines:
            return "нет"
        raw = lines[-1]
        if raw.startswith("{"):
            obj = json.loads(raw)
            stage = str(obj.get("stage") or "UNKNOWN")
            code = str(obj.get("exit_code") or obj.get("code") or "n/a")
            msg = str(obj.get("message") or "").strip()
            return f"{stage} (код {code}) {msg}".strip()
        return raw[:300]
    except Exception as e:
        return f"ошибка чтения pipeline_errors.jsonl: {type(e).__name__}"


def _pipeline_log_ts() -> str:
    if not PIPELINE_LOG.exists():
        return "n/a"
    dt = datetime.fromtimestamp(PIPELINE_LOG.stat().st_mtime, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _send_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text[:3900], "disable_web_page_preview": "true"}
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        if "\"ok\":true" not in body:
            raise RuntimeError(f"telegram send failed: {body[:400]}")


def main() -> int:
    token = _read_text(TOKEN_FILE)
    chat_id = _read_text(CHAT_ID_FILE)

    pipeline_rc = "n/a"
    try:
        rc_file = LOG_DIR / "nightly_pipeline_rc.txt"
        if rc_file.exists():
            pipeline_rc = _read_text(rc_file)
    except Exception:
        pass

    text = "\n".join(
        [
            "Ночной автопилот: health report",
            f"UTC: {_utc_now()}",
            f"pipeline_exit_code: {pipeline_rc}",
            f"pipeline_log_ts: {_pipeline_log_ts()}",
            f"last_error: {_last_error_line()}",
            f"logs: {LOG_DIR}",
        ]
    )
    _send_telegram(token, chat_id, text)
    print("OK: telegram health report sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

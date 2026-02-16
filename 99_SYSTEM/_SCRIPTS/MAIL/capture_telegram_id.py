"""
Advanced script to capture your Chat ID from incoming messages
Run this, then send any message to your bot - it will show your Chat ID!
"""

import json
from urllib import request, parse
from pathlib import Path
import time

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
TOKEN_FILE = ROOT / "99_SYSTEM" / "_SECRETS" / "telegram_bot_token.txt"

def get_updates():
    """Get all messages sent to the bot"""
    token = TOKEN_FILE.read_text().strip()
    
    if not token or token.startswith("YOUR_"):
        print("❌ Token не найден в telegram_bot_token.txt")
        return
    
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    
    try:
        print("🔍 Жду сообщений от тебя в Telegram...")
        print("💬 Отправь ЛЮБОЕ сообщение боту @Noseresty2_bot")
        print("⏳ Проверяю каждые 2 секунды...\n")
        
        for i in range(30):  # Try 30 times (60 seconds)
            with request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            
            if data.get("ok") and data.get("result"):
                updates = data.get("result", [])
                if updates:
                    for update in updates:
                        message = update.get("message", {})
                        if message:
                            chat_id = message.get("chat", {}).get("id")
                            user_id = message.get("from", {}).get("id")
                            text = message.get("text", "")
                            
                            print(f"✅ НАЙДЕНО!")
                            print(f"   Chat ID: {chat_id}")
                            print(f"   User ID: {user_id}")
                            print(f"   Сообщение: {text}")
                            print(f"\n💾 Копируй Chat ID: {chat_id}")
                            return chat_id
            
            print(f"   [{i+1}/30] Жду... ", end="\r")
            time.sleep(2)
        
        print("\n❌ Не получилось. Попробуй еще раз или используй @GetIDs_bot")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    get_updates()

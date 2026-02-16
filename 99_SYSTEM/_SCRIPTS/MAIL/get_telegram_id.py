"""
Quick script to get your Telegram Chat ID by testing the bot token
"""

import json
from urllib import request
from pathlib import Path

ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
TOKEN_FILE = ROOT / "99_SYSTEM" / "_SECRETS" / "telegram_bot_token.txt"

def get_bot_info():
    token = TOKEN_FILE.read_text().strip()
    
    if not token or token.startswith("YOUR_"):
        print("❌ Token не найден в telegram_bot_token.txt")
        return
    
    url = f"https://api.telegram.org/bot{token}/getMe"
    
    try:
        print("🔍 Проверяю токен...")
        with request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        
        if data.get("ok"):
            bot = data.get("result", {})
            print(f"✅ Бот найден!")
            print(f"   Имя: {bot.get('first_name')}")
            print(f"   Username: @{bot.get('username')}")
            print(f"   Bot ID: {bot.get('id')}")
            print("\n💡 Теперь отправь боту сообщение и посмотри в логах!")
        else:
            print(f"❌ Ошибка: {data.get('description')}")
    except Exception as e:
        print(f"❌ Не удалось подключиться: {e}")

if __name__ == "__main__":
    get_bot_info()

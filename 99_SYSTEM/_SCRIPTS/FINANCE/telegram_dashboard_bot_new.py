"""
telegram_dashboard_bot.py - Archiwum 3.0 File Navigator
Nawigacja po strukturze plików z wyszukiwaniem i historią
"""

import sys
import io
from pathlib import Path
from datetime import datetime
import json

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Paths
ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
SECRETS = ROOT / "99_SYSTEM" / "_SECRETS"
HISTORY_FILE = ROOT / "99_SYSTEM" / "_SCRIPTS" / "FINANCE" / ".telegram_history.json"

# Load tokens
def load_token():
    token_file = SECRETS / "telegram_bot_token.txt"
    if not token_file.exists():
        raise FileNotFoundError("telegram_bot_token.txt not found")
    return token_file.read_text(encoding="utf-8").strip()

def load_chat_id():
    chat_file = SECRETS / "telegram_chat_id.txt"
    if not chat_file.exists():
        return None
    return chat_file.read_text(encoding="utf-8").strip()

def check_auth(update: Update) -> bool:
    authorized_chat_id = load_chat_id()
    if not authorized_chat_id:
        return True
    user_chat_id = str(update.effective_chat.id)
    return user_chat_id == authorized_chat_id


# ===== HISTORY =====
def load_history():
    """Load navigation history"""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def save_history(path: str):
    """Save to history (last 10)"""
    history = load_history()
    if path in history:
        history.remove(path)
    history.insert(0, path)
    history = history[:10]
    
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ===== MAIN MENU =====
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню - структура Archiwum"""
    if not check_auth(update):
        await update.message.reply_text("🔐 Dostęp zabroniony")
        return
    
    keyboard = [
        [InlineKeyboardButton("📥 00_INBOX", callback_data="dir_00_INBOX")],
        [InlineKeyboardButton("🧰 CASES", callback_data="dir_CASES")],
        [InlineKeyboardButton("👥 02_KLIENCI", callback_data="dir_02_KLIENCI")],
        [InlineKeyboardButton("🧾 04_DOKUMENTY", callback_data="dir_04_DOKUMENTY")],
        [InlineKeyboardButton("🏗️ PROJECTS", callback_data="dir_PROJECTS")],
        [InlineKeyboardButton("💸 FINANCE", callback_data="dir_FINANCE")],
        [InlineKeyboardButton("⚙️ 99_SYSTEM", callback_data="dir_99_SYSTEM")],
        [
            InlineKeyboardButton("🔎 SZUKAJ", callback_data="search"),
            InlineKeyboardButton("🕒 OSTATNIE", callback_data="history"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🏠 *ARCHIWUM 3.0*\n\nWybierz dział:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


# ===== DIRECTORY NAVIGATION =====
async def show_directory(query, dir_name: str):
    """Show directory contents"""
    dir_path = ROOT / dir_name
    
    if not dir_path.exists():
        await query.edit_message_text("❌ Folder nie istnieje")
        return
    
    save_history(dir_name)
    
    # Get subdirectories
    subdirs = [d for d in dir_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
    subdirs = sorted(subdirs, key=lambda x: x.name)[:15]  # Limit to 15
    
    keyboard = []
    for subdir in subdirs:
        icon = "📁"
        if subdir.name.startswith("_"):
            icon = "📂"
        keyboard.append([InlineKeyboardButton(f"{icon} {subdir.name}", callback_data=f"dir_{dir_name}/{subdir.name}")])
    
    # Files in current dir
    files = [f for f in dir_path.iterdir() if f.is_file() and not f.name.startswith('.')]
    if files:
        files_count = len(files)
        keyboard.append([InlineKeyboardButton(f"📄 Pliki ({files_count})", callback_data=f"files_{dir_name}")])
    
    # Navigation
    keyboard.append([
        InlineKeyboardButton("↩️ Назад", callback_data="menu_back"),
        InlineKeyboardButton("🏠 Menu", callback_data="menu_home"),
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📂 *{dir_name}*\n\nWybierz folder:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def show_files(query, dir_path_str: str):
    """Show files in directory"""
    dir_path = ROOT / dir_path_str
    
    if not dir_path.exists():
        await query.edit_message_text("❌ Folder nie istnieje")
        return
    
    files = [f for f in dir_path.iterdir() if f.is_file() and not f.name.startswith('.')]
    files = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:10]
    
    msg = f"📄 *Pliki w {dir_path_str}*\n\n"
    
    for f in files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        msg += f"├ `{f.name}`\n"
        msg += f"│  {mtime.strftime('%Y-%m-%d %H:%M')}\n"
    
    if not files:
        msg += "Brak plików\n"
    
    keyboard = [[
        InlineKeyboardButton("↩️ Назад", callback_data=f"dir_{dir_path_str}"),
        InlineKeyboardButton("🏠 Menu", callback_data="menu_home"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode="Markdown")


# ===== SEARCH =====
async def show_search_prompt(query):
    """Show search instructions"""
    msg = "🔎 *WYSZUKIWANIE*\n\n"
    msg += "Wpisz frazę do wyszukania:\n"
    msg += "└ Przykłady: `BMW`, `faktura`, `Kowalski`, `ZUS`\n\n"
    msg += "Bot wyszuka w nazwach plików i folderów."
    
    keyboard = [[InlineKeyboardButton("🏠 Menu", callback_data="menu_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode="Markdown")


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle search query"""
    if not check_auth(update):
        return
    
    query_text = update.message.text.lower()
    
    # Skip if it's a command
    if query_text.startswith('/'):
        return
    
    results = []
    
    # Search in all directories
    for path in ROOT.rglob("*"):
        if path.name.startswith('.'):
            continue
        if query_text in path.name.lower():
            rel_path = path.relative_to(ROOT)
            results.append((str(rel_path), path.is_dir()))
        if len(results) >= 10:
            break
    
    msg = f"🔎 *Wyniki dla: {update.message.text}*\n\n"
    
    if results:
        for rel_path, is_dir in results:
            icon = "📁" if is_dir else "📄"
            msg += f"{icon} `{rel_path}`\n"
    else:
        msg += "❌ Nie znaleziono"
    
    await update.message.reply_text(text=msg, parse_mode="Markdown")


# ===== HISTORY =====
async def show_history(query):
    """Show navigation history"""
    history = load_history()
    
    msg = "🕒 *OSTATNIE*\n\n"
    
    if history:
        for i, path in enumerate(history, 1):
            msg += f"{i}. 📂 `{path}`\n"
    else:
        msg += "Brak historii"
    
    keyboard = [[InlineKeyboardButton("🏠 Menu", callback_data="menu_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode="Markdown")


# ===== CALLBACK HANDLER =====
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    if not check_auth(update):
        await update.callback_query.answer("Unauthorized", show_alert=True)
        return
    
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    # Directory navigation
    if callback_data.startswith("dir_"):
        dir_name = callback_data[4:]
        await show_directory(query, dir_name)
    
    # Files view
    elif callback_data.startswith("files_"):
        dir_path = callback_data[6:]
        await show_files(query, dir_path)
    
    # Search
    elif callback_data == "search":
        await show_search_prompt(query)
    
    # History
    elif callback_data == "history":
        await show_history(query)
    
    # Home menu
    elif callback_data == "menu_home":
        keyboard = [
            [InlineKeyboardButton("📥 00_INBOX", callback_data="dir_00_INBOX")],
            [InlineKeyboardButton("🧰 CASES", callback_data="dir_CASES")],
            [InlineKeyboardButton("👥 02_KLIENCI", callback_data="dir_02_KLIENCI")],
            [InlineKeyboardButton("🧾 04_DOKUMENTY", callback_data="dir_04_DOKUMENTY")],
            [InlineKeyboardButton("🏗️ PROJECTS", callback_data="dir_PROJECTS")],
            [InlineKeyboardButton("💸 FINANCE", callback_data="dir_FINANCE")],
            [InlineKeyboardButton("⚙️ 99_SYSTEM", callback_data="dir_99_SYSTEM")],
            [
                InlineKeyboardButton("🔎 SZUKAJ", callback_data="search"),
                InlineKeyboardButton("🕒 OSTATNIE", callback_data="history"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text="🏠 *ARCHIWUM 3.0*\n\nWybierz dział:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    # Back button
    elif callback_data == "menu_back":
        keyboard = [[InlineKeyboardButton("🏠 Menu", callback_data="menu_home")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="↩️ Użyj 🏠 Menu aby wrócić",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )


# ===== MAIN =====
def main():
    """Start the bot"""
    print("[+] Starting Archiwum Navigator Bot...")
    
    token = load_token()
    print("[OK] Token loaded")
    
    chat_id = load_chat_id()
    if chat_id:
        print(f"[OK] Auth enabled for chat ID: {chat_id}")
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    
    # Run bot
    print("[OK] Bot running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

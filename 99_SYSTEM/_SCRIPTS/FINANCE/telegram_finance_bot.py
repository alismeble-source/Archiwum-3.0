"""
telegram_finance_bot.py - Finance status via Telegram

Commands:
  /finance - Full financial summary
  /deadlines - Upcoming deadlines only
  /inbox - Unprocessed files count
  /help - Commands list
"""

import sys
import io
from pathlib import Path
from datetime import datetime, timedelta
import csv

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Telegram bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Paths
ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
FINANCE_DOCS = ROOT / "FINANCE" / "DOCS"
INBOX = ROOT / "FINANCE_DOCS" / "_INBOX"
DEADLINES_CSV = ROOT / "FINANCE" / "_CALENDAR" / "DEADLINES.csv"
SECRETS = ROOT / "99_SYSTEM" / "_SECRETS"

# Load tokens
def load_token():
    """Load bot token from secrets"""
    token_file = SECRETS / "telegram_bot_token.txt"
    if not token_file.exists():
        raise FileNotFoundError("telegram_bot_token.txt not found in _SECRETS")
    return token_file.read_text(encoding="utf-8").strip()

def load_chat_id():
    """Load authorized chat ID"""
    chat_file = SECRETS / "telegram_chat_id.txt"
    if not chat_file.exists():
        return None
    return chat_file.read_text(encoding="utf-8").strip()


# Security: only authorized chat
def check_auth(update: Update) -> bool:
    """Verify user is authorized"""
    authorized_chat_id = load_chat_id()
    if not authorized_chat_id:
        return True  # No restriction if file missing
    
    user_chat_id = str(update.effective_chat.id)
    return user_chat_id == authorized_chat_id


# Data collectors
def get_organized_files():
    """Count organized files by type"""
    stats = {}
    
    for doc_type in ["ZUS", "VAT", "PIT", "FAKTURY", "RACHUNKI", "ZAKUPY"]:
        type_path = FINANCE_DOCS / doc_type
        if type_path.exists():
            files = list(type_path.rglob("*.pdf")) + list(type_path.rglob("*.xml"))
            if files:
                files_sorted = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
                newest = datetime.fromtimestamp(files_sorted[0].stat().st_mtime)
                
                stats[doc_type] = {
                    "count": len(files),
                    "newest": newest.strftime('%Y-%m-%d')
                }
                
                # FAKTURY subfolder breakdown
                if doc_type == "FAKTURY":
                    issued = len(list((type_path / "ISSUED").rglob("*.pdf")))
                    received = len(list((type_path / "RECEIVED").rglob("*.pdf")))
                    stats[doc_type]["issued"] = issued
                    stats[doc_type]["received"] = received
    
    return stats


def get_deadlines():
    """Get upcoming deadlines"""
    if not DEADLINES_CSV.exists():
        return []
    
    with open(DEADLINES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        deadlines = list(reader)
    
    today = datetime.now().date()
    result = []
    
    for dl in deadlines:
        due_date_str = dl.get("DUE_DATE", "")
        if not due_date_str:
            continue
        
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        
        days_left = (due_date - today).days
        
        # Only show if overdue or within 30 days
        if days_left < -30 or days_left > 30:
            continue
        
        if days_left < 0:
            status = f"❌ OVERDUE {abs(days_left)}d"
        elif days_left == 0:
            status = "🔴 TODAY"
        elif days_left <= 7:
            status = f"⚠️ {days_left}d"
        else:
            status = f"✅ {days_left}d"
        
        result.append({
            "status": status,
            "title": dl["TITLE"],
            "due_date": due_date_str,
            "days_left": days_left
        })
    
    # Sort by days_left (overdue first)
    result.sort(key=lambda x: x["days_left"])
    return result


def get_inbox_stats():
    """Count unprocessed files"""
    if not INBOX.exists():
        return {"total": 0, "pdf": 0, "xlsx": 0, "xml": 0}
    
    pdf_files = list(INBOX.rglob("*.pdf"))
    xlsx_files = list(INBOX.rglob("*.xlsx"))
    xml_files = list(INBOX.rglob("*.xml"))
    
    return {
        "total": len(pdf_files) + len(xlsx_files) + len(xml_files),
        "pdf": len(pdf_files),
        "xlsx": len(xlsx_files),
        "xml": len(xml_files)
    }


# Bot commands
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome with menu"""
    if not check_auth(update):
        await update.message.reply_text("Unauthorized")
        return
    
    # Create menu keyboard
    keyboard = [
        [
            InlineKeyboardButton("ZUS 💰", callback_data="cat_zus"),
            InlineKeyboardButton("FAKTURY 📄", callback_data="cat_faktury"),
            InlineKeyboardButton("OPLATY 💳", callback_data="cat_oplaty"),
        ],
        [
            InlineKeyboardButton("PIT 🎓", callback_data="cat_pit"),
            InlineKeyboardButton("ZAKUPY 🛒", callback_data="cat_zakupy"),
        ],
        [
            InlineKeyboardButton("WSZYSTKO 📊", callback_data="cat_all"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💼 **Finance Menu**\n\nSelect category:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help"""
    if not check_auth(update):
        await update.message.reply_text("Unauthorized")
        return
    
    await cmd_start(update, context)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    if not check_auth(update):
        await update.callback_query.answer("Unauthorized", show_alert=True)
        return
    
    query = update.callback_query
    await query.answer()
    
    # Get category
    category = query.data.replace("cat_", "")
    
    # Map categories to display functions
    category_map = {
        "zus": get_zus_summary,
        "faktury": get_faktury_summary,
        "oplaty": get_oplaty_summary,
        "pit": get_pit_summary,
        "zakupy": get_zakupy_summary,
        "all": get_full_summary,
    }
    
    if category in category_map:
        msg = category_map[category]()
        await query.edit_message_text(text=msg, parse_mode="Markdown")


def get_zus_summary() -> str:
    """ZUS files summary"""
    zus_path = FINANCE_DOCS / "ZUS"
    files = list(zus_path.rglob("*.xml")) + list(zus_path.rglob("*.pdf"))
    if not files:
        return "ZUS: No files"
    
    files_sorted = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
    newest = datetime.fromtimestamp(files_sorted[0].stat().st_mtime)
    
    msg = f"*ZUS* 💰\n\n"
    msg += f"Total: {len(files)} files\n"
    msg += f"Newest: {newest.strftime('%Y-%m-%d')}\n\n"
    msg += f"📁 Path: `FINANCE/DOCS/ZUS/`\n"
    return msg


def get_faktury_summary() -> str:
    """Faktury (invoices) summary"""
    faktury_path = FINANCE_DOCS / "FAKTURY"
    issued = len(list((faktury_path / "ISSUED").rglob("*.pdf")))
    received = len(list((faktury_path / "RECEIVED").rglob("*.pdf")))
    
    msg = f"*FAKTURY* 📄\n\n"
    msg += f"Issued (FV): {issued}\n"
    msg += f"Received: {received}\n"
    msg += f"Total: {issued + received}\n\n"
    msg += f"📁 Path: `FINANCE/DOCS/FAKTURY/`\n"
    return msg


def get_oplaty_summary() -> str:
    """Payments/bills summary"""
    rachunki_path = FINANCE_DOCS / "RACHUNKI"
    files = list(rachunki_path.rglob("*.pdf"))
    
    msg = f"*OPLATY* 💳\n\n"
    msg += f"Bills: {len(files)} files\n"
    
    if files:
        files_sorted = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
        newest = datetime.fromtimestamp(files_sorted[0].stat().st_mtime)
        msg += f"Newest: {newest.strftime('%Y-%m-%d')}\n"
    
    msg += f"\n📁 Path: `FINANCE/DOCS/RACHUNKI/`\n"
    return msg


def get_pit_summary() -> str:
    """PIT (income tax) summary"""
    pit_path = FINANCE_DOCS / "PIT"
    files = list(pit_path.rglob("*.pdf"))
    
    msg = f"*PIT* 🎓\n\n"
    msg += f"Declarations: {len(files)}\n\n"
    msg += f"📁 Path: `FINANCE/DOCS/PIT/`\n"
    return msg


def get_zakupy_summary() -> str:
    """Purchases summary"""
    zakupy_path = FINANCE_DOCS / "ZAKUPY"
    files = list(zakupy_path.rglob("*.pdf"))
    
    msg = f"*ZAKUPY* 🛒\n\n"
    msg += f"Purchases: {len(files)}\n"
    
    if files:
        files_sorted = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
        newest = datetime.fromtimestamp(files_sorted[0].stat().st_mtime)
        msg += f"Newest: {newest.strftime('%Y-%m-%d')}\n"
    
    msg += f"\n📁 Path: `FINANCE/DOCS/ZAKUPY/`\n"
    return msg


def get_full_summary() -> str:
    """Full financial summary"""
    organized = get_organized_files()
    deadlines = get_deadlines()
    inbox = get_inbox_stats()
    
    msg = "📊 *FINANCE SUMMARY*\n"
    msg += f"_{datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
    
    msg += "*Files by category:*\n"
    for doc_type, stats in organized.items():
        count = stats["count"]
        if doc_type == "FAKTURY":
            msg += f"├ {doc_type}: {count} ({stats['issued']}✅ / {stats['received']}📥)\n"
        else:
            msg += f"├ {doc_type}: {count}\n"
    
    msg += f"\n*Deadlines:*\n"
    if deadlines:
        for dl in deadlines[:3]:
            msg += f"{dl['status']} {dl['title']}\n"
    else:
        msg += "✅ No upcoming\n"
    
    msg += f"\n*Inbox:* {inbox['total']} unprocessed\n"
    return msg


async def cmd_finance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Full financial summary"""
    if not check_auth(update):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    # Gather data
    organized = get_organized_files()
    deadlines = get_deadlines()
    inbox = get_inbox_stats()
    
    # Build message
    msg = "📊 **FINANCE SUMMARY**\n"
    msg += f"_{datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
    
    # Organized files
    msg += "**Organized Files:**\n"
    for doc_type, stats in organized.items():
        count = stats["count"]
        newest = stats["newest"]
        
        if doc_type == "FAKTURY":
            msg += f"├ {doc_type}: {count} ({stats['issued']} issued, {stats['received']} received)\n"
        else:
            msg += f"├ {doc_type}: {count} (newest {newest})\n"
    
    # Deadlines
    msg += "\n**Deadlines:**\n"
    if deadlines:
        for dl in deadlines[:5]:  # Show max 5
            msg += f"{dl['status']} {dl['title']} ({dl['due_date']})\n"
    else:
        msg += "✅ No upcoming deadlines\n"
    
    # Inbox
    msg += f"\n**Inbox:** {inbox['total']} unprocessed\n"
    msg += f"└ PDF: {inbox['pdf']}, XLSX: {inbox['xlsx']}, XML: {inbox['xml']}\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_deadlines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show only deadlines"""
    if not check_auth(update):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    deadlines = get_deadlines()
    
    msg = "📅 **DEADLINES**\n"
    msg += f"_{datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
    
    if deadlines:
        for dl in deadlines:
            msg += f"{dl['status']} **{dl['title']}**\n"
            msg += f"└ Due: {dl['due_date']}\n\n"
    else:
        msg += "✅ No upcoming deadlines in next 30 days\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show inbox status"""
    if not check_auth(update):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    inbox = get_inbox_stats()
    
    msg = "📥 **INBOX STATUS**\n"
    msg += f"_{datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
    
    if inbox["total"] == 0:
        msg += "✅ Inbox is clean!\n"
    else:
        msg += f"**Total unprocessed:** {inbox['total']}\n"
        msg += f"├ PDF: {inbox['pdf']}\n"
        msg += f"├ XLSX: {inbox['xlsx']}\n"
        msg += f"└ XML: {inbox['xml']}\n\n"
        msg += "💡 Run: `organize_finance_docs.py --run`\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")


# Main
def main():
    """Run bot"""
    print("🤖 Starting Finance Telegram Bot...")
    
    # Load token
    try:
        token = load_token()
        print(f"✅ Token loaded")
    except Exception as e:
        print(f"❌ Error loading token: {e}")
        return
    
    # Check chat ID
    chat_id = load_chat_id()
    if chat_id:
        print(f"✅ Auth enabled for chat ID: {chat_id}")
    else:
        print("⚠️  No telegram_chat_id.txt - bot open to all")
    
    # Create application
    app = Application.builder().token(token).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("finance", cmd_finance))
    app.add_handler(CommandHandler("finansy", cmd_finance))  # Polish
    app.add_handler(CommandHandler("finansy", cmd_finance))  # Russian transliteration
    app.add_handler(CommandHandler("deadlines", cmd_deadlines))
    app.add_handler(CommandHandler("inbox", cmd_inbox))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Run
    print("✅ Bot running... Press Ctrl+C to stop")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

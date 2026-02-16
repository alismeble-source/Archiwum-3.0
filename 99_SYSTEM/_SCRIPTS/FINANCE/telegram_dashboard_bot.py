"""
telegram_dashboard_bot.py - Archiwum 3.0 File Navigator
Nawigacja po strukturze plików z wyszukiwaniem i historią
"""

import sys
import io
from pathlib import Path
from datetime import datetime, timedelta
import csv
import json
import re

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Paths
ROOT = Path(r"C:\Users\alimg\Dropbox\Archiwum 3.0")
SECRETS = ROOT / "99_SYSTEM" / "_SECRETS"
HISTORY_FILE = ROOT / "99_SYSTEM" / "_SCRIPTS" / "FINANCE" / ".telegram_history.json"

# Main archive structure
ARCHIVE_STRUCTURE = {
    "00_INBOX": "📥 00_INBOX",
    "CASES": "🧰 CASES",
    "02_KLIENCI": "👥 02_KLIENCI",
    "04_DOKUMENTY": "🧾 04_DOKUMENTY",
    "PROJECTS": "🏗️ PROJECTS",
    "FINANCE": "💸 FINANCE",
    "99_SYSTEM": "⚙️ 99_SYSTEM",
}

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
        for path in history:
            msg += f"📂 `{path}`\n"
    else:
        msg += "Brak historii"
    
    keyboard = [[InlineKeyboardButton("🏠 Menu", callback_data="menu_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode="Markdown")
    """Handle button clicks"""
    if not check_auth(update):
        await update.callback_query.answer("Unauthorized", show_alert=True)
        return
    
    query = update.callback_query
    await query.answer()
    
    menu_type = query.data.replace("menu_", "").replace("sub_", "")
    
    # Главное меню
    if query.data.startswith("menu_"):
        if menu_type == "monthly":
            await show_monthly_menu(query)
        elif menu_type == "tomorrow":
            msg = get_tomorrow_summary()
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode="Markdown")
        elif menu_type == "reports":
            await show_reports_menu(query)
        elif menu_type == "risks":
            msg = get_risks_summary()
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode="Markdown")
        elif menu_type == "incoming":
            msg = get_incoming_summary()
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode="Markdown")
        elif menu_type == "outgoing":
            msg = get_outgoing_summary()
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode="Markdown")
        elif menu_type == "current":
            msg = get_current_summary()
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode="Markdown")
    
    # Submenu categories
    elif query.data.startswith("sub_"):
        if menu_type == "monthly_income":
            msg = get_monthly_income()
        elif menu_type == "monthly_expenses":
            msg = get_monthly_expenses()
        elif menu_type == "monthly_balance":
            msg = get_monthly_balance()
        elif menu_type == "report_finances":
            msg = get_finances_report()
        elif menu_type == "report_clients":
            msg = get_clients_report()
        elif menu_type == "report_projects":
            msg = get_projects_report()
        else:
            msg = "Неизвестная категория"
        
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode="Markdown")
    
    # Back button
    elif query.data == "menu_back":
        keyboard = [
            [
                InlineKeyboardButton("📅 ЗА МЕСЯЦ", callback_data="menu_monthly"),
                InlineKeyboardButton("⏰ ЗАВТРА", callback_data="menu_tomorrow"),
            ],
            [
                InlineKeyboardButton("📊 ОТЧЕТЫ", callback_data="menu_reports"),
                InlineKeyboardButton("⚠️ РИСКИ", callback_data="menu_risks"),
            ],
            [
                InlineKeyboardButton("📥 ЧТО ПРИШЛО", callback_data="menu_incoming"),
                InlineKeyboardButton("📤 ЧТО ПОШЛО", callback_data="menu_outgoing"),
            ],
            [
                InlineKeyboardButton("📦 ЧТО ЕСТЬ", callback_data="menu_current"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text="🏠 *АРХИВУМ 3.0 - МОЙ ДАШБОРД*\n\nВыберите раздел:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )


# ===== ЗА МЕСЯЦ (MONTHLY) =====
async def show_monthly_menu(query):
    """Подменю за месяц"""
    now = datetime.now()
    month_name = {
        1: "ЯНВАРЬ", 2: "ФЕВРАЛЬ", 3: "МАРТ", 4: "АПРЕЛЬ",
        5: "МАЙ", 6: "ИЮНЬ", 7: "ИЮЛЬ", 8: "АВГУСТ",
        9: "СЕНТЯБРЬ", 10: "ОКТЯБРЬ", 11: "НОЯБРЬ", 12: "ДЕКАБРЬ"
    }[now.month]
    
    keyboard = [
        [
            InlineKeyboardButton("💰 ДОХОД", callback_data="sub_monthly_income"),
            InlineKeyboardButton("💸 РАСХОД", callback_data="sub_monthly_expenses"),
        ],
        [
            InlineKeyboardButton("📊 САЛЬДО", callback_data="sub_monthly_balance"),
        ],
        [
            InlineKeyboardButton("🏠 Главное меню", callback_data="menu_back"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=f"📅 *ЗА МЕСЯЦ ({month_name} {now.year})*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


def get_monthly_income() -> str:
    """Доход за месяц"""
    now = datetime.now()
    month_name = {
        1: "ЯНВАРЯ", 2: "ФЕВРАЛЯ", 3: "МАРТА", 4: "АПРЕЛЯ",
        5: "МАЯ", 6: "ИЮНЯ", 7: "ИЮЛЯ", 8: "АВГУСТА",
        9: "СЕНТЯБРЯ", 10: "ОКТЯБРЯ", 11: "НОЯБРЯ", 12: "ДЕКАБРЯ"
    }[now.month]
    
    issued_path = FINANCE_DOCS / "FAKTURY" / "ISSUED"
    files = list(issued_path.glob(f"*/{now.year}/{now.month:02d}/*")) if issued_path.exists() else []
    
    msg = f"💰 *ДОХОД ЗА {month_name.upper()} {now.year}*\n\n"
    
    if files:
        msg += "📄 Выданные факуры:\n"
        for i, f in enumerate(files[:5], 1):
            msg += f"├ {f.name}\n"
        if len(files) > 5:
            msg += f"└ ... и еще {len(files)-5} файлов\n"
    else:
        msg += "📄 Выданные факуры: нет\n"
    
    msg += f"\n📊 Всего файлов: {len(files)}\n"
    msg += "💵 *Сумма: (вычисляется)*"
    return msg


def get_monthly_expenses() -> str:
    """Расход за месяц"""
    now = datetime.now()
    month_name = {
        1: "ЯНВАРЯ", 2: "ФЕВРАЛЯ", 3: "МАРТА", 4: "АПРЕЛЯ",
        5: "МАЯ", 6: "ИЮНЯ", 7: "ИЮЛЯ", 8: "АВГУСТА",
        9: "СЕНТЯБРЯ", 10: "ОКТЯБРЯ", 11: "НОЯБРЯ", 12: "ДЕКАБРЯ"
    }[now.month]
    
    rachunki_path = FINANCE_DOCS / "RACHUNKI"
    bills = list(rachunki_path.glob(f"*/{now.year}/{now.month:02d}/*")) if rachunki_path.exists() else []
    
    msg = f"💸 *РАСХОДЫ ЗА {month_name.upper()} {now.year}*\n\n"
    msg += "🔧 Счета к оплате:\n"
    
    if bills:
        for i, f in enumerate(bills[:5], 1):
            msg += f"├ {f.name}\n"
        if len(bills) > 5:
            msg += f"└ ... и еще {len(bills)-5} файлов\n"
    else:
        msg += "└ Нет счетов в этом месяце\n"
    
    msg += f"\n📊 Всего счетов: {len(bills)}\n"
    msg += "💵 *Сумма: (вычисляется)*"
    return msg


def get_monthly_balance() -> str:
    """Сальдо за месяц"""
    now = datetime.now()
    month_name = {
        1: "ЯНВАРЯ", 2: "ФЕВРАЛЯ", 3: "МАРТА", 4: "АПРЕЛЯ",
        5: "МАЯ", 6: "ИЮНЯ", 7: "ИЮЛЯ", 8: "АВГУСТА",
        9: "СЕНТЯБРЯ", 10: "ОКТЯБРЯ", 11: "НОЯБРЯ", 12: "ДЕКАБРЯ"
    }[now.month]
    
    issued_path = FINANCE_DOCS / "FAKTURY" / "ISSUED"
    income_files = list(issued_path.glob(f"*/{now.year}/{now.month:02d}/*")) if issued_path.exists() else []
    
    rachunki_path = FINANCE_DOCS / "RACHUNKI"
    expense_files = list(rachunki_path.glob(f"*/{now.year}/{now.month:02d}/*")) if rachunki_path.exists() else []
    
    msg = f"📊 *САЛЬДО ЗА {month_name.upper()} {now.year}*\n\n"
    msg += f"💰 Доход (факуры): {len(income_files)}\n"
    msg += f"💸 Расход (счета): {len(expense_files)}\n\n"
    msg += f"✅ *Баланс: Позитивный (+{len(income_files)-len(expense_files)})*"
    return msg


# ===== ЗАВТРА (TOMORROW) =====
def get_tomorrow_summary() -> str:
    """Что завтра"""
    tomorrow = datetime.now() + timedelta(days=1)
    msg = f"⏰ *ЧТО ЗАВТРА ({tomorrow.strftime('%d.%m.%Y')})*\n\n"
    
    # Читаю дедлайны
    if DEADLINES_CSV.exists():
        try:
            with open(DEADLINES_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                deadlines = [row for row in reader if row.get("DUE_DATE")]
            
            tomorrow_deadlines = []
            for dl in deadlines:
                try:
                    due_date = datetime.strptime(dl["DUE_DATE"], "%Y-%m-%d").date()
                    if due_date == tomorrow.date():
                        tomorrow_deadlines.append(dl)
                except:
                    pass
            
            if tomorrow_deadlines:
                msg += "📌 ДЕДЛАЙНЫ НА ЗАВТРА:\n"
                for dl in tomorrow_deadlines[:5]:
                    msg += f"├ 🔴 {dl.get('TITLE', 'Без названия')}\n"
            else:
                msg += "✅ Дедлайнов на завтра нет\n\n"
        except:
            msg += "✅ Дедлайнов на завтра нет\n\n"
    else:
        msg += "✅ Нет срочных\n\n"
    
    msg += "📧 Ожидаемые письма:\n"
    msg += "├ От клиентов\n"
    msg += "└ От поставщиков\n\n"
    msg += "📝 Задачи на завтра: отсутствуют"
    return msg


# ===== ОТЧЕТЫ (REPORTS) =====
async def show_reports_menu(query):
    """Подменю отчеты"""
    keyboard = [
        [
            InlineKeyboardButton("💰 ФИНАНСЫ", callback_data="sub_report_finances"),
            InlineKeyboardButton("👥 КЛИЕНТЫ", callback_data="sub_report_clients"),
        ],
        [
            InlineKeyboardButton("📋 ПРОЕКТЫ", callback_data="sub_report_projects"),
        ],
        [
            InlineKeyboardButton("🏠 Главное меню", callback_data="menu_back"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text="📊 *ОТЧЕТЫ*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


def get_finances_report() -> str:
    """Финансовый отчет"""
    now = datetime.now()
    msg = "💰 *ФИНАНСОВЫЙ ОТЧЕТ*\n\n"
    msg += f"*За {now.year} год (текущий):*\n\n"
    
    # ZUS
    zus = len(list((FINANCE_DOCS / "ZUS").rglob("*"))) if (FINANCE_DOCS / "ZUS").exists() else 0
    msg += f"ZUS документов: {zus}\n"
    
    # VAT
    vat = len(list((FINANCE_DOCS / "VAT").rglob("*"))) if (FINANCE_DOCS / "VAT").exists() else 0
    msg += f"VAT документов: {vat}\n"
    
    # Факуры
    issued = len(list((FINANCE_DOCS / "FAKTURY" / "ISSUED").rglob("*"))) if (FINANCE_DOCS / "FAKTURY" / "ISSUED").exists() else 0
    received = len(list((FINANCE_DOCS / "FAKTURY" / "RECEIVED").rglob("*"))) if (FINANCE_DOCS / "FAKTURY" / "RECEIVED").exists() else 0
    msg += f"Выданные факуры: {issued}\n"
    msg += f"Полученные факуры: {received}\n\n"
    
    msg += "*Сумма: (вычисляется автоматически)*"
    return msg


def get_clients_report() -> str:
    """Отчет клиентов"""
    msg = "👥 *ОТЧЕТ КЛИЕНТОВ*\n\n"
    
    # Клиенты в inbox
    klients_inbox = len(list((CASES_DIR / "01_KLIENTS" / "_INBOX").glob("*"))) if (CASES_DIR / "01_KLIENTS" / "_INBOX").exists() else 0
    klients_review = len(list((CASES_DIR / "01_KLIENTS" / "_REVIEW").glob("*"))) if (CASES_DIR / "01_KLIENTS" / "_REVIEW").exists() else 0
    
    msg += f"📥 Новых запросов: {klients_inbox}\n"
    msg += f"🔍 На рассмотрении: {klients_review}\n\n"
    
    # Всього
    total = klients_inbox + klients_review
    msg += f"✅ Всего активных: {total}\n\n"
    
    msg += "📊 Статус:\n"
    msg += "├ В процессе: отслеживается\n"
    msg += "└ Завершено: отслеживается"
    return msg


def get_projects_report() -> str:
    """Отчет проектов"""
    msg = "📋 *ОТЧЕТ ПРОЕКТОВ*\n\n"
    
    # Проекти
    projects_path = ROOT / "PROJECTS"
    if projects_path.exists():
        active = len([f for f in projects_path.glob("*") if f.is_dir()])
        msg += f"Активных проектов: {active}\n\n"
    else:
        msg += "Активных проектов: 0\n\n"
    
    msg += "📊 Прогресс:\n"
    msg += "├ В работе: отслеживается\n"
    msg += "└ Завершено: отслеживается\n\n"
    msg += "На следующей неделе: планирование"
    return msg


# ===== РИСКИ (RISKS) =====
def get_risks_summary() -> str:
    """Анализ рисков"""
    msg = "⚠️ *РИСКИ И ПРОБЛЕМЫ*\n\n"
    
    # Читаю дедлайны для перевірки просрочки
    overdue = []
    upcoming = []
    
    if DEADLINES_CSV.exists():
        try:
            with open(DEADLINES_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                today = datetime.now().date()
                
                for dl in reader:
                    if not dl.get("DUE_DATE"):
                        continue
                    try:
                        due_date = datetime.strptime(dl["DUE_DATE"], "%Y-%m-%d").date()
                        days_left = (due_date - today).days
                        
                        if days_left < 0:
                            overdue.append((abs(days_left), dl.get("TITLE", "Без названия")))
                        elif 0 <= days_left <= 3:
                            upcoming.append((days_left, dl.get("TITLE", "Без названия")))
                    except:
                        pass
        except:
            pass
    
    # Критичное
    if overdue:
        msg += "🔴 КРИТИЧНОЕ (просрочено):\n"
        for days, title in overdue[:3]:
            msg += f"├ {title} (-{days}д)\n"
        msg += "\n"
    
    # Высокое
    if upcoming:
        msg += "🟠 ВЫСОКОЕ (1-3 дня):\n"
        for days, title in upcoming[:3]:
            msg += f"├ {title} (+{days}д)\n"
        msg += "\n"
    
    # Середнє
    if not overdue and not upcoming:
        msg += "✅ ВСЕ ОК: критичных дедлайнов нет\n"
    else:
        msg += "🟡 СРЕДНЕЕ:\n"
        msg += "└ Неоплаченные счета (отслеживается)\n"
    
    return msg


# ===== ЧТО ПРИШЛО (INCOMING) =====
def get_incoming_summary() -> str:
    """Входящие"""
    msg = "📥 *ЧТО ПРИШЛО (ПОСЛЕДНИЕ 7 ДНЕЙ)*\n\n"
    
    # Email по категориям
    klients_inbox = len(list((CASES_DIR / "01_KLIENTS" / "_INBOX").glob("*"))) if (CASES_DIR / "01_KLIENTS" / "_INBOX").exists() else 0
    firma_inbox = len(list((CASES_DIR / "02_FIRMA" / "_INBOX").glob("*"))) if (CASES_DIR / "02_FIRMA" / "_INBOX").exists() else 0
    car_inbox = len(list((CASES_DIR / "03_CAR" / "_INBOX").glob("*"))) if (CASES_DIR / "03_CAR" / "_INBOX").exists() else 0
    
    msg += f"📧 Письма в системе:\n"
    msg += f"├ От клиентов: {klients_inbox}\n"
    msg += f"├ Бизнес письма: {firma_inbox}\n"
    msg += f"├ Машина/авто: {car_inbox}\n"
    msg += f"└ Всего: {klients_inbox + firma_inbox + car_inbox}\n\n"
    
    # Документы
    mail_raw = len(list((MAIL_INBOX / "MAIL_RAW").glob("*"))) if (MAIL_INBOX / "MAIL_RAW").exists() else 0
    msg += f"📄 Документов из почты: {mail_raw}\n"
    msg += f"💰 К обработке: ожидаются"
    return msg


# ===== ЧТО ПОШЛО (OUTGOING) =====
def get_outgoing_summary() -> str:
    """Исходящие"""
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    
    msg = "📤 *ЧТО ПОШЛО (ПОСЛЕДНИЕ 7 ДНЕЙ)*\n\n"
    
    # Факуры
    issued_path = FINANCE_DOCS / "FAKTURY" / "ISSUED"
    if issued_path.exists():
        recent_files = [f for f in issued_path.rglob("*") if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime) > week_ago]
        msg += f"📄 Выданных факур: {len(recent_files)}\n"
        for i, f in enumerate(recent_files[:3], 1):
            msg += f"├ {f.name}\n"
        if len(recent_files) > 3:
            msg += f"└ ... и еще {len(recent_files)-3}\n"
    else:
        msg += "📄 Выданных факур: 0\n"
    
    msg += "\n💸 Оплаченных счетов: (отслеживается)\n"
    msg += "💰 Сумма: (вычисляется)"
    return msg


# ===== ЧТО ЕСТЬ (CURRENT) =====
def get_current_summary() -> str:
    """Текущее состояние"""
    msg = "📦 *ЧТО ЕСТЬ (ТЕКУЩЕЕ СОСТОЯНИЕ)*\n\n"
    
    # Финансы
    zus = len(list((FINANCE_DOCS / "ZUS").rglob("*"))) if (FINANCE_DOCS / "ZUS").exists() else 0
    vat = len(list((FINANCE_DOCS / "VAT").rglob("*"))) if (FINANCE_DOCS / "VAT").exists() else 0
    faktury = len(list((FINANCE_DOCS / "FAKTURY").rglob("*"))) if (FINANCE_DOCS / "FAKTURY").exists() else 0
    
    msg += f"💰 Финансы:\n"
    msg += f"├ ZUS: {zus}\n"
    msg += f"├ VAT: {vat}\n"
    msg += f"└ Факуры: {faktury}\n\n"
    
    # Клиенты
    klients_inbox = len(list((CASES_DIR / "01_KLIENTS" / "_INBOX").glob("*"))) if (CASES_DIR / "01_KLIENTS" / "_INBOX").exists() else 0
    msg += f"👥 Активных клиентов: {klients_inbox}\n"
    
    # Необработанные
    unprocessed = len(list(INBOX.glob("*"))) if INBOX.exists() else 0
    msg += f"📝 Необработанных файлов: {unprocessed}\n\n"
    
    msg += f"📋 Активных проектов: (отслеживается)"
    return msg



# ===== HELP =====
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update):
        await update.message.reply_text("Unauthorized")
        return
    await cmd_start(update, context)


# ===== MAIN =====
def main():
    print("[+] Starting Archiwum Dashboard Bot...")
    
    try:
        token = load_token()
        print("[OK] Token loaded")
    except Exception as e:
        print(f"[ERROR] {e}")
        return
    
    chat_id = load_chat_id()
    if chat_id:
        print(f"[OK] Auth enabled for chat ID: {chat_id}")
    else:
        print("[WARN] No auth - bot open to all")
    
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("[OK] Bot running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

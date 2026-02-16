# Financial Automation Scripts

**Created:** 2026-02-03  
**Purpose:** Automate financial document management for AlisMeble business

## Current Status

**ИП (sole proprietor) since ~4 months:**
- VAT registered (JPK-V7M monthly declarations)
- ZUS contributions (self-managed via portal ZUS)
- No accountant — all self-managed

**Workflows:**
1. ZUS — paid monthly via portal, UPO confirmation arrives via email
2. VAT — JPK-V7M filed manually via e-Deklaracje (XML + portal)
3. Bank — mBank, PDF statements only (no API)
4. Faktury — issued via service (inFakt/Fakturownia?), need to learn automation

---

## Scripts

### 1. organize_finance_docs.py

**Purpose:** Clean up chaos in `FINANCE_DOCS/_INBOX/`

**What it does:**
- Scans all PDF/XLSX/XML files recursively
- Classifies by keywords:
  - **ZUS:** deklaracje, UPO, potwierdzenia
  - **VAT:** JPK-V7M, VAT-7, VAT-UE
  - **PIT:** roczne zeznania (PIT-36, PIT-11)
  - **FAKTURY_ISSUED:** FV (faktury sprzedaży)
  - **FAKTURY_RECEIVED:** faktury zakupowe
  - **RACHUNKI:** wyciągi bankowe
  - **ZAKUPY:** potwierdzenia zakupów (Allegro, sklepy)
- Renames: `YYYYMMDD_TYPE_SANITIZED.ext`
- Moves to: `FINANCE/DOCS/{TYPE}/YYYY/MM/`

**Usage:**
```powershell
# Dry run (show what would happen)
python organize_finance_docs.py --dry-run

# Execute (actually move files)
python organize_finance_docs.py --run
```

**Output structure:**
```
FINANCE/DOCS/
  ZUS/
    2026/
      01/
        20260111_ZUS_Deklaracja_ZUSDRA_2025_01_01.pdf
        20260120_ZUS_UPO_platnosc.pdf
  VAT/
    2025/
      09/
        20250930_VAT_Deklaracja_JPKV7M_2025_09.pdf
  FAKTURY/
    ISSUED/
      2025/
        09/
          20250918_FAKTURA_ISSUED_FV_5_2025.pdf
    RECEIVED/
      2026/
        01/
          20260109_FAKTURA_RECEIVED_zakup_material.pdf
```

---

### 2. Email Integration (router_cases_inbox.py)

**Updated:** 2026-02-03

Added financial keywords to `FIRMA_KEYS`:
- `jpk`, `zusdra`, `zusrca`, `vat-7`, `deklaracja`
- `wyciąg`, `przelewy`, `powiadomienie o wystawieniu`
- `potwierdzenie płatności`, `upo`, `e-deklaracje`

**Flow:**
```
Gmail → import_gmail_attachments.py 
  → CASES/_INBOX/*.meta.json
  → router_cases_inbox.py (classifies)
  → CASES/02_FIRMA/_INBOX/ (if FIRMA_KEYS match)
```

**Next step:** Create dedicated `FINANCE/_INBOX/` route for direct filing

---

## TODO (Next Phases)

### Phase 2: Monthly Reconciliation

Create `monthly_reconciliation.py`:
- Extract data from issued faktury (FV) → dochody
- Extract data from received faktury → wydatki
- Generate CSV: `YYYY-MM_reconciliation.csv`
- Update `FINANCE/_CALENDAR/DEADLINES.csv` with payment reminders

### Phase 3: Auto-Reminders

Integrate with Telegram:
- Parse `DEADLINES.csv` for upcoming dates
- Send notifications: "📊 ZUS 01-2026 due in 3 days (20.02)"
- Link to relevant files

### Phase 4: Learn Faktura Automation

Tools to explore:
- **inFakt API** - if using inFakt.pl
- **Fakturownia API** - if using Fakturownia.pl
- **Manual Excel → PDF** - if generating manually

**Goal:** Auto-generate FV from project completion data

---

## File Locations

**Source (chaos):**
- `FINANCE_DOCS/_INBOX/AlisMeble baza dokumentów_*/` (many Unicode conflicts)

**Destination (organized):**
- `FINANCE/DOCS/{ZUS|VAT|PIT|FAKTURY|RACHUNKI|ZAKUPY}/YYYY/MM/`

**Logs:**
- `99_SYSTEM/_LOGS/finance_organize_log.csv`

**Deadlines:**
- `FINANCE/_CALENDAR/DEADLINES.csv`

---

## Current DEADLINES (from CSV)

| TYPE      | TITLE            | DUE_DATE   | PATH                  |
|-----------|------------------|------------|-----------------------|
| PAYMENT   | ZUS 01-2026      | 2026-02-20 | FINANCE/ZUS/2026-01   |
| PAYMENT   | US VAT 01-2026   | 2026-02-25 | FINANCE/US/VAT/2026-01|
| PAYMENT   | FAKTURA PAYCHECK | 2026-01-30 | FINANCE/FAKTURY/      |
| FOLLOW-UP | WYCENA follow-up | 2026-01-18 | CASES/                |

**Status (as of 2026-02-03):**
- ⚠️ ZUS 01-2026 due in 17 days
- ⚠️ VAT 01-2026 due in 22 days
- ❌ FAKTURA PAYCHECK overdue (2026-01-30 passed)

---

## Integration with Existing System

This builds on top of existing [Archiwum 3.0 mail pipeline](../../_SCRIPTS/MAIL/):

**Existing workflow:**
```
Gmail API → import_gmail_attachments.py
  → CASES/_INBOX/*.meta.json + attachments
  → router_cases_inbox.py (classify)
  → {01_KLIENTS|02_FIRMA|03_CAR}/_INBOX
  → telegram_notify_router.py (notifications)
```

**New addition:**
```
CASES/02_FIRMA/_INBOX (financial docs detected)
  ↓
organize_finance_docs.py (scheduled weekly)
  ↓
FINANCE/DOCS/{TYPE}/YYYY/MM/
```

**Future:**
```
FINANCE/DOCS/{TYPE}/YYYY/MM/
  ↓
monthly_reconciliation.py (1st of month)
  ↓
FINANCE/REPORTS/YYYY-MM_reconciliation.csv
  ↓
telegram_finance_reminders.py (check DEADLINES.csv)
```

---

## Notes from User

> "я сам через портал [ZUS]"  
> "в этом году я заполнял ват в7 [JPK-V7M]"  
> "только пдф или то что в почте [bank statements]"  
> "фактуры он высталвял я еще не успел вот как раз хотел научиться=)"

Translation:
- ZUS self-managed via portal
- VAT JPK-V7M self-filed this year
- Bank: only PDF statements (from email or manual download)
- Faktury: service generates them, user wants to learn automation

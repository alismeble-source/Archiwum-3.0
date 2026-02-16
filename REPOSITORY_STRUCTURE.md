# 📂 Complete Repository Structure - Archiwum 3.0

## 🌳 Directory Tree Visualization

```
.
├── 01_FIRMA/                    # Company documents
│   └── .gitkeep
├── 02_KLIENCI/                  # Client database and documentation
│   └── .gitkeep
├── 03_FINANSE/                  # Financial documents
│   └── .gitkeep
├── 04_CAR/                      # Car documents
│   └── .gitkeep
├── 04_DOKUMENTY/                # General documents
│   └── .gitkeep
├── 05_FAMILY/                   # Family documents
│   └── .gitkeep
├── 05_PROJEKTY/                 # Active projects
│   └── .gitkeep
├── 06_ARCHIWUM/                 # Archive data
│   └── .gitkeep
├── 98_INCOMING_DUMPS/           # Uploads and dumps
│   └── .gitkeep
├── 99_SYSTEM/                   # System files
│   ├── api/                     # API configuration
│   │   └── config.json          # API configuration file
│   ├── .gitkeep
│   └── metadata.json            # System metadata
├── ALIS/                        # Personal module
│   └── .gitkeep
├── CORE/                        # System core
│   └── README.md                # Core documentation
├── FORENSIC/                    # Analytics module
│   └── .gitkeep
├── INNE/                        # Miscellaneous
│   └── .gitkeep
├── Juliana/                     # Personal section
│   └── .gitkeep
├── .gitignore                   # Ignored files
└── README.md                    # Main documentation
```

## 📊 Repository Statistics

- **Total Directories:** 17
- **Total Files:** 19
- **Nesting Level:** Up to 2 subfolders
- **System Version:** 3.0.0
- **Created:** 2026-02-16

## 🗂️ Detailed Structure Description

### 📋 Main Categories (01-06)

| Folder | Purpose | Status |
|--------|---------|--------|
| **01_FIRMA** | Company documents | Active |
| **02_KLIENCI** | Client database and documentation | Active |
| **03_FINANSE** | Financial documents, reports, budgets | Active |
| **04_CAR** | Car documents (registration, insurance, service) | Active |
| **04_DOKUMENTY** | General purpose documents | Active |
| **05_FAMILY** | Family documents (personal, medical, education) | Active |
| **05_PROJEKTY** | Active projects and documentation | Active |
| **06_ARCHIWUM** | Archive data and completed projects | Archive |

### 🔧 Specialized Modules

#### ALIS
- **Purpose:** Personal management module
- **Version:** 3.0
- **Status:** Enabled
- **API Endpoints:**
  - `/alis/profile` - User profile
  - `/alis/settings` - Settings
  - `/alis/analytics` - Analytics

#### FORENSIC
- **Purpose:** Analytics module for deep data analysis
- **Version:** 3.0
- **Status:** Enabled
- **API Endpoints:**
  - `/forensic/analyze` - Data analysis
  - `/forensic/reports` - Reports
  - `/forensic/cases` - Cases

#### CORE
- **Purpose:** Archiwum 3.0 system core
- **Version:** 3.0
- **Description:** Core modules and system configuration
- **Files:** `README.md` with documentation

#### INNE
- **Purpose:** Miscellaneous documents and materials
- **Status:** Active category

#### Juliana
- **Purpose:** Personal section
- **Status:** Active category

### ⚙️ System Folders (98-99)

#### 98_INCOMING_DUMPS
- **Purpose:** Incoming uploads, dumps, and temporary files
- **Status:** Ignored in Git (see `.gitignore`)

#### 99_SYSTEM
- **Purpose:** System files and configurations
- **Subfolders:**
  - `api/` - API configuration
- **Files:**
  - `api/config.json` - API v3 configuration
  - `metadata.json` - System metadata

## 🚀 API Modules - 18 Total Endpoints

### 1. ALIS Module (3 endpoints)
- `GET /alis/profile` - Get profile
- `GET/POST /alis/settings` - Manage settings
- `GET /alis/analytics` - Analytics data

### 2. FORENSIC Module (3 endpoints)
- `POST /forensic/analyze` - Start analysis
- `GET /forensic/reports` - Get reports
- `GET /forensic/cases` - List cases

### 3. FINANCE Module (3 endpoints)
- `GET/POST /finance/transactions` - Transactions
- `GET /finance/reports` - Financial reports
- `GET/POST /finance/budgets` - Budget management

### 4. CLIENTS Module (3 endpoints)
- `GET /clients/list` - Client list
- `GET /clients/details` - Client details
- `GET /clients/documents` - Client documents

### 5. PROJECTS Module (3 endpoints)
- `GET /projects/active` - Active projects
- `GET /projects/archive` - Archived projects
- `GET /projects/reports` - Project reports

### 6. DOCUMENTS Module (3 endpoints)
- `GET /documents/search` - Search documents
- `POST /documents/upload` - Upload documents
- `GET /documents/download` - Download documents

## 🔒 Security

Confidential data protected via `.gitignore`:
- Private keys and certificates
- Secret files
- Credentials folders
- Telegram history
- Incoming dumps (98_INCOMING_DUMPS/)

## 📝 Workflow

1. **Incoming documents** → `98_INCOMING_DUMPS/`
2. **Automatic sorting** → API determines category
3. **Placement in category** → Folders 01-06
4. **Archiving** → `06_ARCHIWUM/`

## 🛠️ Technical Stack

- **Version Control:** Git
- **API Version:** v3.0
- **Rate Limit:** 1000 req/period
- **Authentication:** Required
- **CORS:** Enabled
- **Logging:** Enabled (level: info)
- **Log Path:** `99_SYSTEM/logs/`

---

**Last Updated:** 2026-02-16
**Owner:** alismeble-source
**System:** Archiwum 3.0

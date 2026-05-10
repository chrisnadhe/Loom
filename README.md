# Loom — Network Configuration Generator

Loom is a high-performance web application built with **FastAPI**, **HTMX**, and **TailwindCSS** that automates bulk network device configuration. Engineers simply fill in Excel spreadsheets, upload them, map columns to template variables, preview the generated CLI configs, and download — with optional AI-powered security review at every step.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Multi-format Input** | Upload `.xlsx`, `.xls`, or `.csv` files |
| **Multi-file Workflow** | Separate sheets for global params, VLANs, Etherchannels, and port mappings |
| **AI Auto-mapping** | AI suggests column→variable mappings automatically |
| **Live Preview** | Rendered CLI config visible before committing |
| **Inline Editing** | Edit generated configs directly in the browser |
| **AI Config Review** | Security score, issue detection, and actionable recommendations |
| **Bulk Download** | Download all configs as a `.zip` or individually as `.txt` |
| **History** | Every generated config is stored in SQLite with metadata (OS type, template) |
| **Multi-user** | UUID-based session isolation — no Redis required |
| **Dark Mode** | Glassmorphism UI with system-aware dark/light theme |

---

## 🔄 Workflow

```
1. Select OS Type (Cisco IOS / IOS-XE / …)
         │
         ▼
2. Upload Excel Files
   ├── 01_params.xlsx      — device-level settings
   ├── 02_vlans.xlsx       — VLAN definitions       (optional)
   ├── 03_etherchannels.xlsx — port-channel config  (optional)
   └── 04_port_mapping.xlsx — per-port config
         │
         ▼
3. Data Preview & Validation
   └── Rows highlighted if hostname is missing or duplicated
         │
         ▼
4. Variable Mapping
   ├── Manual dropdowns (grouped by category)
   └── "Auto-Map with AI" — AI suggests mappings in one click
         │
         ▼
5. Config Preview & Edit
   ├── Full Jinja2-rendered CLI config per device
   ├── Inline text editing
   └── "Review with AI" — security score + issue analysis
         │
         ▼
6. Confirm & Generate
   ├── Configs saved to SQLite history
   ├── Download all as .zip
   └── Download individual .txt files
         │
         ▼
7. History
   ├── Filter by device name or OS type
   ├── View modal with copy + download
   └── Re-download any past config
```

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.13) |
| Frontend | HTMX 2, TailwindCSS (CDN), Jinja2 |
| Data Processing | Pandas, OpenPyXL |
| Config Templates | Jinja2 `.j2` files |
| Database | SQLModel + SQLite (swappable to PostgreSQL) |
| AI | LiteLLM (Gemini, OpenAI, DeepSeek, OpenRouter) |
| Package Manager | [uv](https://github.com/astral-sh/uv) |

---

## 📋 Installation

### 1. Clone the repository

```bash
git clone https://github.com/chrisnadhe/Loom.git
cd Loom
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your AI API key
```

Key variables in `.env`:

```env
APP_ENV=development          # development | production
AI_MODEL=gemini/gemini-1.5-flash
GEMINI_API_KEY=your_key_here
DATABASE_URL=sqlite:///./loom.db
```

### 3. Install dependencies

```bash
# Requires uv — https://github.com/astral-sh/uv
uv sync
```

### 4. Run

```bash
uv run python -m app.main
```

Open `http://localhost:8000` in your browser.

---

## 📂 Project Structure

```
Loom/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── models/
│   │   ├── config.py            # SQLModel — Configuration table
│   │   └── database.py          # Engine creation (APP_ENV-aware echo)
│   ├── routes/
│   │   ├── api.py               # All API endpoints
│   │   └── views.py             # Page routes (SSR HTML)
│   ├── services/
│   │   ├── ai_service.py        # LiteLLM: mapping suggestions + config review
│   │   ├── data_processor.py    # File parsing, clean_val(), merge logic
│   │   ├── session_store.py     # UUID-based multi-user session isolation
│   │   ├── template_engine.py   # Jinja2 wrapper + variable extraction
│   │   └── validator.py         # Pydantic config validation (non-blocking)
│   ├── static/                  # Static assets
│   └── templates/
│       ├── base.html            # Layout with nav, dark mode, HTMX indicator
│       ├── index.html           # Main upload page
│       ├── history.html         # Config history with search + download
│       ├── templates.html       # Template browser
│       ├── download.html        # Excel template downloads
│       └── components/
│           ├── data_preview.html       # Parsed data table
│           ├── mapping_ui.html         # Mapping form wrapper
│           ├── mapping_form.html       # Column→variable dropdowns
│           ├── config_preview.html     # Editable textarea + AI Review button
│           ├── ai_review_panel.html    # AI security analysis panel
│           └── generation_results.html # Download results
│
├── templates/                   # Jinja2 network config templates (.j2)
│   ├── cisco_ios_complete.j2
│   └── cisco_ios_xe_complete.j2
│
├── .env                         # Local secrets (git-ignored)
├── .env.example                 # Template for .env
├── pyproject.toml
└── Dockerfile
```

---

## 🤖 AI Integration

Loom supports multiple AI providers via **LiteLLM** — swap providers by editing `.env`:

```env
# Google Gemini (default)
AI_MODEL=gemini/gemini-1.5-flash
GEMINI_API_KEY=…

# OpenAI
AI_MODEL=gpt-4o-mini
OPENAI_API_KEY=…

# DeepSeek
AI_MODEL=deepseek/deepseek-chat
DEEPSEEK_API_KEY=…

# OpenRouter (any model)
AI_MODEL=openrouter/openrouter/free
OPENROUTER_API_KEY=…
```

### AI features

1. **Auto-map** (`POST /api/ai/suggest-mapping`) — maps Excel columns to Jinja2 variables
2. **Config Review** (`POST /api/ai/review-config`) — returns:
   - Security score (0–100)
   - Grade: Excellent / Good / Fair / Poor
   - Issues list with severity (critical / warning / info)
   - Actionable recommendations

---

## 🐳 Docker

```bash
docker build -t loom .
docker run -p 8000:8000 --env-file .env loom
```

---

## 📄 License

MIT

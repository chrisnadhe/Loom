# Loom - Network Configuration Generator

Loom is a high-performance web application built with **FastAPI**, **HTMX**, and **TailwindCSS** to automate the generation of network configurations. It bridges the gap between structured data (Excel/CSV) and complex device templates using **Jinja2** and **Generative AI**.

## 🚀 Features

- **Multi-Format Data Support**: Seamlessly process `.xlsx`, `.xls`, and `.csv` files.
- **Template Driven**: Use Jinja2 templates for Cisco IOS, Arista EOS, Aruba AOS-CX, and more.
- **AI-Enhanced Mapping**: Leverage GenAI (Gemini, OpenAI, DeepSeek, etc.) to automatically map data columns to template variables.
- **Live Preview**: Real-time rendering of configurations as you map data.
- **Modern UI**: Clean, responsive dashboard with dark mode and glassmorphism aesthetics.
- **Lightweight & Fast**: Powered by `uv` for package management and FastAPI for high-performance processing.

## 🛠 Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTMX, TailwindCSS, Jinja2
- **Data Processing**: Pandas, OpenPyXL
- **Database**: SQLModel (SQLite/PostgreSQL)
- **Package Manager**: [uv](https://github.com/astral-sh/uv)

## 📋 Installation

1. **Clone the repository**:
   ```bash
   git clone [https://github.com/chrisnadhe/Loom.git](https://github.com/chrisnadhe/Loom.git)
   cd Loom
   ```

2. **Install dependencies**:
   Make sure you have `uv` installed. If not, get it from [here](https://github.com/astral-sh/uv).
   ```bash
   uv sync
   ```

3. **Run the application**:
   ```bash
   uv run python -m app.main
   ```

4. **Access the dashboard**:
   Open your browser and navigate to `http://localhost:8000`.

## 📂 Project Structure

- `app/`: Core application logic.
  - `models/`: Database schemas.
  - `routes/`: API and View endpoints.
  - `services/`: Business logic (Data processing, AI integration).
  - `templates/`: HTML templates for the web interface.
  - `static/`: Static assets (CSS/JS).
- `templates/`: Jinja2 templates for network configurations (Cisco, Arista, etc.).

## 🤖 AI Integration (Phase 2)

Loom supports multiple AI providers via API:
- Google Gemini
- OpenAI
- DeepSeek
- Kimi
- OpenRouter

## 📄 License

MIT

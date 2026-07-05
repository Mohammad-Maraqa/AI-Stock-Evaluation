# Running AI Stock Evaluation Locally

This guide explains how to run the FastAPI backend, React frontend, and optional local Ollama sentiment model.

## Prerequisites

- Python 3.11+ recommended
- Node.js and npm
- Ollama installed locally if you want AI sentiment classification

The app is local-first. It does not require external AI API keys, accounts, databases, Docker, or cloud services.

## 1. Set Up Python Backend

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Start the FastAPI backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

Useful API endpoints:

```text
GET  http://127.0.0.1:8000/api/health
GET  http://127.0.0.1:8000/api/providers/status
GET  http://127.0.0.1:8000/api/analyze?ticker=AAPL
POST http://127.0.0.1:8000/api/watchlist/analyze
```

## 2. Set Up React Frontend

Open a second terminal and run:

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL:

```text
http://127.0.0.1:5173
```

The frontend calls the FastAPI backend through `/api`.

## 3. Optional Ollama Setup

Install and start Ollama, then pull the recommended light local model:

```powershell
ollama pull qwen2.5:3b
ollama serve
```

Default backend settings:

```text
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:3b
```

If Ollama is not running, the app still works. Sentiment falls back to neutral metadata.

## 4. Optional Environment Variables

Create a `.env` file in the project root only if you need overrides:

```text
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:3b
SCRAPER_API_KEY=
```

You can copy `.env.example` to `.env` and edit it. The `.env` file is ignored by Git.

`SCRAPER_API_KEY` is optional and only used if you later configure a scraper proxy.

## 5. Run Tests And Build

From the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m py_compile main.py config.py analysis.py scorers.py utils.py backend\main.py backend\api\app.py backend\schemas.py
```

From `frontend/`:

```powershell
npm test
npm run build
npm audit --audit-level=moderate
```

## 6. Optional Ollama Benchmark

After installing the local models you want to compare, run:

```powershell
.\.venv\Scripts\python.exe -m tools.ollama_benchmark
```

This updates:

```text
docs/OLLAMA_BENCHMARK.md
```

The benchmark uses local Ollama only and does not call external AI APIs.

## Troubleshooting

- If the frontend cannot load data, confirm the backend is running on `http://127.0.0.1:8000`.
- If sentiment is always neutral, confirm Ollama is running and the configured model is installed.
- If FinViz headlines are empty, the ticker may have no recent headlines or FinViz may be temporarily blocking requests.
- If Yahoo Finance data is missing, try another ticker such as `AAPL`, `MSFT`, or `NVDA`.

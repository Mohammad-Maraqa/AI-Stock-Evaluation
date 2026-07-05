# AI-Powered Stock Evaluation

A FastAPI + React stock evaluation dashboard that combines market fundamentals, technical analysis, Scrapy-collected article-aware news sentiment, and data-quality confidence into a composite score from 0 to 100. Derivatives/options are shown as risk context, not as a core score driver.

This project began as a thesis prototype and is being migrated toward a clean, industry-ready architecture with explicit provider boundaries and testable services.

For detailed onboarding and current technical status, see [docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md). For an external review prompt/context packet, see [docs/CHATGPT_REASSESSMENT_BRIEF.md](docs/CHATGPT_REASSESSMENT_BRIEF.md).

## Architecture

```text
React/Vite frontend
  -> FastAPI backend
      -> AnalysisService
          -> MarketDataProvider: yfinance
          -> NewsProvider: Scrapy / FinViz
          -> SentimentProvider: Ollama local, neutral fallback
          -> ScoringEngine
```

The browser never scrapes websites and never receives API keys. All market data, scraping, sentiment calls, and scoring happen in the backend.

## Features

- Ticker or company-name search.
- FastAPI JSON API with typed response schemas.
- React/Vite dashboard using reusable UI components.
- yfinance market data for price history, fundamentals, options, and insider data.
- Scrapy-based FinViz headline extraction with a five-minute in-memory cache.
- Ollama-compatible local sentiment provider with strict JSON validation.
- Neutral sentiment fallback when Ollama is unavailable.
- First-class insider activity, Piotroski quality, and derivatives summary sections.
- Deterministic Fundamental Deep Analysis with summary-first category explanations.
- Deterministic data-quality confidence and degraded-analysis warnings.
- Session-only watchlist comparison mode.
- Opportunity Finder page for theme or ETF-based research discovery, with deterministic ranking, discovery confidence, scan metadata, reasons, risks, and source warnings.
- Composite scoring across fundamentals, technicals, sentiment, and data quality. Fundamental Deep Analysis is explanatory and does not change the composite formula.
- Candlestick chart rendering with Lightweight Charts.

## Project Structure

```text
backend/             FastAPI app, schemas, providers, services
frontend/            React/Vite dashboard
analysis.py          Pure composite-score helper
config.py            Shared weights, env names, sector medians
scorers.py           Scoring engine
tools/               Local Ollama benchmark tooling
utils.py             Rating and normalization helpers
tests/               Backend/domain pytest suite
docs/                Project documentation
```

## Environment Variables

```text
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:3b
SCRAPER_API_KEY=optional_scraperapi_key
```

Copy `.env.example` to `.env` if you want project-local overrides. The `.env` file is ignored by Git.

No key is required for local Ollama, but Ollama must be installed and serving the selected model. If Ollama is unavailable, the backend returns neutral sentiment metadata and keeps the rest of the analysis available.

## No Hallucination Rule

AI may classify sentiment from fetched headlines and may summarize existing factual data. AI must never generate financial metrics, fundamentals, options statistics, insider data, Piotroski signals, competitors, or Opportunity Finder facts.

Opportunity Finder follows the same rule. Discovery sources may suggest tickers, but yfinance validation decides whether a ticker is usable, and deterministic scoring decides ranking. The feature does not use external AI APIs and does not produce buy/sell recommendations.

## Backend Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Useful endpoints:

```text
GET http://127.0.0.1:8000/api/health
GET http://127.0.0.1:8000/api/providers/status
GET http://127.0.0.1:8000/api/analyze?ticker=AAPL
POST http://127.0.0.1:8000/api/watchlist/analyze
GET http://127.0.0.1:8000/api/opportunity/themes
GET http://127.0.0.1:8000/api/opportunity/scan?theme=ai_infrastructure&limit=10
```

## Opportunity Finder

Opportunity Finder is a research discovery tool, not a buy/sell recommendation engine. It surfaces stocks connected to high-growth themes or a user-entered ETF by combining public discovery sources with existing yfinance validation and the app's analysis pipeline.

V1 discovery is intentionally defensive:

- ETF holdings are the primary discovery path.
- Nasdaq/source discovery is best-effort secondary input.
- Public-source failures return structured warnings and partial results instead of breaking the scan.
- Candidates are cheaply validated and ranked for theme relevance before full analysis runs.
- Full analysis is limited by `max_candidates` so scans do not attempt to analyze hundreds of tickers.

The scanner reports discovered, validated, filtered, analyzed, returned counts, and duration. Each result separates `discovery_confidence` from data quality so a company with strong market data but weak theme evidence is easier to spot.

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` requests to the FastAPI backend.

## Verification

```bash
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m py_compile main.py config.py analysis.py scorers.py utils.py backend\main.py backend\api\app.py backend\schemas.py
cd frontend
npm test
npm run build
npm audit --audit-level=moderate
```

Most recent verified state:

- Python tests: `76 passed`
- Frontend tests: `5 passed`
- Frontend production build: passed
- Frontend dependency audit: `0 vulnerabilities`
- FastAPI route tests cover `/api/health`, `/api/providers/status`, `/api/analyze`, `/api/watchlist/analyze`, and Opportunity Finder endpoints with mocked services.

## Limitations

- Yahoo Finance data can be missing, delayed, or inconsistent.
- Public ETF holdings and Nasdaq/source discovery pages can change, block requests, or return incomplete data.
- FinViz HTML can change or block scraping.
- Ollama quality and speed depend on local hardware and selected model.
- Sentiment falls back to neutral when Ollama is unavailable.
- Scores are research signals, not financial advice.
- Opportunity Finder labels are deterministic research categories, not recommendations.

## Reassessment Focus

Before adding new product features, reassess:

- Whether the FastAPI service boundaries are clean enough or need another packaging pass.
- Whether the five-minute in-memory headline cache is enough for local use.
- Whether to run the local Ollama benchmark and update `docs/OLLAMA_BENCHMARK.md` with live model results.
- Which user-facing enhancement should come next: deeper watchlist UX, portfolio analysis, saved reports, or deployment.

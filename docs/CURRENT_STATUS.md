# Current Status: AI Stock Evaluation

## Purpose

AI Stock Evaluation is a FastAPI + React dashboard for evaluating US-listed stocks and ETFs with a multi-factor signal model. It combines fundamentals, technical analysis, AI-classified news sentiment, and data-quality confidence into a single composite score from 0 to 100. Derivatives/options are displayed as risk context rather than a core score driver. The app also includes Opportunity Finder, a deterministic research discovery page for scanning theme or ETF-derived stock candidates.

The project began as an academic thesis prototype and has been migrated away from Streamlit toward a clean, provider-oriented FastAPI + React architecture suitable for future production hardening.

## Current Architecture

```text
React/Vite frontend
  -> FastAPI backend
          -> AnalysisService
              -> MarketDataProvider: yfinance
              -> NewsProvider: Scrapy / FinViz
              -> SentimentProvider: Ollama local, neutral fallback
              -> ScoringEngine
```

The frontend calls backend JSON APIs only. It does not scrape websites, call AI providers, or hold API keys.

## Executive Snapshot

- **Primary app runtime:** FastAPI backend plus React/Vite frontend.
- **Scraping strategy:** Scrapy-backed FinViz headline extraction through a backend `NewsProvider`.
- **Market data strategy:** `yfinance` remains the current source for price history, fundamentals, options, and insider data.
- **AI strategy:** Ollama local sentiment only, with neutral sentiment fallback when Ollama is unavailable.
- **Current maturity:** Migration foundation, reliability hardening, data-quality reporting, and session-only watchlist comparison are in place.
- **Opportunity Finder:** Theme/ETF discovery, candidate validation, deterministic ranking, discovery confidence, scan metadata, and source warnings are available.
- **Best next conversation:** decide whether to focus on architecture hardening, UI parity, data reliability, AI quality, or product features.

## Product Behavior

The app accepts either a ticker symbol, such as `AAPL`, or a company name, such as `Apple`. The backend resolves company names through Yahoo Finance search, gathers market/news data, classifies article-aware sentiment with headline fallback, scores the analytical pillars, and returns a typed JSON response for the React dashboard.

The dashboard displays:

- Composite score and qualitative rating.
- Company identity, sector, and industry.
- Fundamental, sentiment, technical, and derivatives pillar cards.
- Fundamental Deep Analysis with deterministic category scores, concise explanations, and expandable metrics.
- First-class insider activity, Piotroski quality, and derivatives summary panels.
- Data-quality confidence, provider health indicators, and degraded-analysis warnings.
- Session-only watchlist comparison mode.
- Opportunity Finder with theme mode, ETF ticker mode, scan metadata, ranked candidates, deterministic reasons/risks, and a one-click path into full stock analysis.
- Scrapy-collected headlines/articles with sentiment, impact scores, and analysis-depth labels.
- Candlestick chart data with SMA and Bollinger overlays.
- Loading, empty, and error states.

## API Surface

```text
GET /api/health
GET /api/providers/status
GET /api/analyze?ticker=AAPL
POST /api/watchlist/analyze
GET /api/opportunity/themes
GET /api/opportunity/scan?theme=ai_infrastructure&limit=10
```

`/api/analyze` returns:

- `ticker`
- `company`
- `composite`
- `pillars`
- `headlines`
- `chart`
- `providers`
- `insider_activity`
- `piotroski`
- `derivatives`
- `competitors`, currently always an empty list
- `data_quality`
- `fundamental_analysis`

The response schemas live in `backend/schemas.py`.

## Current Verified State

Latest verification evidence:

```text
Python tests: 76 passed
Python py_compile: passed for core backend/domain modules
Frontend tests: 5 passed
Frontend build: passed
npm audit --audit-level=moderate: 0 vulnerabilities
FastAPI route tests cover:
  /api/health
  /api/providers/status
  /api/analyze with mocked services
  /api/watchlist/analyze with mocked services
  /api/opportunity/themes and /api/opportunity/scan with mocked services
```

Live `AAPL` server smoke was not rerun during the local-only constraint cleanup. Earlier browser screenshot capture could not be completed in the sandbox because both Chrome and Edge headless binaries crashed before producing an image.

## Data and Provider Flow

### Market Data

`MarketDataProvider` owns ticker resolution and keeps `yfinance` as the source for:

- price history
- fundamentals
- options and derivatives context
- insider transaction data

### Opportunity Discovery

Opportunity Finder is a synchronous local-first scan pipeline:

```text
selected theme or ETF
  -> ETF holdings discovery, primary and defensive
  -> Nasdaq/source discovery, best-effort secondary
  -> cheap yfinance validation and theme relevance scoring
  -> full AnalysisService only for top candidates
  -> deterministic opportunity scoring, labels, reasons, and risks
```

The scanner is mock-first in tests and does not require live public pages for verification. Public-source failures return structured warnings and partial results instead of breaking the scan. `discovery_confidence` is separate from data quality so weak theme evidence stays visible even when market data is strong.

### News

`ScrapyNewsProvider` collects FinViz headlines, attempts to fetch each linked article, and normalizes results into `Headline` objects. Parsing is implemented with Scrapy selectors in `backend/services/news/finviz_spider.py`.

A five-minute in-memory TTL cache prevents repeated requests for the same ticker during short intervals. It is process-local only and does not add persistence or infrastructure.

### Sentiment

Sentiment providers implement a common interface:

- `OllamaSentimentProvider`
- `CompositeSentimentProvider`

The runtime tries Ollama first and then returns neutral no-AI sentiment if Ollama fails. Sentiment analysis prefers fetched article text when available and falls back to headline-only context when article extraction fails. Model output is required to be strict JSON and is validated before scoring.

AI is an interpretation layer only. It may classify fetched headlines and summarize existing factual data. It must not generate financial metrics, fundamentals, options statistics, insider data, Piotroski signals, or competitors.

Opportunity Finder follows the same rule. AI does not discover stocks, invent tickers, create financial facts, or make buy/sell recommendations.

## Scoring Model

The composite score is calculated with weights from `config.py`:

| Pillar | Weight |
|---|---:|
| Fundamentals | 45% |
| Technical analysis | 30% |
| AI sentiment | 20% |
| Data quality | 5% |

Derivatives/options are excluded from the composite score and presented as risk context.

The existing `ScoringEngine` remains the source of pillar scoring logic. `analysis.py` contains the pure composite-score helper.

## Environment Variables

| Name | Purpose |
|---|---|
| `OLLAMA_BASE_URL` | OpenAI-compatible Ollama endpoint, default `http://localhost:11434/v1` |
| `OLLAMA_MODEL` | Local model name, default `qwen2.5:7b` |
| `SCRAPER_API_KEY` | Optional legacy scraper proxy key |

## Current Project Structure

```text
backend/             FastAPI app, schemas, providers, services
frontend/            React/Vite dashboard
analysis.py          Pure composite-score helper
config.py            Shared weights, env names, sector medians
scorers.py           Scoring engine
tools/               Local Ollama benchmark tooling
utils.py             Rating and normalization helpers
tests/               Backend/domain pytest suite
docs/CURRENT_STATUS.md
```

## Current Code Quality Status

Completed cleanup/migration work:

- Streamlit is no longer the primary app runtime.
- FastAPI exposes typed API endpoints.
- React/Vite provides the dashboard UI.
- Scrapy is introduced for FinViz headline parsing.
- Sentiment provider logic is separated behind Ollama and neutral fallback providers.
- Composite scoring is pure and tested.
- Shared constants live in `config.py`.
- Frontend dependencies pass audit at moderate severity and above.
- Groq and AI-generated competitor paths have been removed.
- Insider activity, Piotroski quality, and derivatives summaries are exposed as first-class API fields and rendered in React.
- `data_loader.py` has been deleted.
- Deterministic `data_quality` is returned by the API and rendered in React.
- Watchlist Mode is available as session-only comparison UI backed by `POST /api/watchlist/analyze`.
- Opportunity Finder V1 is available as a standalone section backed by `GET /api/opportunity/themes` and `GET /api/opportunity/scan`.
- Local Ollama benchmark tooling and a static headline fixture exist in `tools/`.

Remaining cleanup work:

- Backend modules can be further split into domain packages once migration settles.
- Live `AAPL` smoke and browser visual QA should be rerun outside this text-only verification pass.
- `docs/OLLAMA_BENCHMARK.md` is a template until the local model benchmark is run against installed Ollama models.
- Competitor analysis is deferred until a deterministic factual data source exists.

## Reassessment Questions

Use these questions when reviewing the next direction:

1. **Architecture:** Should we keep the current lightweight backend package or perform a deeper domain/application/infrastructure split now?
2. **Data reliability:** Is `yfinance + FinViz scraping` acceptable for the next milestone, or should we introduce paid/official market and news APIs later?
3. **Scraping:** Is the five-minute in-memory TTL cache enough for local use?
4. **AI:** Which local Ollama model gives the best balance of JSON reliability, speed, and sentiment quality?
5. **Product:** Should the next user-facing milestone be deeper watchlist UX, portfolio comparison, or local reports?
6. **Deployment:** Should the next target remain local-only or move toward desktop/self-hosted packaging later?

## Suggested Next Milestones

Recommended order:

1. **Run live local QA**
   - Run FastAPI and React locally.
   - Analyze `AAPL`.
   - Verify Watchlist Mode with several tickers.

2. **Run Ollama benchmark**
   - Pull/install the target local models.
   - Run `.venv\Scripts\python.exe -m tools.ollama_benchmark`.
   - Commit the generated `docs/OLLAMA_BENCHMARK.md` results.

3. **Improve product workflow**
   - Add deeper watchlist sorting/filtering.
   - Add local report export if needed.

4. **Prepare deployment**
   - Add environment examples.
   - Decide local-only vs desktop/self-hosted packaging.

## Local Development

Backend:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Verification:

```bash
.venv\Scripts\python.exe -m pytest -q
cd frontend
npm test
npm run build
npm audit --audit-level=moderate
```

## Known Risks

- Yahoo Finance fields can be missing, delayed, renamed, or inconsistent.
- Public ETF holdings and Nasdaq/source discovery can be unavailable, blocked, incomplete, or structurally changed.
- FinViz can change markup or block scraping.
- Local Ollama quality and latency depend on the installed model and hardware.
- Sentiment quality and latency depend on local Ollama model choice.
- Scores are algorithmic research signals, not investment recommendations.
- Opportunity Finder labels are deterministic research categories, not financial advice or recommendations.

Non-blocking improvement notes are tracked in `docs/IMPROVEMENT_BACKLOG.md`, including article-fetching latency optimization. These should wait until the larger reliability and product milestones are in better shape.

## Handoff Notes for Another AI/Reviewer

Important context:

- The current repo has many uncommitted migration changes.
- `.idea/` is untracked and unrelated.
- `main.py` is no longer the old Streamlit app; it re-exports the FastAPI ASGI app.
- `data_loader.py` has been deleted.
- Competitors are intentionally omitted until a factual data source exists.
- The current goal is live QA and local Ollama benchmarking before choosing the next product milestone.

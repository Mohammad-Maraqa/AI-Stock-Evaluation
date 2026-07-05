# Improvement Backlog

This document captures improvements that are worth doing, but are not the immediate focus while the project is still handling larger architecture, reliability, and product-maturity work.

## Current Focus

The near-term priority is still the bigger project work:

- Preserve FastAPI + React parity with the old Streamlit experience.
- Keep the backend clean, testable, and local-first.
- Finish reliability hardening around provider failures and degraded analysis.
- Improve user-facing product value, especially session-only watchlist mode.
- Keep AI as an interpretation layer only, never a factual data source.

## Future Improvements

### Article Fetching Latency

The current news provider can successfully fetch article text for many FinViz-linked stories, but it fetches article links sequentially. In a live `AVGO` check, the full provider returned 30 headlines, including 25 article-depth items and 5 headline-only items, but the run took about 49.5 seconds.

Functionally this works, but before relying on it heavily we should optimize the article enrichment path. Good options:

- Limit article enrichment to the top 8-12 headlines.
- Fetch article links concurrently with strict per-request timeouts.
- Keep headline-only fallback for links that fail, timeout, block scraping, or produce unreadable text.

The goal is to keep the dashboard fast while still giving Ollama real article context for the most important news items.

Priority: medium, after bigger reliability and product milestones.

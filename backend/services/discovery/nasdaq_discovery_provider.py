import logging
from urllib.parse import urlencode

import requests

from backend.services.discovery.models import DiscoveryCandidate, DiscoveryWarning

logger = logging.getLogger(__name__)


class DiscoveryResult:
    def __init__(self, candidates=None, warnings=None):
        self.candidates = candidates or []
        self.warnings = warnings or []


class NasdaqDiscoveryProvider:
    source = "NASDAQ_DISCOVERY"

    def __init__(self, get=None, timeout_seconds=12):
        self.get = get or requests.get
        self.timeout_seconds = timeout_seconds

    def discover(self, *, theme):
        if not theme:
            return DiscoveryResult([], [])
        candidates = []
        warnings = []
        for keyword in theme.get("nasdaq_industry_keywords", [])[:3]:
            try:
                candidates.extend(self._fetch_keyword(keyword))
            except Exception as exc:
                logger.debug("Nasdaq discovery failed for %s: %s", keyword, exc)
                warnings.append(DiscoveryWarning(self.source, f"Nasdaq discovery unavailable for '{keyword}'."))
        return DiscoveryResult(candidates, warnings)

    def _fetch_keyword(self, keyword):
        query = urlencode({"tableonly": "true", "limit": "25", "exchange": "NASDAQ|NYSE|AMEX", "industry": keyword})
        url = f"https://api.nasdaq.com/api/screener/stocks?{query}"
        response = self.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        data = response.json()
        rows = data.get("data", {}).get("rows", []) or data.get("rows", [])
        candidates = []
        for row in rows:
            ticker = row.get("symbol") or row.get("ticker")
            if not ticker:
                continue
            candidates.append(
                DiscoveryCandidate(
                    ticker=str(ticker),
                    company=str(row.get("name") or row.get("companyName") or ""),
                    sector=str(row.get("sector") or ""),
                    industry=str(row.get("industry") or ""),
                    source=self.source,
                )
            )
        return candidates

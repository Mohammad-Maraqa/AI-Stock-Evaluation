import csv
import io
import logging
import os
import re
import tempfile

import requests
import yfinance as yf

from backend.services.discovery.models import DiscoveryCandidate, DiscoveryWarning

logger = logging.getLogger(__name__)

ISSUER_HOLDINGS_URLS = {
    "SMH": [
        "https://www.vaneck.com/Main/HoldingsBlock/GetDataset/?blockId=144458&pageId=233107&ticker=SMH",
        "https://www.vaneck.com/us/en/investments/semiconductor-etf-smh/holdings/",
    ],
    "SOXX": [
        "https://www.ishares.com/us/products/239705/ishares-phlx-semiconductor-etf/1467271812596.ajax?fileType=csv&fileName=SOXX_holdings&dataType=fund"
    ],
}


class DiscoveryResult:
    def __init__(self, candidates=None, warnings=None):
        self.candidates = candidates or []
        self.warnings = warnings or []


class EtfHoldingsProvider:
    source = "ETF_HOLDINGS"

    def __init__(self, get=None, timeout_seconds=12, ticker_factory=None, cache_setter=None, cache_location=None):
        self.get = get or requests.get
        self.timeout_seconds = timeout_seconds
        self.ticker_factory = ticker_factory or yf.Ticker
        cache_path = cache_location or os.path.join(tempfile.gettempdir(), "ai-stock-evaluation-yfinance")
        try:
            (cache_setter or yf.cache.set_cache_location)(cache_path)
        except Exception as exc:
            logger.debug("Unable to configure yfinance cache at %s: %s", cache_path, exc)

    def discover(self, *, etf, theme):
        etfs = [etf.strip().upper()] if etf else [item.strip().upper() for item in (theme or {}).get("seed_etfs", []) if item.strip()]
        if not etfs:
            return DiscoveryResult([], [DiscoveryWarning(self.source, "No ETF ticker was available for holdings discovery.")])
        candidates = []
        warnings = []
        for etf_ticker in etfs:
            fetched = []
            if etf_ticker in ISSUER_HOLDINGS_URLS:
                try:
                    fetched = self._fetch_known_issuer_holdings(etf_ticker)
                except Exception as exc:
                    logger.debug("Known issuer holdings discovery failed for %s: %s", etf_ticker, exc)
            if not fetched:
                try:
                    fetched = self._fetch_yfinance_holdings(etf_ticker)
                except Exception as exc:
                    logger.debug("yfinance ETF holdings discovery failed for %s: %s", etf_ticker, exc)
            if not fetched:
                try:
                    fetched = self._fetch_yahoo_holdings(etf_ticker)
                except Exception as exc:
                    logger.debug("ETF holdings discovery failed for %s: %s", etf_ticker, exc)
            if not fetched and etf_ticker not in ISSUER_HOLDINGS_URLS:
                try:
                    fetched = self._fetch_known_issuer_holdings(etf_ticker)
                except Exception as exc:
                    logger.debug("Known issuer holdings discovery failed for %s: %s", etf_ticker, exc)
            if not fetched:
                warnings.append(DiscoveryWarning(self.source, f"ETF holdings could not be fetched for {etf_ticker}."))
            candidates.extend(fetched)
        return DiscoveryResult(candidates, warnings)

    def _fetch_yfinance_holdings(self, etf):
        holdings = self.ticker_factory(etf).funds_data.top_holdings
        candidates = []
        if hasattr(holdings, "iterrows"):
            for index, row in holdings.iterrows():
                ticker = row.get("Symbol") or row.get("Ticker") or index
                name = row.get("Name") or row.get("Holding") or ""
                if ticker:
                    candidates.append(DiscoveryCandidate(ticker=str(ticker), company=str(name), source=self.source))
            return candidates
        for item in holdings or []:
            ticker = item.get("symbol") or item.get("ticker")
            if ticker:
                candidates.append(DiscoveryCandidate(ticker=str(ticker), company=str(item.get("name") or ""), source=self.source))
        return candidates

    def _fetch_yahoo_holdings(self, etf):
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{etf}?modules=fundTopHoldings"
        response = self.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        data = response.json()
        holdings = data.get("holdings")
        if holdings is None:
            result = data.get("quoteSummary", {}).get("result", [])
            if result:
                holdings = result[0].get("fundTopHoldings", {}).get("holdings", [])
        candidates = []
        for item in holdings or []:
            ticker = item.get("symbol") or item.get("ticker") or item.get("holdingName")
            if not ticker:
                continue
            candidates.append(
                DiscoveryCandidate(
                    ticker=str(ticker),
                    company=str(item.get("name") or item.get("holdingName") or ""),
                    source=self.source,
                )
            )
        if candidates:
            return candidates
        return self._parse_csv_like_holdings(response.text)

    def _fetch_known_issuer_holdings(self, etf):
        candidates = []
        for url in ISSUER_HOLDINGS_URLS.get(etf, []):
            response = self.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
            try:
                data = response.json()
            except Exception:
                data = None
            if data:
                candidates.extend(self._parse_json_holdings(data))
            if not candidates:
                candidates.extend(self._parse_csv_like_holdings(response.text))
            if not candidates:
                candidates.extend(self._parse_plaintext_holdings(response.text))
            if candidates:
                return candidates
        return candidates

    def _parse_json_holdings(self, data):
        rows = data.get("data") or data.get("holdings") or data.get("rows") or []
        if isinstance(rows, dict):
            rows = rows.get("rows") or rows.get("holdings") or []
        candidates = []
        for row in rows:
            ticker = row.get("Ticker") or row.get("ticker") or row.get("symbol") or row.get("Symbol")
            name = row.get("Holding Name") or row.get("name") or row.get("Name") or row.get("holdingName") or ""
            if ticker and self._is_equity_ticker(str(ticker)):
                candidates.append(DiscoveryCandidate(ticker=str(ticker), company=str(name), source=self.source))
        return candidates

    def _parse_csv_like_holdings(self, text):
        candidates = []
        if not text:
            return candidates
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            ticker = row.get("Ticker") or row.get("Symbol") or row.get("Holding Ticker")
            if ticker and self._is_equity_ticker(ticker):
                candidates.append(DiscoveryCandidate(ticker=ticker, company=row.get("Name", ""), source=self.source))
        return candidates

    def _parse_plaintext_holdings(self, text):
        candidates = []
        if not text:
            return candidates
        clean = re.sub(r"<[^>]+>", " ", text)
        looks_like_holdings_page = "Daily Holdings" in clean or "Total Holdings" in clean or "Holding Name" in clean
        parsing_holdings = not looks_like_holdings_page
        for line in clean.splitlines():
            if looks_like_holdings_page and ("Ticker" in line and "Holding" in line):
                parsing_holdings = True
                continue
            if looks_like_holdings_page and ("Other/Cash" in line or "Portfolio" in line):
                break
            if not parsing_holdings:
                continue
            parts = line.strip().split()
            if not parts:
                continue
            ticker = parts[0]
            if not any(re.match(r"^-?\d+(?:\.\d+)?%?$", part) for part in parts[1:]):
                continue
            if self._is_equity_ticker(ticker):
                name_parts = []
                for part in parts[1:]:
                    if re.match(r"^-?\d+(?:\.\d+)?%?$", part) or re.match(r"^[\d,]+$", part):
                        break
                    name_parts.append(part)
                candidates.append(DiscoveryCandidate(ticker=ticker, company=" ".join(name_parts), source=self.source))
        return candidates

    @staticmethod
    def _is_equity_ticker(ticker):
        clean = ticker.strip().upper()
        blocked = {"CASH", "USD", "DAILY", "TICKER", "TOTAL", "HOLDING", "URL", "AS", "IF", "VANECK"}
        if clean in blocked or "CASH" in clean or clean.startswith("-"):
            return False
        return bool(re.match(r"^[A-Z][A-Z0-9.\-]{0,6}$", clean))

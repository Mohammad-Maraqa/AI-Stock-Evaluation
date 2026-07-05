import logging
import random
import time

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]


def build_session():
    session = requests.Session()
    session.headers.update({"User-Agent": random.choice(USER_AGENTS)})
    return session


def fetch_with_retry(func, retries=3, delay=2, fallback=None, exceptions=(Exception,)):
    for attempt in range(retries):
        try:
            result = func()
            if result is not None:
                return result
        except exceptions as exc:
            logger.debug("Retryable market-data fetch failed on attempt %s/%s: %s", attempt + 1, retries, exc)
        if attempt < retries - 1:
            time.sleep(delay)
    return fallback


def resolve_ticker(user_input, session_factory=build_session):
    clean_input = user_input.strip()
    if len(clean_input) <= 5 and clean_input.isalpha() and clean_input.isupper():
        return clean_input

    search_queries = [clean_input]
    if " " in clean_input:
        search_queries.append(clean_input.replace(" ", ""))
    if " and " in clean_input.lower():
        search_queries.append(clean_input.lower().replace(" and ", " & "))

    us_exchanges = {"NYQ", "NMS", "NGM", "NCM", "ASE", "PCX"}
    for query in search_queries:
        try:
            session = session_factory()
            response = session.get(f"https://query2.finance.yahoo.com/v1/finance/search?q={query}", timeout=6)
            data = response.json()
            for quote in data.get("quotes", []):
                if quote.get("quoteType") == "EQUITY" and quote.get("exchange") in us_exchanges:
                    return quote["symbol"]
        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.debug("Yahoo ticker search failed for query %s: %s", query, exc)
    return clean_input.upper()


class MarketDataProvider:
    name = "yfinance"

    def __init__(self, ticker_factory=None, ticker_resolver=resolve_ticker):
        self.ticker_factory = ticker_factory or yf.Ticker
        self.ticker_resolver = ticker_resolver

    def resolve_ticker(self, query: str) -> str:
        return self.ticker_resolver(query)

    def get_technical_data(self, ticker: str):
        try:
            return self.ticker_factory(ticker).history(period="1y")
        except (RuntimeError, ValueError, KeyError, AttributeError) as exc:
            logger.debug("Unable to fetch price history for %s: %s", ticker, exc)
            return pd.DataFrame()

    def get_fundamental_data(self, ticker: str):
        stock = self.ticker_factory(ticker)
        info = dict(stock.info or {})
        if not info or ("regularMarketPrice" not in info and "currentPrice" not in info):
            return {}

        insider_buys = 0
        insider_sells = 0
        try:
            transactions = stock.insider_transactions
            if transactions is not None and not transactions.empty:
                for _, row in transactions.iterrows():
                    row_text = str(row.values).lower()
                    if "purchase" in row_text or "buy" in row_text:
                        insider_buys += 1
                    elif "sale" in row_text or "sell" in row_text:
                        insider_sells += 1
        except (RuntimeError, ValueError, KeyError, AttributeError) as exc:
            logger.debug("Unable to fetch insider transactions for %s: %s", ticker, exc)

        info["insider_buys"] = insider_buys
        info["insider_sells"] = insider_sells
        info["_financials"] = self._frame_or_none(getattr(stock, "financials", None))
        info["_balance_sheet"] = self._frame_or_none(getattr(stock, "balance_sheet", None))
        info["_cashflow"] = self._frame_or_none(getattr(stock, "cashflow", None))
        return info

    def get_derivative_data(self, ticker: str):
        stock = self.ticker_factory(ticker)
        info = stock.info or {}
        if not info:
            return {"valid": False}

        short_float = info.get("shortPercentFloat")
        if short_float is None:
            shares_short = info.get("sharesShort")
            shares_float = info.get("floatShares")
            if shares_short and shares_float:
                short_float = shares_short / shares_float

        short_ratio = info.get("shortRatio")
        pcr_vol = pcr_oi = avg_iv = None
        try:
            options_dates = stock.options
            if options_dates:
                chain = stock.option_chain(options_dates[0])
                calls_vol = chain.calls["volume"].sum()
                puts_vol = chain.puts["volume"].sum()
                pcr_vol = puts_vol / calls_vol if calls_vol > 0 else None
                calls_oi = chain.calls["openInterest"].sum()
                puts_oi = chain.puts["openInterest"].sum()
                pcr_oi = puts_oi / calls_oi if calls_oi > 0 else None
                call_iv = chain.calls["impliedVolatility"].mean()
                put_iv = chain.puts["impliedVolatility"].mean()
                avg_iv = (call_iv + put_iv) / 2 if pd.notna(call_iv) and pd.notna(put_iv) else None
        except (RuntimeError, ValueError, KeyError, AttributeError) as exc:
            logger.debug("Unable to fetch option-chain data for %s: %s", ticker, exc)

        return {
            "short_float": short_float,
            "short_ratio": short_ratio,
            "pcr_vol": pcr_vol,
            "pcr_oi": pcr_oi,
            "avg_iv": avg_iv,
            "valid": True,
        }

    def is_available(self) -> bool:
        return True

    @staticmethod
    def _frame_or_none(frame):
        return frame if frame is not None and not frame.empty else None

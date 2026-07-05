from pathlib import Path
from unittest.mock import MagicMock

from backend.services.market_data import MarketDataProvider, fetch_with_retry, resolve_ticker


def test_source_files_do_not_import_legacy_data_loader():
    project_root = Path(__file__).resolve().parents[1]
    source_files = [
        *project_root.glob("*.py"),
        *project_root.glob("backend/**/*.py"),
        *project_root.glob("tests/**/*.py"),
    ]

    offenders = []
    for path in source_files:
        if path.name == "test_data_loader.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "data_loader" in text or "DataLoader" in text:
            offenders.append(str(path.relative_to(project_root)))

    assert offenders == []

def test_fetch_with_retry_returns_first_non_none_result():
    attempts = {"count": 0}

    def fetch():
        attempts["count"] += 1
        return "ok" if attempts["count"] == 2 else None

    assert fetch_with_retry(fetch, retries=3, delay=0) == "ok"
    assert attempts["count"] == 2

def test_fetch_with_retry_returns_fallback_after_exceptions():
    def fetch():
        raise RuntimeError("temporary failure")

    assert fetch_with_retry(fetch, retries=2, delay=0, fallback="fallback") == "fallback"

def test_convert_name_to_ticker_returns_uppercase_ticker_without_lookup():
    assert resolve_ticker("AAPL") == "AAPL"

def test_convert_name_to_ticker_resolves_us_equity_from_yahoo_search():
    response = MagicMock()
    response.json.return_value = {
        "quotes": [
            {"quoteType": "ETF", "exchange": "NYQ", "symbol": "SPY"},
            {"quoteType": "EQUITY", "exchange": "NMS", "symbol": "AAPL"},
        ]
    }
    session = MagicMock()
    session.get.return_value = response

    assert resolve_ticker("Apple", session_factory=lambda: session) == "AAPL"


def test_market_data_provider_uses_internal_ticker_resolution():
    provider = MarketDataProvider(ticker_factory=lambda ticker: MagicMock())

    assert provider.resolve_ticker("AAPL") == "AAPL"

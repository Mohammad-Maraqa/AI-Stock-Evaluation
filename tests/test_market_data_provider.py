import pandas as pd

from backend.services.market_data import MarketDataProvider


class FakeTicker:
    info = {"longName": "Apple Inc.", "currentPrice": 200, "sharesShort": 10, "floatShares": 100, "shortRatio": 2}
    financials = pd.DataFrame({"2026": [1]}, index=["Total Revenue"])
    balance_sheet = pd.DataFrame({"2026": [1]}, index=["Total Assets"])
    cashflow = pd.DataFrame({"2026": [1]}, index=["Operating Cash Flow"])
    insider_transactions = pd.DataFrame({"Text": ["Purchase", "Sale"]})
    options = []

    def history(self, period):
        return pd.DataFrame({"Close": [1]})


def test_market_data_provider_fetches_fundamentals_without_legacy_loader():
    provider = MarketDataProvider(ticker_factory=lambda ticker: FakeTicker())

    data = provider.get_fundamental_data("AAPL")

    assert data["longName"] == "Apple Inc."
    assert data["insider_buys"] == 1
    assert data["insider_sells"] == 1
    assert "_financials" in data


def test_market_data_provider_derivatives_falls_back_to_short_float_from_share_counts():
    provider = MarketDataProvider(ticker_factory=lambda ticker: FakeTicker())

    data = provider.get_derivative_data("AAPL")

    assert data["valid"] is True
    assert data["short_float"] == 0.1
    assert data["short_ratio"] == 2


def test_market_data_provider_returns_empty_history_when_yfinance_history_fails():
    class BrokenTicker(FakeTicker):
        def history(self, period):
            raise RuntimeError("history unavailable")

    provider = MarketDataProvider(ticker_factory=lambda ticker: BrokenTicker())

    assert provider.get_technical_data("AAPL").empty


def test_market_data_provider_returns_unavailable_derivatives_when_option_chain_fails():
    class BrokenOptionsTicker(FakeTicker):
        options = ["2026-01-16"]

        def option_chain(self, date):
            raise RuntimeError("options unavailable")

    provider = MarketDataProvider(ticker_factory=lambda ticker: BrokenOptionsTicker())

    data = provider.get_derivative_data("AAPL")

    assert data["valid"] is True
    assert data["pcr_vol"] is None
    assert data["pcr_oi"] is None
    assert data["avg_iv"] is None

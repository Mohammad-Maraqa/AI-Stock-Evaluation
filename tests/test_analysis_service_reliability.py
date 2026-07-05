import pandas as pd

from backend.services.analysis_service import AnalysisService
from backend.services.news.models import Headline
from backend.services.sentiment.base import SentimentProviderError
from backend.services.sentiment.models import SentimentItem, SentimentResult


def price_history(rows=80):
    index = pd.date_range("2026-01-01", periods=rows, freq="D")
    close = [100 + i for i in range(rows)]
    return pd.DataFrame(
        {
            "Open": close,
            "High": [value + 1 for value in close],
            "Low": [value - 1 for value in close],
            "Close": close,
        },
        index=index,
    )


class FakeMarketProvider:
    name = "fake_market"

    def __init__(self, fundamentals=None, derivatives=None, technical=None, fail_fundamentals=False, fail_derivatives=False):
        self.fundamentals = fundamentals if fundamentals is not None else {
            "longName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "currentPrice": 200,
            "trailingPE": 25,
            "returnOnEquity": 0.2,
            "profitMargins": 0.25,
            "revenueGrowth": 0.08,
            "insider_buys": 1,
            "insider_sells": 0,
        }
        self.derivatives = derivatives if derivatives is not None else {
            "valid": True,
            "short_float": 0.03,
            "short_ratio": 2,
            "pcr_vol": 0.8,
            "pcr_oi": 0.9,
            "avg_iv": 0.25,
        }
        self.technical = technical if technical is not None else price_history()
        self.fail_fundamentals = fail_fundamentals
        self.fail_derivatives = fail_derivatives

    def resolve_ticker(self, query):
        return query.upper()

    def get_technical_data(self, ticker):
        return self.technical

    def get_fundamental_data(self, ticker):
        if self.fail_fundamentals:
            raise RuntimeError("fundamentals unavailable")
        return self.fundamentals

    def get_derivative_data(self, ticker):
        if self.fail_derivatives:
            raise RuntimeError("options unavailable")
        return self.derivatives


class FakeNewsProvider:
    name = "fake_news"

    def __init__(self, headlines=None, fail=False):
        self.headlines = headlines if headlines is not None else [
            Headline(
                ticker="AAPL",
                title="Apple expands services",
                link="https://example.com",
                source="Example",
                published_at="Today",
                article_text="Apple expands services with stronger recurring revenue.",
                analysis_depth="article",
            )
        ]
        self.fail = fail

    def get_headlines(self, ticker):
        if self.fail:
            raise RuntimeError("finviz unavailable")
        return self.headlines


class FakeSentimentProvider:
    name = "fake_sentiment"

    def __init__(self, fail=False):
        self.fail = fail

    def analyze(self, request):
        if self.fail:
            raise SentimentProviderError("ollama unavailable")
        return SentimentResult(provider="fake_sentiment", items=[SentimentItem(sentiment="Bullish", score=8) for _ in request.items])


def analyze_with(market=None, news=None, sentiment=None):
    service = AnalysisService(
        market_provider=market or FakeMarketProvider(),
        news_provider=news or FakeNewsProvider(),
        sentiment_provider=sentiment or FakeSentimentProvider(),
    )
    return service.analyze("AAPL")


def test_analysis_returns_degraded_response_when_fundamentals_provider_fails():
    result = analyze_with(market=FakeMarketProvider(fail_fundamentals=True))

    assert result is not None
    assert result.ticker == "AAPL"
    assert result.pillars["fundamental"].score == 0
    assert result.company.name == "AAPL"
    assert result.data_quality.fundamentals == "unavailable"
    assert result.data_quality.confidence < 80
    assert "Fundamental data unavailable." in result.data_quality.warnings


def test_analysis_returns_degraded_response_when_derivatives_provider_fails():
    result = analyze_with(market=FakeMarketProvider(fail_derivatives=True))

    assert result is not None
    assert result.pillars["derivative"].score == 0
    assert result.derivatives.risk_label == "Unavailable"
    assert result.data_quality.derivatives == "unavailable"


def test_analysis_handles_empty_or_unavailable_news_without_crashing():
    empty_result = analyze_with(news=FakeNewsProvider(headlines=[]))
    failed_result = analyze_with(news=FakeNewsProvider(fail=True))

    assert empty_result is not None
    assert empty_result.headlines == []
    assert empty_result.data_quality.news == "empty"
    assert failed_result is not None
    assert failed_result.headlines == []
    assert failed_result.data_quality.news == "unavailable"


def test_analysis_uses_neutral_sentiment_when_ollama_fails():
    result = analyze_with(sentiment=FakeSentimentProvider(fail=True))

    assert result is not None
    assert result.providers["sentiment"] == "none"
    assert result.pillars["sentiment"].meta["counts"]["neut"] == 1
    assert result.data_quality.sentiment == "fallback"
    assert "Sentiment used neutral fallback." in result.data_quality.warnings


def test_analysis_returns_none_when_price_history_is_missing():
    result = analyze_with(market=FakeMarketProvider(technical=pd.DataFrame()))

    assert result is None


def test_analysis_reports_high_data_quality_when_inputs_are_complete():
    result = analyze_with()

    assert result.data_quality.market_data == "ok"
    assert result.data_quality.news == "ok"
    assert result.data_quality.sentiment == "ok"
    assert result.data_quality.fundamentals in {"ok", "partial"}
    assert result.data_quality.derivatives == "ok"
    assert result.data_quality.confidence >= 85


def test_analysis_exposes_article_depth_on_enriched_headlines():
    result = analyze_with()

    assert result.headlines[0].article_text == "Apple expands services with stronger recurring revenue."
    assert result.headlines[0].analysis_depth == "article"
    assert result.pillars["sentiment"].meta["analysis_depth_counts"] == {"article": 1, "headline": 0}


def test_analysis_response_includes_fundamental_deep_analysis_without_changing_composite():
    result = analyze_with()

    assert result.fundamental_analysis.overall_score >= 0
    assert result.fundamental_analysis.bullishness + result.fundamental_analysis.bearishness == 100
    assert len(result.fundamental_analysis.categories) == 7
    assert result.composite.base_score == result.composite.base_score

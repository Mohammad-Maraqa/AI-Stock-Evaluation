import time

import pandas as pd
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.dependencies import get_opportunity_finder_service
from backend.schemas import (
    CompanyInfo,
    CompositeResponse,
    DataQualityResponse,
    FundamentalAnalysisResponse,
    OpportunityScanMetadata,
    OpportunityScanResponse,
    PillarResponse,
)
from backend.services.discovery.etf_holdings_provider import EtfHoldingsProvider
from backend.services.discovery.models import DiscoveryCandidate, DiscoveryWarning
from backend.services.discovery.nasdaq_discovery_provider import NasdaqDiscoveryProvider
from backend.services.discovery.theme_config import get_theme, list_themes
from backend.services.discovery.universe_discovery import merge_candidates
from backend.services.opportunity_finder_service import OpportunityFinderService
from backend.services.opportunity_scoring import (
    assign_opportunity_label,
    calculate_discovery_confidence,
    calculate_opportunity_score,
)


class FakeResponse:
    def __init__(self, payload=None, text="", status_code=200):
        self._payload = payload or {}
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("bad response")

    def json(self):
        return self._payload


class FakeMarketProvider:
    def __init__(self):
        self.fundamentals = {
            "AAA": {
                "symbol": "AAA",
                "longName": "Alpha AI Servers",
                "currentPrice": 42,
                "marketCap": 2_000_000_000,
                "averageVolume": 500_000,
                "sector": "Technology",
                "industry": "Computer Hardware",
                "longBusinessSummary": "Builds AI servers and data center networking systems.",
                "trailingPE": 20,
                "forwardPE": 18,
                "priceToSalesTrailing12Months": 4,
                "debtToEquity": 30,
                "freeCashflow": 100_000_000,
                "operatingCashflow": 140_000_000,
                "profitMargins": 0.18,
                "returnOnEquity": 0.16,
            },
            "BBB": {
                "symbol": "BBB",
                "longName": "Beta Industrial",
                "currentPrice": 32,
                "marketCap": 1_200_000_000,
                "averageVolume": 300_000,
                "sector": "Technology",
                "industry": "Computer Hardware",
                "longBusinessSummary": "Makes data center automation tools.",
                "trailingPE": 16,
            },
            "PENNY": {
                "symbol": "PENNY",
                "longName": "Tiny Corp",
                "currentPrice": 2,
                "marketCap": 100_000_000,
                "averageVolume": 10_000,
            },
        }

    def get_fundamental_data(self, ticker):
        return self.fundamentals.get(ticker, {})

    def get_technical_data(self, ticker):
        if ticker not in self.fundamentals:
            return pd.DataFrame()
        return pd.DataFrame({"Close": [20, 21, 22], "Volume": [100_000, 110_000, 120_000]})


class FakeAnalysisService:
    def __init__(self):
        self.calls = []

    def analyze(self, ticker):
        self.calls.append(ticker)
        if ticker == "FAIL":
            raise RuntimeError("analysis failed")
        fund_score = 88 if ticker == "AAA" else 45
        return {
            "ticker": ticker,
            "company": CompanyInfo(name=f"{ticker} Corp", sector="Technology", industry="Computer Hardware"),
            "composite": CompositeResponse(base_score=70, final_score=72, rating="Research Candidate"),
            "pillars": {
                "fundamental": PillarResponse(score=fund_score, meta={"trailingPE": 20}),
                "sentiment": PillarResponse(score=65, meta={"counts": {"bull": 2, "bear": 0, "neut": 1}}),
                "technical": PillarResponse(score=70, meta={"Trend": True, "RSI": 55}),
                "derivative": PillarResponse(score=50, meta={}),
            },
            "headlines": [],
            "chart": {"candles": [{"close": 20}, {"close": 22}], "overlays": {}},
            "providers": {"market_data": "fake"},
            "data_quality": DataQualityResponse(confidence=90),
            "fundamental_analysis": FundamentalAnalysisResponse(overall_score=fund_score),
        }


class SlowMarketProvider(FakeMarketProvider):
    def get_fundamental_data(self, ticker):
        if ticker == "SLOW":
            time.sleep(0.05)
        return super().get_fundamental_data(ticker)


class SlowAnalysisService(FakeAnalysisService):
    def analyze(self, ticker):
        if ticker == "SLOW":
            time.sleep(0.05)
        return super().analyze(ticker)


def test_themes_are_keyword_only_and_include_v1_set():
    themes = list_themes()

    assert len(themes) >= 10
    assert any(theme["id"] == "ai_infrastructure" for theme in themes)
    assert "tickers" not in get_theme("ai_infrastructure")
    assert get_theme("semiconductors")["seed_etfs"] == ["SMH", "SOXX"]


def test_etf_holdings_provider_parses_mocked_public_payload():
    payload = {"holdings": [{"symbol": "AAA", "name": "Alpha AI Servers"}, {"ticker": "BBB", "name": "Beta"}]}
    provider = EtfHoldingsProvider(get=lambda url, timeout: FakeResponse(payload=payload))

    result = provider.discover(etf="TEST", theme=None)

    assert [candidate.ticker for candidate in result.candidates] == ["AAA", "BBB"]
    assert result.warnings == []


def test_etf_holdings_provider_prefers_mocked_yfinance_top_holdings():
    class FakeFundsData:
        top_holdings = pd.DataFrame(
            {"Name": ["Alpha AI Servers", "Beta Chips"]},
            index=["AAA", "BBB"],
        )

    class FakeTicker:
        funds_data = FakeFundsData()

    provider = EtfHoldingsProvider(ticker_factory=lambda ticker: FakeTicker())

    result = provider.discover(etf="SMH", theme=None)

    assert [candidate.ticker for candidate in result.candidates] == ["AAA", "BBB"]
    assert result.warnings == []


def test_etf_holdings_provider_configures_writable_yfinance_cache():
    calls = []

    EtfHoldingsProvider(cache_setter=lambda path: calls.append(path), cache_location="D:/tmp/yf-cache")

    assert calls == ["D:/tmp/yf-cache"]


def test_etf_holdings_provider_returns_warning_on_failure():
    def broken_get(url, timeout):
        raise RuntimeError("blocked")

    provider = EtfHoldingsProvider(get=broken_get)

    result = provider.discover(etf="TEST", theme=None)

    assert result.candidates == []
    assert result.warnings[0].source == "ETF_HOLDINGS"


def test_etf_holdings_provider_uses_theme_seed_etfs_when_no_manual_etf():
    def fake_get(url, timeout):
        if "SMH" in url:
            return FakeResponse(payload={"holdings": [{"symbol": "AAA", "name": "Alpha"}]})
        return FakeResponse(payload={"holdings": [{"symbol": "BBB", "name": "Beta"}]})

    provider = EtfHoldingsProvider(get=fake_get, ticker_factory=lambda ticker: (_ for _ in ()).throw(RuntimeError("no yf")))

    result = provider.discover(etf=None, theme=get_theme("semiconductors"))

    assert [candidate.ticker for candidate in result.candidates] == ["AAA", "BBB"]
    assert result.warnings == []


def test_etf_holdings_provider_parses_known_issuer_html_fallback_for_smh():
    html = """
    Daily Holdings (%) as of 06/17/2026
    Ticker Holding Name % of Net Assets Market Value (US$)
    NVDA Nvidia Corp 14.17 11,327,466,932
    TSM Taiwan Semiconductor Manufacturing Co L 9.30 7,433,702,987
    AMD Advanced Micro Devices Inc 7.25 5,796,632,581
    -USD CASH- -- 0.02 16,013,970
    """
    provider = EtfHoldingsProvider(
        get=lambda url, timeout: FakeResponse(text=html),
        ticker_factory=lambda ticker: (_ for _ in ()).throw(RuntimeError("no yf")),
    )

    result = provider.discover(etf="SMH", theme=None)

    assert [candidate.ticker for candidate in result.candidates] == ["NVDA", "TSM", "AMD"]


def test_etf_holdings_provider_uses_known_issuer_before_yfinance_for_mapped_etfs():
    html = "NVDA Nvidia Corp 14.17"
    yfinance_calls = []
    provider = EtfHoldingsProvider(
        get=lambda url, timeout: FakeResponse(text=html),
        ticker_factory=lambda ticker: yfinance_calls.append(ticker),
    )

    result = provider.discover(etf="SMH", theme=None)

    assert [candidate.ticker for candidate in result.candidates] == ["NVDA"]
    assert yfinance_calls == []


def test_etf_holdings_provider_ignores_non_holdings_issuer_text_before_next_url():
    responses = [
        FakeResponse(text="URL as VanEck 2026 if not a holdings table"),
        FakeResponse(text="Daily Holdings (%)\nTicker Holding Name % of Net Assets\nNVDA Nvidia Corp 14.17\n"),
    ]

    provider = EtfHoldingsProvider(
        get=lambda url, timeout: responses.pop(0),
        ticker_factory=lambda ticker: None,
    )

    result = provider.discover(etf="SMH", theme=None)

    assert [candidate.ticker for candidate in result.candidates] == ["NVDA"]


def test_nasdaq_provider_is_best_effort_and_mockable():
    provider = NasdaqDiscoveryProvider(get=lambda url, timeout: FakeResponse(payload={"data": {"rows": [{"symbol": "AAA", "name": "Alpha", "industry": "Computer Hardware"}]}}))

    result = provider.discover(theme=get_theme("ai_infrastructure"))

    assert result.candidates[0].ticker == "AAA"
    assert result.candidates[0].source == "NASDAQ_DISCOVERY"


def test_merge_candidates_deduplicates_and_counts_sources():
    merged = merge_candidates([
        DiscoveryCandidate(ticker="AAA", company="Alpha", source="ETF_HOLDINGS"),
        DiscoveryCandidate(ticker="aaa", company="", source="NASDAQ_DISCOVERY"),
    ])

    assert len(merged) == 1
    assert merged[0].ticker == "AAA"
    assert merged[0].source_consensus == 2
    assert merged[0].sources == ["ETF_HOLDINGS", "NASDAQ_DISCOVERY"]


def test_opportunity_scoring_assigns_labels_and_risks_from_facts():
    analysis = FakeAnalysisService().analyze("AAA")
    score = calculate_opportunity_score(analysis, FakeMarketProvider().get_fundamental_data("AAA"), theme_relevance_score=88)

    assert score.opportunity_score >= 70
    assert score.label == "Underrated Candidate"
    assert "Strong profitability quality." in score.reasons


def test_weak_theme_evidence_label_is_separate_from_insufficient_data():
    assert assign_opportunity_label(fundamental=80, valuation=70, underhype=70, data_quality=90, theme_relevance=35) == "Weak Theme Evidence"
    assert assign_opportunity_label(fundamental=80, valuation=70, underhype=70, data_quality=35, theme_relevance=80) == "Insufficient Data"


def test_discovery_confidence_uses_relevance_consensus_and_source_quality():
    assert calculate_discovery_confidence(85, ["ETF_HOLDINGS", "NASDAQ_DISCOVERY"], 2) == "high"
    assert calculate_discovery_confidence(62, ["ETF_HOLDINGS"], 1) == "medium"
    assert calculate_discovery_confidence(40, ["NASDAQ_DISCOVERY"], 1) == "low"


def test_opportunity_service_validates_ranks_then_analyzes_only_top_candidates():
    analysis = FakeAnalysisService()
    service = OpportunityFinderService(
        market_provider=FakeMarketProvider(),
        analysis_service=analysis,
        etf_provider=lambda theme, etf: (
            [
                DiscoveryCandidate(ticker="AAA", company="Alpha", source="ETF_HOLDINGS"),
                DiscoveryCandidate(ticker="BBB", company="Beta", source="ETF_HOLDINGS"),
                DiscoveryCandidate(ticker="PENNY", company="Tiny", source="ETF_HOLDINGS"),
            ],
            [],
        ),
        nasdaq_provider=lambda theme: ([DiscoveryCandidate(ticker="AAA", company="Alpha", source="NASDAQ_DISCOVERY")], []),
    )

    response = service.scan(theme_id="ai_infrastructure", etf=None, limit=1, max_candidates=1)

    assert response.scan_metadata.discovered_count == 4
    assert response.scan_metadata.validated_count == 2
    assert response.scan_metadata.filtered_count == 1
    assert response.scan_metadata.analyzed_count == 1
    assert response.scan_metadata.returned_count == 1
    assert analysis.calls == ["AAA"]
    assert response.results[0].discovery_confidence == "high"


def test_opportunity_service_returns_partial_results_when_secondary_source_fails():
    service = OpportunityFinderService(
        market_provider=FakeMarketProvider(),
        analysis_service=FakeAnalysisService(),
        etf_provider=lambda theme, etf: ([DiscoveryCandidate(ticker="AAA", company="Alpha", source="ETF_HOLDINGS")], []),
        nasdaq_provider=lambda theme: ([], [DiscoveryWarning(source="NASDAQ_DISCOVERY", message="Nasdaq unavailable.")]),
    )

    response = service.scan(theme_id="ai_infrastructure", etf=None, limit=10, max_candidates=10)

    assert response.results
    assert response.source_warnings[0].source == "NASDAQ_DISCOVERY"


def test_opportunity_service_records_timeout_warning_for_slow_scan():
    def slow_provider(theme, etf):
        time.sleep(0.02)
        return [DiscoveryCandidate(ticker="AAA", company="Alpha", source="ETF_HOLDINGS")], []

    service = OpportunityFinderService(
        market_provider=FakeMarketProvider(),
        analysis_service=FakeAnalysisService(),
        etf_provider=slow_provider,
        nasdaq_provider=lambda theme: ([], []),
        provider_timeout_seconds=0.001,
    )

    response = service.scan(theme_id="ai_infrastructure", etf=None, limit=10, max_candidates=10)

    assert any("timed out" in warning.message.lower() for warning in response.source_warnings)


def test_opportunity_service_skips_validation_that_exceeds_timeout():
    market = SlowMarketProvider()
    market.fundamentals["SLOW"] = dict(market.fundamentals["AAA"])
    service = OpportunityFinderService(
        market_provider=market,
        analysis_service=FakeAnalysisService(),
        etf_provider=lambda theme, etf: (
            [
                DiscoveryCandidate(ticker="SLOW", company="Slow", source="ETF_HOLDINGS"),
                DiscoveryCandidate(ticker="AAA", company="Alpha", source="ETF_HOLDINGS"),
            ],
            [],
        ),
        nasdaq_provider=lambda theme: ([], []),
        validation_timeout_seconds=0.001,
    )

    response = service.scan(theme_id="ai_infrastructure", etf=None, limit=10, max_candidates=10)

    assert [result.ticker for result in response.results] == ["AAA"]
    assert any("Validation timed out for SLOW" == warning.message for warning in response.source_warnings)


def test_opportunity_service_skips_analysis_that_exceeds_timeout():
    analysis = SlowAnalysisService()
    market = FakeMarketProvider()
    market.fundamentals["SLOW"] = dict(market.fundamentals["AAA"])
    service = OpportunityFinderService(
        market_provider=market,
        analysis_service=analysis,
        etf_provider=lambda theme, etf: (
            [
                DiscoveryCandidate(ticker="SLOW", company="Slow", source="ETF_HOLDINGS"),
                DiscoveryCandidate(ticker="AAA", company="Alpha", source="ETF_HOLDINGS"),
            ],
            [],
        ),
        nasdaq_provider=lambda theme: ([], []),
        analysis_timeout_seconds=0.001,
        max_analysis_timeouts=3,
    )

    response = service.scan(theme_id="ai_infrastructure", etf=None, limit=10, max_candidates=10)

    assert [result.ticker for result in response.results] == ["AAA", "SLOW"]
    assert response.results[1].label == "Insufficient Data"
    assert any("Analysis timed out for SLOW" == warning.message for warning in response.source_warnings)


def test_opportunity_service_returns_validation_only_fallback_when_all_analysis_times_out():
    class AlwaysSlowAnalysis(FakeAnalysisService):
        def analyze(self, ticker):
            time.sleep(0.05)
            return super().analyze(ticker)

    service = OpportunityFinderService(
        market_provider=FakeMarketProvider(),
        analysis_service=AlwaysSlowAnalysis(),
        etf_provider=lambda theme, etf: ([DiscoveryCandidate(ticker="AAA", company="Alpha", source="ETF_HOLDINGS")], []),
        nasdaq_provider=lambda theme: ([], []),
        analysis_timeout_seconds=0.001,
    )

    response = service.scan(theme_id="ai_infrastructure", etf=None, limit=10, max_candidates=10)

    assert response.results[0].ticker == "AAA"
    assert response.results[0].label == "Insufficient Data"
    assert "Full analysis timed out; this is a validation-only candidate." in response.results[0].risks


def test_opportunity_service_stops_full_analysis_after_timeout_budget_is_exhausted():
    class AlwaysSlowAnalysis(FakeAnalysisService):
        def analyze(self, ticker):
            time.sleep(0.05)
            return super().analyze(ticker)

    market = FakeMarketProvider()
    for ticker in ["BBB", "CCC"]:
        market.fundamentals[ticker] = dict(market.fundamentals["AAA"])
    service = OpportunityFinderService(
        market_provider=market,
        analysis_service=AlwaysSlowAnalysis(),
        etf_provider=lambda theme, etf: (
            [
                DiscoveryCandidate(ticker="AAA", company="Alpha", source="ETF_HOLDINGS"),
                DiscoveryCandidate(ticker="BBB", company="Beta", source="ETF_HOLDINGS"),
                DiscoveryCandidate(ticker="CCC", company="Gamma", source="ETF_HOLDINGS"),
            ],
            [],
        ),
        nasdaq_provider=lambda theme: ([], []),
        analysis_timeout_seconds=0.001,
        max_analysis_timeouts=1,
    )

    response = service.scan(theme_id="ai_infrastructure", etf=None, limit=3, max_candidates=3)

    assert [result.ticker for result in response.results] == ["AAA", "BBB", "CCC"]
    assert all(result.label == "Insufficient Data" for result in response.results)
    assert len([warning for warning in response.source_warnings if "Analysis timed out" in warning.message]) == 1


def test_opportunity_service_validates_only_bounded_ranked_prefix():
    market = FakeMarketProvider()
    for ticker in ["CCC", "DDD"]:
        market.fundamentals[ticker] = dict(market.fundamentals["AAA"])
    service = OpportunityFinderService(
        market_provider=market,
        analysis_service=FakeAnalysisService(),
        etf_provider=lambda theme, etf: (
            [
                DiscoveryCandidate(ticker="AAA", company="Alpha", source="ETF_HOLDINGS"),
                DiscoveryCandidate(ticker="BBB", company="Beta", source="ETF_HOLDINGS"),
                DiscoveryCandidate(ticker="CCC", company="Gamma", source="ETF_HOLDINGS"),
                DiscoveryCandidate(ticker="DDD", company="Delta", source="ETF_HOLDINGS"),
            ],
            [],
        ),
        nasdaq_provider=lambda theme: ([], []),
        validation_candidate_multiplier=2,
    )

    response = service.scan(theme_id="ai_infrastructure", etf=None, limit=1, max_candidates=1)

    assert response.scan_metadata.discovered_count == 4
    assert response.scan_metadata.validated_count == 2


class FakeOpportunityService:
    def list_themes(self):
        return [{"id": "ai_infrastructure", "name": "AI Infrastructure", "description": "AI compute."}]

    def scan(self, theme_id, etf, limit, max_candidates):
        return OpportunityScanResponse(
            mode="theme",
            theme={"id": theme_id, "name": "AI Infrastructure"},
            source_warnings=[],
            candidate_count=1,
            analyzed_count=1,
            scan_metadata=OpportunityScanMetadata(
                discovered_count=1,
                validated_count=1,
                filtered_count=0,
                analyzed_count=1,
                returned_count=1,
                duration_ms=5,
            ),
            results=[],
        )


def test_opportunity_api_themes_and_scan_use_injected_service():
    app = create_app()
    app.dependency_overrides[get_opportunity_finder_service] = lambda: FakeOpportunityService()
    client = TestClient(app)

    themes = client.get("/api/opportunity/themes")
    scan = client.get("/api/opportunity/scan", params={"theme": "ai_infrastructure", "limit": 99, "max_candidates": 99})

    assert themes.status_code == 200
    assert themes.json()["themes"][0]["id"] == "ai_infrastructure"
    assert scan.status_code == 200
    assert scan.json()["scan_metadata"]["duration_ms"] == 5


def test_opportunity_api_requires_theme_or_etf_and_rejects_invalid_theme():
    client = TestClient(create_app())

    missing = client.get("/api/opportunity/scan")
    invalid = client.get("/api/opportunity/scan", params={"theme": "not_real"})

    assert missing.status_code == 400
    assert invalid.status_code == 400

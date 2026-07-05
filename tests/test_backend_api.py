import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.dependencies import get_analysis_service, get_provider_status_service
from backend.schemas import (
    AnalysisResponse,
    CompanyInfo,
    CompositeResponse,
    DerivativesSummary,
    DataQualityResponse,
    InsiderActivity,
    PillarResponse,
    PiotroskiSummary,
    ProviderStatus,
    ProvidersResponse,
    WatchlistAnalyzeResponse,
)
from backend.services.analysis_service import to_jsonable


class FakeAnalysisService:
    def analyze(self, query):
        if query == "BAD":
            return None
        return AnalysisResponse(
            ticker="AAPL",
            company=CompanyInfo(name="Apple Inc.", sector="Technology", industry="Consumer Electronics"),
            composite=CompositeResponse(base_score=70.0, final_score=72.0, rating="Bullish Bias", insider_booster=2.0),
            pillars={
                "fundamental": PillarResponse(score=75, meta={"PE": 28}),
                "sentiment": PillarResponse(score=60, meta={"summary": "Mixed"}),
                "technical": PillarResponse(score=70, meta={"Trend": True}),
                "derivative": PillarResponse(score=50, meta={}),
            },
            headlines=[],
            chart={"candles": [], "overlays": {}},
            providers={"news": "fake_news", "sentiment": "fake_ai", "market_data": "fake_market"},
            insider_activity=InsiderActivity(buys=3, sells=1, net=2, booster=2.0, summary="Net insider buying"),
            piotroski=PiotroskiSummary(raw_score=4, max_score=6, score=66.7, signals={"ROA Positive": 1}),
            derivatives=DerivativesSummary(avg_iv=22.0, short_float=4.2, short_ratio=1.4, pcr_vol=0.8, pcr_oi=0.9, technical_trend=True),
            competitors=[],
            data_quality=DataQualityResponse(
                market_data="ok",
                news="ok",
                sentiment="ok",
                fundamentals="ok",
                derivatives="ok",
                insider_activity="ok",
                confidence=96,
                warnings=[],
            ),
        )


class FakeProviderStatusService:
    def get_status(self):
        return ProvidersResponse(
            ollama=ProviderStatus(available=True, detail="reachable"),
            news=ProviderStatus(available=True, detail="scrapy ready"),
            market_data=ProviderStatus(available=True, detail="yfinance ready"),
        )


def test_health_endpoint():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_providers_status_endpoint_uses_injected_service():
    app = create_app()
    app.dependency_overrides[get_provider_status_service] = lambda: FakeProviderStatusService()
    client = TestClient(app)

    response = client.get("/api/providers/status")

    assert response.status_code == 200
    assert response.json()["ollama"]["available"] is True
    assert "groq" not in response.json()


def test_analyze_endpoint_returns_typed_analysis_response():
    app = create_app()
    app.dependency_overrides[get_analysis_service] = lambda: FakeAnalysisService()
    client = TestClient(app)

    response = client.get("/api/analyze", params={"ticker": "AAPL"})

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert body["company"]["name"] == "Apple Inc."
    assert body["composite"]["rating"] == "Bullish Bias"
    assert body["providers"]["sentiment"] == "fake_ai"
    assert body["insider_activity"]["net"] == 2
    assert body["piotroski"]["signals"] == {"ROA Positive": 1}
    assert body["derivatives"]["avg_iv"] == 22.0
    assert body["competitors"] == []
    assert body["data_quality"]["confidence"] == 96
    assert "fundamental_analysis" in body
    assert body["fundamental_analysis"]["categories"] == []


def test_analyze_endpoint_returns_404_for_unknown_ticker():
    app = create_app()
    app.dependency_overrides[get_analysis_service] = lambda: FakeAnalysisService()
    client = TestClient(app)

    response = client.get("/api/analyze", params={"ticker": "BAD"})

    assert response.status_code == 404
    assert "Could not find data" in response.json()["detail"]


def test_watchlist_analyze_endpoint_returns_items_and_per_ticker_errors():
    app = create_app()
    app.dependency_overrides[get_analysis_service] = lambda: FakeAnalysisService()
    client = TestClient(app)

    response = client.post("/api/watchlist/analyze", json={"tickers": ["AAPL", "BAD"]})

    assert response.status_code == 200
    body = response.json()
    assert [item["ticker"] for item in body["items"]] == ["AAPL"]
    assert body["errors"] == [{"ticker": "BAD", "detail": "Could not find data for 'BAD'."}]


def test_to_jsonable_converts_numpy_scalars_and_nested_values():
    value = {"trend": np.bool_(True), "score": np.float64(12.5), "items": [np.int64(3)]}

    assert to_jsonable(value) == {"trend": True, "score": 12.5, "items": [3]}

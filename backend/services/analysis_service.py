from concurrent.futures import ThreadPoolExecutor
import logging
from dataclasses import dataclass

import pandas as pd

from backend.schemas import (
    AnalysisResponse,
    ChartResponse,
    CompanyInfo,
    CompositeResponse,
    DerivativesSummary,
    DataQualityResponse,
    HeadlineResponse,
    InsiderActivity,
    PillarResponse,
    PiotroskiSummary,
)
from backend.services.market_data import MarketDataProvider
from backend.services.fundamental_analysis_service import FundamentalAnalysisService
from backend.services.news.provider import ScrapyNewsProvider
from backend.services.sentiment.base import SentimentProviderError
from backend.services.sentiment.batching import BatchingSentimentProvider
from backend.services.sentiment.composite import CompositeSentimentProvider
from backend.services.sentiment.models import SentimentInput, SentimentRequest
from backend.services.sentiment.ollama_provider import OllamaSentimentProvider
from analysis import compute_composite_score
from scorers import ScoringEngine
from utils import get_rating
import os
import numpy as np
import config  # noqa: F401 - loads project-local .env at service startup

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderOutcome:
    value: object
    failed: bool = False


def _line_data(df, column):
    return [
        {"time": int(index.timestamp()), "value": round(float(value), 4)}
        for index, value in df[column].items()
        if pd.notna(value)
    ]


def build_chart_payload(df):
    chart_df = df.copy()
    chart_df["sma_50"] = chart_df["Close"].rolling(50).mean()
    chart_df["sma_200"] = chart_df["Close"].rolling(min(200, len(chart_df))).mean()
    close = chart_df["Close"]
    rolling = close.rolling(20)
    middle = rolling.mean()
    std = rolling.std()
    chart_df["bb_high"] = middle + 2 * std
    chart_df["bb_low"] = middle - 2 * std
    candles = [
        {
            "time": int(row.Index.timestamp()),
            "open": round(float(row.Open), 4),
            "high": round(float(row.High), 4),
            "low": round(float(row.Low), 4),
            "close": round(float(row.Close), 4),
        }
        for row in chart_df.itertuples()
        if pd.notna(row.Open) and pd.notna(row.High) and pd.notna(row.Low) and pd.notna(row.Close)
    ]
    return ChartResponse(
        candles=candles,
        overlays={
            "sma50": _line_data(chart_df, "sma_50"),
            "sma200": _line_data(chart_df, "sma_200"),
            "bbHigh": _line_data(chart_df, "bb_high"),
            "bbLow": _line_data(chart_df, "bb_low"),
        },
    )


def to_jsonable(value):
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, pd.DataFrame):
        return {}
    if isinstance(value, pd.Series):
        return {}
    return value


class NeutralSentimentProvider:
    name = "none"

    def analyze(self, request):
        from backend.services.sentiment.models import SentimentItem, SentimentResult

        return SentimentResult(provider=self.name, items=[SentimentItem(sentiment="Neutral", score=0) for _ in request.items])

    def is_available(self):
        return True


def build_insider_activity(meta_fund):
    buys = int(meta_fund.get("insider_buys") or 0)
    sells = int(meta_fund.get("insider_sells") or 0)
    net = buys - sells
    booster = float(meta_fund.get("insider_booster") or 0)
    if buys == 0 and sells == 0:
        summary = "No insider transactions detected"
    elif net > 0:
        summary = "Net insider buying"
    elif net < 0:
        summary = "Net insider selling"
    else:
        summary = "Balanced insider activity"
    return InsiderActivity(buys=buys, sells=sells, net=net, booster=booster, summary=summary)


def build_piotroski_summary(meta_fund):
    raw_score = int(meta_fund.get("piotroski_raw") or 0)
    max_score = int(meta_fund.get("piotroski_max") or 0)
    score = (raw_score / max_score) * 100 if max_score else None
    return PiotroskiSummary(
        raw_score=raw_score,
        max_score=max_score,
        score=round(score, 1) if score is not None else None,
        signals=to_jsonable(meta_fund.get("piotroski_signals") or {}),
    )


def build_derivatives_summary(meta_deriv, technical_trend):
    avg_iv = meta_deriv.get("avg_iv")
    short_float = meta_deriv.get("short_float")
    if avg_iv is None and short_float is None and meta_deriv.get("pcr_vol") is None and meta_deriv.get("pcr_oi") is None:
        risk_label = "Unavailable"
    elif (avg_iv is not None and avg_iv > 70) or (short_float is not None and short_float > 15):
        risk_label = "Elevated"
    elif technical_trend:
        risk_label = "Trend-supported"
    else:
        risk_label = "Mixed"
    return DerivativesSummary(
        pcr_vol=to_jsonable(meta_deriv.get("pcr_vol")),
        pcr_oi=to_jsonable(meta_deriv.get("pcr_oi")),
        short_float=to_jsonable(short_float),
        short_ratio=to_jsonable(meta_deriv.get("short_ratio")),
        avg_iv=to_jsonable(avg_iv),
        technical_trend=bool(technical_trend) if technical_trend is not None else None,
        risk_label=risk_label,
    )


def future_or_default(future, default, label, ticker):
    try:
        value = future.result()
        return ProviderOutcome(value=default if value is None else value, failed=False)
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as exc:
        logger.debug("%s provider failed for %s: %s", label, ticker, exc)
        return ProviderOutcome(value=default, failed=True)


def build_data_quality(
    *,
    market_data_ok,
    headlines,
    news_failed,
    sentiment_provider,
    fundamental_data,
    derivative_data,
    meta_fund,
):
    warnings = []
    confidence = 100

    market_data = "ok" if market_data_ok else "unavailable"
    if market_data != "ok":
        confidence -= 40
        warnings.append("Market price history unavailable.")

    if news_failed:
        news = "unavailable"
        confidence -= 10
        warnings.append("News provider unavailable.")
    elif not headlines:
        news = "empty"
        confidence -= 6
        warnings.append("No recent headlines found.")
    else:
        news = "ok"

    if sentiment_provider == "none":
        sentiment = "fallback"
        confidence -= 15
        warnings.append("Sentiment used neutral fallback.")
    else:
        sentiment = "ok"

    if not fundamental_data:
        fundamentals = "unavailable"
        confidence -= 25
        warnings.append("Fundamental data unavailable.")
    else:
        expected = ("trailingPE", "returnOnEquity", "profitMargins", "revenueGrowth")
        missing = [field for field in expected if fundamental_data.get(field) is None]
        fundamentals = "partial" if missing else "ok"
        if missing:
            confidence -= 10
            warnings.append("Fundamental data is partial.")

    if not derivative_data.get("valid"):
        derivatives = "unavailable"
        confidence -= 15
        warnings.append("Options and derivatives data unavailable.")
    else:
        option_fields = ("pcr_vol", "pcr_oi", "avg_iv")
        missing_options = [field for field in option_fields if derivative_data.get(field) is None]
        derivatives = "partial" if missing_options else "ok"
        if missing_options:
            confidence -= 7
            warnings.append("Options data is partial.")

    has_insider_fields = "insider_buys" in meta_fund and "insider_sells" in meta_fund
    insider_activity = "ok" if has_insider_fields else "unavailable"
    if not has_insider_fields:
        confidence -= 5
        warnings.append("Insider activity unavailable.")

    return DataQualityResponse(
        market_data=market_data,
        news=news,
        sentiment=sentiment,
        fundamentals=fundamentals,
        derivatives=derivatives,
        insider_activity=insider_activity,
        confidence=max(0, min(100, confidence)),
        warnings=warnings,
    )


class AnalysisService:
    def __init__(self, market_provider, news_provider, sentiment_provider, scoring_engine=None):
        self.market_provider = market_provider
        self.news_provider = news_provider
        self.sentiment_provider = sentiment_provider
        self.scoring_engine = scoring_engine or ScoringEngine()
        self.fundamental_analysis_service = FundamentalAnalysisService()

    @classmethod
    def from_environment(cls):
        ollama = OllamaSentimentProvider(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            model=os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
        )
        sentiment = CompositeSentimentProvider([BatchingSentimentProvider(ollama), NeutralSentimentProvider()])
        return cls(MarketDataProvider(), ScrapyNewsProvider(), sentiment)

    def analyze(self, query: str):
        ticker = self.market_provider.resolve_ticker(query)
        df_tech = self.market_provider.get_technical_data(ticker)
        if df_tech is None or df_tech.empty:
            return None

        score_tech, meta_tech = self.scoring_engine.calculate_technical(df_tech)
        with ThreadPoolExecutor(max_workers=3) as executor:
            headlines_future = executor.submit(self.news_provider.get_headlines, ticker)
            derivative_future = executor.submit(self.market_provider.get_derivative_data, ticker)
            fundamental_future = executor.submit(self.market_provider.get_fundamental_data, ticker)
            headlines_outcome = future_or_default(headlines_future, [], "news", ticker)
            derivative_outcome = future_or_default(derivative_future, {"valid": False}, "derivative", ticker)
            fundamental_outcome = future_or_default(fundamental_future, {}, "fundamental", ticker)

        headlines = headlines_outcome.value
        derivative_data = derivative_outcome.value
        fundamental_data = fundamental_outcome.value

        sentiment_items = [
            SentimentInput(
                title=headline.title,
                article_text=getattr(headline, "article_text", ""),
                analysis_depth=getattr(headline, "analysis_depth", "headline"),
            )
            for headline in headlines
        ]
        request = SentimentRequest(ticker=ticker, items=sentiment_items)
        try:
            sentiment_result = self.sentiment_provider.analyze(request)
        except SentimentProviderError:
            sentiment_result = NeutralSentimentProvider().analyze(request)

        enriched_headlines = []
        social_headlines = []
        for index, headline in enumerate(headlines):
            sentiment_item = sentiment_result.items[index] if index < len(sentiment_result.items) else None
            sentiment = sentiment_item.sentiment if sentiment_item else "Neutral"
            impact = sentiment_item.score if sentiment_item else 0
            enriched_headlines.append(
                HeadlineResponse(
                    **headline.__dict__,
                    sentiment=sentiment,
                    score=impact,
                )
            )
            social_headlines.append({**headline.__dict__, "sentiment": sentiment, "score": impact})

        score_social, meta_social = self.scoring_engine.calculate_social({"headlines": social_headlines})
        technical_trend = meta_tech.get("Trend", True)
        score_deriv, meta_deriv = self.scoring_engine.calculate_derivative(derivative_data, technical_trend=technical_trend)
        score_fund, meta_fund = self.scoring_engine.calculate_fundamental(fundamental_data)
        fundamental_analysis = self.fundamental_analysis_service.analyze(fundamental_data)
        data_quality = build_data_quality(
            market_data_ok=True,
            headlines=headlines,
            news_failed=headlines_outcome.failed,
            sentiment_provider=sentiment_result.provider,
            fundamental_data=fundamental_data,
            derivative_data=derivative_data,
            meta_fund=meta_fund,
        )
        composite = compute_composite_score(
            score_fund,
            score_social,
            score_tech,
            score_deriv,
            data_quality=data_quality.confidence,
            insider_booster=meta_fund.get("insider_booster", 0),
        )
        rating, _ = get_rating(composite.final_score)

        return AnalysisResponse(
            ticker=ticker,
            company=CompanyInfo(
                name=meta_fund.get("longName") or meta_fund.get("shortName") or ticker,
                sector=meta_fund.get("sector", ""),
                industry=meta_fund.get("industry", ""),
            ),
            composite=CompositeResponse(
                base_score=composite.base_score,
                final_score=composite.final_score,
                rating=rating,
                insider_booster=composite.insider_booster,
            ),
            pillars={
                "fundamental": PillarResponse(score=score_fund, meta=to_jsonable(meta_fund)),
                "sentiment": PillarResponse(score=score_social, meta=to_jsonable(meta_social)),
                "technical": PillarResponse(score=score_tech, meta=to_jsonable(meta_tech)),
                "derivative": PillarResponse(score=score_deriv, meta=to_jsonable(meta_deriv)),
            },
            headlines=enriched_headlines,
            chart=build_chart_payload(df_tech),
            providers={
                "news": self.news_provider.name,
                "sentiment": sentiment_result.provider,
                "market_data": self.market_provider.name,
            },
            insider_activity=build_insider_activity(meta_fund),
            piotroski=build_piotroski_summary(meta_fund),
            derivatives=build_derivatives_summary(meta_deriv, technical_trend),
            competitors=[],
            data_quality=data_quality,
            fundamental_analysis=fundamental_analysis,
        )

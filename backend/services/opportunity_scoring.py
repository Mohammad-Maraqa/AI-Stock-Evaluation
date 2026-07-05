from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpportunityScore:
    opportunity_score: float
    fundamental_score: float
    valuation_score: float
    sentiment_score: float
    technical_score: float
    underhype_score: float
    data_quality_score: float
    label: str
    reasons: list[str]
    risks: list[str]


def _get(obj: Any, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _nested(obj: Any, *keys, default=None):
    current = obj
    for key in keys:
        current = _get(current, key, None)
        if current is None:
            return default
    return current


def _score_from_ratio(value, bands):
    if value is None:
        return 55
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 55
    for threshold, score in bands:
        if number <= threshold:
            return score
    return bands[-1][1]


def calculate_valuation_score(fundamentals: dict[str, Any]) -> tuple[float, list[str]]:
    values = []
    risks = []
    trailing_pe = fundamentals.get("trailingPE")
    forward_pe = fundamentals.get("forwardPE")
    price_sales = fundamentals.get("priceToSalesTrailing12Months")
    peg = fundamentals.get("pegRatio")
    ev_ebitda = fundamentals.get("enterpriseToEbitda")

    if trailing_pe is not None:
        values.append(_score_from_ratio(trailing_pe, [(15, 85), (25, 72), (40, 55), (70, 35), (9999, 20)]))
        if trailing_pe > 50:
            risks.append("High trailing earnings multiple.")
    if forward_pe is not None:
        values.append(_score_from_ratio(forward_pe, [(15, 85), (25, 72), (40, 55), (70, 35), (9999, 20)]))
    if price_sales is not None:
        values.append(_score_from_ratio(price_sales, [(3, 82), (7, 65), (12, 48), (20, 32), (9999, 18)]))
        if price_sales > 15:
            risks.append("High sales multiple.")
    if peg is not None:
        values.append(_score_from_ratio(peg, [(1, 85), (2, 70), (3, 52), (5, 35), (9999, 20)]))
    if ev_ebitda is not None:
        values.append(_score_from_ratio(ev_ebitda, [(10, 82), (16, 68), (25, 50), (40, 34), (9999, 20)]))

    return (sum(values) / len(values) if values else 55), risks


def calculate_underhype_score(valuation, sentiment, technical, fundamentals, analysis) -> tuple[float, list[str], list[str]]:
    score = 55.0
    reasons = []
    risks = []
    if valuation >= 70:
        score += 15
        reasons.append("Valuation appears reasonable relative to available metrics.")
    elif valuation < 40:
        score -= 20
        risks.append("Valuation appears stretched relative to available metrics.")

    rsi = _nested(analysis, "pillars", "technical", "meta", "RSI")
    if rsi is not None and rsi > 75:
        score -= 15
        risks.append("Technical indicators look overheated.")
    elif technical >= 60:
        score += 10
        reasons.append("Technical setup is constructive without clear overextension.")

    if 50 <= sentiment <= 75:
        score += 8
        reasons.append("Sentiment is positive but not euphoric.")
    elif sentiment > 85:
        score -= 10
        risks.append("Sentiment appears very one-sided.")

    if fundamentals.get("debtToEquity") is not None and fundamentals["debtToEquity"] > 150:
        score -= 10
        risks.append("Leverage is elevated.")
    return max(0, min(100, score)), reasons, risks


def assign_opportunity_label(*, fundamental, valuation, underhype, data_quality, theme_relevance):
    if data_quality < 45:
        return "Insufficient Data"
    if theme_relevance < 50:
        return "Weak Theme Evidence"
    if fundamental >= 70 and valuation >= 60 and underhype >= 70:
        return "Underrated Candidate"
    if fundamental >= 70 and underhype < 45:
        return "High Quality, Overhyped"
    if fundamental >= 70 and valuation >= 45:
        return "High Quality, Fairly Valued"
    if fundamental < 45 and valuation >= 65:
        return "Cheap but Weak"
    if fundamental < 45:
        return "Low Quality / Avoid"
    return "Speculative Turnaround"


def calculate_discovery_confidence(theme_relevance_score, sources, source_consensus):
    has_etf = "ETF_HOLDINGS" in sources
    if theme_relevance_score >= 80 and has_etf and source_consensus >= 2:
        return "high"
    if theme_relevance_score >= 55 and (has_etf or source_consensus >= 2):
        return "medium"
    return "low"


def calculate_opportunity_score(analysis, fundamentals, theme_relevance_score):
    fundamental = _nested(analysis, "fundamental_analysis", "overall_score")
    if not fundamental:
        fundamental = _nested(analysis, "pillars", "fundamental", "score", default=0)
    sentiment = _nested(analysis, "pillars", "sentiment", "score", default=50)
    technical = _nested(analysis, "pillars", "technical", "score", default=50)
    data_quality = _nested(analysis, "data_quality", "confidence", default=60)
    valuation, valuation_risks = calculate_valuation_score(fundamentals)
    underhype, underhype_reasons, underhype_risks = calculate_underhype_score(
        valuation, sentiment, technical, fundamentals, analysis
    )
    opportunity = (
        fundamental * 0.30
        + valuation * 0.20
        + sentiment * 0.15
        + technical * 0.15
        + underhype * 0.10
        + data_quality * 0.10
    )

    reasons = []
    risks = []
    if fundamental >= 70:
        reasons.append("Strong fundamental score.")
    if fundamentals.get("profitMargins") is not None and fundamentals["profitMargins"] > 0.12:
        reasons.append("Strong profitability quality.")
    if fundamentals.get("freeCashflow") is not None and fundamentals["freeCashflow"] > 0:
        reasons.append("Positive free cash flow.")
    if fundamentals.get("operatingCashflow") is not None and fundamentals.get("freeCashflow") is not None:
        if fundamentals["freeCashflow"] <= 0 < fundamentals["operatingCashflow"]:
            risks.append("Operating cash flow does not translate into positive free cash flow.")
    if fundamentals.get("debtToEquity") is not None and fundamentals["debtToEquity"] > 120:
        risks.append("Debt level should be monitored.")
    if data_quality < 70:
        risks.append("Some data fields are missing or degraded.")
    reasons.extend(underhype_reasons)
    risks.extend(valuation_risks)
    risks.extend(underhype_risks)

    label = assign_opportunity_label(
        fundamental=fundamental,
        valuation=valuation,
        underhype=underhype,
        data_quality=data_quality,
        theme_relevance=theme_relevance_score,
    )
    return OpportunityScore(
        opportunity_score=round(max(0, min(100, opportunity)), 1),
        fundamental_score=round(float(fundamental), 1),
        valuation_score=round(float(valuation), 1),
        sentiment_score=round(float(sentiment), 1),
        technical_score=round(float(technical), 1),
        underhype_score=round(float(underhype), 1),
        data_quality_score=round(float(data_quality), 1),
        label=label,
        reasons=reasons or ["Scored from available deterministic analysis fields."],
        risks=risks or ["No major deterministic risk flag was identified from available fields."],
    )

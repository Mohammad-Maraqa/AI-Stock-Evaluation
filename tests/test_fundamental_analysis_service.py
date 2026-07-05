import pandas as pd

from backend.services.fundamental_analysis_service import FundamentalAnalysisService


def financial_frame(**rows):
    return pd.DataFrame(
        {
            "2026": rows,
            "2025": {key: value * 0.8 for key, value in rows.items()},
        }
    ).T


def statement_frame(current, previous):
    return pd.DataFrame({"2026": current, "2025": previous})


def rich_fundamentals():
    return {
        "currentPrice": 200,
        "totalRevenue": 120_000_000_000,
        "revenueGrowth": 0.22,
        "grossMargins": 0.65,
        "ebitdaMargins": 0.35,
        "profitMargins": 0.24,
        "totalCash": 20_000_000_000,
        "totalDebt": 30_000_000_000,
        "debtToEquity": 45,
        "currentRatio": 1.8,
        "quickRatio": 1.2,
        "freeCashflow": 18_000_000_000,
        "operatingCashflow": 25_000_000_000,
        "trailingEps": 8,
        "earningsGrowth": 0.18,
        "trailingPE": 25,
        "forwardPE": 22,
        "dividendYield": 0.012,
        "_financials": statement_frame(
            {
                "Total Revenue": 120_000_000_000,
                "Gross Profit": 78_000_000_000,
                "EBITDA": 42_000_000_000,
                "Net Income": 28_800_000_000,
            },
            {
                "Total Revenue": 98_000_000_000,
                "Gross Profit": 58_800_000_000,
                "EBITDA": 29_400_000_000,
                "Net Income": 17_640_000_000,
            },
        ),
        "_balance_sheet": statement_frame(
            {
                "Total Assets": 180_000_000_000,
                "Total Liabilities Net Minority Interest": 90_000_000_000,
                "Stockholders Equity": 90_000_000_000,
                "Current Assets": 55_000_000_000,
                "Current Liabilities": 30_000_000_000,
                "Cash And Cash Equivalents": 20_000_000_000,
                "Total Debt": 30_000_000_000,
            },
            {
                "Total Assets": 160_000_000_000,
                "Total Liabilities Net Minority Interest": 88_000_000_000,
                "Stockholders Equity": 72_000_000_000,
                "Current Assets": 48_000_000_000,
                "Current Liabilities": 33_000_000_000,
                "Cash And Cash Equivalents": 18_000_000_000,
                "Total Debt": 32_000_000_000,
            },
        ),
        "_cashflow": statement_frame(
            {
                "Operating Cash Flow": 25_000_000_000,
                "Free Cash Flow": 18_000_000_000,
            },
            {
                "Operating Cash Flow": 20_000_000_000,
                "Free Cash Flow": 12_000_000_000,
            },
        ),
    }


def category(result, name):
    return next(item for item in result.categories if item.name == name)


def test_revenue_growth_scoring_and_metrics_are_deterministic():
    result = FundamentalAnalysisService().analyze(rich_fundamentals())
    revenue = category(result, "Revenue Growth")

    assert revenue.status == "ok"
    assert revenue.score == 10
    assert revenue.bullishness == 100
    assert revenue.metrics["current_revenue"] == 120_000_000_000
    assert revenue.metrics["previous_revenue"] == 98_000_000_000
    assert round(revenue.metrics["revenue_growth_pct"], 2) == 22.45
    assert "Revenue increased" in revenue.explanation


def test_profitability_solidity_liquidity_cash_flow_leverage_and_returns_score():
    result = FundamentalAnalysisService().analyze(rich_fundamentals())

    assert category(result, "Profitability").score >= 8
    assert category(result, "Solvency").score >= 8
    assert category(result, "Liquidity").score >= 8
    assert category(result, "Cash Flow").score >= 8
    assert category(result, "Leverage").score >= 7
    assert category(result, "Shareholder Returns").score >= 7
    assert result.overall_score >= 80
    assert result.bullishness + result.bearishness == 100


def test_missing_financial_fields_return_partial_or_unavailable_categories():
    result = FundamentalAnalysisService().analyze({"currentPrice": 100})

    assert result.overall_score == 0
    assert result.bullishness == 0
    assert result.bearishness == 100
    assert "Fundamental deep analysis is unavailable." in result.warnings
    assert all(item.status == "unavailable" for item in result.categories)


def test_negative_cash_flow_and_high_leverage_are_penalized():
    data = rich_fundamentals()
    data["freeCashflow"] = -1_000_000_000
    data["totalDebt"] = 120_000_000_000
    data["debtToEquity"] = 220
    data["_cashflow"] = statement_frame(
        {"Operating Cash Flow": 2_000_000_000, "Free Cash Flow": -1_000_000_000},
        {"Operating Cash Flow": 5_000_000_000, "Free Cash Flow": 3_000_000_000},
    )

    result = FundamentalAnalysisService().analyze(data)

    assert category(result, "Cash Flow").score <= 4
    assert category(result, "Leverage").score <= 4

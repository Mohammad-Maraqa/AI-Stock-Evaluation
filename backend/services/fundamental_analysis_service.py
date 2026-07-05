from numbers import Number

from backend.schemas import FundamentalAnalysisResponse, FundamentalCategoryResponse


def _is_number(value):
    return isinstance(value, Number) and not isinstance(value, bool)


def _pct(value):
    return value * 100 if _is_number(value) and abs(value) <= 1 else value


def _safe_divide(numerator, denominator):
    if not _is_number(numerator) or not _is_number(denominator) or denominator == 0:
        return None
    return numerator / abs(denominator)


def _clamp_score(value):
    return max(0, min(10, round(value, 1)))


def _score_to_sentiment(score):
    bullishness = round(score * 10)
    return bullishness, 100 - bullishness


class FundamentalAnalysisService:
    def analyze(self, fundamentals) -> FundamentalAnalysisResponse:
        categories = [
            self._revenue_growth(fundamentals),
            self._profitability(fundamentals),
            self._solvency(fundamentals),
            self._liquidity(fundamentals),
            self._cash_flow(fundamentals),
            self._leverage(fundamentals),
            self._shareholder_returns(fundamentals),
        ]
        available = [category for category in categories if category.status != "unavailable"]
        if not available:
            return FundamentalAnalysisResponse(
                categories=categories,
                warnings=["Fundamental deep analysis is unavailable."],
            )

        overall = round((sum(category.score for category in available) / len(available)) * 10)
        bullishness = overall
        summary = self._summary(categories, overall)
        warnings = [] if len(available) == len(categories) else ["Some fundamental categories have partial or unavailable data."]
        return FundamentalAnalysisResponse(
            overall_score=overall,
            bullishness=bullishness,
            bearishness=100 - bullishness,
            summary=summary,
            warnings=warnings,
            categories=categories,
        )

    def _metric(self, data, key):
        value = data.get(key)
        return value if _is_number(value) else None

    def _statement_value(self, data, frame_key, candidates, offset=0):
        frame = data.get(frame_key)
        if frame is None:
            return None
        for candidate in candidates:
            try:
                if candidate in frame.index and len(frame.columns) > offset:
                    value = frame.loc[candidate].iloc[offset]
                    return value if _is_number(value) else None
            except (AttributeError, KeyError, IndexError, TypeError):
                continue
        return None

    def _category(self, name, status, score, metrics, explanation):
        bullishness, bearishness = _score_to_sentiment(score)
        return FundamentalCategoryResponse(
            name=name,
            status=status,
            score=_clamp_score(score),
            bullishness=bullishness,
            bearishness=bearishness,
            explanation=explanation,
            metrics=metrics,
        )

    def _unavailable(self, name):
        return self._category(name, "unavailable", 0, {}, "Not enough data available.")

    def _revenue_growth(self, data):
        current = self._statement_value(data, "_financials", ["Total Revenue"], 0) or self._metric(data, "totalRevenue")
        previous = self._statement_value(data, "_financials", ["Total Revenue"], 1)
        growth = _safe_divide(current - previous, previous) if _is_number(current) and _is_number(previous) else self._metric(data, "revenueGrowth")
        if growth is None:
            return self._unavailable("Revenue Growth")
        score = 10 if growth >= 0.20 else 8 if growth >= 0.10 else 6 if growth >= 0.03 else 4 if growth >= 0 else 2 if growth >= -0.10 else 0
        direction = "increased" if growth >= 0 else "declined"
        metrics = {
            "current_revenue": current,
            "previous_revenue": previous,
            "revenue_growth_pct": round(growth * 100, 2),
        }
        return self._category("Revenue Growth", "ok" if previous is not None else "partial", score, metrics, f"Revenue {direction} {abs(growth) * 100:.1f}% year over year.")

    def _profitability(self, data):
        revenue = self._statement_value(data, "_financials", ["Total Revenue"], 0) or self._metric(data, "totalRevenue")
        previous_revenue = self._statement_value(data, "_financials", ["Total Revenue"], 1)
        gross_margin = self._metric(data, "grossMargins")
        ebitda_margin = self._metric(data, "ebitdaMargins")
        net_margin = self._metric(data, "profitMargins")
        gross_profit = self._statement_value(data, "_financials", ["Gross Profit"], 0)
        ebitda = self._statement_value(data, "_financials", ["EBITDA"], 0)
        net_income = self._statement_value(data, "_financials", ["Net Income", "Net Income Common Stockholders"], 0)
        previous_net_income = self._statement_value(data, "_financials", ["Net Income", "Net Income Common Stockholders"], 1)
        if gross_margin is None:
            gross_margin = _safe_divide(gross_profit, revenue)
        if ebitda_margin is None:
            ebitda_margin = _safe_divide(ebitda, revenue)
        if net_margin is None:
            net_margin = _safe_divide(net_income, revenue)
        margins = [value for value in (gross_margin, ebitda_margin, net_margin) if value is not None]
        if not margins:
            return self._unavailable("Profitability")
        scores = [10 if value >= 0.35 else 8 if value >= 0.20 else 6 if value >= 0.10 else 4 if value >= 0 else 1 for value in margins]
        score = sum(scores) / len(scores)
        if net_margin is not None and net_margin < 0:
            score = min(score, 4)
        previous_net_margin = _safe_divide(previous_net_income, previous_revenue)
        improved = previous_net_margin is not None and net_margin is not None and net_margin > previous_net_margin
        metrics = {
            "gross_margin": round(gross_margin * 100, 2) if gross_margin is not None else None,
            "ebitda_margin": round(ebitda_margin * 100, 2) if ebitda_margin is not None else None,
            "net_margin": round(net_margin * 100, 2) if net_margin is not None else None,
            "net_income": net_income,
        }
        explanation = f"Net margin is {net_margin * 100:.1f}%." if net_margin is not None else "Available margin data supports the profitability score."
        if improved:
            explanation = f"Net margin improved to {net_margin * 100:.1f}%, indicating stronger operating efficiency."
        return self._category("Profitability", "ok" if len(margins) >= 2 else "partial", score, metrics, explanation)

    def _solvency(self, data):
        assets = self._statement_value(data, "_balance_sheet", ["Total Assets"], 0)
        liabilities = self._statement_value(data, "_balance_sheet", ["Total Liabilities Net Minority Interest", "Total Liabilities"], 0)
        equity = self._statement_value(data, "_balance_sheet", ["Stockholders Equity", "Total Equity Gross Minority Interest"], 0)
        debt_to_equity = self._metric(data, "debtToEquity")
        if debt_to_equity is not None and debt_to_equity > 10:
            debt_to_equity = debt_to_equity / 100
        if debt_to_equity is None:
            debt = self._metric(data, "totalDebt") or self._statement_value(data, "_balance_sheet", ["Total Debt"], 0)
            debt_to_equity = _safe_divide(debt, equity)
        if debt_to_equity is None and not any(value is not None for value in (assets, liabilities, equity)):
            return self._unavailable("Solvency")
        score = 10 if debt_to_equity is not None and debt_to_equity < 0.4 else 8 if debt_to_equity is not None and debt_to_equity < 0.8 else 6 if debt_to_equity is not None and debt_to_equity < 1.5 else 3 if debt_to_equity is not None and debt_to_equity < 2.5 else 1
        if equity is not None and equity <= 0:
            score = min(score, 3)
        metrics = {"assets": assets, "liabilities": liabilities, "equity": equity, "debt_to_equity": round(debt_to_equity, 2) if debt_to_equity is not None else None}
        explanation = f"Debt-to-equity of {debt_to_equity:.2f} indicates {'conservative' if score >= 8 else 'elevated'} leverage." if debt_to_equity is not None else "Balance sheet data is partial."
        return self._category("Solvency", "ok" if debt_to_equity is not None and equity is not None else "partial", score, metrics, explanation)

    def _liquidity(self, data):
        current_ratio = self._metric(data, "currentRatio")
        quick_ratio = self._metric(data, "quickRatio")
        current_assets = self._statement_value(data, "_balance_sheet", ["Current Assets", "Total Current Assets"], 0)
        current_liabilities = self._statement_value(data, "_balance_sheet", ["Current Liabilities", "Total Current Liabilities"], 0)
        if current_ratio is None:
            current_ratio = _safe_divide(current_assets, current_liabilities)
        working_capital = current_assets - current_liabilities if current_assets is not None and current_liabilities is not None else None
        if current_ratio is None and quick_ratio is None and working_capital is None:
            return self._unavailable("Liquidity")
        scores = []
        if current_ratio is not None:
            scores.append(10 if current_ratio >= 2 else 8 if current_ratio >= 1.5 else 6 if current_ratio >= 1 else 2)
        if quick_ratio is not None:
            scores.append(10 if quick_ratio >= 1.5 else 8 if quick_ratio >= 1 else 5 if quick_ratio >= 0.7 else 2)
        score = sum(scores) / len(scores) if scores else 5
        if working_capital is not None and working_capital < 0:
            score = min(score, 5)
        metrics = {"current_ratio": current_ratio, "quick_ratio": quick_ratio, "working_capital": working_capital}
        return self._category("Liquidity", "ok" if current_ratio is not None and quick_ratio is not None else "partial", score, metrics, f"Current ratio of {current_ratio:.2f} indicates short-term liquidity coverage." if current_ratio is not None else "Liquidity data is partial.")

    def _cash_flow(self, data):
        ocf = self._statement_value(data, "_cashflow", ["Operating Cash Flow", "Total Cash From Operating Activities"], 0) or self._metric(data, "operatingCashflow")
        fcf = self._statement_value(data, "_cashflow", ["Free Cash Flow"], 0) or self._metric(data, "freeCashflow")
        previous_fcf = self._statement_value(data, "_cashflow", ["Free Cash Flow"], 1)
        growth = _safe_divide(fcf - previous_fcf, previous_fcf) if fcf is not None and previous_fcf is not None else None
        if ocf is None and fcf is None:
            return self._unavailable("Cash Flow")
        score = 8 if fcf is not None and fcf > 0 else 4
        if growth is not None and growth >= 0.20:
            score = 10
        elif growth is not None and growth < 0:
            score = min(score, 5)
        if fcf is not None and fcf < 0:
            score = min(score, 4)
        metrics = {"operating_cash_flow": ocf, "free_cash_flow": fcf, "fcf_growth_pct": round(growth * 100, 2) if growth is not None else None}
        explanation = f"Free cash flow {'increased' if growth and growth >= 0 else 'changed'} {abs(growth) * 100:.1f}% year over year." if growth is not None else "Available cash flow data supports the score."
        return self._category("Cash Flow", "ok" if growth is not None else "partial", score, metrics, explanation)

    def _leverage(self, data):
        total_debt = self._metric(data, "totalDebt") or self._statement_value(data, "_balance_sheet", ["Total Debt"], 0)
        cash = self._metric(data, "totalCash") or self._statement_value(data, "_balance_sheet", ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"], 0)
        ebitda = self._statement_value(data, "_financials", ["EBITDA"], 0)
        net_debt = total_debt - cash if total_debt is not None and cash is not None else None
        debt_ebitda = _safe_divide(total_debt, ebitda)
        if total_debt is None and net_debt is None and debt_ebitda is None:
            return self._unavailable("Leverage")
        if net_debt is not None and net_debt <= 0:
            score = 10
        elif debt_ebitda is not None:
            score = 10 if debt_ebitda < 1 else 8 if debt_ebitda < 2 else 4 if debt_ebitda < 3.5 else 2
        else:
            score = 6
        metrics = {"total_debt": total_debt, "net_debt": net_debt, "debt_to_ebitda": round(debt_ebitda, 2) if debt_ebitda is not None else None}
        return self._category("Leverage", "ok" if debt_ebitda is not None else "partial", score, metrics, f"Debt to EBITDA is {debt_ebitda:.2f}, indicating {'low' if score >= 8 else 'elevated'} leverage." if debt_ebitda is not None else "Leverage data is partial.")

    def _shareholder_returns(self, data):
        eps = self._metric(data, "trailingEps")
        eps_growth = self._metric(data, "earningsGrowth")
        pe = self._metric(data, "trailingPE")
        forward_pe = self._metric(data, "forwardPE")
        dividend_yield = self._metric(data, "dividendYield")
        if not any(value is not None for value in (eps, eps_growth, pe, forward_pe, dividend_yield)):
            return self._unavailable("Shareholder Returns")
        score = 5
        if eps_growth is not None:
            score += 3 if eps_growth >= 0.20 else 2 if eps_growth >= 0.05 else -2 if eps_growth < 0 else 0
        if pe is not None:
            score += 2 if pe < 20 else 0 if pe < 35 else -2
        if forward_pe is not None and pe is not None and forward_pe < pe:
            score += 1
        if dividend_yield is not None and dividend_yield > 0:
            score += 0.5
        metrics = {"eps": eps, "eps_growth_pct": round(eps_growth * 100, 2) if eps_growth is not None else None, "pe_ratio": pe, "forward_pe": forward_pe, "dividend_yield_pct": round(_pct(dividend_yield), 2) if dividend_yield is not None else None}
        explanation = f"EPS growth is {eps_growth * 100:.1f}% while valuation is {pe:.1f}x earnings." if eps_growth is not None and pe is not None else "Shareholder return data is partial."
        return self._category("Shareholder Returns", "ok" if eps_growth is not None and pe is not None else "partial", _clamp_score(score), metrics, explanation)

    def _summary(self, categories, overall):
        strongest = max(categories, key=lambda category: category.score)
        weakest = min(categories, key=lambda category: category.score)
        if overall >= 75:
            return f"Strong fundamentals led by {strongest.name.lower()}, with {weakest.name.lower()} as the main watch item."
        if overall >= 50:
            return f"Mixed fundamentals with strength in {strongest.name.lower()} and pressure in {weakest.name.lower()}."
        return f"Weak fundamentals with the largest concern in {weakest.name.lower()}."

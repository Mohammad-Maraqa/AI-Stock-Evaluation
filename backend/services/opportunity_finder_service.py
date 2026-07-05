import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from backend.schemas import (
    OpportunityResultResponse,
    OpportunityScanMetadata,
    OpportunityScanResponse,
    OpportunityScoreBreakdown,
    OpportunitySourceWarning,
)
from backend.services.analysis_service import AnalysisService
from backend.services.discovery.etf_holdings_provider import EtfHoldingsProvider
from backend.services.discovery.models import DiscoveryCandidate, DiscoveryWarning
from backend.services.discovery.nasdaq_discovery_provider import NasdaqDiscoveryProvider
from backend.services.discovery.theme_config import get_theme, list_themes
from backend.services.discovery.universe_discovery import merge_candidates
from backend.services.market_data import MarketDataProvider
from backend.services.opportunity_scoring import calculate_discovery_confidence, calculate_opportunity_score


def _contains_any(text, keywords):
    haystack = (text or "").lower()
    return any(str(keyword).lower() in haystack for keyword in keywords)


class OpportunityFinderService:
    def __init__(
        self,
        market_provider=None,
        analysis_service=None,
        etf_provider=None,
        nasdaq_provider=None,
        provider_timeout_seconds=15,
        validation_timeout_seconds=4,
        analysis_timeout_seconds=10,
        max_analysis_timeouts=1,
        validation_candidate_multiplier=3,
    ):
        self.market_provider = market_provider or MarketDataProvider()
        self.analysis_service = analysis_service or AnalysisService.from_environment()
        self.etf_provider = etf_provider or EtfHoldingsProvider(timeout_seconds=provider_timeout_seconds)
        self.nasdaq_provider = nasdaq_provider or NasdaqDiscoveryProvider(timeout_seconds=provider_timeout_seconds)
        self.provider_timeout_seconds = provider_timeout_seconds
        self.validation_timeout_seconds = validation_timeout_seconds
        self.analysis_timeout_seconds = analysis_timeout_seconds
        self.max_analysis_timeouts = max_analysis_timeouts
        self.validation_candidate_multiplier = validation_candidate_multiplier

    @classmethod
    def from_environment(cls):
        return cls()

    def list_themes(self):
        return list_themes()

    def scan(self, theme_id=None, etf=None, limit=10, max_candidates=25):
        started = time.perf_counter()
        limit = max(1, min(int(limit or 10), 25))
        max_candidates = max(1, min(int(max_candidates or 25), 50))
        theme = get_theme(theme_id) if theme_id else None
        if theme_id and theme is None:
            raise ValueError(f"Unknown opportunity theme '{theme_id}'.")

        raw_candidates, warnings = self._discover(theme, etf)
        merged = merge_candidates(raw_candidates)
        validated = []
        filtered_count = 0
        candidates_to_validate = self._rank_for_validation(merged)
        validation_cap = min(
            len(candidates_to_validate),
            max(max_candidates, limit) * self.validation_candidate_multiplier,
        )
        for candidate in candidates_to_validate[:validation_cap]:
            valid = self._run_with_timeout(
                lambda candidate=candidate: self._validate_candidate(candidate),
                self.validation_timeout_seconds,
            )
            if valid == "timeout":
                warnings.append(DiscoveryWarning("YAHOO_VALIDATION", f"Validation timed out for {candidate.ticker}"))
                filtered_count += 1
                continue
            if valid is None:
                filtered_count += 1
            else:
                validated.append(valid)
        filtered_count += max(0, len(merged) - validation_cap)

        relevance_ranked = []
        for candidate, fundamentals in validated:
            relevance, reasons = self._calculate_relevance(candidate, fundamentals, theme, etf)
            min_relevance = int(theme.get("min_relevance", 50)) if theme else 35
            if relevance < min_relevance:
                filtered_count += 1
                continue
            relevance_ranked.append((candidate, fundamentals, relevance, reasons))
        relevance_ranked.sort(key=lambda item: (item[2], item[0].source_consensus), reverse=True)

        results = []
        timed_out_candidates = []
        analyzed_count = 0
        analysis_timeouts = 0
        analysis_attempts = relevance_ranked[:max_candidates]
        for index, (candidate, fundamentals, relevance, discovery_reasons) in enumerate(analysis_attempts):
            if len(results) >= limit:
                break
            if analysis_timeouts >= self.max_analysis_timeouts:
                for fallback_candidate, fallback_fundamentals, fallback_relevance, fallback_reasons in analysis_attempts[index:]:
                    if len(results) >= limit:
                        break
                    results.append(
                        self._build_validation_only_result(
                            fallback_candidate,
                            fallback_fundamentals,
                            fallback_relevance,
                            fallback_reasons,
                        )
                    )
                break
            analysis = self._run_with_timeout(
                lambda candidate=candidate: self.analysis_service.analyze(candidate.ticker),
                self.analysis_timeout_seconds,
            )
            if analysis == "timeout":
                analysis_timeouts += 1
                warnings.append(DiscoveryWarning("ANALYSIS", f"Analysis timed out for {candidate.ticker}"))
                timed_out_candidates.append((candidate, fundamentals, relevance, discovery_reasons))
                results.append(self._build_validation_only_result(candidate, fundamentals, relevance, discovery_reasons))
                continue
            if analysis == "error":
                warnings.append(DiscoveryWarning("ANALYSIS", f"Analysis failed for {candidate.ticker}."))
                continue
            if analysis is None:
                warnings.append(DiscoveryWarning("ANALYSIS", f"Analysis failed for {candidate.ticker}."))
                continue
            analyzed_count += 1
            score = calculate_opportunity_score(analysis, fundamentals, relevance)
            confidence = calculate_discovery_confidence(relevance, candidate.sources, candidate.source_consensus)
            risks = list(score.risks)
            if confidence == "low":
                risks.append("Weak theme evidence; review the connection to the selected theme.")
            results.append(
                OpportunityResultResponse(
                    ticker=candidate.ticker,
                    company=fundamentals.get("longName") or fundamentals.get("shortName") or candidate.company or candidate.ticker,
                    opportunity_score=score.opportunity_score,
                    label=score.label,
                    theme_relevance_score=round(relevance, 1),
                    discovery_confidence=confidence,
                    source_consensus=candidate.source_consensus,
                    scores=OpportunityScoreBreakdown(
                        fundamental=score.fundamental_score,
                        valuation=score.valuation_score,
                        sentiment=score.sentiment_score,
                        technical=score.technical_score,
                        underhype=score.underhype_score,
                        data_quality=score.data_quality_score,
                    ),
                    reasons=discovery_reasons + score.reasons,
                    risks=risks,
                    sources=candidate.sources,
                )
            )
        if not results and timed_out_candidates:
            for candidate, fundamentals, relevance, discovery_reasons in timed_out_candidates[:limit]:
                results.append(self._build_validation_only_result(candidate, fundamentals, relevance, discovery_reasons))
        results.sort(key=lambda item: item.opportunity_score, reverse=True)
        results = results[:limit]
        duration_ms = int((time.perf_counter() - started) * 1000)
        return OpportunityScanResponse(
            mode="etf" if etf and not theme else "theme",
            theme={"id": theme["id"], "name": theme["name"]} if theme else None,
            etf=etf.strip().upper() if etf else None,
            source_warnings=[OpportunitySourceWarning(source=warning.source, message=warning.message) for warning in warnings],
            candidate_count=len(merged),
            analyzed_count=analyzed_count,
            scan_metadata=OpportunityScanMetadata(
                discovered_count=len(raw_candidates),
                validated_count=len(validated),
                filtered_count=filtered_count,
                analyzed_count=analyzed_count,
                returned_count=len(results),
                duration_ms=duration_ms,
            ),
            results=results,
        )

    def _build_validation_only_result(self, candidate, fundamentals, relevance, discovery_reasons):
        confidence = calculate_discovery_confidence(relevance, candidate.sources, candidate.source_consensus)
        reasons = list(discovery_reasons)
        if fundamentals.get("profitMargins") is not None and fundamentals["profitMargins"] > 0:
            reasons.append("Company has positive profitability metrics in available market data.")
        if fundamentals.get("freeCashflow") is not None and fundamentals["freeCashflow"] > 0:
            reasons.append("Company has positive free cash flow in available market data.")
        return OpportunityResultResponse(
            ticker=candidate.ticker,
            company=fundamentals.get("longName") or fundamentals.get("shortName") or candidate.company or candidate.ticker,
            opportunity_score=round(min(60, max(35, relevance * 0.55)), 1),
            label="Insufficient Data",
            theme_relevance_score=round(relevance, 1),
            discovery_confidence=confidence,
            source_consensus=candidate.source_consensus,
            scores=OpportunityScoreBreakdown(
                fundamental=0,
                valuation=0,
                sentiment=0,
                technical=0,
                underhype=0,
                data_quality=35,
            ),
            reasons=reasons or ["Passed ticker validation and theme relevance checks."],
            risks=["Full analysis timed out; this is a validation-only candidate."],
            sources=candidate.sources,
        )

    @staticmethod
    def _run_with_timeout(func, timeout_seconds):
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(func)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            return "timeout"
        except Exception:
            executor.shutdown(wait=False, cancel_futures=True)
            return "error"
        finally:
            if future.done():
                executor.shutdown(wait=False, cancel_futures=True)

    def _discover(self, theme, etf):
        candidates = []
        warnings = []
        for source, call in (
            ("ETF_HOLDINGS", lambda: self._run_provider(self.etf_provider, theme, etf)),
            ("NASDAQ_DISCOVERY", lambda: self._run_nasdaq(theme)),
        ):
            started = time.perf_counter()
            source_candidates, source_warnings = call()
            elapsed = time.perf_counter() - started
            if elapsed > self.provider_timeout_seconds:
                warnings.append(DiscoveryWarning(source, f"{source} timed out; partial results may be incomplete."))
            candidates.extend(source_candidates)
            warnings.extend(source_warnings)
        return candidates, warnings

    def _run_provider(self, provider, theme, etf):
        if callable(provider):
            return provider(theme, etf)
        result = provider.discover(etf=etf, theme=theme)
        return result.candidates, result.warnings

    def _run_nasdaq(self, theme):
        if callable(self.nasdaq_provider):
            return self.nasdaq_provider(theme)
        result = self.nasdaq_provider.discover(theme=theme)
        return result.candidates, result.warnings

    @staticmethod
    def _rank_for_validation(candidates):
        return sorted(candidates, key=lambda candidate: (candidate.source_consensus, "ETF_HOLDINGS" in candidate.sources), reverse=True)

    def _validate_candidate(self, candidate: DiscoveryCandidate):
        fundamentals = self.market_provider.get_fundamental_data(candidate.ticker)
        if not fundamentals:
            return None
        name = fundamentals.get("longName") or fundamentals.get("shortName") or candidate.company
        quote_type = str(fundamentals.get("quoteType") or fundamentals.get("typeDisp") or "").upper()
        if not name or "ETF" in quote_type or "FUND" in quote_type:
            return None
        price = fundamentals.get("currentPrice") or fundamentals.get("regularMarketPrice")
        market_cap = fundamentals.get("marketCap")
        volume = fundamentals.get("averageVolume") or fundamentals.get("averageVolume10days")
        if price is not None and price < 5:
            return None
        if market_cap is not None and market_cap < 500_000_000:
            return None
        if volume is not None and volume < 100_000:
            return None
        technical = self.market_provider.get_technical_data(candidate.ticker)
        if technical is None or technical.empty:
            return None
        return candidate, fundamentals

    def _calculate_relevance(self, candidate, fundamentals, theme, etf):
        score = 0
        reasons = []
        if "ETF_HOLDINGS" in candidate.sources:
            score += 25
            reasons.append("Appeared in ETF holdings related to the selected theme.")
        if "NASDAQ_DISCOVERY" in candidate.sources:
            score += 20
            reasons.append("Matched Nasdaq/source discovery keywords.")
        if candidate.source_consensus > 1:
            score += 10
            reasons.append("Appeared in multiple independent discovery sources.")
        if etf and "ETF_HOLDINGS" in candidate.sources:
            score += 15
        if not theme:
            return min(100, score + 20), reasons

        industry_text = " ".join([fundamentals.get("sector", ""), fundamentals.get("industry", ""), candidate.sector, candidate.industry])
        if _contains_any(industry_text, theme.get("nasdaq_industry_keywords", [])):
            score += 15
            reasons.append("Sector or industry matched the selected theme.")
        if _contains_any(fundamentals.get("longBusinessSummary", ""), theme.get("business_summary_keywords", [])):
            score += 20
            reasons.append("Business summary matched theme keywords.")
        return min(100, score), reasons

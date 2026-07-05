from backend.services.discovery.models import DiscoveryCandidate


def merge_candidates(candidates: list[DiscoveryCandidate]) -> list[DiscoveryCandidate]:
    merged: dict[str, DiscoveryCandidate] = {}
    for candidate in candidates:
        ticker = candidate.ticker.strip().upper()
        if not ticker:
            continue
        if ticker not in merged:
            candidate.ticker = ticker
            candidate.sources = list(dict.fromkeys(candidate.sources or [candidate.source]))
            candidate.source_consensus = len(candidate.sources)
            merged[ticker] = candidate
            continue
        existing = merged[ticker]
        existing.company = existing.company or candidate.company
        existing.sector = existing.sector or candidate.sector
        existing.industry = existing.industry or candidate.industry
        for source in candidate.sources or [candidate.source]:
            if source and source not in existing.sources:
                existing.sources.append(source)
        existing.source_consensus = len(existing.sources)
    return list(merged.values())

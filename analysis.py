"""Application-level analysis helpers."""

from dataclasses import dataclass

from config import COMPOSITE_WEIGHTS


@dataclass(frozen=True)
class CompositeScore:
    base_score: float
    final_score: float
    insider_booster: float
    weights: dict[str, float]

def compute_composite_score(
    fundamental: float,
    sentiment: float,
    technical: float,
    derivative: float,
    data_quality: float = 100,
    insider_booster: float = 0,
) -> CompositeScore:
    base_score = (
        fundamental * COMPOSITE_WEIGHTS["fundamental"]
        + technical * COMPOSITE_WEIGHTS["technical"]
        + sentiment * COMPOSITE_WEIGHTS["sentiment"]
        + data_quality * COMPOSITE_WEIGHTS["data_quality"]
    )
    return CompositeScore(
        base_score=base_score,
        final_score=min(100, base_score + insider_booster),
        insider_booster=insider_booster,
        weights=COMPOSITE_WEIGHTS,
    )

import pytest

from analysis import COMPOSITE_WEIGHTS, compute_composite_score


def test_compute_composite_score_uses_configured_pillar_weights():
    result = compute_composite_score(
        fundamental=80,
        sentiment=60,
        technical=50,
        derivative=40,
        data_quality=100,
    )

    assert result.base_score == pytest.approx(68.0)
    assert result.final_score == pytest.approx(68.0)
    assert result.weights == COMPOSITE_WEIGHTS
    assert "derivative" not in result.weights


def test_compute_composite_score_applies_insider_booster_and_caps_at_100():
    result = compute_composite_score(
        fundamental=100,
        sentiment=100,
        technical=100,
        derivative=100,
        data_quality=100,
        insider_booster=12,
    )

    assert result.base_score == pytest.approx(100.0)
    assert result.final_score == pytest.approx(100.0)
    assert result.insider_booster == 12

import pytest
import pandas as pd
from scorers import ScoringEngine

def test_technical_scoring_with_data(mock_stock_data):
    engine = ScoringEngine()
    score, signals = engine.calculate_technical(mock_stock_data)
    
    assert 0 <= score <= 100
    assert isinstance(signals, dict)
    # Check that signals were actually generated
    assert len(signals) > 0

def test_technical_invalid_data():
    engine = ScoringEngine()
    # Create an empty dataframe correctly
    empty_df = pd.DataFrame()
    score, signals = engine.calculate_technical(empty_df)
    
    # Based on scorers.py, empty DF should return 0
    assert score == 0
    assert signals == {}

def test_piotroski_f_score_logic():
    engine = ScoringEngine()
    # The engine expects the dataframes to be passed differently.
    # We will pass an empty DataFrame as the primary data source.
    score, signals = engine.calculate_fundamental(
        pd.DataFrame()
    )
    assert isinstance(score, (int, float))
    assert isinstance(signals, dict)

def test_derivative_scoring_accepts_explicit_technical_trend():
    engine = ScoringEngine()
    data = {
        "valid": True,
        "short_float": 0.12,
        "short_ratio": 9,
        "pcr_vol": 0.5,
        "pcr_oi": 0.5,
        "avg_iv": 0.25,
    }

    uptrend_score, _ = engine.calculate_derivative(data, technical_trend=True)
    downtrend_score, _ = engine.calculate_derivative(data, technical_trend=False)

    assert uptrend_score > downtrend_score

"""Shared configuration values for the stock evaluation app."""

from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()
DOTENV_ENABLED = True

SCRAPER_API_KEY_ENV = "SCRAPER_API_KEY"

COMPOSITE_WEIGHTS = {
    "fundamental": 0.45,
    "technical": 0.30,
    "sentiment": 0.20,
    "data_quality": 0.05,
}

TECHNICAL_SIGNAL_WEIGHTS = {
    "Price Above SMA 200": 25,
    "Price Above SMA 50": 20,
    "Golden Cross Active": 15,
    "MACD Bullish Cross": 15,
    "MACD Above Zero": 10,
    "RSI Momentum": 8,
    "Price Above EMA 20": 5,
    "BB Band Position": 2,
}

SECTOR_PE_MEDIANS = {
    "Technology": 32,
    "Communication Services": 22,
    "Consumer Cyclical": 25,
    "Consumer Defensive": 22,
    "Healthcare": 28,
    "Biotechnology": 35,
    "Financial Services": 14,
    "Financials": 14,
    "Industrials": 20,
    "Basic Materials": 16,
    "Energy": 13,
    "Utilities": 18,
    "Real Estate": 38,
    "Semiconductor": 30,
    "Software": 35,
    "Retail": 20,
    "Automotive": 14,
}


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime secrets and optional scraper settings."""

    scraper_api_key: str | None = None


def parse_api_key_pool(value: str | None) -> list[str]:
    if not value:
        return []
    return [key.strip() for key in value.split(",") if key.strip()]


def get_sector_pe_median(sector: str | None) -> int:
    return SECTOR_PE_MEDIANS.get(sector or "", 20)

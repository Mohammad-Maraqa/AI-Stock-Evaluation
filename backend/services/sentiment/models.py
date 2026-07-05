from dataclasses import dataclass


@dataclass(frozen=True)
class SentimentInput:
    title: str
    article_text: str = ""
    analysis_depth: str = "headline"


@dataclass(frozen=True)
class SentimentRequest:
    ticker: str
    items: list[SentimentInput]


@dataclass(frozen=True)
class SentimentItem:
    sentiment: str
    score: float


@dataclass(frozen=True)
class SentimentResult:
    provider: str
    items: list[SentimentItem]

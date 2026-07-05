from dataclasses import dataclass


@dataclass(frozen=True)
class Headline:
    ticker: str
    title: str
    link: str
    source: str
    published_at: str = ""
    article_text: str = ""
    analysis_depth: str = "headline"

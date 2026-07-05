from datetime import timedelta
import logging

import requests
from scrapy.selector import Selector

from backend.services.news.cache import HeadlineCache
from backend.services.news.finviz_spider import parse_finviz_headlines

logger = logging.getLogger(__name__)


class NewsProvider:
    name = "news"

    def get_headlines(self, ticker: str):
        raise NotImplementedError


def extract_article_text(html: str, limit: int = 2500) -> str:
    selector = Selector(text=html)
    paragraphs = []
    for paragraph in selector.css("article p::text, main p::text, p::text").getall():
        text = " ".join(paragraph.split())
        if len(text) >= 40:
            paragraphs.append(text)
    combined = " ".join(paragraphs)
    return combined[:limit].strip()


class ScrapyNewsProvider(NewsProvider):
    name = "scrapy_finviz"

    def __init__(self, cache=None, get=None, timeout=8):
        self.cache = cache or HeadlineCache(ttl=timedelta(minutes=5))
        self.get = get or requests.get
        self.timeout = timeout

    def _with_article_text(self, headline):
        try:
            response = self.get(headline.link, timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            article_text = extract_article_text(response.text)
        except requests.RequestException as exc:
            logger.debug("Article fetch failed for %s: %s", headline.link, exc)
            article_text = ""

        if not article_text:
            return headline

        return type(headline)(
            ticker=headline.ticker,
            title=headline.title,
            link=headline.link,
            source=headline.source,
            published_at=headline.published_at,
            article_text=article_text,
            analysis_depth="article",
        )

    def get_headlines(self, ticker: str):
        cached = self.cache.get(ticker)
        if cached is not None:
            return cached

        url = f"https://finviz.com/quote.ashx?t={ticker.upper()}"
        try:
            response = self.get(url, timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            headlines = [self._with_article_text(headline) for headline in parse_finviz_headlines(response.text, ticker)]
        except requests.RequestException as exc:
            logger.debug("FinViz Scrapy provider failed for %s: %s", ticker, exc)
            headlines = []

        self.cache.set(ticker, headlines)
        return headlines

from urllib.parse import urlparse

import scrapy
from scrapy.selector import Selector

from backend.services.news.models import Headline


def source_name(url: str) -> str:
    domain = urlparse(url).netloc.replace("www.", "")
    if "finance.yahoo" in domain:
        return "Yahoo Finance"
    if "motleyfool" in domain or "fool.com" in domain:
        return "Motley Fool"
    if "seekingalpha" in domain:
        return "Seeking Alpha"
    if "marketwatch" in domain:
        return "MarketWatch"
    if "benzinga" in domain:
        return "Benzinga"
    if "barrons" in domain:
        return "Barron's"
    if "bloomberg" in domain:
        return "Bloomberg"
    if "cnbc" in domain:
        return "CNBC"
    if "wsj" in domain:
        return "WSJ"
    if "finviz" in domain:
        return "FinViz"
    return domain.capitalize() or "News"


def parse_finviz_headlines(html: str, ticker: str, limit: int = 30) -> list[Headline]:
    selector = Selector(text=html)
    headlines = []
    for row in selector.css("#news-table tr"):
        anchor = row.css("a")
        title = (anchor.css("::text").get() or "").strip()
        link = (anchor.css("::attr(href)").get() or "").strip()
        if not title or not link:
            continue
        if not link.startswith("http"):
            link = "https://finviz.com/" + link.lstrip("/")

        raw_time = " ".join(part.strip() for part in row.css("td::text").getall() if part.strip())
        headlines.append(
            Headline(
                ticker=ticker.upper(),
                title=title,
                link=link,
                source=source_name(link),
                published_at=raw_time,
            )
        )
        if len(headlines) >= limit:
            break
    return headlines


class FinVizNewsSpider(scrapy.Spider):
    name = "finviz_news"

    def __init__(self, ticker: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticker = ticker.upper()
        self.start_urls = [f"https://finviz.com/quote.ashx?t={self.ticker}"]

    def parse(self, response):
        for headline in parse_finviz_headlines(response.text, self.ticker):
            yield headline.__dict__

from datetime import datetime, timedelta, timezone

from backend.services.news.cache import HeadlineCache
from backend.services.news.finviz_spider import parse_finviz_headlines
from backend.services.news.models import Headline
from backend.services.news.provider import ScrapyNewsProvider, extract_article_text


def test_parse_finviz_headlines_normalizes_rows():
    html = """
    <table id="news-table">
      <tr><td>Today 08:00AM</td><td><a href="https://finance.yahoo.com/news/aapl">Apple expands AI services</a></td></tr>
      <tr><td>09:00AM</td><td><a href="/quote.ashx?t=AAPL">Relative link</a></td></tr>
    </table>
    """

    headlines = parse_finviz_headlines(html, "AAPL")

    assert headlines == [
        Headline(
            ticker="AAPL",
            title="Apple expands AI services",
            link="https://finance.yahoo.com/news/aapl",
            source="Yahoo Finance",
            published_at="Today 08:00AM",
        ),
        Headline(
            ticker="AAPL",
            title="Relative link",
            link="https://finviz.com/quote.ashx?t=AAPL",
            source="FinViz",
            published_at="09:00AM",
        ),
    ]


def test_headline_cache_returns_recent_values_and_expires_old_values():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cache = HeadlineCache(ttl=timedelta(minutes=30), clock=lambda: now)
    headlines = [Headline(ticker="AAPL", title="One", link="https://example.com", source="Example", published_at="")]

    cache.set("aapl", headlines)

    assert cache.get("AAPL") == headlines

    cache.clock = lambda: now + timedelta(minutes=31)

    assert cache.get("AAPL") is None


def test_scrapy_news_provider_uses_five_minute_cache_for_polite_refetching():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cache = HeadlineCache(ttl=timedelta(minutes=5), clock=lambda: now)
    calls = []

    class FakeResponse:
        text = """
        <table id="news-table">
          <tr><td>Today</td><td><a href="https://example.com/aapl">Cached headline</a></td></tr>
        </table>
        """

        def raise_for_status(self):
            return None

    def fake_get(url, timeout, headers):
        calls.append(url)
        return FakeResponse()

    provider = ScrapyNewsProvider(cache=cache, get=fake_get)

    first = provider.get_headlines("AAPL")
    second = provider.get_headlines("AAPL")

    assert len(calls) == 2
    assert second == first

    cache.clock = lambda: now + timedelta(minutes=6)
    provider.get_headlines("AAPL")

    assert len(calls) == 4


def test_extract_article_text_collects_readable_paragraphs_with_limit():
    html = """
    <html>
      <body>
        <script>ignore me</script>
        <p>Apple reported stronger revenue than analysts expected.</p>
        <p>Management said services demand remained resilient.</p>
      </body>
    </html>
    """

    text = extract_article_text(html, limit=80)

    assert text == "Apple reported stronger revenue than analysts expected. Management said services"


def test_scrapy_news_provider_enriches_headlines_with_article_text_when_available():
    calls = []

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    def fake_get(url, timeout, headers):
        calls.append(url)
        if "finviz" in url:
            return FakeResponse(
                """
                <table id="news-table">
                  <tr><td>Today</td><td><a href="https://example.com/aapl">Headline only</a></td></tr>
                </table>
                """
            )
        return FakeResponse("<p>Full article context says guidance improved materially.</p>")

    provider = ScrapyNewsProvider(cache=HeadlineCache(ttl=timedelta(minutes=5)), get=fake_get)

    headlines = provider.get_headlines("AAPL")

    assert headlines[0].article_text == "Full article context says guidance improved materially."
    assert headlines[0].analysis_depth == "article"
    assert calls == ["https://finviz.com/quote.ashx?t=AAPL", "https://example.com/aapl"]

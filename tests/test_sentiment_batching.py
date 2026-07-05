from backend.services.sentiment.base import SentimentProviderError
from backend.services.sentiment.batching import BatchingSentimentProvider
from backend.services.sentiment.models import SentimentInput, SentimentItem, SentimentRequest, SentimentResult


class RecordingProvider:
    name = "recording"

    def __init__(self):
        self.requests = []

    def analyze(self, request):
        self.requests.append(request)
        return SentimentResult(
            provider=self.name,
            items=[SentimentItem(sentiment="Bullish", score=index) for index, _ in enumerate(request.items)],
        )

    def is_available(self):
        return True


def test_batching_provider_splits_large_sentiment_requests():
    provider = RecordingProvider()
    batching = BatchingSentimentProvider(provider, batch_size=3)
    request = SentimentRequest(
        ticker="AVGO",
        items=[SentimentInput(title=f"Headline {index}") for index in range(8)],
    )

    result = batching.analyze(request)

    assert [len(call.items) for call in provider.requests] == [3, 3, 2]
    assert result.provider == "recording"
    assert len(result.items) == 8


def test_batching_provider_truncates_article_context():
    provider = RecordingProvider()
    batching = BatchingSentimentProvider(provider, batch_size=3, max_article_chars=20)
    request = SentimentRequest(
        ticker="AVGO",
        items=[SentimentInput(title="Headline", article_text="x" * 100, analysis_depth="article")],
    )

    batching.analyze(request)

    assert provider.requests[0].items[0].article_text == "x" * 20


def test_batching_provider_limits_items_sent_to_model():
    provider = RecordingProvider()
    batching = BatchingSentimentProvider(provider, batch_size=2, max_items=5)
    request = SentimentRequest(
        ticker="AVGO",
        items=[SentimentInput(title=f"Headline {index}") for index in range(8)],
    )

    result = batching.analyze(request)

    assert [len(call.items) for call in provider.requests] == [2, 2, 1]
    assert len(result.items) == 5


def test_batching_provider_keeps_partial_results_when_one_item_fails():
    class PartiallyFailingProvider:
        name = "ollama"

        def __init__(self):
            self.calls = 0

        def analyze(self, request):
            self.calls += 1
            if self.calls == 2:
                raise SentimentProviderError("bad item")
            return SentimentResult(provider=self.name, items=[SentimentItem(sentiment="Bullish", score=8)])

        def is_available(self):
            return True

    provider = PartiallyFailingProvider()
    batching = BatchingSentimentProvider(provider, batch_size=1)
    request = SentimentRequest(
        ticker="AVGO",
        items=[SentimentInput(title="A"), SentimentInput(title="B"), SentimentInput(title="C")],
    )

    result = batching.analyze(request)

    assert result.provider == "ollama"
    assert [item.sentiment for item in result.items] == ["Bullish", "Neutral", "Bullish"]

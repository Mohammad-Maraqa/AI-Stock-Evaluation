from dataclasses import replace

from backend.services.sentiment.base import SentimentProvider, SentimentProviderError
from backend.services.sentiment.models import SentimentItem, SentimentRequest, SentimentResult


class BatchingSentimentProvider(SentimentProvider):
    def __init__(
        self,
        provider: SentimentProvider,
        batch_size: int = 1,
        max_article_chars: int = 300,
        max_items: int = 10,
    ):
        self.provider = provider
        self.batch_size = batch_size
        self.max_article_chars = max_article_chars
        self.max_items = max_items
        self.name = provider.name

    def analyze(self, request: SentimentRequest) -> SentimentResult:
        if not request.items:
            return SentimentResult(provider=self.name, items=[])

        all_items = []
        provider_name = self.name
        trimmed_items = [
            replace(item, article_text=item.article_text[: self.max_article_chars])
            for item in request.items[: self.max_items]
        ]

        for start in range(0, len(trimmed_items), self.batch_size):
            batch = trimmed_items[start : start + self.batch_size]
            try:
                result = self.provider.analyze(SentimentRequest(ticker=request.ticker, items=batch))
                provider_name = result.provider
                all_items.extend(result.items[: len(batch)])
            except SentimentProviderError:
                all_items.extend(SentimentItem(sentiment="Neutral", score=0) for _ in batch)

        return SentimentResult(provider=provider_name, items=all_items)

    def is_available(self) -> bool:
        return self.provider.is_available()

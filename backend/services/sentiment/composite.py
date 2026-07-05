from backend.services.sentiment.base import SentimentProvider, SentimentProviderError
from backend.services.sentiment.models import SentimentResult


class CompositeSentimentProvider(SentimentProvider):
    name = "auto"

    def __init__(self, providers):
        self.providers = list(providers)

    def analyze(self, request) -> SentimentResult:
        last_error = None
        for provider in self.providers:
            try:
                return provider.analyze(request)
            except SentimentProviderError as exc:
                last_error = exc
                continue
        raise SentimentProviderError(f"No sentiment provider available: {last_error}")

    def is_available(self) -> bool:
        return any(provider.is_available() for provider in self.providers)

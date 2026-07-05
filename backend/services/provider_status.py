import os

import config  # noqa: F401 - loads project-local .env before reading settings
from backend.schemas import ProviderStatus, ProvidersResponse
from backend.services.sentiment.ollama_provider import OllamaSentimentProvider


class ProviderStatusService:
    def __init__(self, ollama_provider=None):
        self.ollama_provider = ollama_provider or OllamaSentimentProvider(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            model=os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
        )

    @classmethod
    def from_environment(cls):
        return cls()

    def get_status(self):
        ollama_available = self.ollama_provider.is_available()
        model = getattr(self.ollama_provider, "model", "unknown model")
        base_url = getattr(self.ollama_provider, "base_url", "unknown URL")
        ollama_detail = (
            f"reachable ({model} at {base_url})"
            if ollama_available
            else f"not reachable ({model} at {base_url}); start Ollama and install the configured model"
        )
        return ProvidersResponse(
            ollama=ProviderStatus(available=ollama_available, detail=ollama_detail),
            news=ProviderStatus(available=True, detail="scrapy_finviz configured"),
            market_data=ProviderStatus(available=True, detail="yfinance configured"),
        )

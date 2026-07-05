import requests

from backend.services.sentiment.base import SentimentProvider, SentimentProviderError
from backend.services.sentiment.json_utils import parse_sentiment_payload, sentiment_prompt


class OllamaSentimentProvider(SentimentProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, post=None, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.post = post or requests.post
        self.timeout = timeout

    def analyze(self, request):
        last_error = None
        for correction in (False, True):
            try:
                response = self.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": sentiment_prompt(request.ticker, request.items, correction)}],
                        "temperature": 0,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return parse_sentiment_payload(self.name, content)
            except (KeyError, TypeError, requests.RequestException, SentimentProviderError, RuntimeError) as exc:
                last_error = exc
        raise SentimentProviderError(f"Ollama sentiment failed: {last_error}")

    def is_available(self) -> bool:
        try:
            response = requests.get(self.base_url.replace("/v1", "") + "/api/tags", timeout=2)
            return response.status_code < 500
        except requests.RequestException:
            return False

import json

from backend.services.sentiment.base import SentimentProviderError
from backend.services.sentiment.composite import CompositeSentimentProvider
from backend.services.sentiment.models import SentimentItem, SentimentResult
from backend.services.sentiment.models import SentimentInput, SentimentRequest
from backend.services.sentiment.json_utils import parse_sentiment_payload, sentiment_prompt
from backend.services.sentiment.ollama_provider import OllamaSentimentProvider


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("bad status")

    def json(self):
        return self._payload


def test_ollama_provider_parses_strict_json_response():
    calls = []

    def post(url, json, timeout):
        calls.append((url, json, timeout))
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"analysis":[{"sentiment":"Bullish","score":8}]}'
                        }
                    }
                ]
            }
        )

    provider = OllamaSentimentProvider(base_url="http://localhost:11434/v1", model="qwen2.5:7b", post=post)
    result = provider.analyze(SentimentRequest(ticker="AAPL", items=[SentimentInput(title="Apple expands AI services")]))

    assert result.provider == "ollama"
    assert result.items[0].sentiment == "Bullish"
    assert result.items[0].score == 8
    assert calls[0][0] == "http://localhost:11434/v1/chat/completions"


def test_ollama_provider_retries_malformed_json_once():
    responses = [
        FakeResponse({"choices": [{"message": {"content": "not-json"}}]}),
        FakeResponse({"choices": [{"message": {"content": '{"analysis":[{"sentiment":"Neutral","score":1}]}'}}]}),
    ]

    def post(url, json, timeout):
        return responses.pop(0)

    provider = OllamaSentimentProvider(base_url="http://localhost:11434/v1", model="qwen2.5:7b", post=post)
    result = provider.analyze(SentimentRequest(ticker="AAPL", items=[SentimentInput(title="Apple headline")]))

    assert result.items[0].sentiment == "Neutral"
    assert result.items[0].score == 1


def test_composite_sentiment_provider_falls_back_to_next_provider():
    class BrokenProvider:
        name = "broken"

        def analyze(self, request):
            raise SentimentProviderError("offline")

        def is_available(self):
            return False

    class WorkingProvider:
        name = "working"

        def analyze(self, request):
            return SentimentResult(provider="working", items=[SentimentItem(sentiment="Bearish", score=7)])

        def is_available(self):
            return True

    provider = CompositeSentimentProvider([BrokenProvider(), WorkingProvider()])
    result = provider.analyze(SentimentRequest(ticker="AAPL", items=[SentimentInput(title="Apple headline")]))

    assert result.provider == "working"
    assert result.items[0].sentiment == "Bearish"


def test_sentiment_prompt_prefers_article_text_and_marks_headline_fallback():
    prompt = sentiment_prompt(
        "AAPL",
        [
            SentimentInput(title="Headline A", article_text="Article A says margins improved."),
            SentimentInput(title="Headline B"),
        ],
    )

    assert "Article A says margins improved." in prompt
    assert '"analysis_depth": "article"' in prompt
    assert '"analysis_depth": "headline"' in prompt
    assert "Headline B" in prompt


def test_sentiment_parser_accepts_markdown_fenced_json():
    result = parse_sentiment_payload(
        "ollama",
        '```json\n{"analysis":[{"sentiment":"Bullish","score":8}]}\n```',
    )

    assert result.items[0].sentiment == "Bullish"
    assert result.items[0].score == 8


def test_sentiment_parser_accepts_single_wrapped_payload_list():
    result = parse_sentiment_payload(
        "ollama",
        '[{"analysis":[{"sentiment":"Bearish","score":7}]}]',
    )

    assert result.items[0].sentiment == "Bearish"
    assert result.items[0].score == 7


def test_sentiment_parser_accepts_direct_sentiment_item_list():
    result = parse_sentiment_payload(
        "ollama",
        '```json\n[{"sentiment":"Bullish","score":8}]\n```',
    )

    assert result.items[0].sentiment == "Bullish"
    assert result.items[0].score == 8


def test_sentiment_parser_accepts_direct_sentiment_item_object():
    result = parse_sentiment_payload(
        "ollama",
        '{"sentiment":"Neutral","score":2}',
    )

    assert result.items[0].sentiment == "Neutral"
    assert result.items[0].score == 2

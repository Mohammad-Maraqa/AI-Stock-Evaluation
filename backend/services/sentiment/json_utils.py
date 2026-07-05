import json
import re

from backend.services.sentiment.base import SentimentProviderError
from backend.services.sentiment.models import SentimentItem, SentimentResult


VALID_SENTIMENTS = {"Bullish", "Bearish", "Neutral"}


def _clean_json_content(content: str) -> str:
    cleaned = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    return fenced.group(1).strip() if fenced else cleaned


def _normalize_payload(payload):
    if isinstance(payload, list):
        if len(payload) == 1 and isinstance(payload[0], dict) and "analysis" in payload[0]:
            return payload[0]
        if all(isinstance(item, dict) and "sentiment" in item for item in payload):
            return {"analysis": payload}
    if isinstance(payload, dict) and "analysis" not in payload and "sentiment" in payload:
        return {"analysis": [payload]}
    return payload


def parse_sentiment_payload(provider: str, content: str) -> SentimentResult:
    try:
        payload = _normalize_payload(json.loads(_clean_json_content(content)))
    except json.JSONDecodeError as exc:
        raise SentimentProviderError("Model returned malformed JSON") from exc

    if not isinstance(payload, dict):
        raise SentimentProviderError("Model JSON must be an object")

    analysis = payload.get("analysis")
    if not isinstance(analysis, list):
        raise SentimentProviderError("Model JSON does not include an analysis list")

    items = []
    for item in analysis:
        sentiment = str(item.get("sentiment", "Neutral")).strip()
        if "bullish" in sentiment.lower():
            sentiment = "Bullish"
        elif "bearish" in sentiment.lower():
            sentiment = "Bearish"
        else:
            sentiment = "Neutral"

        try:
            score = float(item.get("score", 0))
        except (TypeError, ValueError):
            score = 0
        items.append(SentimentItem(sentiment=sentiment if sentiment in VALID_SENTIMENTS else "Neutral", score=max(0, min(10, score))))

    return SentimentResult(provider=provider, items=items)


def _sentiment_contexts(items):
    contexts = []
    for item in items:
        text = item.article_text.strip() if item.article_text else item.title
        depth = "article" if item.article_text else "headline"
        contexts.append({"title": item.title, "analysis_depth": depth, "text": text})
    return contexts


def sentiment_prompt(ticker: str, items, correction: bool = False) -> str:
    strict = "The prior response was invalid. " if correction else ""
    return (
        f'{strict}Analyze these news items for "{ticker}". '
        "Classify each as Bullish, Bearish, or Neutral and assign an impact score from 0 to 10. "
        "Prefer article text when analysis_depth is article. Use headline text only when article text is unavailable. "
        'Return JSON only in this exact shape: {"analysis":[{"sentiment":"Bullish","score":8}]}. '
        f"News items: {json.dumps(_sentiment_contexts(items))}"
    )

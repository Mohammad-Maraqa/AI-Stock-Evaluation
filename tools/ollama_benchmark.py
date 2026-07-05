import argparse
import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import requests

from backend.services.sentiment.json_utils import parse_sentiment_payload, sentiment_prompt
from backend.services.sentiment.models import SentimentInput

DEFAULT_MODELS = ["qwen2.5:7b", "llama3.1:8b", "mistral", "gemma"]


@dataclass(frozen=True)
class BenchmarkResult:
    model: str
    headline: str
    valid_json: bool
    sentiment: str
    latency_ms: int
    error: str = ""


def load_headlines(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [item["headline"] for item in payload["headlines"]]


def evaluate_model(model: str, headlines: list[str], base_url: str, post=requests.post) -> list[BenchmarkResult]:
    results = []
    for headline in headlines:
        started = time.perf_counter()
        try:
            response = post(
                f"{base_url.rstrip('/')}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": sentiment_prompt("BENCH", [SentimentInput(title=headline)], correction=False)}],
                    "temperature": 0,
                },
                timeout=45,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = parse_sentiment_payload(model, content)
            sentiment = parsed.items[0].sentiment if parsed.items else ""
            results.append(
                BenchmarkResult(
                    model=model,
                    headline=headline,
                    valid_json=True,
                    sentiment=sentiment,
                    latency_ms=round((time.perf_counter() - started) * 1000),
                )
            )
        except (requests.RequestException, KeyError, TypeError, ValueError, RuntimeError) as exc:
            results.append(
                BenchmarkResult(
                    model=model,
                    headline=headline,
                    valid_json=False,
                    sentiment="",
                    latency_ms=round((time.perf_counter() - started) * 1000),
                    error=str(exc),
                )
            )
    return results


def summarize_results(results: list[BenchmarkResult]):
    grouped = defaultdict(list)
    for result in results:
        grouped[result.model].append(result)

    summary = {}
    for model, model_results in grouped.items():
        total = len(model_results)
        valid = sum(result.valid_json for result in model_results)
        failures = total - valid
        average_latency = round(sum(result.latency_ms for result in model_results) / total) if total else 0
        sentiment_counts = Counter(result.sentiment for result in model_results if result.sentiment)
        dominant_count = sentiment_counts.most_common(1)[0][1] if sentiment_counts else 0
        summary[model] = {
            "total": total,
            "json_validity_rate": valid / total if total else 0,
            "failure_rate": failures / total if total else 0,
            "average_latency_ms": average_latency,
            "sentiment_consistency": dominant_count / valid if valid else 0,
        }
    return summary


def recommended_model(summary):
    if not summary:
        return ""
    return sorted(
        summary.items(),
        key=lambda item: (
            -item[1]["json_validity_rate"],
            item[1]["failure_rate"],
            -item[1]["sentiment_consistency"],
            item[1]["average_latency_ms"],
        ),
    )[0][0]


def percent(value: float) -> str:
    return f"{round(value * 100)}%"


def render_report(results: list[BenchmarkResult]) -> str:
    summary = summarize_results(results)
    recommendation = recommended_model(summary)
    lines = [
        "# Ollama Sentiment Benchmark Report",
        "",
        f"Recommended default model: `{recommendation}`" if recommendation else "Recommended default model: unavailable",
        "",
        "| Model | JSON Validity | Failure Rate | Avg Latency | Sentiment Consistency |",
        "|---|---:|---:|---:|---:|",
    ]
    for model, stats in sorted(summary.items()):
        lines.append(
            f"| {model} | {percent(stats['json_validity_rate'])} | {percent(stats['failure_rate'])} | "
            f"{stats['average_latency_ms']} ms | {percent(stats['sentiment_consistency'])} |"
        )
    lines.extend(
        [
            "",
            "This report is generated from local Ollama responses only. It does not call external AI APIs.",
        ]
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Benchmark local Ollama sentiment models.")
    parser.add_argument("--fixture", default="tools/ollama_headlines.json")
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    parser.add_argument("--report", default="docs/OLLAMA_BENCHMARK.md")
    args = parser.parse_args()

    headlines = load_headlines(Path(args.fixture))
    results = []
    for model in args.models:
        results.extend(evaluate_model(model, headlines, args.base_url))
    report = render_report(results)
    Path(args.report).write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()

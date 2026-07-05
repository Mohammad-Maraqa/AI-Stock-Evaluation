from tools.ollama_benchmark import BenchmarkResult, summarize_results, render_report


def test_summarize_results_records_json_validity_latency_and_failures():
    results = [
        BenchmarkResult(model="qwen2.5:7b", headline="A", valid_json=True, sentiment="Bullish", latency_ms=120, error=""),
        BenchmarkResult(model="qwen2.5:7b", headline="B", valid_json=False, sentiment="", latency_ms=80, error="bad json"),
        BenchmarkResult(model="mistral", headline="A", valid_json=True, sentiment="Bearish", latency_ms=220, error=""),
    ]

    summary = summarize_results(results)

    assert summary["qwen2.5:7b"]["json_validity_rate"] == 0.5
    assert summary["qwen2.5:7b"]["failure_rate"] == 0.5
    assert summary["qwen2.5:7b"]["average_latency_ms"] == 100
    assert summary["mistral"]["sentiment_consistency"] == 1.0


def test_render_report_recommends_highest_validity_then_lowest_latency_model():
    results = [
        BenchmarkResult(model="slow", headline="A", valid_json=True, sentiment="Bullish", latency_ms=300, error=""),
        BenchmarkResult(model="fast", headline="A", valid_json=True, sentiment="Bullish", latency_ms=100, error=""),
        BenchmarkResult(model="broken", headline="A", valid_json=False, sentiment="", latency_ms=50, error="bad json"),
    ]

    report = render_report(results)

    assert "# Ollama Sentiment Benchmark Report" in report
    assert "Recommended default model: `fast`" in report
    assert "| fast | 100%" in report

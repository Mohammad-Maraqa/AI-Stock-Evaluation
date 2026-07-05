# Ollama Sentiment Benchmark Report

Run this local-only benchmark with:

```bash
.venv\Scripts\python.exe -m tools.ollama_benchmark
```

The script evaluates `qwen2.5:7b`, `llama3.1:8b`, `mistral`, and `gemma` against `tools/ollama_headlines.json`, then rewrites this report with JSON validity, latency, failure rate, sentiment consistency, and a recommended default model.

No external AI APIs are used.

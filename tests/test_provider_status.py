from backend.services.provider_status import ProviderStatusService


class OfflineOllamaProvider:
    model = "qwen2.5:7b"
    base_url = "http://localhost:11434/v1"

    def is_available(self):
        return False


def test_provider_status_explains_unreachable_ollama():
    status = ProviderStatusService(ollama_provider=OfflineOllamaProvider()).get_status()

    assert status.ollama.available is False
    assert "not reachable" in status.ollama.detail
    assert "qwen2.5:7b" in status.ollama.detail
    assert "localhost:11434" in status.ollama.detail

class SentimentProviderError(RuntimeError):
    pass


class SentimentProvider:
    name = "sentiment"

    def analyze(self, request):
        raise NotImplementedError

    def is_available(self) -> bool:
        return True

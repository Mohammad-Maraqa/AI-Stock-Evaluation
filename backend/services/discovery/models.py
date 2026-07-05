from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiscoveryWarning:
    source: str
    message: str


@dataclass
class DiscoveryCandidate:
    ticker: str
    company: str = ""
    sector: str = ""
    industry: str = ""
    source: str = ""
    sources: list[str] = field(default_factory=list)
    source_consensus: int = 1

    def __post_init__(self):
        self.ticker = self.ticker.strip().upper()
        if not self.sources and self.source:
            self.sources = [self.source]

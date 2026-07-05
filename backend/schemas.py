from typing import Any

from pydantic import BaseModel, Field


class CompanyInfo(BaseModel):
    name: str
    sector: str = ""
    industry: str = ""


class CompositeResponse(BaseModel):
    base_score: float
    final_score: float
    rating: str
    insider_booster: float = 0


class PillarResponse(BaseModel):
    score: float
    meta: dict[str, Any] = Field(default_factory=dict)


class HeadlineResponse(BaseModel):
    ticker: str
    title: str
    link: str
    source: str
    published_at: str = ""
    sentiment: str | None = None
    score: float | None = None
    article_text: str = ""
    analysis_depth: str = "headline"


class ChartResponse(BaseModel):
    candles: list[dict[str, Any]] = Field(default_factory=list)
    overlays: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class InsiderActivity(BaseModel):
    buys: int = 0
    sells: int = 0
    net: int = 0
    booster: float = 0
    summary: str = "No insider activity signal available"


class PiotroskiSummary(BaseModel):
    raw_score: int = 0
    max_score: int = 0
    score: float | None = None
    signals: dict[str, int] = Field(default_factory=dict)


class DerivativesSummary(BaseModel):
    pcr_vol: float | None = None
    pcr_oi: float | None = None
    short_float: float | None = None
    short_ratio: float | None = None
    avg_iv: float | None = None
    technical_trend: bool | None = None
    risk_label: str = "Unavailable"


class DataQualityResponse(BaseModel):
    market_data: str = "ok"
    news: str = "ok"
    sentiment: str = "ok"
    fundamentals: str = "ok"
    derivatives: str = "ok"
    insider_activity: str = "ok"
    confidence: int = 100
    warnings: list[str] = Field(default_factory=list)


class FundamentalCategoryResponse(BaseModel):
    name: str
    status: str = "unavailable"
    score: float = 0
    bullishness: int = 0
    bearishness: int = 100
    explanation: str = "Not enough data available."
    metrics: dict[str, Any] = Field(default_factory=dict)


class FundamentalAnalysisResponse(BaseModel):
    overall_score: int = 0
    bullishness: int = 0
    bearishness: int = 100
    summary: str = "Fundamental deep analysis is unavailable."
    warnings: list[str] = Field(default_factory=list)
    categories: list[FundamentalCategoryResponse] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    ticker: str
    company: CompanyInfo
    composite: CompositeResponse
    pillars: dict[str, PillarResponse]
    headlines: list[HeadlineResponse] = Field(default_factory=list)
    chart: ChartResponse | dict[str, Any] = Field(default_factory=ChartResponse)
    providers: dict[str, str]
    insider_activity: InsiderActivity = Field(default_factory=InsiderActivity)
    piotroski: PiotroskiSummary = Field(default_factory=PiotroskiSummary)
    derivatives: DerivativesSummary = Field(default_factory=DerivativesSummary)
    competitors: list[dict[str, Any]] = Field(default_factory=list)
    data_quality: DataQualityResponse = Field(default_factory=DataQualityResponse)
    fundamental_analysis: FundamentalAnalysisResponse = Field(default_factory=FundamentalAnalysisResponse)


class ProviderStatus(BaseModel):
    available: bool
    detail: str


class ProvidersResponse(BaseModel):
    ollama: ProviderStatus
    news: ProviderStatus
    market_data: ProviderStatus


class WatchlistAnalyzeRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)


class WatchlistAnalyzeError(BaseModel):
    ticker: str
    detail: str


class WatchlistAnalyzeResponse(BaseModel):
    items: list[AnalysisResponse] = Field(default_factory=list)
    errors: list[WatchlistAnalyzeError] = Field(default_factory=list)


class OpportunityThemeResponse(BaseModel):
    id: str
    name: str
    description: str


class OpportunityThemesResponse(BaseModel):
    themes: list[OpportunityThemeResponse] = Field(default_factory=list)


class OpportunitySourceWarning(BaseModel):
    source: str
    message: str


class OpportunityScoreBreakdown(BaseModel):
    fundamental: float
    valuation: float
    sentiment: float
    technical: float
    underhype: float
    data_quality: float


class OpportunityResultResponse(BaseModel):
    ticker: str
    company: str
    opportunity_score: float
    label: str
    theme_relevance_score: float
    discovery_confidence: str
    source_consensus: int
    scores: OpportunityScoreBreakdown
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class OpportunityScanMetadata(BaseModel):
    discovered_count: int = 0
    validated_count: int = 0
    filtered_count: int = 0
    analyzed_count: int = 0
    returned_count: int = 0
    duration_ms: int = 0


class OpportunityScanResponse(BaseModel):
    mode: str
    theme: dict[str, str] | None = None
    etf: str | None = None
    source_warnings: list[OpportunitySourceWarning] = Field(default_factory=list)
    candidate_count: int = 0
    analyzed_count: int = 0
    scan_metadata: OpportunityScanMetadata = Field(default_factory=OpportunityScanMetadata)
    results: list[OpportunityResultResponse] = Field(default_factory=list)

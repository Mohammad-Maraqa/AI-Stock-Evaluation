from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.api.dependencies import get_analysis_service, get_opportunity_finder_service, get_provider_status_service
from backend.schemas import (
    AnalysisResponse,
    OpportunityScanResponse,
    OpportunityThemesResponse,
    ProvidersResponse,
    WatchlistAnalyzeRequest,
    WatchlistAnalyzeResponse,
    WatchlistAnalyzeError,
)
from backend.services.analysis_service import AnalysisService
from backend.services.opportunity_finder_service import OpportunityFinderService
from backend.services.provider_status import ProviderStatusService


def create_app() -> FastAPI:
    app = FastAPI(title="AI Stock Evaluation API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/providers/status", response_model=ProvidersResponse)
    def providers_status(
        service: ProviderStatusService = Depends(get_provider_status_service),
    ):
        return service.get_status()

    @app.get("/api/analyze", response_model=AnalysisResponse)
    def analyze(
        ticker: str = Query(..., min_length=1, max_length=40),
        service: AnalysisService = Depends(get_analysis_service),
    ):
        result = service.analyze(ticker.strip())
        if result is None:
            raise HTTPException(status_code=404, detail=f"Could not find data for '{ticker}'.")
        return result

    @app.get("/api/opportunity/themes", response_model=OpportunityThemesResponse)
    def opportunity_themes(
        service: OpportunityFinderService = Depends(get_opportunity_finder_service),
    ):
        return OpportunityThemesResponse(themes=service.list_themes())

    @app.get("/api/opportunity/scan", response_model=OpportunityScanResponse)
    def opportunity_scan(
        theme: str | None = Query(None, min_length=1, max_length=80),
        etf: str | None = Query(None, min_length=1, max_length=12),
        limit: int = Query(10, ge=1),
        max_candidates: int = Query(25, ge=1),
        service: OpportunityFinderService = Depends(get_opportunity_finder_service),
    ):
        if not theme and not etf:
            raise HTTPException(status_code=400, detail="At least one of 'theme' or 'etf' is required.")
        try:
            return service.scan(
                theme_id=theme.strip() if theme else None,
                etf=etf.strip().upper() if etf else None,
                limit=min(limit, 25),
                max_candidates=min(max_candidates, 50),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/watchlist/analyze", response_model=WatchlistAnalyzeResponse)
    def analyze_watchlist(
        request: WatchlistAnalyzeRequest,
        service: AnalysisService = Depends(get_analysis_service),
    ):
        items = []
        errors = []
        seen = set()
        for raw_ticker in request.tickers:
            ticker = raw_ticker.strip()
            if not ticker:
                continue
            key = ticker.upper()
            if key in seen:
                continue
            seen.add(key)
            result = service.analyze(ticker)
            if result is None:
                errors.append(WatchlistAnalyzeError(ticker=key, detail=f"Could not find data for '{ticker}'."))
            else:
                items.append(result)
        return WatchlistAnalyzeResponse(items=items, errors=errors)

    return app


app = create_app()

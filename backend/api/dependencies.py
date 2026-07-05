from functools import lru_cache

from backend.services.analysis_service import AnalysisService
from backend.services.opportunity_finder_service import OpportunityFinderService
from backend.services.provider_status import ProviderStatusService


@lru_cache(maxsize=1)
def get_analysis_service() -> AnalysisService:
    return AnalysisService.from_environment()


@lru_cache(maxsize=1)
def get_provider_status_service() -> ProviderStatusService:
    return ProviderStatusService.from_environment()


@lru_cache(maxsize=1)
def get_opportunity_finder_service() -> OpportunityFinderService:
    return OpportunityFinderService.from_environment()

import type { AnalysisResponse, OpportunityScanResponse, OpportunityThemesResponse, WatchlistResponse } from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export async function fetchAnalysis(ticker: string): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE}/api/analyze?ticker=${encodeURIComponent(ticker)}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Analysis failed' }));
    throw new Error(body.detail ?? 'Analysis failed');
  }
  return response.json();
}

export async function fetchWatchlistAnalysis(tickers: string[]): Promise<WatchlistResponse> {
  const response = await fetch(`${API_BASE}/api/watchlist/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tickers }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Watchlist analysis failed' }));
    throw new Error(body.detail ?? 'Watchlist analysis failed');
  }
  return response.json();
}

export async function fetchOpportunityThemes(): Promise<OpportunityThemesResponse> {
  const response = await fetch(`${API_BASE}/api/opportunity/themes`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Opportunity themes failed' }));
    throw new Error(body.detail ?? 'Opportunity themes failed');
  }
  return response.json();
}

export async function fetchOpportunityScan(params: {
  theme?: string;
  etf?: string;
  limit: number;
  maxCandidates: number;
}): Promise<OpportunityScanResponse> {
  const query = new URLSearchParams();
  if (params.theme) {
    query.set('theme', params.theme);
  }
  if (params.etf) {
    query.set('etf', params.etf);
  }
  query.set('limit', String(params.limit));
  query.set('max_candidates', String(params.maxCandidates));
  const response = await fetch(`${API_BASE}/api/opportunity/scan?${query.toString()}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Opportunity scan failed' }));
    throw new Error(body.detail ?? 'Opportunity scan failed');
  }
  return response.json();
}

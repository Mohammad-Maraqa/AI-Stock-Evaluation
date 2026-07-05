import { useState } from 'react';
import { fetchWatchlistAnalysis } from '../api';
import type { AnalysisResponse, WatchlistError } from '../types';

type PillarScores = AnalysisResponse['pillars'];

function pillarValue(pillars: PillarScores, key: keyof PillarScores) {
  return Math.round(pillars[key]?.score ?? 0);
}

export function WatchlistPanel() {
  const [draft, setDraft] = useState('');
  const [tickers, setTickers] = useState<string[]>([]);
  const [items, setItems] = useState<AnalysisResponse[]>([]);
  const [errors, setErrors] = useState<WatchlistError[]>([]);
  const [loading, setLoading] = useState(false);

  function addTicker() {
    const ticker = draft.trim().toUpperCase();
    if (!ticker || tickers.includes(ticker)) {
      setDraft('');
      return;
    }
    setTickers((current) => [...current, ticker]);
    setDraft('');
  }

  function removeTicker(ticker: string) {
    setTickers((current) => current.filter((item) => item !== ticker));
    setItems((current) => current.filter((item) => item.ticker !== ticker));
    setErrors((current) => current.filter((item) => item.ticker !== ticker));
  }

  async function refreshWatchlist() {
    if (tickers.length === 0) {
      return;
    }
    setLoading(true);
    try {
      const result = await fetchWatchlistAnalysis(tickers);
      setItems(result.items);
      setErrors(result.errors);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel watchlist-panel" aria-label="Watchlist">
      <div className="panel-heading">
        <span>Watchlist</span>
        <strong>{tickers.length}</strong>
      </div>
      <div className="watchlist-controls">
        <input
          aria-label="Watchlist ticker"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              addTicker();
            }
          }}
          placeholder="Add ticker"
        />
        <button type="button" onClick={addTicker}>Add ticker</button>
        <button type="button" onClick={refreshWatchlist} disabled={loading || tickers.length === 0}>
          {loading ? 'Refreshing...' : 'Refresh watchlist'}
        </button>
      </div>
      {tickers.length > 0 && (
        <div className="watchlist-tickers">
          {tickers.map((ticker) => (
            <button key={ticker} type="button" onClick={() => removeTicker(ticker)} aria-label={`Remove ${ticker}`}>
              {ticker} x
            </button>
          ))}
        </div>
      )}
      {items.length > 0 && (
        <div className="watchlist-table" role="table" aria-label="Watchlist Comparison">
          <h2>Watchlist Comparison</h2>
          <div className="watchlist-row watchlist-head" role="row">
            <span>Ticker</span>
            <span>Company</span>
            <span>Composite</span>
            <span>Pillars</span>
            <span>Confidence</span>
          </div>
          {items.map((item) => (
            <div className="watchlist-row" role="row" key={item.ticker}>
              <strong>{item.ticker}</strong>
              <span>{item.company.name}</span>
              <span>{item.composite.final_score.toFixed(1)}</span>
              <span>
                F {pillarValue(item.pillars, 'fundamental')} / S {pillarValue(item.pillars, 'sentiment')} / T{' '}
                {pillarValue(item.pillars, 'technical')} / D {pillarValue(item.pillars, 'derivative')}
              </span>
              <span>Confidence {item.data_quality.confidence}%</span>
            </div>
          ))}
        </div>
      )}
      {errors.length > 0 && (
        <ul className="quality-warnings">
          {errors.map((error) => (
            <li key={error.ticker}>{error.ticker}: {error.detail}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

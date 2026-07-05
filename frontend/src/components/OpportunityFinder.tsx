import { useEffect, useState } from 'react';
import { fetchOpportunityScan, fetchOpportunityThemes } from '../api';
import type { OpportunityScanResponse, OpportunityTheme } from '../types';
import { OpportunityResultCard } from './OpportunityResultCard';
import { ThemeSelector } from './ThemeSelector';

interface OpportunityFinderProps {
  onOpenAnalysis: (ticker: string) => void;
}

type ScanMode = 'theme' | 'etf';

export function OpportunityFinder({ onOpenAnalysis }: OpportunityFinderProps) {
  const [themes, setThemes] = useState<OpportunityTheme[]>([]);
  const [mode, setMode] = useState<ScanMode>('theme');
  const [theme, setTheme] = useState('');
  const [etf, setEtf] = useState('');
  const [limit, setLimit] = useState(10);
  const [maxCandidates, setMaxCandidates] = useState(25);
  const [scan, setScan] = useState<OpportunityScanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchOpportunityThemes()
      .then((response) => {
        if (cancelled) {
          return;
        }
        setThemes(response.themes);
        setTheme((current) => current || response.themes[0]?.id || '');
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Could not load themes');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function runScan() {
    setLoading(true);
    setError(null);
    try {
      setScan(await fetchOpportunityScan({
        theme: mode === 'theme' ? theme : undefined,
        etf: mode === 'etf' ? etf.trim().toUpperCase() : undefined,
        limit,
        maxCandidates,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Opportunity scan failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="opportunity-finder" aria-label="Opportunity Finder">
      <div className="panel opportunity-controls">
        <div className="panel-heading">
          <span>Opportunity Finder</span>
          <strong>{scan?.results.length ?? 0}</strong>
        </div>
        <p className="disclaimer">Research discovery tool, not financial advice.</p>
        <div className="mode-toggle" role="group" aria-label="Opportunity scan mode">
          <button type="button" className={mode === 'theme' ? 'active' : ''} onClick={() => setMode('theme')}>
            Scan by industry/theme
          </button>
          <button type="button" className={mode === 'etf' ? 'active' : ''} onClick={() => setMode('etf')}>
            Scan by ETF ticker
          </button>
        </div>
        <div className="opportunity-form-grid">
          {mode === 'theme' ? (
            <ThemeSelector themes={themes} value={theme} onChange={setTheme} />
          ) : (
            <label className="field-stack">
              <span>ETF ticker</span>
              <input aria-label="ETF ticker" value={etf} onChange={(event) => setEtf(event.target.value)} placeholder="SMH" />
            </label>
          )}
          <label className="field-stack">
            <span>Limit</span>
            <input aria-label="Result limit" type="number" min={1} max={25} value={limit} onChange={(event) => setLimit(Number(event.target.value))} />
          </label>
          <label className="field-stack">
            <span>Max candidates</span>
            <input
              aria-label="Max candidates"
              type="number"
              min={1}
              max={50}
              value={maxCandidates}
              onChange={(event) => setMaxCandidates(Number(event.target.value))}
            />
          </label>
          <button type="button" onClick={runScan} disabled={loading || (mode === 'theme' && !theme) || (mode === 'etf' && !etf.trim())}>
            {loading ? 'Scanning...' : 'Run scan'}
          </button>
        </div>
        {error && <div className="state-panel error">{error}</div>}
      </div>

      {loading && <div className="state-panel">Scanning opportunity universe...</div>}

      {scan && (
        <>
          <div className="summary-grid opportunity-metadata">
            <article>Discovered {scan.scan_metadata.discovered_count}</article>
            <article>Validated {scan.scan_metadata.validated_count}</article>
            <article>Filtered {scan.scan_metadata.filtered_count}</article>
            <article>Analyzed {scan.scan_metadata.analyzed_count}</article>
            <article>Returned {scan.scan_metadata.returned_count}</article>
            <article>{scan.scan_metadata.duration_ms} ms</article>
          </div>
          {scan.source_warnings.length > 0 && (
            <ul className="quality-warnings">
              {scan.source_warnings.map((warning) => (
                <li key={`${warning.source}-${warning.message}`}>{warning.source}: {warning.message}</li>
              ))}
            </ul>
          )}
          {scan.results.length === 0 ? (
            <div className="state-panel">No ranked candidates returned for this scan.</div>
          ) : (
            <div className="opportunity-results">
              {scan.results.map((result, index) => (
                <OpportunityResultCard key={result.ticker} rank={index + 1} result={result} onOpenAnalysis={onOpenAnalysis} />
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}

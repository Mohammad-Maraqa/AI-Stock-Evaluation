import { useState } from 'react';
import { fetchAnalysis } from './api';
import { AnalysisDetails } from './components/AnalysisDetails';
import { DataQualityPanel } from './components/DataQualityPanel';
import { FundamentalDeepAnalysis } from './components/FundamentalDeepAnalysis';
import { HeadlineList } from './components/HeadlineList';
import { OpportunityFinder } from './components/OpportunityFinder';
import { PillarPanel } from './components/PillarPanel';
import { ScoreSummary } from './components/ScoreSummary';
import { SearchForm } from './components/SearchForm';
import { TechnicalChart } from './components/TechnicalChart';
import { WatchlistPanel } from './components/WatchlistPanel';
import type { AnalysisResponse, PillarKey } from './types';
import './styles.css';

const pillarOrder: PillarKey[] = ['fundamental', 'sentiment', 'technical', 'derivative'];

export function App() {
  const [mode, setMode] = useState<'stock' | 'opportunity'>('stock');
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function analyze(ticker: string) {
    setMode('stock');
    setLoading(true);
    setError(null);
    try {
      setAnalysis(await fetchAnalysis(ticker));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <h1>AI Stock Evaluation</h1>
        <p>Refining market noise into institutional-grade clarity.</p>
        <nav className="app-mode-toggle" aria-label="App sections">
          <button type="button" className={mode === 'stock' ? 'active' : ''} onClick={() => setMode('stock')}>
            Stock Analysis
          </button>
          <button type="button" className={mode === 'opportunity' ? 'active' : ''} onClick={() => setMode('opportunity')}>
            Opportunity Finder
          </button>
        </nav>
        {mode === 'stock' && <SearchForm onSubmit={analyze} loading={loading} />}
      </header>

      {mode === 'opportunity' ? (
        <OpportunityFinder onOpenAnalysis={analyze} />
      ) : (
        <>
          {loading && <div className="state-panel">Fetching real-time analysis...</div>}
          {error && <div className="state-panel error">{error}</div>}

          {!analysis && !loading && !error && (
            <section className="intro-grid">
              <article>Fundamental analysis with transparent factor scoring.</article>
              <article>Scrapy-powered news collection with AI sentiment classification.</article>
              <article>Technical, options, and short-interest context in one workflow.</article>
            </section>
          )}

          <WatchlistPanel />

          {analysis && (
            <>
              <section className="company-heading">
                <h2>{analysis.ticker} <span>{analysis.company.name}</span></h2>
                <p>{[analysis.company.sector, analysis.company.industry].filter(Boolean).join(' / ')}</p>
              </section>
              <ScoreSummary analysis={analysis} />
              <DataQualityPanel quality={analysis.data_quality} />
              <FundamentalDeepAnalysis analysis={analysis.fundamental_analysis} />
              <AnalysisDetails
                insiderActivity={analysis.insider_activity}
                piotroski={analysis.piotroski}
                derivatives={analysis.derivatives}
              />
              <section className="dashboard-grid">
                <div className="pillar-stack">
                  {pillarOrder.map((key) => (
                    <PillarPanel key={key} name={key} pillar={analysis.pillars[key]} />
                  ))}
                  <HeadlineList headlines={analysis.headlines} />
                </div>
                <TechnicalChart chart={analysis.chart} />
              </section>
            </>
          )}
        </>
      )}
    </main>
  );
}

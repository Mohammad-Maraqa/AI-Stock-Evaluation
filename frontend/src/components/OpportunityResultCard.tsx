import type { OpportunityResult } from '../types';
import { OpportunityScoreBreakdown } from './OpportunityScoreBreakdown';

interface OpportunityResultCardProps {
  rank: number;
  result: OpportunityResult;
  onOpenAnalysis: (ticker: string) => void;
}

function renderList(items: string[], empty: string) {
  if (items.length === 0) {
    return <li>{empty}</li>;
  }
  return items.map((item) => <li key={item}>{item}</li>);
}

export function OpportunityResultCard({ rank, result, onOpenAnalysis }: OpportunityResultCardProps) {
  return (
    <article className="panel opportunity-result">
      <div className="opportunity-result-head">
        <div>
          <span>#{rank}</span>
          <h3>{result.ticker} <small>{result.company}</small></h3>
        </div>
        <strong>{result.opportunity_score.toFixed(1)}</strong>
      </div>
      <div className="opportunity-badges">
        <span>{result.label}</span>
        <span>Discovery Confidence: {result.discovery_confidence}</span>
        <span>Relevance {Math.round(result.theme_relevance_score)}</span>
        <span>Sources {result.source_consensus}</span>
      </div>
      <OpportunityScoreBreakdown scores={result.scores} />
      <div className="opportunity-detail-grid">
        <section>
          <h4>Reasons</h4>
          <ul>{renderList(result.reasons, 'No deterministic reason available.')}</ul>
        </section>
        <section>
          <h4>Risks</h4>
          <ul>{renderList(result.risks, 'No deterministic risk flag available.')}</ul>
        </section>
      </div>
      <div className="opportunity-footer">
        <span>{result.sources.join(' / ')}</span>
        <button type="button" onClick={() => onOpenAnalysis(result.ticker)} aria-label={`Open full analysis for ${result.ticker}`}>
          Open full analysis
        </button>
      </div>
    </article>
  );
}

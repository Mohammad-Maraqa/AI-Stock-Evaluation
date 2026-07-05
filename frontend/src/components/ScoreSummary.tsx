import type { AnalysisResponse } from '../types';

function ratingColor(score: number) {
  if (score >= 80) return '#f2ca50';
  if (score >= 60) return '#d4af37';
  if (score >= 40) return '#a89060';
  if (score >= 20) return '#ff8070';
  return '#ff4444';
}

export function ScoreSummary({ analysis }: { analysis: AnalysisResponse }) {
  const color = ratingColor(analysis.composite.final_score);

  return (
    <section className="summary-grid" aria-label="Score summary">
      <article className="metric-card" style={{ borderTopColor: color }}>
        <span>Composite Score</span>
        <strong style={{ color }}>{analysis.composite.final_score.toFixed(1)}<small>/100</small></strong>
      </article>
      <article className="metric-card" style={{ borderTopColor: color }}>
        <span>Signal Strength</span>
        <strong style={{ color }}>{analysis.composite.rating}</strong>
      </article>
      <article className="metric-card">
        <span>Company</span>
        <strong>{analysis.ticker}</strong>
        <em>{analysis.company.name}</em>
      </article>
    </section>
  );
}

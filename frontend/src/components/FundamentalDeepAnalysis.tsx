import { useState } from 'react';
import type { FundamentalAnalysis, FundamentalAnalysisCategory } from '../types';

function formatLabel(key: string) {
  return key.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatMetricValue(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return 'N/A';
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  if (typeof value === 'number') {
    if (Math.abs(value) >= 1_000_000_000) {
      return `$${(value / 1_000_000_000).toFixed(2)}B`;
    }
    if (Math.abs(value) >= 1_000_000) {
      return `$${(value / 1_000_000).toFixed(2)}M`;
    }
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  return value;
}

function CategoryCard({ category }: { category: FundamentalAnalysisCategory }) {
  const [expanded, setExpanded] = useState(false);
  const metrics = Object.entries(category.metrics);

  return (
    <article className="fundamental-category">
      <div className="fundamental-category-head">
        <div>
          <h3>{category.name}</h3>
          <span className={`quality-pill quality-${category.status}`}>{category.status}</span>
        </div>
        <strong>{category.score.toFixed(1)}/10</strong>
      </div>
      <div className="sentiment-meter" aria-label={`${category.name} bullishness`}>
        <span style={{ width: `${Math.max(0, Math.min(100, category.bullishness))}%` }} />
      </div>
      <p>{category.explanation}</p>
      <div className="fundamental-split">
        <span>Bullish {category.bullishness}%</span>
        <span>Bearish {category.bearishness}%</span>
      </div>
      <button className="metric-toggle" type="button" onClick={() => setExpanded((value) => !value)}>
        {expanded ? 'Hide' : 'View'} {category.name} metrics
      </button>
      {expanded && (
        <dl className="meta-list fundamental-metrics">
          {metrics.length === 0 ? (
            <div>
              <dt>Metrics</dt>
              <dd>N/A</dd>
            </div>
          ) : (
            metrics.map(([key, value]) => (
              <div key={key}>
                <dt>{formatLabel(key)}</dt>
                <dd>{formatMetricValue(value)}</dd>
              </div>
            ))
          )}
        </dl>
      )}
    </article>
  );
}

export function FundamentalDeepAnalysis({ analysis }: { analysis: FundamentalAnalysis }) {
  return (
    <section className="panel fundamental-deep" aria-label="Fundamental deep analysis">
      <div className="panel-heading">
        <span>Fundamental Deep Analysis</span>
        <strong>{analysis.overall_score}/100</strong>
      </div>
      <div className="fundamental-overview">
        <div className="sentiment-meter overall-meter" aria-label="Overall fundamental bullishness">
          <span style={{ width: `${Math.max(0, Math.min(100, analysis.bullishness))}%` }} />
        </div>
        <div className="fundamental-split">
          <span>Bullish {analysis.bullishness}%</span>
          <span>Bearish {analysis.bearishness}%</span>
        </div>
        <p>{analysis.summary}</p>
      </div>
      {analysis.warnings.length > 0 && (
        <ul className="quality-warnings">
          {analysis.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
      <div className="fundamental-category-grid">
        {analysis.categories.map((category) => (
          <CategoryCard key={category.name} category={category} />
        ))}
      </div>
    </section>
  );
}

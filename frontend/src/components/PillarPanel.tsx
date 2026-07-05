import type { Pillar, PillarKey } from '../types';

const labels: Record<PillarKey, string> = {
  fundamental: 'Fundamentals',
  sentiment: 'AI Sentiment',
  technical: 'Technical Analysis',
  derivative: 'Derivatives & Options',
};

function formatMetaKey(key: string) {
  return key
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatMetaValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return 'N/A';
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  if (Array.isArray(value)) {
    return `${value.length} items`;
  }
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => `${key}: ${formatMetaValue(item)}`)
      .join(', ');
  }
  return String(value);
}

export function PillarPanel({ name, pillar }: { name: PillarKey; pillar: Pillar }) {
  const metaEntries = Object.entries(pillar.meta)
    .filter(([key]) => key !== 'details')
    .slice(0, 4);

  return (
    <article className="panel">
      <div className="panel-heading">
        <span>{labels[name]}</span>
        <strong>{pillar.score.toFixed(0)}</strong>
      </div>
      <div className="progress-track" aria-label={`${labels[name]} score`}>
        <div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, pillar.score))}%` }} />
      </div>
      <dl className="meta-list">
        {metaEntries.map(([key, value]) => (
          <div key={key}>
            <dt>{formatMetaKey(key)}</dt>
            <dd>{formatMetaValue(value)}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

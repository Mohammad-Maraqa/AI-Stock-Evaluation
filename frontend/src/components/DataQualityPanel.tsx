import type { DataQuality } from '../types';

const providerLabels: Array<[keyof Omit<DataQuality, 'confidence' | 'warnings'>, string]> = [
  ['market_data', 'Market'],
  ['fundamentals', 'Fundamentals'],
  ['derivatives', 'Derivatives'],
  ['news', 'News'],
  ['sentiment', 'Sentiment'],
  ['insider_activity', 'Insiders'],
];

export function DataQualityPanel({ quality }: { quality: DataQuality }) {
  return (
    <section className="panel quality-panel" aria-label="Data quality">
      <div className="panel-heading">
        <span>Data Confidence</span>
        <strong>{quality.confidence}%</strong>
      </div>
      <div className="quality-indicators">
        {providerLabels.map(([key, label]) => (
          <span key={key} className={`quality-pill quality-${quality[key]}`}>
            {label}: {quality[key]}
          </span>
        ))}
      </div>
      {quality.warnings.length > 0 && (
        <ul className="quality-warnings">
          {quality.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

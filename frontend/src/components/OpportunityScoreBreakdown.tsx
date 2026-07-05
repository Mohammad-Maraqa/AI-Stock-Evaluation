import type { OpportunityScores } from '../types';

interface OpportunityScoreBreakdownProps {
  scores: OpportunityScores;
}

const scoreLabels: Array<[keyof OpportunityScores, string]> = [
  ['fundamental', 'Fundamental'],
  ['valuation', 'Valuation'],
  ['sentiment', 'Sentiment'],
  ['technical', 'Technical'],
  ['underhype', 'Underhype'],
  ['data_quality', 'Data Quality'],
];

export function OpportunityScoreBreakdown({ scores }: OpportunityScoreBreakdownProps) {
  return (
    <dl className="opportunity-score-grid">
      {scoreLabels.map(([key, label]) => (
        <div key={key}>
          <dt>{label}</dt>
          <dd>{Math.round(scores[key])}</dd>
        </div>
      ))}
    </dl>
  );
}

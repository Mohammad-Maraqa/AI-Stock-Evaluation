import type { ReactNode } from 'react';
import type { DerivativesSummary, InsiderActivity, PiotroskiSummary } from '../types';

function formatValue(value: number | boolean | null | undefined, suffix = '') {
  if (value === null || value === undefined) {
    return 'N/A';
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  return `${Number.isInteger(value) ? value : value.toFixed(2)}${suffix}`;
}

function DetailItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function DetailPanel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="panel detail-panel">
      <div className="panel-heading">
        <span>{title}</span>
      </div>
      <dl className="meta-list">{children}</dl>
    </article>
  );
}

export function AnalysisDetails({
  insiderActivity,
  piotroski,
  derivatives,
}: {
  insiderActivity: InsiderActivity;
  piotroski: PiotroskiSummary;
  derivatives: DerivativesSummary;
}) {
  const piotroskiScore = piotroski.score === null || piotroski.score === undefined ? 'N/A' : `${piotroski.score.toFixed(1)}%`;

  return (
    <section className="detail-grid" aria-label="Detailed factual analysis">
      <DetailPanel title="Insider Activity">
        <DetailItem label="Summary" value={insiderActivity.summary} />
        <DetailItem label="Buys" value={insiderActivity.buys} />
        <DetailItem label="Sells" value={insiderActivity.sells} />
        <DetailItem label="Net" value={insiderActivity.net} />
        <DetailItem label="Booster" value={formatValue(insiderActivity.booster)} />
      </DetailPanel>

      <DetailPanel title="Piotroski Quality">
        <DetailItem label="Raw Score" value={`${piotroski.raw_score}/${piotroski.max_score}`} />
        <DetailItem label="Available Score" value={piotroskiScore} />
        {Object.entries(piotroski.signals).slice(0, 6).map(([label, value]) => (
          <DetailItem key={label} label={label} value={value ? 'Pass' : 'Fail'} />
        ))}
      </DetailPanel>

      <DetailPanel title="Derivatives Snapshot">
        <DetailItem label="Risk Label" value={derivatives.risk_label} />
        <DetailItem label="Put/Call Volume" value={formatValue(derivatives.pcr_vol)} />
        <DetailItem label="Put/Call OI" value={formatValue(derivatives.pcr_oi)} />
        <DetailItem label="Short Float" value={formatValue(derivatives.short_float, '%')} />
        <DetailItem label="Short Ratio" value={formatValue(derivatives.short_ratio)} />
        <DetailItem label="Average IV" value={formatValue(derivatives.avg_iv, '%')} />
        <DetailItem label="Trend Supported" value={formatValue(derivatives.technical_trend)} />
      </DetailPanel>
    </section>
  );
}

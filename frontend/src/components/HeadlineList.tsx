import type { Headline } from '../types';

export function HeadlineList({ headlines }: { headlines: Headline[] }) {
  return (
    <section className="panel headlines" aria-label="Analyzed headlines">
      <div className="panel-heading">
        <span>Analyzed Headlines</span>
        <strong>{headlines.length}</strong>
      </div>
      {headlines.length === 0 ? (
        <p className="muted">No headlines available for this ticker.</p>
      ) : (
        <ul>
          {headlines.map((headline) => {
            const contextLabel = headline.analysis_depth === 'article' ? 'Article context' : 'Headline context';
            return (
              <li key={`${headline.link}-${headline.title}`}>
                <a href={headline.link} target="_blank" rel="noreferrer">
                  {headline.title}
                </a>
                <span>
                  {headline.source} / {headline.sentiment ?? 'Neutral'} / Impact {headline.score ?? 0}/10 / {contextLabel}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

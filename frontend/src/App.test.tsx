import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';

const sampleAnalysis = {
  ticker: 'AAPL',
  company: { name: 'Apple Inc.', sector: 'Technology', industry: 'Consumer Electronics' },
  composite: { base_score: 70, final_score: 72, rating: 'Bullish Bias', insider_booster: 2 },
  pillars: {
    fundamental: { score: 75, meta: { PE: 28 } },
    sentiment: {
      score: 60,
      meta: {
        summary: 'Mixed',
        counts: { bull: 1, bear: 0, neut: 0 },
        analysis_depth_counts: { article: 1, headline: 0 },
      },
    },
    technical: { score: 70, meta: { Trend: true } },
    derivative: { score: 50, meta: { avg_iv: 22 } },
  },
  headlines: [
    {
      ticker: 'AAPL',
      title: 'Apple expands AI services',
      link: 'https://example.com',
      source: 'Example',
      published_at: 'Today',
      sentiment: 'Bullish',
      score: 8,
      article_text: 'Apple expands services with stronger recurring revenue.',
      analysis_depth: 'article',
    },
  ],
  chart: { candles: [], overlays: {} },
  providers: { news: 'scrapy_finviz', sentiment: 'ollama', market_data: 'yfinance' },
  insider_activity: { buys: 3, sells: 1, net: 2, booster: 2, summary: 'Net insider buying' },
  piotroski: { raw_score: 4, max_score: 6, score: 66.7, signals: { 'ROA Positive': 1 } },
  derivatives: { avg_iv: 22, short_float: 4.2, short_ratio: 1.4, pcr_vol: 0.8, pcr_oi: 0.9, technical_trend: true },
  competitors: [],
  fundamental_analysis: {
    overall_score: 84,
    bullishness: 84,
    bearishness: 16,
    summary: 'Strong fundamentals led by profitability, with leverage as the main watch item.',
    warnings: [],
    categories: [
      {
        name: 'Revenue Growth',
        status: 'ok',
        score: 9,
        bullishness: 90,
        bearishness: 10,
        explanation: 'Revenue increased 22.0% year over year.',
        metrics: {
          current_revenue: 120000000000,
          previous_revenue: 98000000000,
          revenue_growth_pct: 22.45,
        },
      },
      {
        name: 'Liquidity',
        status: 'partial',
        score: 6,
        bullishness: 60,
        bearishness: 40,
        explanation: 'Liquidity data is partial.',
        metrics: {
          current_ratio: null,
          quick_ratio: 1.1,
        },
      },
    ],
  },
  data_quality: {
    market_data: 'ok',
    news: 'ok',
    sentiment: 'ok',
    fundamentals: 'ok',
    derivatives: 'ok',
    insider_activity: 'ok',
    confidence: 96,
    warnings: [],
  },
};

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => sampleAnalysis,
    }));
  });

  it('submits a ticker and renders score cards plus headlines', async () => {
    render(<App />);

    await userEvent.clear(screen.getByLabelText(/ticker or company name/i));
    await userEvent.type(screen.getByLabelText(/ticker or company name/i), 'AAPL');
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }));

    expect(await screen.findByText('72.0')).toBeInTheDocument();
    expect(screen.getByText('Bullish Bias')).toBeInTheDocument();
    expect(screen.getByText('Apple expands AI services')).toBeInTheDocument();
    expect(screen.getByText(/article context/i)).toBeInTheDocument();
    expect(screen.getByText('Fundamentals')).toBeInTheDocument();
    expect(screen.getByText('bull: 1, bear: 0, neut: 0')).toBeInTheDocument();
    expect(screen.queryByText('[object Object]')).not.toBeInTheDocument();
    expect(screen.getByText('Insider Activity')).toBeInTheDocument();
    expect(screen.getByText('Piotroski Quality')).toBeInTheDocument();
    expect(screen.getByText('Derivatives Snapshot')).toBeInTheDocument();
    expect(screen.getByText('Data Confidence')).toBeInTheDocument();
    expect(screen.getByText('96%')).toBeInTheDocument();
    expect(screen.getByText('Fundamental Deep Analysis')).toBeInTheDocument();
    expect(screen.getByText('84/100')).toBeInTheDocument();
    expect(screen.getByText('Bullish 84%')).toBeInTheDocument();
    expect(screen.getByText('Revenue Growth')).toBeInTheDocument();
    expect(screen.getByText('Revenue increased 22.0% year over year.')).toBeInTheDocument();
    expect(screen.queryByText('current revenue')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /view revenue growth metrics/i }));
    expect(screen.getByText('Current Revenue')).toBeInTheDocument();
    expect(screen.getByText('$120.00B')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /view liquidity metrics/i }));
    expect(screen.getByText('N/A')).toBeInTheDocument();
    expect(screen.queryByText(/competitor/i)).not.toBeInTheDocument();
  });

  it('renders an error state when the backend rejects analysis', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'Could not find data' }),
    }));

    render(<App />);
    await userEvent.click(screen.getByRole('button', { name: /analyze/i }));

    expect(await screen.findByText('Could not find data')).toBeInTheDocument();
  });

  it('adds, refreshes, compares, and removes watchlist tickers', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [sampleAnalysis], errors: [] }),
    }));

    render(<App />);

    await userEvent.type(screen.getByLabelText(/watchlist ticker/i), 'AAPL');
    await userEvent.click(screen.getByRole('button', { name: /add ticker/i }));
    await userEvent.click(screen.getByRole('button', { name: /refresh watchlist/i }));

    expect(await screen.findByText('Watchlist Comparison')).toBeInTheDocument();
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.getByText('Confidence 96%')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /remove AAPL/i }));

    expect(screen.queryByText('Watchlist Comparison')).not.toBeInTheDocument();
  });

  it('renders opportunity finder results with metadata, reasons, and risks', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.includes('/api/opportunity/themes')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            themes: [{ id: 'ai_infrastructure', name: 'AI Infrastructure', description: 'AI compute.' }],
          }),
        });
      }
      if (url.includes('/api/opportunity/scan')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'theme',
            theme: { id: 'ai_infrastructure', name: 'AI Infrastructure' },
            source_warnings: [{ source: 'NASDAQ_DISCOVERY', message: 'Nasdaq unavailable.' }],
            candidate_count: 2,
            analyzed_count: 1,
            scan_metadata: {
              discovered_count: 4,
              validated_count: 2,
              filtered_count: 1,
              analyzed_count: 1,
              returned_count: 1,
              duration_ms: 1200,
            },
            results: [{
              ticker: 'AAA',
              company: 'Alpha AI Servers',
              opportunity_score: 84,
              label: 'Underrated Candidate',
              theme_relevance_score: 88,
              discovery_confidence: 'high',
              source_consensus: 2,
              scores: {
                fundamental: 88,
                valuation: 70,
                sentiment: 65,
                technical: 72,
                underhype: 80,
                data_quality: 90,
              },
              reasons: ['Appeared in ETF holdings related to the selected theme.', 'Strong fundamental score.'],
              risks: ['Debt level should be monitored.'],
              sources: ['ETF_HOLDINGS', 'NASDAQ_DISCOVERY'],
            }],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => sampleAnalysis });
    }));

    render(<App />);
    await userEvent.click(screen.getByRole('button', { name: /opportunity finder/i }));

    expect(await screen.findByText('Research discovery tool, not financial advice.')).toBeInTheDocument();
    expect(screen.getByLabelText(/industry theme/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /run scan/i }));

    expect(await screen.findByText('Alpha AI Servers')).toBeInTheDocument();
    expect(screen.getByText('Underrated Candidate')).toBeInTheDocument();
    expect(screen.getByText('Discovery Confidence: high')).toBeInTheDocument();
    expect(screen.getByText('Discovered 4')).toBeInTheDocument();
    expect(screen.getByText('Validated 2')).toBeInTheDocument();
    expect(screen.getByText('Returned 1')).toBeInTheDocument();
    expect(screen.getByText('NASDAQ_DISCOVERY: Nasdaq unavailable.')).toBeInTheDocument();
    expect(screen.getByText('Appeared in ETF holdings related to the selected theme.')).toBeInTheDocument();
    expect(screen.getByText('Debt level should be monitored.')).toBeInTheDocument();
    expect(screen.queryByText('[object Object]')).not.toBeInTheDocument();
  });

  it('supports ETF mode and opens a result in the existing stock analysis view', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.includes('/api/opportunity/themes')) {
        return Promise.resolve({ ok: true, json: async () => ({ themes: [] }) });
      }
      if (url.includes('/api/opportunity/scan')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'etf',
            etf: 'SMH',
            source_warnings: [],
            candidate_count: 1,
            analyzed_count: 1,
            scan_metadata: {
              discovered_count: 1,
              validated_count: 1,
              filtered_count: 0,
              analyzed_count: 1,
              returned_count: 1,
              duration_ms: 500,
            },
            results: [{
              ticker: 'AAPL',
              company: 'Apple Inc.',
              opportunity_score: 75,
              label: 'High Quality, Fairly Valued',
              theme_relevance_score: 70,
              discovery_confidence: 'medium',
              source_consensus: 1,
              scores: {
                fundamental: 84,
                valuation: 60,
                sentiment: 65,
                technical: 70,
                underhype: 62,
                data_quality: 96,
              },
              reasons: ['Appeared in ETF holdings related to the selected theme.'],
              risks: ['No major deterministic risk flag was identified from available fields.'],
              sources: ['ETF_HOLDINGS'],
            }],
          }),
        });
      }
      if (url.includes('/api/analyze')) {
        return Promise.resolve({ ok: true, json: async () => sampleAnalysis });
      }
      return Promise.resolve({ ok: true, json: async () => ({ items: [], errors: [] }) });
    }));

    render(<App />);
    await userEvent.click(screen.getByRole('button', { name: /opportunity finder/i }));
    await userEvent.click(await screen.findByRole('button', { name: /scan by etf ticker/i }));
    await userEvent.type(screen.getByLabelText(/etf ticker/i), 'SMH');
    await userEvent.click(screen.getByRole('button', { name: /run scan/i }));
    await userEvent.click(await screen.findByRole('button', { name: /open full analysis for AAPL/i }));

    expect(await screen.findByText('Bullish Bias')).toBeInTheDocument();
  });
});

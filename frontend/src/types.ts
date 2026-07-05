export type PillarKey = 'fundamental' | 'sentiment' | 'technical' | 'derivative';

export interface CompanyInfo {
  name: string;
  sector: string;
  industry: string;
}

export interface CompositeScore {
  base_score: number;
  final_score: number;
  rating: string;
  insider_booster: number;
}

export interface Pillar {
  score: number;
  meta: Record<string, unknown>;
}

export interface Headline {
  ticker: string;
  title: string;
  link: string;
  source: string;
  published_at: string;
  sentiment?: string | null;
  score?: number | null;
  article_text?: string;
  analysis_depth?: 'article' | 'headline' | string;
}

export interface InsiderActivity {
  buys: number;
  sells: number;
  net: number;
  booster: number;
  summary: string;
}

export interface PiotroskiSummary {
  raw_score: number;
  max_score: number;
  score?: number | null;
  signals: Record<string, number>;
}

export interface DerivativesSummary {
  pcr_vol?: number | null;
  pcr_oi?: number | null;
  short_float?: number | null;
  short_ratio?: number | null;
  avg_iv?: number | null;
  technical_trend?: boolean | null;
  risk_label: string;
}

export interface DataQuality {
  market_data: string;
  news: string;
  sentiment: string;
  fundamentals: string;
  derivatives: string;
  insider_activity: string;
  confidence: number;
  warnings: string[];
}

export interface FundamentalAnalysisCategory {
  name: string;
  status: string;
  score: number;
  bullishness: number;
  bearishness: number;
  explanation: string;
  metrics: Record<string, string | number | boolean | null | undefined>;
}

export interface FundamentalAnalysis {
  overall_score: number;
  bullishness: number;
  bearishness: number;
  summary: string;
  warnings: string[];
  categories: FundamentalAnalysisCategory[];
}

export interface AnalysisResponse {
  ticker: string;
  company: CompanyInfo;
  composite: CompositeScore;
  pillars: Record<PillarKey, Pillar>;
  headlines: Headline[];
  chart: {
    candles: Array<Record<string, number>>;
    overlays: Record<string, Array<Record<string, number>>>;
  };
  providers: Record<string, string>;
  insider_activity: InsiderActivity;
  piotroski: PiotroskiSummary;
  derivatives: DerivativesSummary;
  competitors: Array<Record<string, unknown>>;
  data_quality: DataQuality;
  fundamental_analysis: FundamentalAnalysis;
}

export interface WatchlistError {
  ticker: string;
  detail: string;
}

export interface WatchlistResponse {
  items: AnalysisResponse[];
  errors: WatchlistError[];
}

export interface OpportunityTheme {
  id: string;
  name: string;
  description: string;
}

export interface OpportunityThemesResponse {
  themes: OpportunityTheme[];
}

export interface OpportunitySourceWarning {
  source: string;
  message: string;
}

export interface OpportunityScores {
  fundamental: number;
  valuation: number;
  sentiment: number;
  technical: number;
  underhype: number;
  data_quality: number;
}

export interface OpportunityResult {
  ticker: string;
  company: string;
  opportunity_score: number;
  label: string;
  theme_relevance_score: number;
  discovery_confidence: 'high' | 'medium' | 'low' | string;
  source_consensus: number;
  scores: OpportunityScores;
  reasons: string[];
  risks: string[];
  sources: string[];
}

export interface OpportunityScanMetadata {
  discovered_count: number;
  validated_count: number;
  filtered_count: number;
  analyzed_count: number;
  returned_count: number;
  duration_ms: number;
}

export interface OpportunityScanResponse {
  mode: 'theme' | 'etf' | string;
  theme?: { id: string; name: string } | null;
  etf?: string | null;
  source_warnings: OpportunitySourceWarning[];
  candidate_count: number;
  analyzed_count: number;
  scan_metadata: OpportunityScanMetadata;
  results: OpportunityResult[];
}

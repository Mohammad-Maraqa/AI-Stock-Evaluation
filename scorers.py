import logging

from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, MACD, EMAIndicator
from ta.volatility import BollingerBands

from config import get_sector_pe_median, TECHNICAL_SIGNAL_WEIGHTS

logger = logging.getLogger(__name__)


class ScoringEngine:
    def __init__(self):
        self.current_tech_trend = True

    def _row(self, df, candidates):
        for name in candidates:
            try:
                if name in df.index:
                    return df.loc[name]
            except Exception as exc:
                logger.debug("Unable to read candidate row %s: %s", name, exc)
        return None

    # ─────────────────────────────────────────────────────────
    #  TECHNICAL  –  Weighted binary signal count
    # ─────────────────────────────────────────────────────────
    def calculate_technical(self, df):
        if df.empty or len(df) < 50:
            return 0, {}

        close = df['Close']
        price = close.iloc[-1]

        rsi       = RSIIndicator(close).rsi().iloc[-1]
        sma_50    = SMAIndicator(close, window=50).sma_indicator().iloc[-1]
        ema_20    = EMAIndicator(close, window=20).ema_indicator().iloc[-1]
        sma_200   = SMAIndicator(close, window=min(200, len(df))).sma_indicator().iloc[-1]

        macd_calc   = MACD(close)
        macd_line   = macd_calc.macd().iloc[-1]
        macd_signal = macd_calc.macd_signal().iloc[-1]

        bb        = BollingerBands(close)
        bb_high   = bb.bollinger_hband().iloc[-1]
        bb_low    = bb.bollinger_lband().iloc[-1]

        is_uptrend = price > sma_50
        self.current_tech_trend = is_uptrend

        # (label, bullish=1/bearish=-1, weight)
        signals = [
            ('Price Above SMA 200',  1 if price > sma_200        else -1, TECHNICAL_SIGNAL_WEIGHTS['Price Above SMA 200']),
            ('Price Above SMA 50',   1 if price > sma_50         else -1, TECHNICAL_SIGNAL_WEIGHTS['Price Above SMA 50']),
            ('Golden Cross Active',  1 if sma_50 > sma_200       else -1, TECHNICAL_SIGNAL_WEIGHTS['Golden Cross Active']),
            ('MACD Bullish Cross',   1 if macd_line > macd_signal else -1, TECHNICAL_SIGNAL_WEIGHTS['MACD Bullish Cross']),
            ('MACD Above Zero',      1 if macd_line > 0           else -1, TECHNICAL_SIGNAL_WEIGHTS['MACD Above Zero']),
            ('RSI Momentum',         1 if (is_uptrend and 50 <= rsi <= 82) or (not is_uptrend and rsi < 45) else -1, TECHNICAL_SIGNAL_WEIGHTS['RSI Momentum']),
            ('Price Above EMA 20',   1 if price > ema_20          else -1, TECHNICAL_SIGNAL_WEIGHTS['Price Above EMA 20']),
            ('BB Band Position',     1 if (is_uptrend and price >= bb_high * 0.98) or (not is_uptrend and price < bb_high) else -1, TECHNICAL_SIGNAL_WEIGHTS['BB Band Position']),
        ]

        total_w     = sum(w for _, _, w in signals)
        bull_w      = sum(w for _, s, w in signals if s == 1)
        final_score = (bull_w / total_w) * 100

        meta = {
            "RSI": rsi, "SMA50": sma_50, "SMA200": sma_200, "EMA20": ema_20,
            "MACD": macd_line, "MACD_Signal": macd_signal,
            "BB_High": bb_high, "BB_Low": bb_low,
            "Price": price, "Trend": is_uptrend,
            "signal_details": [(lbl, s) for lbl, s, _ in signals]
        }
        return final_score, meta

    # ─────────────────────────────────────────────────────────
    #  SENTIMENT
    # ─────────────────────────────────────────────────────────
    def calculate_social(self, social_data):
        empty_meta = {"summary": "", "details": [], "counts": {"bull": 0, "bear": 0, "neut": 0}}
        if "error" in social_data:
            empty_meta["summary"] = f"⚠️ ERROR: {social_data['error']}"
            return 0, empty_meta
        headlines = social_data.get('headlines', [])
        if not headlines:
            empty_meta["summary"] = "No relevant news found."
            return 0, empty_meta

        depth_counts = {
            "article": sum(1 for item in headlines if item.get("analysis_depth") == "article"),
            "headline": sum(1 for item in headlines if item.get("analysis_depth") != "article"),
        }

        bull_pow = bear_pow = bull_cnt = bear_cnt = neut_cnt = 0
        for item in headlines:
            sentiment = item.get('sentiment', '').lower()
            s = item.get('score', 0)
            if "bullish" in sentiment:   bull_pow += s; bull_cnt += 1
            elif "bearish" in sentiment: bear_pow += s; bear_cnt += 1
            else:                        neut_cnt += 1

        neutral_anchor = neut_cnt * 0.2
        total_power    = bull_pow + bear_pow + neutral_anchor
        final_score    = 50 if total_power == 0 else ((bull_pow + neutral_anchor / 2) / total_power) * 100

        if final_score > 60:   summary = f"Bullish Bias — {bull_cnt} positive signals"
        elif final_score < 40: summary = f"Bearish Bias — {bear_cnt} negative signals"
        else:                  summary = "Mixed / Neutral Sentiment"

        return final_score, {
            "summary": summary, "details": headlines,
            "counts": {"bull": bull_cnt, "bear": bear_cnt, "neut": neut_cnt},
            "analysis_depth_counts": depth_counts,
        }

    # ─────────────────────────────────────────────────────────
    #  DERIVATIVES
    # ─────────────────────────────────────────────────────────
    def calculate_derivative(self, data, technical_trend=None):
        if not data.get('valid'):
            return 0, {}

        pcr_vol     = data.get('pcr_vol')
        pcr_oi      = data.get('pcr_oi')
        short_float = data.get('short_float')
        short_ratio = data.get('short_ratio')
        avg_iv      = data.get('avg_iv')

        scores = {}
        options_signal_count = sum(value is not None for value in (pcr_vol, pcr_oi, avg_iv))
        short_signal_count = sum(value is not None for value in (short_float, short_ratio))
        is_uptrend = self.current_tech_trend if technical_trend is None else technical_trend

        if short_float is not None:
            sf = short_float * 100
            if not is_uptrend:
                float_score = 15 if sf > 10 else 50
            else:
                float_score = 70 if sf < 3 else 30 if sf > 15 else 50
            scores['float'] = (float_score, 0.10)

        if short_ratio is not None:
            sf_pct = short_float * 100 if short_float is not None else 0
            if not is_uptrend:
                ratio_score = 20 if short_ratio > 5 else 50
            else:
                ratio_score = 85 if short_ratio > 8 and sf_pct > 10 else 60 if short_ratio < 3 else 35
            scores['ratio'] = (ratio_score, 0.10)

        if pcr_oi is not None:
            if pcr_oi < 0.6:    oi_score = 95
            elif pcr_oi < 0.9:  oi_score = 75
            elif pcr_oi > 1.2:  oi_score = 25
            else:               oi_score = 50
            scores['oi'] = (oi_score, 0.30)

        if pcr_vol is not None:
            if pcr_vol < 0.7:   vol_score = 85
            elif pcr_vol > 1.1: vol_score = 35
            else:               vol_score = 50
            scores['vol'] = (vol_score, 0.15)

        if avg_iv is not None:
            iv_pct = avg_iv * 100
            if is_uptrend:
                if iv_pct > 80:   iv_score = 25
                elif iv_pct > 60: iv_score = 42
                elif iv_pct > 40: iv_score = 60
                elif iv_pct > 20: iv_score = 78
                else:             iv_score = 90
            else:
                if iv_pct > 70:   iv_score = 15
                elif iv_pct > 50: iv_score = 30
                elif iv_pct > 35: iv_score = 50
                elif iv_pct > 20: iv_score = 70
                else:             iv_score = 85
            scores['iv'] = (iv_score, 0.15)

        if not scores:
            return 0, {}

        total_w     = sum(w for _, w in scores.values())
        final_score = sum(s * w for s, w in scores.values()) / total_w

        # Prevent sparse derivative data from looking highly confident.
        if options_signal_count == 0 and short_signal_count <= 1:
            final_score = 0
        elif options_signal_count == 0:
            final_score = min(final_score, 35)
        elif options_signal_count == 1:
            final_score = min(final_score, 55)

        meta = {
            "pcr_vol":     pcr_vol,
            "pcr_oi":      pcr_oi,
            "short_float": short_float * 100 if short_float is not None else None,
            "short_ratio": short_ratio,
            "avg_iv":      avg_iv * 100 if avg_iv is not None else None
        }
        return final_score, meta

    # ─────────────────────────────────────────────────────────
    #  FUNDAMENTALS  –  5-pillar model (Seeking Alpha architecture)
    #
    #  Pillar 1 – PROFITABILITY  35%  (ROE, Margin, ROA)
    #  Pillar 2 – GROWTH         30%  (Revenue growth, earnings trend)
    #  Pillar 3 – VALUATION      15%  (Sector-relative PE, PEG proxy)
    #  Pillar 4 – FINANCIAL HLTH 10%  (Debt, current ratio)
    #  Pillar 5 – FCF QUALITY    10%  (FCF yield)
    #
    #  Piotroski kept as a display-only quality badge, not a scoring driver.
    # ─────────────────────────────────────────────────────────
    def calculate_fundamental(self, info):
        if info is None or (hasattr(info, 'empty') and info.empty) or (isinstance(info, dict) and not info):
            return 0, {}

        sector     = info.get('sector', 'Unknown')
        pe         = info.get('trailingPE')
        pb         = info.get('priceToBook')
        roe        = info.get('returnOnEquity')
        roa        = info.get('returnOnAssets')
        debt_eq    = info.get('debtToEquity')
        rev_growth = info.get('revenueGrowth')
        margins    = info.get('profitMargins')
        op_margins = info.get('operatingMargins')
        fcf        = info.get('freeCashflow')
        market_cap = info.get('marketCap')
        eps_growth = info.get('earningsGrowth')

        insider_buys  = info.get('insider_buys', 0)
        insider_sells = info.get('insider_sells', 0)

        is_distressed = (roe is not None and roe < 0) or (margins is not None and margins < 0)

        pe_median = get_sector_pe_median(sector)

        # ── Piotroski (display badge only) ───────────────────
        p_score, p_signals, p_raw, p_max = self._piotroski(info)

        # ─────────────────────────────────────────────────────
        #  PILLAR 1: PROFITABILITY  (35%)
        #  Based on ROE, net margin, operating margin, ROA
        # ─────────────────────────────────────────────────────
        prof_components = []

        if roe is not None:
            if roe > 0.40:   roe_s = 100
            elif roe > 0.20: roe_s = 85
            elif roe > 0.10: roe_s = 65
            elif roe > 0:    roe_s = 45
            else:            roe_s = 5
            prof_components.append((roe_s, 0.45))

        if margins is not None:
            if margins > 0.30:   mg_s = 100
            elif margins > 0.20: mg_s = 85
            elif margins > 0.10: mg_s = 70
            elif margins > 0:    mg_s = 45
            else:                mg_s = 5
            prof_components.append((mg_s, 0.35))

        if roa is not None:
            if roa > 0.15:   roa_s = 100
            elif roa > 0.08: roa_s = 80
            elif roa > 0.03: roa_s = 60
            elif roa > 0:    roa_s = 40
            else:            roa_s = 5
            prof_components.append((roa_s, 0.20))

        if prof_components:
            tw   = sum(w for _, w in prof_components)
            prof_score = sum(s * w for s, w in prof_components) / tw
        else:
            prof_score = None

        # ─────────────────────────────────────────────────────
        #  PILLAR 2: GROWTH  (30%)
        #  Revenue growth (primary) + EPS growth (secondary)
        # ─────────────────────────────────────────────────────
        growth_components = []

        if rev_growth is not None:
            if rev_growth >= 0.40:   rg_s = 100
            elif rev_growth >= 0.20: rg_s = 88
            elif rev_growth >= 0.10: rg_s = 72
            elif rev_growth >= 0.05: rg_s = 55
            elif rev_growth >= 0:    rg_s = 40
            else:                    rg_s = 8
            growth_components.append((rg_s, 0.65))

        if eps_growth is not None:
            if eps_growth >= 0.40:   eg_s = 100
            elif eps_growth >= 0.20: eg_s = 85
            elif eps_growth >= 0.05: eg_s = 65
            elif eps_growth >= 0:    eg_s = 45
            else:                    eg_s = 10
            growth_components.append((eg_s, 0.35))

        if growth_components:
            tw          = sum(w for _, w in growth_components)
            growth_score = sum(s * w for s, w in growth_components) / tw
        else:
            growth_score = None

        # ─────────────────────────────────────────────────────
        #  PILLAR 3: VALUATION  (15%)
        #  Sector-relative PE.  High P/B only penalised if ROE < 20%.
        # ─────────────────────────────────────────────────────
        val_score = None
        if pe is not None:
            ratio = pe / pe_median
            if ratio < 0.5:   val_score = 100
            elif ratio < 0.8: val_score = 88
            elif ratio < 1.1: val_score = 74
            elif ratio < 1.5: val_score = 52
            elif ratio < 2.0: val_score = 32
            else:             val_score = 15
            # Only penalise high PB when ROE doesn't justify it
            if pb is not None and pb > 10 and (roe is None or roe < 0.20):
                val_score = max(5, val_score - 20)

        # ─────────────────────────────────────────────────────
        #  PILLAR 4: FINANCIAL HEALTH  (10%)
        #  Debt-to-equity
        # ─────────────────────────────────────────────────────
        health_score = None
        if debt_eq is not None:
            if debt_eq < 30:    health_score = 95
            elif debt_eq < 80:  health_score = 80
            elif debt_eq < 150: health_score = 62
            elif debt_eq < 250: health_score = 40
            else:               health_score = 20

        # ─────────────────────────────────────────────────────
        #  PILLAR 5: FCF QUALITY  (10%)
        # ─────────────────────────────────────────────────────
        fcf_score = None
        if fcf is not None and market_cap is not None and market_cap > 0:
            yield_ = fcf / market_cap
            if yield_ > 0.06:   fcf_score = 100
            elif yield_ > 0.03: fcf_score = 82
            elif yield_ > 0.01: fcf_score = 62
            elif yield_ > 0:    fcf_score = 42
            else:               fcf_score = 10

        # ─────────────────────────────────────────────────────
        #  COMPOSITE (weighted, only over available pillars)
        # ─────────────────────────────────────────────────────
        pool = {}
        if prof_score   is not None: pool['prof']   = (prof_score,   0.35)
        if growth_score is not None: pool['growth']  = (growth_score, 0.30)
        if val_score    is not None: pool['val']     = (val_score,    0.15)
        if health_score is not None: pool['health']  = (health_score, 0.10)
        if fcf_score    is not None: pool['fcf']     = (fcf_score,    0.10)

        empty_meta = {
            **info, "PE": pe, "PB": pb, "ROE": roe,
            "DebtEq": debt_eq, "RevGrowth": rev_growth, "Margins": margins,
            "insider_buys": insider_buys, "insider_sells": insider_sells,
            "insider_booster": 0, "is_distressed": is_distressed,
            "sector_pe_median": pe_median,
            "piotroski_signals": p_signals, "piotroski_raw": p_raw, "piotroski_max": p_max,
            "pillar_scores": {}
        }

        if not pool:
            return 0, empty_meta

        total_w     = sum(w for _, w in pool.values())
        final_score = sum(s * w for s, w in pool.values()) / total_w

        # Distressed company hard cap
        if is_distressed:
            final_score = min(final_score, 35)

        # Stretch scores away from the middle (same as before)
        if final_score >= 70:
            final_score = 70 + (final_score - 70) * 1.3
        elif final_score <= 35:
            final_score = 35 - (35 - final_score) * 1.3
        final_score = max(0, min(100, final_score))

        booster = min(insider_buys * 1.5, 10)
        if is_distressed and insider_sells > 20:
            booster = 0

        pillar_scores = {
            "Profitability": round(prof_score)   if prof_score   is not None else None,
            "Growth":        round(growth_score) if growth_score is not None else None,
            "Valuation":     round(val_score)    if val_score    is not None else None,
            "Health":        round(health_score) if health_score is not None else None,
            "FCF Quality":   round(fcf_score)    if fcf_score    is not None else None,
        }

        meta = {
            **info,
            "PE": pe, "PB": pb, "ROE": roe,
            "DebtEq": debt_eq, "RevGrowth": rev_growth, "Margins": margins,
            "insider_buys": insider_buys, "insider_sells": insider_sells,
            "insider_booster": booster, "is_distressed": is_distressed,
            "sector_pe_median": pe_median,
            "piotroski_signals": p_signals, "piotroski_raw": p_raw, "piotroski_max": p_max,
            "pillar_scores": pillar_scores
        }
        return final_score, meta

    # ─────────────────────────────────────────────────────────
    #  PIOTROSKI helper (display badge only, not composite driver)
    # ─────────────────────────────────────────────────────────
    def _piotroski(self, info):
        fin = info.get('_financials')
        bs  = info.get('_balance_sheet')
        cf  = info.get('_cashflow')

        score   = 0
        signals = {}

        roa = info.get('returnOnAssets')
        if roa is not None:
            v = 1 if roa > 0 else 0; score += v
            signals['ROA Positive'] = v

        ocf = info.get('operatingCashflow')
        if ocf is not None:
            v = 1 if ocf > 0 else 0; score += v
            signals['CFO Positive'] = v

        has_multi = (
            fin is not None and bs is not None and
            getattr(fin, 'shape', (0, 0))[1] >= 2 and
            getattr(bs,  'shape', (0, 0))[1] >= 2
        )

        if has_multi:
            ni      = self._row(fin, ['Net Income', 'Net Income Common Stockholders'])
            ta      = self._row(bs,  ['Total Assets'])
            rev     = self._row(fin, ['Total Revenue'])
            gp      = self._row(fin, ['Gross Profit'])
            ltd     = self._row(bs,  ['Long Term Debt', 'Long Term Debt And Capital Lease Obligation'])
            ca      = self._row(bs,  ['Current Assets', 'Total Current Assets'])
            cl      = self._row(bs,  ['Current Liabilities', 'Total Current Liabilities'])
            sh      = self._row(bs,  ['Ordinary Shares Number', 'Share Issued'])
            cf_row  = self._row(cf,  ['Operating Cash Flow', 'Total Cash From Operating Activities']) if cf is not None else None

            if ni is not None and ta is not None and len(ta) > 2:
                try:
                    roa_c = ni.iloc[0] / abs(ta.iloc[1]) if ta.iloc[1] != 0 else None
                    roa_p = ni.iloc[1] / abs(ta.iloc[2]) if ta.iloc[2] != 0 else None
                    if roa_c is not None and roa_p is not None:
                        v = 1 if roa_c > roa_p else 0; score += v
                        signals['ΔROA Improving'] = v
                except Exception as exc:
                    logger.debug("Unable to calculate Piotroski ROA trend: %s", exc)

            if cf_row is not None and ta is not None and ni is not None:
                try:
                    ta1   = abs(ta.iloc[1])
                    cfroa = cf_row.iloc[0] / ta1 if ta1 != 0 else None
                    roa2  = ni.iloc[0]     / ta1 if ta1 != 0 else None
                    if cfroa is not None and roa2 is not None:
                        v = 1 if cfroa > roa2 else 0; score += v
                        signals['Earnings Quality (CFO > NI)'] = v
                except Exception as exc:
                    logger.debug("Unable to calculate Piotroski earnings quality: %s", exc)

            if ltd is not None and ta is not None:
                try:
                    lev_c = ltd.iloc[0] / abs(ta.iloc[0]) if ta.iloc[0] != 0 else None
                    lev_p = ltd.iloc[1] / abs(ta.iloc[1]) if ta.iloc[1] != 0 else None
                    if lev_c is not None and lev_p is not None:
                        v = 1 if lev_c <= lev_p else 0; score += v
                        signals['Leverage Stable/Falling'] = v
                except Exception as exc:
                    logger.debug("Unable to calculate Piotroski leverage signal: %s", exc)

            if ca is not None and cl is not None:
                try:
                    cr_c = ca.iloc[0] / abs(cl.iloc[0]) if cl.iloc[0] != 0 else None
                    cr_p = ca.iloc[1] / abs(cl.iloc[1]) if cl.iloc[1] != 0 else None
                    if cr_c is not None and cr_p is not None:
                        v = 1 if cr_c >= cr_p else 0; score += v
                        signals['Liquidity Improving'] = v
                except Exception as exc:
                    logger.debug("Unable to calculate Piotroski liquidity signal: %s", exc)

            if sh is not None:
                try:
                    v = 1 if sh.iloc[0] <= sh.iloc[1] * 1.02 else 0; score += v
                    signals['No Share Dilution'] = v
                except Exception as exc:
                    logger.debug("Unable to calculate Piotroski dilution signal: %s", exc)

            if gp is not None and rev is not None:
                try:
                    gm_c = gp.iloc[0] / abs(rev.iloc[0]) if rev.iloc[0] != 0 else None
                    gm_p = gp.iloc[1] / abs(rev.iloc[1]) if rev.iloc[1] != 0 else None
                    if gm_c is not None and gm_p is not None:
                        v = 1 if gm_c >= gm_p else 0; score += v
                        signals['Gross Margin Stable/Rising'] = v
                except Exception as exc:
                    logger.debug("Unable to calculate Piotroski gross margin signal: %s", exc)

            if rev is not None and ta is not None and len(ta) > 2:
                try:
                    at_c = abs(rev.iloc[0]) / abs(ta.iloc[1]) if ta.iloc[1] != 0 else None
                    at_p = abs(rev.iloc[1]) / abs(ta.iloc[2]) if ta.iloc[2] != 0 else None
                    if at_c is not None and at_p is not None:
                        v = 1 if at_c >= at_p else 0; score += v
                        signals['Asset Turnover Improving'] = v
                except Exception as exc:
                    logger.debug("Unable to calculate Piotroski asset turnover signal: %s", exc)

        n = len(signals)
        if n == 0:
            return None, {}, 0, 0
        return (score / n) * 100, signals, score, n

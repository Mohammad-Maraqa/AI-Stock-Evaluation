import { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';
import type { AnalysisResponse } from '../types';

export function TechnicalChart({ chart }: { chart: AnalysisResponse['chart'] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || chart.candles.length === 0) return;

    const chartApi = createChart(containerRef.current, {
      height: 420,
      layout: { background: { color: '#111316' }, textColor: '#c6c6c6' },
      grid: { vertLines: { color: 'rgba(255,255,255,0.04)' }, horzLines: { color: 'rgba(255,255,255,0.04)' } },
    });
    chartApi.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    }).setData(chart.candles as never[]);

    const overlays = [
      ['sma50', '#bfcdff'],
      ['sma200', '#ffb4ab'],
      ['bbHigh', 'rgba(242,202,80,0.35)'],
      ['bbLow', 'rgba(242,202,80,0.35)'],
    ] as const;
    overlays.forEach(([key, color]) => {
      const data = chart.overlays[key] ?? [];
      if (data.length > 0) {
        chartApi.addLineSeries({ color, lineWidth: 1, priceLineVisible: false }).setData(data as never[]);
      }
    });
    chartApi.timeScale().fitContent();

    return () => chartApi.remove();
  }, [chart]);

  return (
    <section className="chart-panel panel">
      <div className="panel-heading">
        <span>Price Action & Indicators</span>
      </div>
      {chart.candles.length === 0 ? <p className="muted">Chart data unavailable.</p> : <div ref={containerRef} className="chart" />}
    </section>
  );
}

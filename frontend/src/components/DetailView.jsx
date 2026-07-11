// Drilldown detail "page" for the selected symbol: header, price + forecast
// chart, and the walk-forward backtest.

import { forwardRef } from "react";
import { displayTicker, formatINR } from "./SignalCard.jsx";
import PriceChart from "./PriceChart.jsx";
import ForecastSummary from "./ForecastSummary.jsx";
import BacktestView from "./BacktestView.jsx";

const DetailView = forwardRef(function DetailView(
  { selected, name, signal, history, forecast },
  ref
) {
  if (!selected) return null;
  const pts = history?.points;

  const price =
    forecast?.last_price ?? signal?.last_price ?? (pts?.length ? pts[pts.length - 1].close : null);

  let dayChange = null;
  if (pts && pts.length >= 2) {
    dayChange = (pts[pts.length - 1].close / pts[pts.length - 2].close - 1) * 100;
  }
  const dirClass = dayChange == null ? "txt-flat" : dayChange >= 0 ? "txt-up" : "txt-down";
  const arrow = dayChange == null ? "—" : dayChange >= 0 ? "▲" : "▼";

  return (
    <>
      <div className="detail-head" ref={ref}>
        <div>
          <div className="detail-title">
            {name}{" "}
            <span className="detail-ticker">{displayTicker(selected)} · NSE</span>
          </div>
          <div className="detail-sub">
            {formatINR(price)}{" "}
            {dayChange != null && (
              <span className={dirClass}>
                {arrow} {Math.abs(dayChange).toFixed(2)}%
              </span>
            )}{" "}
            · last close
          </div>
        </div>
        <div className="source-tag">yfinance · NewsAPI · FinBERT · XGBoost</div>
      </div>

      <div className="section" style={{ marginTop: 14 }}>
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">
              <span className="sw" /> Price &amp; 5-day forecast
            </div>
            <div className="panel-caption">Source: Yahoo Finance · daily close, ₹</div>
          </div>
          <ForecastSummary forecast={forecast} />
          <div className="chart-box">
            <PriceChart ticker={displayTicker(selected)} points={pts} forecast={forecast} />
          </div>
          <p className="disclaimer">
            The dashed green line is the model's 5-day price forecast; the shaded cone is its ±1σ
            uncertainty band — a projection from the signal and volatility, not advice.
          </p>
        </div>
      </div>

      <div className="section" style={{ marginTop: 14 }}>
        <div className="panel">
          <div className="panel-head">
            <div className="panel-title">
              <span className="sw" /> Walk-forward backtest
            </div>
            <div className="panel-caption">The honesty engine</div>
          </div>
          <BacktestView ticker={selected} />
        </div>
      </div>
    </>
  );
});

export default DetailView;

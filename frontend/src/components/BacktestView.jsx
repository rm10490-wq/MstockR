// Walk-forward backtest — the honesty engine. Strategy equity vs buy-&-hold.

import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { fetchBacktest } from "../api.js";

function pct(v) {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

export default function BacktestView({ ticker }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!ticker) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    fetchBacktest(ticker)
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setError("Backtest failed. Is the model trained?"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  if (!ticker) return <div className="chart-empty">Select a ticker to backtest.</div>;
  if (loading)
    return <div className="chart-empty">Running walk-forward backtest for {ticker}… (~5s)</div>;
  if (error) return <div className="chart-empty">{error}</div>;
  if (!data || !data.found)
    return <div className="chart-empty">Not enough history to backtest {ticker}.</div>;

  const s = data.stats;
  const beat = s.strategy_return_pct - s.buyhold_return_pct;
  const series = data.points.map((p) => ({
    date: p.date,
    strategy: +((p.strategy - 1) * 100).toFixed(2),
    buyhold: +((p.buyhold - 1) * 100).toFixed(2),
  }));

  return (
    <>
      <div className="legend-row">
        <span><span className="legend-sw" style={{ background: "var(--navy)" }} /> Strategy equity</span>
        <span><span className="legend-sw" style={{ background: "var(--faint)" }} /> Buy &amp; hold</span>
      </div>
      <div className="chart-box">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={series} margin={{ top: 8, right: 16, bottom: 0, left: -6 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="date" tick={{ fill: "var(--faint)", fontSize: 11 }}
                   tickFormatter={(d) => d.slice(0, 7)} minTickGap={40} />
            <YAxis tick={{ fill: "var(--faint)", fontSize: 11 }} width={44}
                   tickFormatter={(v) => v + "%"} />
            <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--hairline)",
                     borderRadius: 8, color: "var(--ink)", fontSize: 13 }}
                     formatter={(v) => (v >= 0 ? "+" : "") + v + "%"} />
            <ReferenceLine y={0} stroke="var(--hairline-strong)" />
            <Line type="monotone" dataKey="strategy" name="Model (long/flat)"
                  stroke="var(--navy)" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="buyhold" name="Buy & hold"
                  stroke="var(--faint)" strokeWidth={2} strokeDasharray="5 4" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="stat-strip">
        <div className="stat-mini">
          <div className="k">Accuracy</div>
          <div className={`v ${s.accuracy > 0.5 ? "pos" : "neg"}`}>
            {s.accuracy ? (s.accuracy * 100).toFixed(1) + "%" : "—"}
          </div>
        </div>
        <div className="stat-mini">
          <div className="k">Strategy return</div>
          <div className={`v ${s.strategy_return_pct >= 0 ? "pos" : "neg"}`}>{pct(s.strategy_return_pct)}</div>
        </div>
        <div className="stat-mini">
          <div className="k">Buy &amp; hold</div>
          <div className={`v ${s.buyhold_return_pct >= 0 ? "pos" : "neg"}`}>{pct(s.buyhold_return_pct)}</div>
        </div>
        <div className="stat-mini">
          <div className="k">vs buy &amp; hold</div>
          <div className={`v ${beat >= 0 ? "pos" : "neg"}`}>{pct(beat)}</div>
        </div>
      </div>

      <div className="honesty-box">
        <span className="ic">⚠</span>
        <p>
          {beat >= 0 ? (
            <>
              <b>Strategy beat buy-&amp;-hold here — but that isn't proof of edge.</b> A long/flat
              strategy can win just by sitting in cash through a drawdown, even at ~50% accuracy.
              No trading costs are modelled, and the pooled model's out-of-sample AUC is ≈0.50.
            </>
          ) : (
            <>
              <b>Buy-&amp;-hold wins here.</b> The strategy sat in cash through part of a rally —
              dodging a drawdown is not the same as predictive skill, and trading costs aren't modelled.
            </>
          )}{" "}
          Walk-forward, no look-ahead ({s.horizon_days}-day horizon, {s.retrains} retrains,
          {" "}{s.n_predictions} predictions). Educational only, not advice.
        </p>
      </div>
    </>
  );
}

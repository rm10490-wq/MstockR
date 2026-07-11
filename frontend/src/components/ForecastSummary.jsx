// Prominent forward-looking prediction: direction, price target, range, horizon.

const inr = (v) =>
  v == null ? "—" : "₹" + Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 });

function dirLabel(d) {
  return d === "up" ? "▲ UP" : d === "down" ? "▼ DOWN" : "▬ FLAT";
}
function dirClass(d) {
  return d === "up" ? "pos" : d === "down" ? "neg" : "flat";
}

export default function ForecastSummary({ forecast }) {
  if (!forecast || !forecast.found) return null;
  const f = forecast;
  const pct = f.expected_change_pct;
  const pctStr = `${pct >= 0 ? "+" : ""}${pct?.toFixed(2)}%`;

  return (
    <div className="forecast">
      <div className={`fc-headline ${dirClass(f.direction)}`}>
        <span className="fc-dir">{dirLabel(f.direction)}</span>
        <span className="fc-horizon">{f.horizon_days}-day forecast</span>
      </div>
      <div className="fc-stats">
        <div className="fc-stat">
          <span className="fc-label">Target price</span>
          <span className="fc-value">{inr(f.target)}</span>
        </div>
        <div className="fc-stat">
          <span className="fc-label">Expected move</span>
          <span className={`fc-value ${pct >= 0 ? "pos" : "neg"}`}>{pctStr}</span>
        </div>
        <div className="fc-stat">
          <span className="fc-label">Range (±1σ)</span>
          <span className="fc-value sm">{inr(f.target_low)} – {inr(f.target_high)}</span>
        </div>
        <div className="fc-stat">
          <span className="fc-label">
            {f.prob_up != null ? "P(up)" : "Confidence"}
          </span>
          <span className="fc-value">
            {f.prob_up != null
              ? (f.prob_up * 100).toFixed(0) + "%"
              : f.confidence != null
              ? (f.confidence * 100).toFixed(0) + "%"
              : "—"}
          </span>
        </div>
      </div>
      <p className="fc-basis">
        {f.model === "xgboost" ? "Trained XGBoost model" : "Momentum baseline"} ·
        {" "}cone widens with {f.daily_vol_pct}% daily volatility · projection, not advice.
      </p>
    </div>
  );
}

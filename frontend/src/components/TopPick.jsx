// Today's top signal — highlights the strongest-ranked item (indices here).
// Heuristic model output, deliberately framed as a read, not advice.

import { displayTicker, formatINR } from "./SignalCard.jsx";

const DIR = {
  up: { badge: "dir-up", arrow: "▲ Up" },
  down: { badge: "dir-down", arrow: "▼ Down" },
  flat: { badge: "dir-flat", arrow: "— Flat" },
};

function scoreOf(sig) {
  const sign = sig.direction === "up" ? 1 : sig.direction === "down" ? -1 : 0;
  return sign * (sig.confidence ?? 0.5);
}

export default function TopPick({ signals, onSelect }) {
  if (!signals || signals.length === 0) return null;

  const top = [...signals].sort((a, b) => scoreOf(b) - scoreOf(a))[0];
  const dir = DIR[top.direction] ?? DIR.flat;
  const topName = top.name || displayTicker(top.ticker);

  return (
    <div className="toppick">
      <div>
        <div className="toppick-label">
          Today's top signal <span className="heuristic-tag">heuristic — not advice</span>
        </div>
        <button className="toppick-stock" onClick={() => onSelect(top.ticker)}>
          {topName}
          <span className={`dir-badge ${dir.badge}`}>{dir.arrow}</span>
          <span className="toppick-name">{displayTicker(top.ticker)}</span>
        </button>
      </div>

      <div className="toppick-meta">
        <div className="toppick-stat">
          <span className="k">Confidence</span>
          <span className="v">{Math.round((top.confidence ?? 0.5) * 100)}%</span>
        </div>
        <div className="toppick-stat">
          <span className="k">Expected move</span>
          <span className="v">
            {top.expected_change_pct >= 0 ? "+" : ""}
            {(top.expected_change_pct ?? 0).toFixed(2)}%
          </span>
        </div>
        <div className="toppick-stat">
          <span className="k">Last price</span>
          <span className="v">{formatINR(top.last_price)}</span>
        </div>
        <div className="toppick-stat">
          <span className="k">{top.prob_up != null ? "P(up)" : "Signal"}</span>
          <span className="v">
            {top.prob_up != null ? (top.prob_up * 100).toFixed(0) + "%" : top.direction}
          </span>
        </div>
      </div>
    </div>
  );
}

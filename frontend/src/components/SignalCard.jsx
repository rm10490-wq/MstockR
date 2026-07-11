// One card per ticker: direction, expected move, confidence, live INR price.

const DIR = {
  up: { label: "▲ Up", cls: "dir-up" },
  down: { label: "▼ Down", cls: "dir-down" },
  flat: { label: "— Flat", cls: "dir-flat" },
};

// "RELIANCE.NS" -> "RELIANCE", "^NSEI" -> "NSEI"; keep raw symbol for actions.
export function displayTicker(symbol) {
  return symbol.replace(/\.(NS|BO)$/i, "").replace(/^\^/, "");
}

export function formatINR(value) {
  if (value == null) return "—";
  return "₹" + value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export default function SignalCard({ signal, name, selected, onSelect }) {
  const dir = DIR[signal.direction] ?? DIR.flat;
  const conf = Math.round((signal.confidence ?? 0.5) * 100);
  const change = signal.expected_change_pct ?? 0;
  const isIndex = signal.ticker.startsWith("^");
  const label = name || signal.name || displayTicker(signal.ticker);

  return (
    <button
      className={`sig-card ${selected ? "active" : ""}`}
      onClick={() => onSelect(signal.ticker)}
      aria-pressed={selected}
    >
      <div className="sig-top">
        <div>
          <div className="sig-name">{label}</div>
          <div className="sig-sector">
            {displayTicker(signal.ticker)} · {isIndex ? "Index" : "NSE"}
          </div>
        </div>
        <span className={`dir-badge ${dir.cls}`}>{dir.label}</span>
      </div>

      {signal.last_price != null && (
        <div className="sig-price">{formatINR(signal.last_price)}</div>
      )}

      <div className="sig-row">
        <span>Expected move</span>
        <b className={change >= 0 ? "txt-up" : "txt-down"}>
          {change >= 0 ? "+" : ""}
          {change.toFixed(2)}%
        </b>
      </div>
      <div className="sig-row">
        <span>Confidence</span>
        <b>{conf}%</b>
      </div>
      <div className="conf-bar">
        <div className={`conf-fill ${dir.cls}`} style={{ width: `${conf}%` }} />
      </div>
    </button>
  );
}

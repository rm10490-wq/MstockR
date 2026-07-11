// Actual close + 5-day avg, with the forward FORECAST path and volatility cone.

import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from "recharts";

export default function PriceChart({ ticker, points, forecast }) {
  if (!points || points.length === 0) {
    return <div className="chart-empty">Loading {ticker} history…</div>;
  }

  // Merge history + forecast into one date-keyed series so the forecast line
  // and cone extend seamlessly past the last real close.
  const byDate = new Map();
  for (const p of points) {
    byDate.set(p.date, { date: p.date, close: p.close, sma: p.sma });
  }
  if (forecast?.points?.length) {
    for (const f of forecast.points) {
      const e = byDate.get(f.date) || { date: f.date };
      e.forecast = f.forecast;
      e.band = [f.low, f.high]; // range area (Recharts accepts [min,max])
      byDate.set(f.date, e);
    }
  }
  const data = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
  const splitDate = points[points.length - 1].date; // last real close

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
        <XAxis
          dataKey="date"
          tick={{ fill: "var(--ink-faint)", fontSize: 11 }}
          tickFormatter={(d) => d.slice(5)}
          minTickGap={28}
        />
        <YAxis
          tick={{ fill: "var(--ink-faint)", fontSize: 11 }}
          domain={["auto", "auto"]}
          width={60}
          tickFormatter={(v) => "₹" + Math.round(v).toLocaleString("en-IN")}
        />
        <Tooltip
          contentStyle={{
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: 8,
            color: "var(--ink)",
            fontSize: 13,
          }}
          formatter={(v) =>
            Array.isArray(v)
              ? `₹${v[0].toLocaleString("en-IN")} – ₹${v[1].toLocaleString("en-IN")}`
              : "₹" + Number(v).toLocaleString("en-IN")
          }
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {forecast?.found && (
          <ReferenceLine x={splitDate} stroke="var(--line-strong)" strokeDasharray="2 4"
                         label={{ value: "now", fill: "var(--ink-faint)", fontSize: 10 }} />
        )}
        {/* Forecast uncertainty cone */}
        <Area type="monotone" dataKey="band" name="Forecast range"
              stroke="none" fill="var(--up)" fillOpacity={0.12} connectNulls />
        <Line type="monotone" dataKey="close" name="Close (₹)"
              stroke="var(--teal)" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="sma" name="5-day avg"
              stroke="var(--accent)" strokeWidth={2} strokeDasharray="5 4" dot={false} />
        {/* Forward forecast path */}
        <Line type="monotone" dataKey="forecast" name="Forecast"
              stroke="var(--up)" strokeWidth={2.5} strokeDasharray="6 3"
              dot={false} connectNulls />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

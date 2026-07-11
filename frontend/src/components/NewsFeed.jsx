// Watchlist news feed, FinBERT-scored, with a sentiment filter. Click a
// headline's ticker to jump to its analysis.

import { useState } from "react";
import { displayTicker } from "./SignalCard.jsx";

function timeAgo(iso) {
  const mins = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

const SENT = {
  positive: { cls: "sent-pos", label: "Positive" },
  negative: { cls: "sent-neg", label: "Negative" },
  neutral: { cls: "sent-neu", label: "Neutral" },
};

const FILTERS = ["All", "Positive", "Negative", "Neutral"];

export default function NewsFeed({ articles = [], onSelectTicker }) {
  const [filter, setFilter] = useState("All");

  const shown =
    filter === "All"
      ? articles
      : articles.filter((a) => (a.sentiment_label || "neutral") === filter.toLowerCase());

  return (
    <div className="panel">
      <div className="panel-head">
        <div className="news-filter">
          {FILTERS.map((f) => (
            <button
              key={f}
              className={`range-chip ${filter === f ? "active" : ""}`}
              onClick={() => setFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>
        <div className="panel-caption">Source: NewsAPI · scored by FinBERT</div>
      </div>

      {shown.length === 0 && (
        <p className="news-empty">No {filter.toLowerCase()} headlines right now.</p>
      )}

      {shown.map((a) => {
        const sent = SENT[a.sentiment_label] || SENT.neutral;
        return (
          <article className="news-item" key={a.id}>
            <div className="news-top">
              <span className="news-headline">
                {a.url ? (
                  <a href={a.url} target="_blank" rel="noreferrer">{a.headline}</a>
                ) : (
                  a.headline
                )}
              </span>
              <span className={`sent-tag ${sent.cls}`}>{sent.label}</span>
            </div>
            <div className="news-meta">
              {a.ticker && a.ticker !== "MARKET" ? (
                <button className="news-ticker-btn" onClick={() => onSelectTicker?.(a.ticker)}>
                  {displayTicker(a.ticker)}
                </button>
              ) : (
                <span className="news-ticker-btn" style={{ cursor: "default" }}>MARKET</span>
              )}
              <span>{a.source}</span>
              <span>{timeAgo(a.published_at)}</span>
              {a.surprise != null && (
                <span className="surprise">surprise {a.surprise.toFixed(2)}</span>
              )}
            </div>
          </article>
        );
      })}

      <div className="section-desc" style={{ marginTop: 12, marginBottom: 0 }}>
        Sentiment is informational context — it is not yet an input to the model's signal.
      </div>
    </div>
  );
}
